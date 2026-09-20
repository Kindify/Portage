"""Build portage.sqlite from the Justice Laws XML.

Session 2 scope: the English Income Tax Act only. French and the Regulations
follow in session 3. Run with `python -m portage.build`.
"""

import csv
import datetime as dt
import pathlib
import random
import re
import sqlite3
from collections import defaultdict

from .parse import parse
from .refs import extract

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DB_PATH = ROOT / "portage.sqlite"

SOURCES = [
    {
        "act": "ITA",
        "name": "Income Tax Act",
        "citation": "RSC 1985, c 1 (5th Supp)",
        "en": {"xml": DATA / "ITA-eng.xml",
               "url": "https://laws-lois.justice.gc.ca/eng/XML/I-3.3.xml"},
        "fr": {"xml": DATA / "ITA-fra.xml",
               "url": "https://laws-lois.justice.gc.ca/fra/XML/I-3.3.xml"},
    },
    {
        "act": "ITR",
        "name": "Income Tax Regulations",
        "citation": "CRC, c 945",
        "en": {"xml": DATA / "ITR-eng.xml",
               "url": "https://laws-lois.justice.gc.ca/eng/XML/C.R.C.,_c._945.xml"},
        "fr": {"xml": DATA / "ITR-fra.xml",
               "url": "https://laws-lois.justice.gc.ca/fra/XML/C.R.C.,_ch._945.xml"},
    },
]

SCHEMA = """
CREATE TABLE sections (
    id              INTEGER PRIMARY KEY,
    act             TEXT    NOT NULL,
    citation_path   TEXT    NOT NULL,
    level           TEXT    NOT NULL,
    parent_id       INTEGER REFERENCES sections(id),
    parent_path     TEXT,
    order_index     INTEGER,
    order_index_fr  INTEGER,
    is_addressable  INTEGER NOT NULL,
    label_raw       TEXT,
    label_raw_fr    TEXT,
    label_anomaly   INTEGER NOT NULL DEFAULT 0,
    anomaly_reason  TEXT,
    label_anomaly_fr INTEGER NOT NULL DEFAULT 0,
    anomaly_reason_fr TEXT,
    heading_en      TEXT,
    heading_fr      TEXT,
    text_en         TEXT,
    text_fr         TEXT,
    defined_term_en TEXT,
    defined_term_fr TEXT,
    history_note    TEXT,
    bilingual_gap   INTEGER NOT NULL DEFAULT 0,
    alignment_unverified INTEGER NOT NULL DEFAULT 0,
    alignment       TEXT,
    same_path_counterpart TEXT,
    source_url      TEXT,
    source_url_fr   TEXT,
    UNIQUE (act, citation_path)
);
CREATE INDEX idx_sections_parent ON sections(parent_id);
CREATE INDEX idx_sections_path   ON sections(act, citation_path);
CREATE INDEX idx_sections_order  ON sections(act, order_index);
CREATE INDEX idx_sections_align  ON sections(act, alignment);

CREATE TABLE cross_references (
    id                 INTEGER PRIMARY KEY,
    act                TEXT    NOT NULL,
    lang               TEXT    NOT NULL,
    from_id            INTEGER REFERENCES sections(id),
    from_citation_path TEXT    NOT NULL,
    ref_kind           TEXT    NOT NULL,
    raw_text           TEXT    NOT NULL,
    reference_type     TEXT,
    target_link        TEXT,
    target_act         TEXT,
    to_citation_path   TEXT,
    to_id              INTEGER REFERENCES sections(id),
    resolution         TEXT    NOT NULL,
    candidate_count    INTEGER NOT NULL DEFAULT 0,
    unresolved_reason  TEXT,
    method             TEXT    NOT NULL DEFAULT 'tagged',
    order_index        INTEGER NOT NULL
);

CREATE INDEX idx_xref_from ON cross_references(act, from_citation_path);
CREATE INDEX idx_xref_to   ON cross_references(act, to_citation_path);
CREATE INDEX idx_xref_kind ON cross_references(act, ref_kind, resolution);

-- One row per candidate definition for a DefinitionRef. A reference with
-- several candidates gets several rows; the reference itself never picks one.
-- Which definition governs at a location is a scope question, and CLAUDE.md
-- puts scope questions outside the data.
CREATE TABLE definition_ref_candidates (
    ref_id        INTEGER NOT NULL REFERENCES cross_references(id),
    definition_id INTEGER NOT NULL REFERENCES sections(id),
    citation_path TEXT    NOT NULL,
    PRIMARY KEY (ref_id, definition_id)
);

CREATE INDEX idx_defcand_def ON definition_ref_candidates(definition_id);

CREATE VIRTUAL TABLE sections_fts_en USING fts5(
    citation_path, heading_en, text_en, content=''
);

CREATE VIRTUAL TABLE sections_fts_fr USING fts5(
    citation_path, heading_fr, text_fr, content=''
);

CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
"""


