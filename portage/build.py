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

from .parse import parse

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
    source_url      TEXT,
    source_url_fr   TEXT,
    UNIQUE (act, citation_path)
);
CREATE INDEX idx_sections_parent ON sections(parent_id);
CREATE INDEX idx_sections_path   ON sections(act, citation_path);
CREATE INDEX idx_sections_order  ON sections(act, order_index);

CREATE VIRTUAL TABLE sections_fts_en USING fts5(
    citation_path, heading_en, text_en, content=''
);

CREATE VIRTUAL TABLE sections_fts_fr USING fts5(
    citation_path, heading_fr, text_fr, content=''
);

CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
"""


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
            if bool(r["is_addressable"]) is addressable and r["parent_path"]:
                out[r["parent_path"]].append(r["citation_path"])
        return {k: tuple(v) for k, v in out.items()}

    suspect = set()
    # Addressable children and non-addressable fragments are compared
    # separately. A subsection whose continued-text fragments differ in number
    # says nothing about whether its paragraphs correspond, and vice versa.
    for addressable in (True, False):
        en_kids = children(en_records, addressable)
        fr_kids = children(fr_records, addressable)
        for parent in set(en_kids) & set(fr_kids):
            if en_kids[parent] != fr_kids[parent]:
                suspect |= set(en_kids[parent]) & set(fr_kids[parent])
    return suspect


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
SPOT_CHECKS = ROOT / "tests" / "spot_checks.md"


def _first_sentence(text):
    text = " ".join((text or "").split())
    if not text:
        return "(no text of its own - see its subsections)"
    m = re.search(r"(?<=[.;:])\s", text)
    cut = m.start() if m and m.start() < 400 else min(len(text), 300)
    return text[:cut + 1].strip()


def _write_spot_checks(conn, meta):
    """Acceptance test 4: 20 citation paths for Matt to check by hand.

    The sample is seeded, so it is the same 20 on every build. An unseeded
    sample would change every run and there would be nothing to check against.
    Change SPOT_CHECK_SEED to draw a fresh set.
    """
    rows = conn.execute(
        "SELECT citation_path, level, heading_en, COALESCE(text_en,'') "
        "FROM sections WHERE act='ITA' AND is_addressable=1 "
        "AND citation_path NOT LIKE '%~%' ORDER BY order_index"
    ).fetchall()
    sample = random.Random(SPOT_CHECK_SEED).sample(rows, 20)
    sample.sort(key=lambda r: rows.index(r))

    lines = [
        "# Spot checks",
        "",
        "Twenty citation paths drawn from the build, for checking by hand against",
        "<https://laws-lois.justice.gc.ca/eng/acts/I-3.3/>.",
        "",
        "Regenerated on every build. The sample is seeded (`SPOT_CHECK_SEED` in",
        "`portage/build.py`), so it stays the same until someone changes the seed -",
        "otherwise there would be nothing stable to check against.",
        "",
        "Paths containing `~` are excluded from the sample. Those are derived keys",
        "for definitions and continued text, and cannot be looked up by hand on the",
        "Justice Laws site - see the open question in PLAN.md.",
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
        "Source: Income Tax Act, RSC 1985, c 1 (5th Supp), consolidation date %s."
        % meta["consolidation_date"],
        "Unofficial reproduction. Not an official version.",
        "",
    ]
    SPOT_CHECKS.parent.mkdir(parents=True, exist_ok=True)
    SPOT_CHECKS.write_text("\n".join(lines), encoding="utf-8")


def build(db_path=DB_PATH):
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)

    all_meta = {}
    unverified_rows = []
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
        for rec in fr_records:
            path = rec["citation_path"]
            if path in en_paths:
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
        unverified = _unverified_alignments(en_records, fr_records)
        for path in sorted(unverified):
            conn.execute(
                "UPDATE sections SET alignment_unverified=1 "
                "WHERE act=? AND citation_path=?", (act, path))
            row = conn.execute(
                "SELECT level, parent_path, SUBSTR(COALESCE(text_en,''),1,70), "
                "SUBSTR(COALESCE(text_fr,''),1,70) FROM sections "
                "WHERE act=? AND citation_path=?", (act, path)).fetchone()
            unverified_rows.append(
                (act, path, row[0], row[1],
                 " ".join(row[2].split()), " ".join(row[3].split())))

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
    n_unv = _write_catalogue(
        DATA / "alignment_unverified.csv", unverified_rows,
        ["act", "citation_path", "level", "parent_path", "text_en_start", "text_fr_start"])
    n_gap = _write_catalogue(
        DATA / "bilingual_gaps.csv", gaps,
        ["act", "citation_path", "level", "present_in",
         "defined_term_en", "defined_term_fr", "text_start"])

    _write_spot_checks(conn, all_meta["ITA"]["en"])

    rows = conn.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
    addressable = conn.execute(
        "SELECT COUNT(*) FROM sections WHERE is_addressable=1").fetchone()[0]
    both = conn.execute(
        "SELECT COUNT(*) FROM sections WHERE text_en IS NOT NULL AND text_fr IS NOT NULL"
    ).fetchone()[0]

    retrieved = {}
    for src in SOURCES:
        for lang in ("en", "fr"):
            retrieved[lang] = dt.datetime.fromtimestamp(
                src[lang]["xml"].stat().st_mtime, dt.timezone.utc).date().isoformat()

    meta_rows = {
        "source": "Justice Laws Website, Department of Justice Canada",
        "source_format": "XML consolidation",
        "instruments": "Income Tax Act (RSC 1985, c 1 (5th Supp)) - English and French",
        "consolidation_date": all_meta["ITA"]["en"]["consolidation_date"],
        "consolidation_date_fr": all_meta["ITA"]["fr"]["consolidation_date"],
        "last_amended_date": all_meta["ITA"]["en"]["last_amended_date"],
        "currency_date": all_meta["ITA"]["en"]["currency_date"],
        "retrieved_date": retrieved["en"],
        "retrieved_date_fr": retrieved["fr"],
        "source_url_ita_en": SOURCES[0]["en"]["url"],
        "source_url_ita_fr": SOURCES[0]["fr"]["url"],
        "build_timestamp": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "rows_sections": str(rows),
        "rows_addressable": str(addressable),
        "rows_both_languages": str(both),
        "rows_bilingual_gaps": str(n_gap),
        "rows_alignment_unverified": str(n_unv),
        "rows_label_anomalies": str(n_anom),
        "rows_definition_key_fallbacks": str(n_fb),
        "phase": "0",
        "session": "3 - Income Tax Act, both languages",
        "official": "no - unofficial reproduction, not an official version",
    }
    conn.executemany("INSERT INTO meta (key,value) VALUES (?,?)", sorted(meta_rows.items()))

    conn.commit()
    conn.close()
    return {"rows": rows, "addressable": addressable, "both_languages": both,
            "bilingual_gaps": n_gap, "label_anomalies": n_anom,
            "definition_fallbacks": n_fb, "alignment_unverified": n_unv}


if __name__ == "__main__":
    result = build()
    print("Built %s" % DB_PATH)
    for k, v in result.items():
        print("  %-14s %s" % (k, v))
