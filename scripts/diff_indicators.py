"""Diff the indicators of two builds, one row per (measure, column) that moved.

The record of what a fix actually changed. Run against the released database
and the current one:

    python -m scripts.diff_indicators dist/v0.3.0/portage.sqlite portage.sqlite

It calls nothing and reads nothing but the two files. The output is committed
as data, because the released database it compares against is a build artifact
that is not in the repository - nobody can regenerate this from a clean clone,
so the file itself is the evidence.
"""

import csv
import pathlib
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "indicator_changes_v0.3.0_to_v0.3.1.csv"

#: Which fix a column's movement is attributable to. Columns fed by references
#: are decided per measure, below, because C and D both move them.
BY_COLUMN = {
    "beneficiaries_latest": "A",
    "beneficiaries_latest_year": "A",
    "cost_per_beneficiary": "A",
    "cost_per_beneficiary_note": "A",
    "amending_acts_count": "B",
    "amending_acts_method": "B",
}
REFERENCE_FED = {
    "provisions_cited", "provisions_resolved", "provisions_not_in_consolidation",
    "provisions_repealed_stub", "sections_touched", "shared_with_measures",
}


def _reference_fix(new, measure_id):
    """C or D, from the references that actually changed for this measure.

    C moved a paragraph onto the definition that owns it, which shows up as a
    127(9) path. D read a combined repeal label as covering the subsections it
    names, which shows up as the new status. Asking the data which happened is
    better than assigning the fix by column name, because both fixes move the
    same columns.
    """
    paths = [r[0] or "" for r in new.execute(
        "SELECT citation_path FROM measure_references WHERE measure_id=? "
        "AND status='resolved_combined_stub'", (measure_id,))]
    if paths:
        return "D"
    paths = [r[0] or "" for r in new.execute(
        "SELECT citation_path FROM measure_references WHERE measure_id=? "
        "AND status='resolved' AND citation_path LIKE '127(9)%'", (measure_id,))]
    if paths:
        return "C"
    return "C/D"          # a knock-on: shares a provision with a measure above


def diff(old_path, new_path):
    old = sqlite3.connect(old_path)
    new = sqlite3.connect(new_path)
    columns = [r[1] for r in new.execute("PRAGMA table_info(indicators)")]
    shared = [c for c in columns
              if c in {r[1] for r in old.execute("PRAGMA table_info(indicators)")}]

    def rows(conn):
        sql = "SELECT measure_id,%s FROM indicators" % ",".join(
            '"%s"' % c for c in shared[1:])
        return {r[0]: dict(zip(shared[1:], r[1:])) for r in conn.execute(sql)}

    before, after = rows(old), rows(new)
    names = dict(new.execute(
        "SELECT measure_id, COALESCE(name_en, name_fr) FROM indicators"))

    out = []
    for mid in sorted(set(before) & set(after)):
        for column in shared[1:]:
            a, b = before[mid][column], after[mid][column]
            if a == b:
                continue
            if isinstance(a, float) and isinstance(b, float) and abs(a - b) < 1e-9:
                continue
            fix = BY_COLUMN.get(column)
            if fix is None and column in REFERENCE_FED:
                fix = _reference_fix(new, mid)
            out.append((mid, (names.get(mid) or "")[:70], column,
                        "" if a is None else a, "" if b is None else b,
                        fix or "?"))
    return out


def main(argv=None):
    argv = list(argv or sys.argv[1:])
    if len(argv) != 2:
        raise SystemExit(__doc__)
    rows = diff(argv[0], argv[1])
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(["measure_id", "measure_name", "column",
                         "old_value", "new_value", "fix"])
        writer.writerows(rows)
    print("%d changed values written to %s" % (len(rows), OUT.name))
    from collections import Counter
    for fix, n in sorted(Counter(r[5] for r in rows).items()):
        print("   fix %-4s %4d values, %3d measures"
              % (fix, n, len({r[0] for r in rows if r[5] == fix})))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