def _definition_join_suspects(en_records, fr_records):
    """Definition paths that join but do not join symmetrically.

    A join is symmetric when each file agrees about both terms: the English
    file's own term equals the French file's extracted English equivalent, and
    the English file's extracted French equivalent equals the French file's own
    term. If the two files disagree about what the other language calls this
    definition, the shared key is not enough to treat them as the same
    provision, so they are not joined.
    """
    en = {r["citation_path"]: r for r in en_records if r["level"] == "definition"}
    fr = {r["citation_path"]: r for r in fr_records if r["level"] == "definition"}
    suspects = {}
    for path in set(en) & set(fr):
        e, f = en[path], fr[path]
        same_en = e["defined_term_en"] == f["defined_term_en"]
        same_fr = e["defined_term_fr"] == f["defined_term_fr"]
        if same_en and same_fr:
            continue
        reasons = []
        if not same_en:
            reasons.append("english term differs between files")
        if not same_fr:
            reasons.append("french term differs between files")
        suspects[path] = (e, f, "; ".join(reasons))
    return suspects


def _unverified_alignments(en_records, fr_records):
    """Paths joined by label under a parent whose children differ between files.

    A mechanical, structural test: it compares the *set of child labels* under
    each parent. It makes no judgment about whether two texts correspond - it
    only identifies where the label alone is not evidence that they do.
    """
    from collections import defaultdict

    def children(records, addressable):
        out = defaultdict(list)
        for r in records:
            if bool(r["is_addressable"]) is not addressable or not r["parent_path"]:
                continue
            # Definitions are excluded from the fragment comparison. They are
            # keyed by defined term, not by position, so a subsection holding a
            # different *set* of definitions in each language says nothing about
            # whether a term present in both is the same definition. That
            # question is answered by the symmetric join rule instead.
            if r["level"] == "definition":
                continue
            out[r["parent_path"]].append(r["citation_path"])
        return {k: tuple(v) for k, v in out.items()}

    # Addressable children and non-addressable fragments are compared
    # separately. A subsection whose continued-text fragments differ in number
    # says nothing about whether its paragraphs correspond, and vice versa.
    # They are also resolved differently: addressable rows are split so each
    # language stands alone, fragments are joined but flagged. See
    # docs/citation-path-rule.md section 6.
    out = {}
    for addressable in (True, False):
        suspect = set()
        en_kids = children(en_records, addressable)
        fr_kids = children(fr_records, addressable)
        for parent in set(en_kids) & set(fr_kids):
            if en_kids[parent] != fr_kids[parent]:
                suspect |= set(en_kids[parent]) & set(fr_kids[parent])
        out["split" if addressable else "flagged"] = suspect
    return out


#: Path suffixes that mark a key this project derived rather than read from a
#: <Label>. A key ending in one of these carries no independent meaning, so a
#: cross-language join on it is positional.
ORDINAL_KEYS = ("~c", "~f", "~h", "~t", "~d")


def _set_alignment(conn):
    """Record how each row's two languages came to be on the same row.

    verified   - joined on a key read from the source: a <Label> path whose
                 siblings match in both files, or a defined term that both files
                 agree about (see the symmetric join rule).
    positional - joined on an ordinal this project assigned, which carries no
                 meaning of its own. The two texts occupy the same position
                 inside the same provision; that is all that is known.
    unverified - joined, but the provision's children differ between the files,
                 so even the position is not evidence.
    split      - deliberately not joined: one half of a pair separated because
                 the two languages structure the provision differently.
    single     - present in one language only.
    """
    conn.execute("UPDATE sections SET alignment='single'")
    conn.execute(
        "UPDATE sections SET alignment='split' WHERE same_path_counterpart IS NOT NULL")
    conn.execute(
        "UPDATE sections SET alignment='verified' "
        "WHERE text_en IS NOT NULL AND text_fr IS NOT NULL "
        "AND same_path_counterpart IS NULL")
    like = " OR ".join("citation_path LIKE '%" + k + "%'" for k in ORDINAL_KEYS)
    conn.execute(
        "UPDATE sections SET alignment='positional' "
        "WHERE alignment='verified' AND (" + like + ")")
    # The stronger warning wins where both apply.
    conn.execute(
        "UPDATE sections SET alignment='unverified' "
        "WHERE alignment_unverified=1 AND text_en IS NOT NULL AND text_fr IS NOT NULL")


