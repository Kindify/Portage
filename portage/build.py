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
        "lang": "en",
        "xml": DATA / "ITA-eng.xml",
        "source_url": "https://laws-lois.justice.gc.ca/eng/XML/I-3.3.xml",
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
    order_index     INTEGER NOT NULL,
    is_addressable  INTEGER NOT NULL,
    label_raw       TEXT,
    label_anomaly   INTEGER NOT NULL DEFAULT 0,
    anomaly_reason  TEXT,
    heading_en      TEXT,
    heading_fr      TEXT,
    text_en         TEXT,
    text_fr         TEXT,
    defined_term_en TEXT,
    defined_term_fr TEXT,
    history_note    TEXT,
    bilingual_gap   INTEGER NOT NULL DEFAULT 0,
    source_url      TEXT    NOT NULL,
    UNIQUE (act, citation_path)
);
CREATE INDEX idx_sections_parent ON sections(parent_id);
CREATE INDEX idx_sections_path   ON sections(act, citation_path);
CREATE INDEX idx_sections_order  ON sections(act, order_index);

CREATE VIRTUAL TABLE sections_fts_en USING fts5(
    citation_path, heading_en, text_en, content=''
);

CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
"""


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

    retrieved = dt.datetime.fromtimestamp(
        SOURCES[0]["xml"].stat().st_mtime, dt.timezone.utc
    ).date().isoformat()

    all_meta = {}
    anomalies = []
    counts = {}

    for src in SOURCES:
        records, meta = parse(src["xml"], src["act"], src["source_url"])
        all_meta[src["act"]] = meta

        ids = {}
        for rec in records:
            cur = conn.execute(
                """INSERT INTO sections
                   (act, citation_path, level, parent_path, order_index,
                    is_addressable, label_raw, label_anomaly, anomaly_reason,
                    heading_en, text_en, defined_term_en, defined_term_fr,
                    history_note, source_url)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (rec["act"], rec["citation_path"], rec["level"], rec["parent_path"],
                 rec["order_index"], rec["is_addressable"], rec["label_raw"],
                 rec["label_anomaly"], rec["anomaly_reason"] or None,
                 rec["heading_en"], rec["text_en"], rec["defined_term_en"],
                 rec["defined_term_fr"], rec["history_note"], rec["source_url"]),
            )
            ids[(rec["act"], rec["citation_path"])] = cur.lastrowid

        conn.execute(
            """UPDATE sections SET parent_id = (
                   SELECT p.id FROM sections p
                   WHERE p.act = sections.act AND p.citation_path = sections.parent_path)
               WHERE parent_path IS NOT NULL AND parent_path != ''"""
        )

        for rec in records:
            if rec["label_anomaly"]:
                anomalies.append(
                    (rec["act"], rec["citation_path"], rec["level"],
                     rec["label_raw"] or "", rec["anomaly_reason"])
                )

        counts[src["act"]] = len(records)

    conn.execute(
        """INSERT INTO sections_fts_en (rowid, citation_path, heading_en, text_en)
           SELECT id, citation_path, COALESCE(heading_en,''), COALESCE(text_en,'')
           FROM sections WHERE text_en IS NOT NULL AND text_en != ''"""
    )

    n_anom = _write_catalogue(
        DATA / "label_anomalies.csv", anomalies,
        ["act", "citation_path", "level", "label_raw", "reason"],
    )

    _write_spot_checks(conn, all_meta["ITA"])

    rows = conn.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
    addressable = conn.execute(
        "SELECT COUNT(*) FROM sections WHERE is_addressable=1").fetchone()[0]
    meta_rows = {
        "source": "Justice Laws Website, Department of Justice Canada",
        "source_format": "XML consolidation",
        "instruments": "Income Tax Act (RSC 1985, c 1 (5th Supp)) - English only (session 2)",
        "consolidation_date": all_meta["ITA"]["consolidation_date"],
        "last_amended_date": all_meta["ITA"]["last_amended_date"],
        "currency_date": all_meta["ITA"]["currency_date"],
        "retrieved_date": retrieved,
        "build_timestamp": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "rows_sections": str(rows),
        "rows_addressable": str(addressable),
        "rows_label_anomalies": str(n_anom),
        "phase": "0",
        "session": "2 - English Income Tax Act only",
        "official": "no - unofficial reproduction, not an official version",
    }
    for src in SOURCES:
        meta_rows["source_url_%s" % src["act"].lower()] = src["source_url"]
    conn.executemany("INSERT INTO meta (key,value) VALUES (?,?)", sorted(meta_rows.items()))

    conn.commit()
    conn.close()
    return {"rows": rows, "addressable": addressable, "anomalies": n_anom}


if __name__ == "__main__":
    result = build()
    print("Built %s" % DB_PATH)
    for k, v in result.items():
        print("  %-14s %s" % (k, v))
