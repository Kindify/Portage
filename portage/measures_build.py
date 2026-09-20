"""Build the tax expenditure tables from the committed snapshot.

Five tables, specified in CLAUDE.md. Reads only `data/finance/2026/`.
"""

import csv
import re
from collections import Counter, defaultdict

from lxml import html as LH

from .finance import (FIELD_SLOTS, PAGES, SNAPSHOT, REPORT_YEAR, COST_TOKENS,
                      parse_all, text_of, normalise_label)
from .measure_refs import extract

RETRIEVED_DATE = "2026-09-19"

#: How a reference ended up. 'resolved' is the only success.
REF_STATUS = (
    "resolved",
    "not_in_consolidation",   # a real provision, repealed or not yet in our snapshot
    "instrument_not_held",
    "schedule_or_class",
    "no_provision",
    "no_instrument",
    "term_not_joined",
)

SCHEMA = """
CREATE TABLE measures (
    id              INTEGER PRIMARY KEY,
    report_year     INTEGER NOT NULL,
    slug_en         TEXT,
    slug_fr         TEXT,
    name_en         TEXT,
    name_fr         TEXT,
    part_en         INTEGER,
    part_fr         INTEGER,
    source_url_en   TEXT,
    source_url_fr   TEXT,
    retrieved_date  TEXT NOT NULL,
    bilingual_gap   INTEGER NOT NULL DEFAULT 0,
    %s
);

CREATE TABLE measure_references (
    id              INTEGER PRIMARY KEY,
    measure_id      INTEGER NOT NULL REFERENCES measures(id),
    lang            TEXT NOT NULL,
    order_index     INTEGER NOT NULL,
    raw_text        TEXT NOT NULL,
    instrument      TEXT,
    instrument_name TEXT,
    citation_path   TEXT,
    section_id      INTEGER REFERENCES sections(id),
    status          TEXT NOT NULL,
    reason          TEXT,
    defined_term    TEXT,
    variable        TEXT,
    method          TEXT NOT NULL DEFAULT 'pattern'
);

CREATE TABLE measure_costs (
    id              INTEGER PRIMARY KEY,
    measure_id      INTEGER NOT NULL REFERENCES measures(id),
    lang            TEXT NOT NULL,
    order_index     INTEGER NOT NULL,
    row_label       TEXT,
    year            INTEGER NOT NULL,
    year_header     TEXT,
    value_millions  REAL,
    value_kind      TEXT NOT NULL,
    raw_value       TEXT NOT NULL
);

CREATE TABLE measure_history (
    id              INTEGER PRIMARY KEY,
    measure_id      INTEGER NOT NULL REFERENCES measures(id),
    order_index     INTEGER NOT NULL,
    year            INTEGER,
    text_en         TEXT,
    text_fr         TEXT
);

CREATE TABLE measure_beneficiary_counts (
    id              INTEGER PRIMARY KEY,
    measure_id      INTEGER NOT NULL REFERENCES measures(id),
    lang            TEXT NOT NULL,
    year            INTEGER,
    count           INTEGER,
    raw_value       TEXT NOT NULL
);

CREATE INDEX idx_mref_measure ON measure_references(measure_id, status);
CREATE INDEX idx_mref_path    ON measure_references(instrument, citation_path);
CREATE INDEX idx_mcost_measure ON measure_costs(measure_id, year);
""" % ",\n    ".join(
    "%s_%s TEXT" % (slot, lang) for slot in FIELD_SLOTS for lang in ("en", "fr"))


def _history_items(lang, part, slug):
    """One entry per <li> under Implementation and recent history."""
    name, _url = PAGES[(lang, part)]
    doc = LH.fromstring((SNAPSHOT / name).read_bytes())
    for table in doc.xpath("//main//table"):
        cap = table.xpath("./caption[@id]")
        if not cap or cap[0].get("id") != slug:
            continue
        rows = table.xpath("./tbody/tr")
        if len(rows) <= 5:
            return []
        td = rows[5].xpath("./td")
        if not td:
            return []
        items = [text_of(li) for li in td[0].xpath(".//li")]
        return items or ([text_of(td[0])] if text_of(td[0]) else [])
    return []