def _write_catalogue(path, rows, header):
    """Anomalies are catalogued, not counted - see docs/decisions.md.

    Sorted deterministically so a rebuild produces a byte-identical file and the
    test can diff it against the committed fixture.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        for row in sorted(rows):
            w.writerow(row)
    return len(rows)


SPOT_CHECK_SEED = 20260918
SPOT_CHECKS_DIR = ROOT / "tests" / "spot_checks"


def _first_sentence(text):
    text = " ".join((text or "").split())
    if not text:
        return "(no text of its own - see its subsections)"
    m = re.search(r"(?<=[.;:])\s", text)
    cut = m.start() if m and m.start() < 400 else min(len(text), 300)
    return text[:cut + 1].strip()


#: Shortest first sentence worth handing a checker. Below this there is not
#: enough text to search for on the official site - "at the earlier of" appears
#: hundreds of times and locates nothing.
MIN_SPOT_CHECK_CHARS = 25

#: A provision whose text is only a repeal note. Nothing to compare.
REPEALED_MARKER = re.compile(r"^\s*\[\s*(Repealed|Abrogé)", re.IGNORECASE)


def _is_checkable(text):
    """Can a person actually find this on the official site?

    Excludes text too short to search for and bare repeal notes. Both were hit
    in the first round of hand checks: seven of the eighty sampled rows had to
    be skipped as unsearchable, which wastes the checker's time and - worse -
    tempts a tired checker to mark them passed.
    """
    if REPEALED_MARKER.match(text or ""):
        return False
    return len(_first_sentence(text or "")) >= MIN_SPOT_CHECK_CHARS


def _spot_check_sample(conn, act, lang):
    """The seeded twenty for one instrument and language, in document order.

    Rows a checker could not verify are excluded before sampling - see
    _is_checkable.
    """
    text_col, head_col = "text_%s" % lang, "heading_%s" % lang
    rows = conn.execute(
        "SELECT citation_path, level, COALESCE(%s,''), COALESCE(%s,'') "
        "FROM sections WHERE act=? AND is_addressable=1 "
        "AND citation_path NOT LIKE '%%~%%' AND citation_path NOT LIKE '%%#%%' "
        "AND %s IS NOT NULL AND %s != '' "
        "ORDER BY COALESCE(order_index, order_index_fr)"
        % (head_col, text_col, text_col, text_col), (act,)).fetchall()
    rows = [r for r in rows if _is_checkable(r[3])]
    if not rows:
        return []
    sample = random.Random(SPOT_CHECK_SEED).sample(rows, min(20, len(rows)))
    sample.sort(key=lambda r: rows.index(r))
    return sample


def _write_spot_checks(conn, act, lang, consolidation_date):
    """Acceptance test 4: citation paths for Matt to check by hand.

    One file per instrument per language. The sample is seeded, so it is the
    same set on every build - an unseeded sample would change every run and
    there would be nothing stable to check against. Change SPOT_CHECK_SEED to
    draw a fresh set.

    Paths containing `~` or `#` are excluded: those are keys we derived, and
    they cannot be looked up on the Justice Laws site.
    """
    names = {"ITA": ("Income Tax Act", "acts/I-3.3"),
             "ITR": ("Income Tax Regulations", "regulations/C.R.C.,_c._945")}
    title, slug = names[act]

    sample = _spot_check_sample(conn, act, lang)
    if not sample:
        return

    site = "https://laws-lois.justice.gc.ca/%s/%s/" % (
        "eng" if lang == "en" else "fra", slug)
    lines = [
        "# Spot checks - %s (%s)" % (title, "English" if lang == "en" else "French"),
        "",
        "Twenty citation paths drawn from the build, for checking by hand against",
        "<%s>." % site,
        "",
        "Regenerated on every build. The sample is seeded (`SPOT_CHECK_SEED` in",
        "`portage/build.py`), so it stays the same until someone changes the seed.",
        "",
        "Paths containing `~` or `#` are excluded from the sample - those are keys",
        "this project derived, not citations Justice Canada would recognise.",
        "",
        "| # | Citation | Level | Heading | First sentence |",
        "|---|---|---|---|---|",
    ]
    for i, (path, level, heading, text) in enumerate(sample, 1):
        cell = _first_sentence(text).replace("|", "\\|")
        head = (heading or "-").replace("|", "\\|")
        lines.append("| %d | `%s` | %s | %s | %s |" % (i, path, level, head, cell))
    lines += [
        "",
        "Source: %s, consolidation date %s." % (title, consolidation_date),
        "Unofficial reproduction. Not an official version.",
        "",
    ]
    out = SPOT_CHECKS_DIR / ("spot_checks_%s_%s.md" % (act.lower(), lang))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")


def _write_spot_check_results_template(conn):
    """Create tests/spot_checks/RESULTS.md, pre-filled, if it does not exist.

    Never overwritten. Once Matt starts recording results the file is his; a
    build that clobbered it would destroy the only check in this project that
    does not compare the XML against itself.
    """
    out = SPOT_CHECKS_DIR / "RESULTS.md"
    if out.exists():
        return
    names = {"ITA": "Income Tax Act", "ITR": "Income Tax Regulations"}
    sites = {
        ("ITA", "en"): "https://laws-lois.justice.gc.ca/eng/acts/I-3.3/",
        ("ITA", "fr"): "https://laws-lois.justice.gc.ca/fra/acts/I-3.3/",
        ("ITR", "en"): "https://laws-lois.justice.gc.ca/eng/regulations/C.R.C.,_c._945/",
        ("ITR", "fr"): "https://laws-lois.justice.gc.ca/fra/regulations/C.R.C.,_ch._945/",
    }
    lines = [
        "# Spot check results",
        "",
        "Hand verification of the build against the official Justice Laws site.",
        "",
        "This is the only check in the project that does not compare the XML "
        "against itself.",
        "Every automated guard - the round trip, the uniqueness test, the "
        "symmetric join -",
        "reads the same four files the build reads. If those files were "
        "misread in the same",
        "way twice, only a human looking at the published text would notice.",
        "",
        "**How to use this file.** Open the matching `spot_checks_*.md` beside "
        "the official",
        "page, find each citation, and compare the first sentence. Record "
        "`pass`, `fail` or",
        "`partial` below, with a note for anything that is not a clean pass. "
        "Put the date you",
        "checked each block in its heading.",
        "",
        "This file is **never overwritten by the build**. It is yours.",
        "",
    ]
    for act in ("ITA", "ITR"):
        for lang in ("en", "fr"):
            rows = _spot_check_sample(conn, act, lang)
            if not rows:
                continue
            lines += [
                "---",
                "",
                "## %s - %s" % (names[act], "English" if lang == "en" else "French"),
                "",
                "Source list: `spot_checks_%s_%s.md`  " % (act.lower(), lang),
                "Official site: <%s>  " % sites[(act, lang)],
                "**Checked on:** _(date)_  ",
                "**Result:** _(x of %d pass)_" % len(rows),
                "",
                "| # | Citation | Result | Notes |",
                "|---|---|---|---|",
            ]
            for i, (path, _level, _heading, _text) in enumerate(rows, 1):
                lines.append("| %d | `%s` |  |  |" % (i, path))
            lines.append("")
    lines += [
        "---",
        "",
        "## Summary",
        "",
        "| Instrument | Language | Checked on | Pass | Fail | Partial |",
        "|---|---|---|---|---|---|",
        "| Income Tax Act | English |  |  |  |  |",
        "| Income Tax Act | French |  |  |  |  |",
        "| Income Tax Regulations | English |  |  |  |  |",
        "| Income Tax Regulations | French |  |  |  |  |",
        "",
        "Once every block is filled in, update the Hand verification paragraph "
        "in README's",
        "Methods section with the date and the outcome.",
        "",
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")


def build(db_path=DB_PATH):
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)

    all_meta = {}
    unverified_rows = []
    join_suspects = []
    anomalies = []
    def_fallbacks = []
    gaps = []

    for src in SOURCES:
        act = src["act"]

        en_records, en_meta = parse(src["en"]["xml"], act, src["en"]["url"])
        fr_records, fr_meta = parse(src["fr"]["xml"], act, src["fr"]["url"])
        all_meta[act] = {"en": en_meta, "fr": fr_meta}

        # English first: it defines the row set and the document order.
        for rec in en_records:
            conn.execute(
                """INSERT INTO sections
                   (act, citation_path, level, parent_path, order_index,
                    is_addressable, label_raw, label_anomaly, anomaly_reason,
                    heading_en, text_en, defined_term_en, defined_term_fr,
                    history_note, source_url)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (act, rec["citation_path"], rec["level"], rec["parent_path"],
                 rec["order_index"], rec["is_addressable"], rec["label_raw"],
                 rec["label_anomaly"], rec["anomaly_reason"] or None,
                 rec["heading_en"], rec["text_en"], rec["defined_term_en"],
                 rec["defined_term_fr"], rec["history_note"], src["en"]["url"]),
            )

        # French joins on citation_path. A path the English file does not have
        # becomes its own row with text_en NULL - never merged onto a
        # neighbouring record, never matched by position.
        en_paths = {r["citation_path"] for r in en_records}
        suspects = _definition_join_suspects(en_records, fr_records)
        divergent = _unverified_alignments(en_records, fr_records)
        # Addressable rows under a divergent parent are split so that neither
        # language is presented as a translation of the other. Fragments are
        # joined but flagged - they are not citable, so the risk is lower.
        split_paths = divergent["split"]
        for path, (e, f, reason) in sorted(suspects.items()):
            join_suspects.append(
                (act, path, e["defined_term_en"] or "", f["defined_term_en"] or "",
                 e["defined_term_fr"] or "", f["defined_term_fr"] or "", reason))

        for rec in fr_records:
            path = rec["citation_path"]
            if path in split_paths:
                conn.execute(
                    """INSERT INTO sections
                       (act, citation_path, level, parent_path, order_index_fr,
                        is_addressable, label_raw_fr, label_anomaly_fr,
                        anomaly_reason_fr, heading_fr, text_fr,
                        defined_term_en, defined_term_fr, bilingual_gap,
                        same_path_counterpart, source_url_fr)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?)""",
                    (act, path + "~fr", rec["level"], rec["parent_path"],
                     rec["order_index"], rec["is_addressable"], rec["label_raw"],
                     rec["label_anomaly"], rec["anomaly_reason"] or None,
                     rec["heading_en"], rec["text_en"], rec["defined_term_en"],
                     rec["defined_term_fr"], path, src["fr"]["url"]),
                )
            elif path in suspects:
                # Not joined. The French record becomes its own row, marked so
                # that its path is visibly derived rather than citable.
                conn.execute(
                    """INSERT INTO sections
                       (act, citation_path, level, parent_path, order_index_fr,
                        is_addressable, label_raw_fr, label_anomaly_fr,
                        anomaly_reason_fr, heading_fr, text_fr,
                        defined_term_en, defined_term_fr, bilingual_gap,
                        same_path_counterpart, source_url_fr)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?)""",
                    (act, path + "~fr", rec["level"], rec["parent_path"],
                     rec["order_index"], rec["is_addressable"], rec["label_raw"],
                     1, suspects[path][2], rec["heading_en"], rec["text_en"],
                     rec["defined_term_en"], rec["defined_term_fr"],
                     path, src["fr"]["url"]),
                )
            elif path in en_paths:
                conn.execute(
                    """UPDATE sections SET
                           order_index_fr=?, label_raw_fr=?, label_anomaly_fr=?,
                           anomaly_reason_fr=?, heading_fr=?, text_fr=?,
                           source_url_fr=?
                       WHERE act=? AND citation_path=?""",
                    (rec["order_index"], rec["label_raw"], rec["label_anomaly"],
                     rec["anomaly_reason"] or None, rec["heading_en"],
                     rec["text_en"], src["fr"]["url"], act, path),
                )
            else:
                conn.execute(
                    """INSERT INTO sections
                       (act, citation_path, level, parent_path, order_index_fr,
                        is_addressable, label_raw_fr, label_anomaly_fr,
                        anomaly_reason_fr, heading_fr, text_fr,
                        defined_term_en, defined_term_fr, bilingual_gap,
                        source_url_fr)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)""",
                    (act, path, rec["level"], rec["parent_path"],
                     rec["order_index"], rec["is_addressable"], rec["label_raw"],
                     rec["label_anomaly"], rec["anomaly_reason"] or None,
                     rec["heading_en"], rec["text_en"], rec["defined_term_en"],
                     rec["defined_term_fr"], src["fr"]["url"]),
                )

        conn.execute(
            "UPDATE sections SET bilingual_gap=1 "
            "WHERE act=? AND (text_en IS NULL OR text_fr IS NULL)", (act,))

        # Where a parent's set of child labels differs between the two files,
        # the children that happen to share a label cannot be assumed to
        # correspond. English 51(1)(a) is a condition; French 51(1)a) is a rule.
        # Joining them on the label alone is forcing alignment, so the pairing is
        # kept but marked unverified rather than asserted. See PLAN.md.
        conn.execute(
            """UPDATE sections SET same_path_counterpart = citation_path || '~fr'
               WHERE act=? AND citation_path || '~fr' IN (
                   SELECT citation_path FROM sections WHERE act=?)""",
            (act, act))

        for path in sorted(divergent["flagged"]):
            conn.execute(
                "UPDATE sections SET alignment_unverified=1 "
                "WHERE act=? AND citation_path=?", (act, path))
        for resolution, paths in (("split", divergent["split"]),
                                  ("flagged", divergent["flagged"])):
            for path in sorted(paths):
                row = conn.execute(
                    "SELECT level, parent_path, SUBSTR(COALESCE(text_en,''),1,70), "
                    "SUBSTR(COALESCE(text_fr,''),1,70) FROM sections "
                    "WHERE act=? AND citation_path=?", (act, path)).fetchone()
                fr_text = row[3]
                if resolution == "split":
                    other = conn.execute(
                        "SELECT SUBSTR(COALESCE(text_fr,''),1,70) FROM sections "
                        "WHERE act=? AND citation_path=?",
                        (act, path + "~fr")).fetchone()
                    fr_text = other[0] if other else ""
                unverified_rows.append(
                    (act, path, row[0], row[1], resolution,
                     " ".join(row[2].split()), " ".join(fr_text.split())))

        conn.execute(
            """UPDATE sections SET parent_id = (
                   SELECT p.id FROM sections p
                   WHERE p.act = sections.act AND p.citation_path = sections.parent_path)
               WHERE parent_path IS NOT NULL AND parent_path != ''"""
        )

        for lang, records in (("en", en_records), ("fr", fr_records)):
            for rec in records:
                if not rec["label_anomaly"]:
                    continue
                reason = rec["anomaly_reason"]
                row = (act, lang, rec["citation_path"], rec["level"],
                       rec["label_raw"] or "", reason)
                if rec["level"] == "definition":
                    def_fallbacks.append(row)
                else:
                    anomalies.append(row)

        for row in conn.execute(
            """SELECT citation_path, level,
                      CASE WHEN text_en IS NULL THEN 'fr' ELSE 'en' END AS present_in,
                      COALESCE(defined_term_en,''), COALESCE(defined_term_fr,''),
                      COALESCE(text_en, text_fr, '')
               FROM sections WHERE act=? AND bilingual_gap=1
               ORDER BY citation_path""", (act,)):
            gaps.append((act, row[0], row[1], row[2], row[3], row[4],
                         " ".join(row[5].split())[:80]))

    # Phase 1 step 1: tagged cross-references. See docs/reference-rule.md.
    # Candidates come from the section rows rather than the parse records, so a
    # definition counts in a language only if it carries text in that language.
    cur = conn.execute(
        "SELECT act, citation_path, level, defined_term_en, defined_term_fr, "
        "text_en, text_fr FROM sections")
    columns = [d[0] for d in cur.description]
    section_records = [dict(zip(columns, r)) for r in cur.fetchall()]
    by_act = defaultdict(list)
    for rec in section_records:
        by_act[rec["act"]].append(rec)

    unresolved_rows = []
    for src in SOURCES:
        for lang in ("en", "fr"):
            for row in extract(src[lang]["xml"], src["act"], lang,
                               src[lang]["url"], by_act[src["act"]]):
                cur = conn.execute(
                    """INSERT INTO cross_references
                       (act, lang, from_citation_path, ref_kind, raw_text,
                        reference_type, target_link, target_act,
                        to_citation_path, resolution, candidate_count,
                        unresolved_reason, method, order_index)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'tagged',?)""",
                    (row["act"], row["lang"], row["from_citation_path"],
                     row["ref_kind"], row["raw_text"], row["reference_type"],
                     row["target_link"], row["target_act"],
                     row["to_citation_path"], row["resolution"],
                     len(row["candidate_paths"]),
                     row["unresolved_reason"] or None, row["order_index"]))
                ref_id = cur.lastrowid
                for path in row["candidate_paths"]:
                    conn.execute(
                        """INSERT OR IGNORE INTO definition_ref_candidates
                           (ref_id, definition_id, citation_path)
                           SELECT ?, s.id, ? FROM sections s
                           WHERE s.act=? AND s.citation_path=?""",
                        (ref_id, path, row["act"], path))
                if row["resolution"] != "unique":
                    unresolved_rows.append(
                        (row["act"], row["lang"], row["from_citation_path"],
                         row["ref_kind"], row["raw_text"][:100],
                         row["resolution"], row["unresolved_reason"],
                         "; ".join(row["candidate_paths"][:6])))

    conn.execute(
        """UPDATE cross_references SET from_id = (
               SELECT s.id FROM sections s
               WHERE s.act = cross_references.act
                 AND s.citation_path = cross_references.from_citation_path)""")
    conn.execute(
        """UPDATE cross_references SET to_id = (
               SELECT s.id FROM sections s
               WHERE s.act = cross_references.target_act
                 AND s.citation_path = cross_references.to_citation_path)
           WHERE to_citation_path IS NOT NULL""")

    n_xrefs = conn.execute("SELECT COUNT(*) FROM cross_references").fetchone()[0]
    n_unique = conn.execute(
        "SELECT COUNT(*) FROM cross_references WHERE resolution='unique'").fetchone()[0]
    n_ambig = conn.execute(
        "SELECT COUNT(*) FROM cross_references WHERE resolution='ambiguous'").fetchone()[0]

    n_xref_unres = _write_catalogue(
        DATA / "unresolved_tagged_references.csv", sorted(unresolved_rows),
        ["act", "lang", "from_citation_path", "ref_kind", "raw_text",
         "resolution", "reason", "candidates"])

    # A term defined in more than one place is a finding in its own right, not
    # merely a reason a reference failed to resolve.
    multi = [
        (r[0], r[1], r[2], r[3], r[4]) for r in conn.execute(
            """SELECT act, lang, raw_text, candidate_count,
                      (SELECT GROUP_CONCAT(citation_path, '; ')
                       FROM (SELECT citation_path FROM definition_ref_candidates
                             WHERE ref_id = x.id ORDER BY citation_path))
               FROM cross_references x
               WHERE resolution='ambiguous'
               GROUP BY act, lang, raw_text
               ORDER BY act, lang, raw_text""")]
    n_multi = _write_catalogue(
        DATA / "terms_defined_more_than_once.csv", multi,
        ["act", "lang", "term", "definition_count", "definitions"])

    _set_alignment(conn)

    positional_rows = [
        (r[0], r[1], r[2], r[3], r[4])
        for r in conn.execute(
            "SELECT act, citation_path, level, parent_path, "
            "SUBSTR(COALESCE(text_en,''),1,70) FROM sections "
            "WHERE alignment='positional' ORDER BY act, citation_path")
    ]
    n_pos = _write_catalogue(
        DATA / "alignment_positional.csv",
        [(a, p_, l, pp, " ".join(t.split())) for a, p_, l, pp, t in positional_rows],
        ["act", "citation_path", "level", "parent_path", "text_en_start"])

    conn.execute(
        """INSERT INTO sections_fts_en (rowid, citation_path, heading_en, text_en)
           SELECT id, citation_path, COALESCE(heading_en,''), COALESCE(text_en,'')
           FROM sections WHERE text_en IS NOT NULL AND text_en != ''"""
    )
    conn.execute(
        """INSERT INTO sections_fts_fr (rowid, citation_path, heading_fr, text_fr)
           SELECT id, citation_path, COALESCE(heading_fr,''), COALESCE(text_fr,'')
           FROM sections WHERE text_fr IS NOT NULL AND text_fr != ''"""
    )

    n_anom = _write_catalogue(
        DATA / "label_anomalies.csv", anomalies,
        ["act", "lang", "citation_path", "level", "label_raw", "reason"])
    n_fb = _write_catalogue(
        DATA / "definition_key_fallbacks.csv", def_fallbacks,
        ["act", "lang", "citation_path", "level", "label_raw", "reason"])
    n_sus = _write_catalogue(
        DATA / "definition_join_suspects.csv", join_suspects,
        ["act", "citation_path", "term_en_from_en_file", "term_en_from_fr_file",
         "term_fr_from_en_file", "term_fr_from_fr_file", "reason"])
    n_unv = _write_catalogue(
        DATA / "alignment_unverified.csv", unverified_rows,
        ["act", "citation_path", "level", "parent_path", "resolution",
         "text_en_start", "text_fr_start"])
    n_gap = _write_catalogue(
        DATA / "bilingual_gaps.csv", gaps,
        ["act", "citation_path", "level", "present_in",
         "defined_term_en", "defined_term_fr", "text_start"])

    for src in SOURCES:
        for lang in ("en", "fr"):
            _write_spot_checks(conn, src["act"], lang,
                               all_meta[src["act"]]["en"]["consolidation_date"])
    _write_spot_check_results_template(conn)

    rows = conn.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
    addressable = conn.execute(
        "SELECT COUNT(*) FROM sections WHERE is_addressable=1").fetchone()[0]
    both = conn.execute(
        "SELECT COUNT(*) FROM sections WHERE text_en IS NOT NULL AND text_fr IS NOT NULL"
    ).fetchone()[0]


    meta_rows = {
        "source": "Justice Laws Website, Department of Justice Canada",
        "source_format": "XML consolidation",
        "instruments": "; ".join(
            "%s (%s)" % (s_["name"], s_["citation"]) for s_ in SOURCES),
        "languages": "en, fr",
        "consolidation_date": all_meta["ITA"]["en"]["consolidation_date"],
        "last_amended_date": all_meta["ITA"]["en"]["last_amended_date"],
        "currency_date": all_meta["ITA"]["en"]["currency_date"],
        "build_timestamp": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "rows_sections": str(rows),
        "rows_addressable": str(addressable),
        "rows_both_languages": str(both),
        "rows_bilingual_gaps": str(n_gap),
        "rows_alignment_unverified": str(n_unv),
        "rows_definition_join_suspects": str(n_sus),
        "rows_alignment_positional": str(n_pos),
        "rows_cross_references": str(n_xrefs),
        "rows_cross_references_unique": str(n_unique),
        "rows_cross_references_ambiguous": str(n_ambig),
        "rows_terms_defined_more_than_once": str(n_multi),
        "rows_unresolved_tagged_references": str(n_xref_unres),
        "rows_label_anomalies": str(n_anom),
        "rows_definition_key_fallbacks": str(n_fb),
        "phase": "0",
        "schema_version": "1",
        "session": "4 - Act and Regulations, both languages",
        "official": "no - unofficial reproduction, not an official version",
    }
    for src in SOURCES:
        act = src["act"]
        for lang in ("en", "fr"):
            key = "%s_%s" % (act.lower(), lang)
            meta_rows["source_url_" + key] = src[lang]["url"]
            meta_rows["consolidation_date_" + key] = \
                all_meta[act][lang]["consolidation_date"]
            meta_rows["retrieved_date_" + key] = dt.datetime.fromtimestamp(
                src[lang]["xml"].stat().st_mtime,
                dt.timezone.utc).date().isoformat()
        meta_rows["rows_" + act.lower()] = str(conn.execute(
            "SELECT COUNT(*) FROM sections WHERE act=?", (act,)).fetchone()[0])

    conn.executemany("INSERT INTO meta (key,value) VALUES (?,?)", sorted(meta_rows.items()))

    conn.commit()
    conn.close()
    return {"rows": rows, "addressable": addressable, "both_languages": both,
            "bilingual_gaps": n_gap, "label_anomalies": n_anom,
            "definition_fallbacks": n_fb, "alignment_unverified": n_unv,
            "definition_join_suspects": n_sus, "alignment_positional": n_pos,
            "cross_references": n_xrefs, "xref_unique": n_unique,
            "xref_ambiguous": n_ambig, "terms_multi_defined": n_multi}


if __name__ == "__main__":
    result = build()
    print("Built %s" % DB_PATH)
    for k, v in result.items():
        print("  %-14s %s" % (k, v))