_COUNT = re.compile(r"\b(?:About|Approximately|Environ|Quelque)?\s*"
                    r"([\d][\d,   ]{2,})\s+[^.]*?\bin (\d{4})\b", re.I)


def _beneficiary_rows(text):
    """(year, count, raw) from the Number of beneficiaries prose.

    Populated only where exactly one "<number> ... in <year>" pair is present.
    Anything else keeps its raw text with NULL count and year - the field is
    prose, and a half-read sentence is worse than an honest blank.
    """
    if not text:
        return []
    hits = _COUNT.findall(text)
    if len(hits) != 1:
        return [(None, None, text)]
    number, year = hits[0]
    digits = re.sub(r"[,   ]", "", number)
    return [(int(year), int(digits), text)]


def _cost_signature(costs):
    """Numeric cost values, which are identical in both editions."""
    return tuple(sorted(
        (c["year"], c["value_millions"]) for c in costs
        if c["value_millions"] is not None))


def _reference_signature(rows):
    """The set of resolvable references, which is language-independent."""
    return tuple(sorted({
        (r["instrument"] or "", r["citation_path"] or "")
        for r in rows if r["citation_path"]}))


def _term_map(conn):
    """French defined term -> English, from Phase 0's symmetric join only."""
    out = {}
    for fr, en in conn.execute(
            "SELECT defined_term_fr, defined_term_en FROM sections "
            "WHERE level='definition' AND defined_term_fr IS NOT NULL "
            "AND defined_term_en IS NOT NULL AND alignment='verified'"):
        out.setdefault(fr, en)
    return out


def _classify(row, known_paths, instrument):
    """Turn an extractor row into a status."""
    if row.get("reason") == "term_not_joined":
        return "term_not_joined"
    if row["citation_path"]:
        if (instrument, row["citation_path"]) in known_paths:
            return "resolved"
        return "not_in_consolidation"
    reason = row["reason"] or ""
    if "Schedule, Class or Part" in reason:
        return "schedule_or_class"
    if "not held by this dataset" in reason:
        return "instrument_not_held"
    if "no instrument named" in reason:
        return "no_instrument"
    return "no_provision"


def build_measures(conn, write_catalogue):
    """Populate the five tables and write the Phase 1 catalogues."""
    conn.executescript(SCHEMA)

    parsed = parse_all()
    known_paths = {(a, p) for a, p in
                   conn.execute("SELECT act, citation_path FROM sections")}
    section_id = {(a, p): i for a, p, i in
                  conn.execute("SELECT act, citation_path, id FROM sections")}
    term_map = _term_map(conn)

    # Extract references and costs for every measure, in both languages.
    for lang in ("en", "fr"):
        for measure in parsed[lang]:
            measure["refs"] = extract(
                measure["fields"]["legal_reference"], lang, term_map)

    # Bilingual join: reference set plus cost values, never position. Measures
    # are alphabetical within each language, so order means nothing across
    # editions - the Phase 0 lesson, one level up.
    fr_by_sig = defaultdict(list)
    for measure in parsed["fr"]:
        fr_by_sig[(_reference_signature(measure["refs"]),
                   _cost_signature(measure["costs"]))].append(measure)

    pairs, gaps, used = [], [], set()
    for measure in parsed["en"]:
        sig = (_reference_signature(measure["refs"]),
               _cost_signature(measure["costs"]))
        candidates = [m for m in fr_by_sig.get(sig, []) if id(m) not in used]
        if len(candidates) == 1 and any(sig):
            used.add(id(candidates[0]))
            pairs.append((measure, candidates[0]))
        else:
            pairs.append((measure, None))
            gaps.append((measure["slug"], "en", measure["name"][:90],
                         "no unique French match on reference set and cost values"
                         if not candidates else
                         "%d French measures share this signature" % len(candidates)))
    for measure in parsed["fr"]:
        if id(measure) not in used:
            pairs.append((None, measure))
            gaps.append((measure["slug"], "fr", measure["name"][:90],
                         "no unique English match on reference set and cost values"))

    label_rows, cost_token_rows, unresolved, no_refs = Counter(), Counter(), [], []

    for en_m, fr_m in pairs:
        columns, values = [], []
        for slot_i, slot in enumerate(FIELD_SLOTS):
            for lang, m in (("en", en_m), ("fr", fr_m)):
                columns.append("%s_%s" % (slot, lang))
                values.append(m["fields"].get(slot) if m else None)
        base = ["report_year", "slug_en", "slug_fr", "name_en", "name_fr",
                "part_en", "part_fr", "source_url_en", "source_url_fr",
                "retrieved_date", "bilingual_gap"]
        base_values = [
            REPORT_YEAR,
            en_m["slug"] if en_m else None, fr_m["slug"] if fr_m else None,
            en_m["name"] if en_m else None, fr_m["name"] if fr_m else None,
            en_m["part"] if en_m else None, fr_m["part"] if fr_m else None,
            en_m["source_url"] if en_m else None,
            fr_m["source_url"] if fr_m else None,
            RETRIEVED_DATE, 0 if (en_m and fr_m) else 1,
        ]
        cur = conn.execute(
            "INSERT INTO measures (%s) VALUES (%s)"
            % (",".join(base + columns), ",".join("?" * (len(base) + len(columns)))),
            base_values + values)
        measure_id = cur.lastrowid

        for lang, m in (("en", en_m), ("fr", fr_m)):
            if not m:
                continue
            for slot_i, label in m["labels"]:
                label_rows[(lang, slot_i, FIELD_SLOTS[slot_i], label)] += 1

            has_resolved = False
            for row in m["refs"]:
                status = _classify(row, known_paths, row["instrument"])
                has_resolved = has_resolved or status == "resolved"
                conn.execute(
                    """INSERT INTO measure_references
                       (measure_id, lang, order_index, raw_text, instrument,
                        instrument_name, citation_path, section_id, status,
                        reason, defined_term, variable)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (measure_id, lang, row["order_index"], row["raw_text"],
                     row["instrument"], row["instrument_name"],
                     row["citation_path"] if status == "resolved" else row["citation_path"],
                     section_id.get((row["instrument"], row["citation_path"])),
                     status, row["reason"] or None,
                     row.get("defined_term"), row.get("variable")))
                if status != "resolved":
                    unresolved.append(
                        (m["name"][:80], lang, row["instrument"] or "",
                         row["citation_path"] or "", status,
                         row["reason"] or "", row["raw_text"][:140]))
            if not m["refs"]:
                no_refs.append((m["name"][:90], lang,
                                (m["fields"]["legal_reference"] or "")[:120]))

            for i, cost in enumerate(m["costs"], start=1):
                cost_token_rows[(cost["raw_value"], cost["value_kind"])] += 1
                conn.execute(
                    """INSERT INTO measure_costs
                       (measure_id, lang, order_index, row_label, year,
                        year_header, value_millions, value_kind, raw_value)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (measure_id, lang, i, cost["row_label"], cost["year"],
                     cost["year_header"], cost["value_millions"],
                     cost["value_kind"], cost["raw_value"]))

            for year, count, raw in _beneficiary_rows(
                    m["fields"]["number_of_beneficiaries"]):
                conn.execute(
                    """INSERT INTO measure_beneficiary_counts
                       (measure_id, lang, year, count, raw_value)
                       VALUES (?,?,?,?,?)""",
                    (measure_id, lang, year, count, raw))

        en_items = _history_items("en", en_m["part"], en_m["slug"]) if en_m else []
        fr_items = _history_items("fr", fr_m["part"], fr_m["slug"]) if fr_m else []
        for i in range(max(len(en_items), len(fr_items))):
            en_text = en_items[i] if i < len(en_items) else None
            fr_text = fr_items[i] if i < len(fr_items) else None
            year = re.search(r"\b(19|20)\d{2}\b", en_text or fr_text or "")
            conn.execute(
                """INSERT INTO measure_history
                   (measure_id, order_index, year, text_en, text_fr)
                   VALUES (?,?,?,?,?)""",
                (measure_id, i + 1, int(year.group(0)) if year else None,
                 en_text, fr_text))

    counts = {}
    counts["field_label_variants"] = write_catalogue(
        "field_label_variants.csv",
        sorted((lang, slot, key, label, n)
               for (lang, slot, key, label), n in label_rows.items()),
        ["lang", "slot", "field", "label_as_published", "measures"])
    # Symbols only. A number is a value, not a token, and listing all 1,600 of
    # them would make the fixture churn on every edition while hiding the thing
    # it exists to catch: an unannounced new symbol.
    symbols = Counter()
    numeric = 0
    for (raw, kind), n in cost_token_rows.items():
        if re.search(r"\d", raw):
            numeric += n
        else:
            symbols[(raw, kind)] += n
    token_rows = sorted(
        (raw, kind, _legend_match(raw), n) for (raw, kind), n in symbols.items())
    token_rows.append(("(numeric value)", "estimate or projection", "n/a", numeric))
    counts["cost_tokens"] = write_catalogue(
        "cost_tokens.csv", token_rows,
        ["raw_value", "value_kind", "legend_match", "cells"])
    counts["unresolved_references"] = write_catalogue(
        "unresolved_references.csv", sorted(unresolved),
        ["measure", "lang", "instrument", "citation_path", "status", "reason",
         "raw_text"])
    counts["measure_join_gaps"] = write_catalogue(
        "measure_join_gaps.csv", sorted(gaps),
        ["slug", "lang", "name", "reason"])
    counts["measures_without_references"] = write_catalogue(
        "measures_without_references.csv", sorted(no_refs),
        ["measure", "lang", "legal_reference"])
    counts["reference_precision_sample"] = write_reference_sample(
        conn, SNAPSHOT.parent.parent.parent / "tests" / "spot_checks" / "references.md")
    return counts


REFERENCE_SAMPLE_SEED = 20260919


def write_reference_sample(conn, out_path):
    """Acceptance test 8: 30 (raw_text, citation_path) pairs to check by hand.

    Seeded, so the set is stable between builds, and never overwritten once
    results are recorded - the same discipline as the Phase 0 spot checks.
    """
    import random

    if out_path.exists():
        return 0
    rows = conn.execute(
        """SELECT m.name_en, r.lang, r.instrument, r.citation_path, r.raw_text,
                  SUBSTR(COALESCE(s.text_en, s.text_fr, ''), 1, 150)
           FROM measure_references r
           JOIN measures m ON m.id = r.measure_id
           LEFT JOIN sections s ON s.id = r.section_id
           WHERE r.status='resolved'
           ORDER BY m.name_en, r.lang, r.order_index""").fetchall()
    if not rows:
        return 0
    sample = random.Random(REFERENCE_SAMPLE_SEED).sample(rows, min(30, len(rows)))

    lines = [
        "# Precision sample - measure references", "",
        "Thirty references that resolved, drawn from the build, for checking by",
        "hand. For each: does the cited provision in `raw_text` really correspond",
        "to `citation_path`, and does the text quoted from the Act match it?", "",
        "Resolution is mechanical, so what this checks is whether the grammar is",
        "reading Finance's citation the way a person would - the one thing no",
        "automated test in this project can tell us, because every one of them",
        "reads the same grammar.", "",
        "Seeded (`REFERENCE_SAMPLE_SEED` in `portage/measures_build.py`) and",
        "**never overwritten by the build**.", "",
        "| # | Measure | Lang | Citation | As published | Provision text | Result | Notes |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for i, (name, lang, instrument, path, raw, text) in enumerate(sample, 1):
        clean = lambda s: (s or "").replace("|", "\\|").replace("\n", " ")
        lines.append("| %d | %s | %s | `%s %s` | %s | %s |  |  |" % (
            i, clean(name)[:46], lang, instrument, path,
            clean(raw)[:70], clean(text)[:70]))
    lines += ["", "Source: Report on Federal Tax Expenditures 2026, retrieved "
              "2026-09-19. Provision text from the Income Tax Act / Regulations, "
              "consolidation 2026-06-18.", ""]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return len(sample)


#: Tokens Finance documents in the published legend, against tokens Portage
#: inferred. See README, Known limits.
_LEGEND = {"n.a.", "n.d.", "–", "X", "S", "F"}


def _legend_match(raw):
    if raw in _LEGEND:
        return "legend"
    if raw == "":
        return "portage"
    if raw in ("-", "n.d"):
        return "variant"
    return "number" if re.search(r"\d", raw) else "portage"
