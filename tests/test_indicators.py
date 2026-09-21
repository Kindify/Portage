"""Phase 2 acceptance tests.

CLAUDE.md lists seven. Four are mechanical and are here. Two need Matt before
they can assert anything - the hand-recomputed cost changes and the temporal
scope precision sample - and each has an empty fixture that turns into a real
test the moment he fills it in. The seventh, the temporal-scope verbatim rule,
is here and is vacuous until Phase 2 step 3 fills the table; it is written now
so that it fails the first time a row arrives that breaks it.
"""

import csv
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"


# -- 1. Every column is defined, and the doc is current ---------------------

def test_every_indicator_column_has_a_definition(conn):
    from portage.indicators import COLUMN_NOTES

    cols = [r[1] for r in conn.execute("PRAGMA table_info(indicators)")]
    missing = [c for c in cols if c not in COLUMN_NOTES]
    extra = [k for k in COLUMN_NOTES if k not in cols]
    assert not missing, "columns with no definition entry: %s" % missing
    assert not extra, "definition entries for columns that do not exist: %s" % extra


def test_the_definitions_doc_is_current(conn):
    """The file on disk must be what the generator produces.

    The build regenerates the file, so this cannot catch a hand edit on its own
    - a hand edit shows up as a git diff after the next build. What it catches
    is a generator that writes something other than what it returns, and the
    two assertions below are the substantive ones: every view and every column
    has to actually appear in the file, not merely in the dict the file is
    generated from.
    """
    from portage.indicators import VIEWS, generate_definitions

    on_disk = (ROOT / "docs" / "indicator-definitions.md").read_text(encoding="utf-8")
    generated = generate_definitions(conn)
    assert on_disk.splitlines() == generated.splitlines(), (
        "docs/indicator-definitions.md is stale - rebuild to regenerate it")

    for name, _prose, _sql in VIEWS:
        assert "\n## `%s`\n" % name in on_disk, "no section for view %s" % name
    for col in (r[1] for r in conn.execute("PRAGMA table_info(indicators)")):
        assert "| `%s` |" % col in on_disk, "no table row for column %s" % col


def test_every_view_has_prose(conn):
    from portage.indicators import VIEWS

    declared = {name for name, _prose, _sql in VIEWS}
    built = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='view'")}
    assert declared == built
    for name, prose, _sql in VIEWS:
        assert len(prose.split()) > 20, "%s has no real prose entry" % name


# -- 2. Hand recomputation, supplied by Matt --------------------------------

def test_cost_change_matches_the_hand_computed_fixture(conn):
    """Cost changes Matt computed in a spreadsheet from the published pages.

    The fixture is empty until he supplies the three measures CLAUDE.md asks
    for. An empty fixture passes; a wrong number does not.
    """
    path = FIXTURES / "cost_change_by_hand.csv"
    rows = [r for r in csv.DictReader(open(path, encoding="utf-8"))
            if r["measure_name_en"].strip()]
    if not rows:
        pytest.skip("no hand-computed rows yet - see PLAN.md, Phase 2 step 4")
    for row in rows:
        got = conn.execute(
            """SELECT cost_first_estimate, cost_latest_estimate, cost_change_abs
                 FROM indicators WHERE name_en = ?""",
            (row["measure_name_en"],)).fetchone()
        assert got is not None, "no measure named %r" % row["measure_name_en"]
        assert got["cost_first_estimate"] == pytest.approx(float(row["first_estimate"]))
        assert got["cost_latest_estimate"] == pytest.approx(float(row["latest_estimate"]))
        assert got["cost_change_abs"] == pytest.approx(float(row["change_abs"]))


# -- 3. The CLAUDE.md fixture measure ---------------------------------------

def test_the_reorganization_deferral(conn):
    """CLAUDE.md's Phase 2 fixture, with one value changed by an amendment.

    CLAUDE.md asks for cost_status = 'not_costed'. Finance published no cost
    table at all for this measure, and the fifth value Matt adopted on
    2026-09-20 distinguishes that from a table showing no estimate. The
    assertion is 'no_cost_table' for that reason and no other.
    """
    row = conn.execute(
        "SELECT * FROM indicators WHERE name_en = ?",
        ("Deferral for asset transfers to a corporation and corporate "
         "reorganizations",)).fetchone()
    assert row is not None
    assert row["cost_status"] == "no_cost_table"
    assert row["cost_figure_basis"] == "no_cost_table"
    assert row["cost_latest_estimate"] is None
    assert row["beneficiaries_latest"] is None
    assert row["provisions_resolved"] == 4

    paths = [r[0] for r in conn.execute(
        """SELECT citation_path FROM measure_resolved_provisions
            WHERE measure_id = ? ORDER BY citation_path""", (row["measure_id"],))]
    assert paths == ["55", "85", "87", "88"]


def test_paragraph_20_1_ss(conn):
    """Phase 1's fixture, still resolving through the Phase 2 view."""
    rows = [r[0] for r in conn.execute(
        """SELECT citation_path FROM measure_resolved_provisions
            WHERE citation_path = '20(1)(ss)' AND act = 'ITA'""")]
    assert rows == ["20(1)(ss)"]


# -- 4. No indicator is non-null where an input is null ---------------------

@pytest.mark.parametrize("label,sql", [
    ("cost_change_abs without both estimates, or with equal years",
     """SELECT COUNT(*) FROM indicators WHERE cost_change_abs IS NOT NULL
         AND (cost_first_estimate IS NULL OR cost_latest_estimate IS NULL
              OR cost_first_estimate_year = cost_latest_estimate_year)"""),
    ("cost_change_pct with a null or zero first estimate",
     """SELECT COUNT(*) FROM indicators WHERE cost_change_pct IS NOT NULL
         AND (cost_change_abs IS NULL OR cost_first_estimate IS NULL
              OR cost_first_estimate = 0)"""),
    ("cost_per_beneficiary without both inputs in the same year",
     """SELECT COUNT(*) FROM indicators WHERE cost_per_beneficiary IS NOT NULL
         AND (cost_latest_estimate IS NULL OR beneficiaries_latest IS NULL
              OR cost_latest_estimate_year <> beneficiaries_latest_year)"""),
    ("years_since_last_change without a last change year",
     """SELECT COUNT(*) FROM indicators WHERE years_since_last_change IS NOT NULL
         AND last_change_year IS NULL"""),
    ("a cost figure without a figure row to read it from",
     """SELECT COUNT(*) FROM indicators WHERE cost_figure_row_label IS NULL
         AND (cost_latest_estimate IS NOT NULL OR cost_first_estimate IS NOT NULL
              OR cost_latest_projection IS NOT NULL)"""),
    ("amending_acts_method without a count",
     """SELECT COUNT(*) FROM indicators
         WHERE (amending_acts_method IS NULL) <> (amending_acts_count IS NULL)"""),
    ("beneficiaries_latest_year without a count",
     """SELECT COUNT(*) FROM indicators WHERE beneficiaries_latest_year IS NOT NULL
         AND beneficiaries_latest IS NULL"""),
    ("objective_category_internal with no matched category",
     """SELECT COUNT(*) FROM indicators i WHERE i.objective_category_internal IS NOT NULL
         AND NOT EXISTS (SELECT 1 FROM measure_objective_categories c
                          WHERE c.measure_id = i.measure_id)"""),
])
def test_no_indicator_survives_a_null_input(conn, label, sql):
    assert conn.execute(sql).fetchone()[0] == 0, label


def test_columns_documented_as_never_null_are_never_null(conn):
    """The null rules in the definitions are assertions, not commentary.

    Every column whose documented rule begins "never" is checked against the
    data. This is the one test where the doc and the test are the same thing:
    a column that starts producing nulls fails here until either the data or
    the definition is fixed.
    """
    from portage.indicators import COLUMN_NOTES

    offenders = []
    for col, (_meaning, null_when) in sorted(COLUMN_NOTES.items()):
        if not null_when.startswith("never"):
            continue
        n = conn.execute(
            'SELECT COUNT(*) FROM indicators WHERE "%s" IS NULL' % col).fetchone()[0]
        if n:
            offenders.append((col, n))
    assert not offenders, (
        "columns documented as never null that are null: %s" % offenders)


def test_a_cost_estimate_is_never_zero_standing_in_for_missing(conn):
    """Finance's non-numeric tokens must never have become numbers."""
    assert conn.execute(
        """SELECT COUNT(*) FROM measure_costs
            WHERE value_millions IS NOT NULL
              AND value_kind NOT IN ('estimate','projection')""").fetchone()[0] == 0


# -- 5. Temporal scope ------------------------------------------------------

def test_every_temporal_phrase_is_verbatim(conn):
    """CLAUDE.md: the phrase must be a substring of the provision's text_en.

    Vacuous until Phase 2 step 3 fills the table, and written now so that it
    is already in place when the first row arrives.
    """
    bad = []
    for sid, phrase in conn.execute(
            "SELECT section_id, phrase FROM provision_temporal_scope"):
        text = conn.execute(
            "SELECT text_en FROM sections WHERE id=?", (sid,)).fetchone()[0]
        if not text or phrase not in text:
            bad.append((sid, phrase))
    assert not bad, "phrases that are not verbatim substrings: %s" % bad[:5]


def test_the_prompt_doc_is_current():
    """docs/temporal-scope-prompt.md must match the script.

    The prompt is the one judgment this project delegates to a model, and it
    is the thing Matt reads before the key is supplied. A doc that has drifted
    from the script would be worse than no doc.
    """
    from scripts.extract_temporal_scope import prompt_doc

    on_disk = (ROOT / "docs" / "temporal-scope-prompt.md").read_text(encoding="utf-8")
    assert on_disk.splitlines() == prompt_doc().splitlines(), (
        "docs/temporal-scope-prompt.md is stale - regenerate it from "
        "scripts/extract_temporal_scope.py")


def test_the_extraction_never_runs_from_the_build():
    """CLAUDE.md: the API is called from a batch script, never from the build.

    Asserted by import graph rather than by reading the code. It runs in a
    fresh interpreter on purpose: inside this process a sibling test has
    already imported the batch script, so checking this process's sys.modules
    would prove nothing about what the build pulls in.
    """
    import subprocess

    probe = (
        "import sys, json;"
        "import portage.build;"
        "print(json.dumps(sorted("
        "  m for m in sys.modules"
        "  if m == 'anthropic' or m.startswith('anthropic.')"
        "     or m.startswith('scripts'))))"
    )
    out = subprocess.run([sys.executable, "-c", probe], cwd=str(ROOT),
                         capture_output=True, text=True, check=True)
    leaked = json.loads(out.stdout.strip())
    assert leaked == [], (
        "importing portage.build pulled in %s - the build must never reach "
        "the API or the batch script" % leaked)


def test_temporal_bounds_carry_a_date_that_is_in_the_phrase(conn):
    """Never infer a date the text does not state.

    The phrase is verbatim (asserted above); this asserts the date came out of
    that phrase rather than out of the model's own knowledge. Vacuous until
    step 3 runs, like the rest.
    """
    import re

    bad = []
    for phrase, date, year in conn.execute(
            "SELECT phrase, bound_date, bound_year FROM provision_temporal_scope"):
        years = re.findall(r"\b(1[89]\d\d|20\d\d)\b", phrase)
        if date is not None and date[:4] not in years:
            bad.append((phrase, date))
        if year is not None and str(year) not in years:
            bad.append((phrase, year))
    assert not bad, "bounds whose date is not in their phrase: %s" % bad[:5]


def test_every_temporal_row_names_the_prompt_that_wrote_it(conn):
    """Two prompt versions produce rows into one table.

    Round 1 ran under one prompt; the taxonomy rerun adds the `at` kind and
    the phase-down rule and runs under another. A row that cannot say which
    wrote it is unreadable evidence, and `meta` must name every version the
    rows actually carry.
    """
    used = {r[0] for r in conn.execute(
        "SELECT DISTINCT prompt_sha256 FROM provision_temporal_scope")}
    if not used:
        pytest.skip("provision_temporal_scope is empty - Phase 2 step 3")
    assert None not in used, "temporal rows with no prompt_sha256"
    meta = dict(conn.execute("SELECT key, value FROM meta"))
    named = {h.strip() for h in
             meta.get("temporal_scope_prompt_sha256_in_rows", "").split(";")
             if h.strip()}
    assert used == named, "prompts in rows %s but meta names %s" % (used, named)


def test_bound_kind_is_one_of_the_four(conn):
    kinds = {r[0] for r in conn.execute(
        "SELECT DISTINCT bound_kind FROM provision_temporal_scope")}
    assert kinds <= {"start", "end", "step_down", "at"}, (
        "unexpected bound_kind values: %s" % (kinds - {"start", "end", "step_down", "at"}))


def test_temporal_precision_matches_the_stored_bound(conn):
    """bound_precision must describe what bound_date/bound_year actually hold.

    The column exists so nothing has to guess whether a date is exact. A row
    where it disagrees with the value would be worse than no column at all.
    """
    import re

    bad = []
    for date, year, prec in conn.execute(
            """SELECT bound_date, bound_year, bound_precision
                 FROM provision_temporal_scope"""):
        if prec == "day":
            ok = date is not None and re.fullmatch(r"\d{4}-\d{2}-\d{2}", date)
        elif prec == "month":
            ok = date is not None and re.fullmatch(r"\d{4}-\d{2}", date)
        elif prec == "year":
            ok = date is None and year is not None
        else:
            ok = False
        if not ok:
            bad.append((date, year, prec))
    assert not bad, "rows whose precision does not match their bound: %s" % bad[:5]


def test_phrase_match_describes_how_the_phrase_was_found(conn):
    """The stored phrase is always the source's bytes; this says how it was
    located. A row marked `exact` must contain no exotic space, and one marked
    `whitespace_normalized` must contain at least one - otherwise the column
    is decoration rather than provenance.
    """
    from scripts.extract_temporal_scope import _SPACE_VARIANTS

    bad = []
    for phrase, match in conn.execute(
            "SELECT phrase, phrase_match FROM provision_temporal_scope"):
        has_odd = any(ch in phrase for ch in _SPACE_VARIANTS)
        if match == "exact" and has_odd:
            bad.append(("exact but contains an exotic space", phrase))
        elif match == "whitespace_normalized" and not has_odd:
            bad.append(("normalized but contains none", phrase))
        elif match not in ("exact", "whitespace_normalized"):
            bad.append(("phrase_match is %r" % match, phrase))
    assert not bad, "rows whose phrase_match does not describe them: %s" % bad[:5]


def test_temporal_rows_are_reachable_from_the_provision_finance_cited(conn):
    """cited_section_id must be the row itself or one of its ancestors."""
    bad = []
    for sid, cited in conn.execute(
            "SELECT section_id, cited_section_id FROM provision_temporal_scope"):
        node, seen = sid, set()
        while node is not None and node not in seen:
            if node == cited:
                break
            seen.add(node)
            node = conn.execute(
                "SELECT parent_id FROM sections WHERE id=?", (node,)).fetchone()[0]
        else:
            bad.append((sid, cited))
    assert not bad, "rows whose cited_section_id is not an ancestor: %s" % bad[:5]


def test_temporal_scope_records_its_provenance(conn):
    """A model extraction with no model, prompt and date recorded is not data."""
    n = conn.execute("SELECT COUNT(*) FROM provision_temporal_scope").fetchone()[0]
    if n == 0:
        pytest.skip("provision_temporal_scope is empty - Phase 2 step 3")
    meta = dict(conn.execute("SELECT key, value FROM meta"))
    for required in ("temporal_scope_model", "temporal_scope_prompt_sha256",
                     "temporal_scope_run_date", "temporal_scope_batch_ids",
                     "temporal_scope_batch_max_tokens"):
        assert required in meta, "meta is missing %s" % required
        assert meta[required] not in ("", "None"), "%s is empty" % required

    # Every batch a row claims must be one meta names, and every batch meta
    # names must have produced rows. Two batches made this dataset under
    # different output ceilings; a row that cannot say which is unprovenanced.
    named = {b.strip() for b in meta["temporal_scope_batch_ids"].split(";")}
    used = {r[0] for r in conn.execute(
        "SELECT DISTINCT batch_id FROM provision_temporal_scope")}
    assert None not in used, "rows with no batch_id"
    assert used == named, "batches in rows %s but meta names %s" % (used, named)


# -- 6. The views run, and return what the fixture records ------------------

def test_view_row_counts_match_the_fixture(conn):
    from portage.indicators import VIEWS

    expected = {r["view"]: int(r["rows"]) for r in
                csv.DictReader(open(FIXTURES / "view_row_counts.csv", encoding="utf-8"))}
    actual = {name: conn.execute('SELECT COUNT(*) FROM "%s"' % name).fetchone()[0]
              for name, _p, _s in VIEWS}
    assert actual == expected, (
        "view row counts differ from the fixture. If this is intended, update "
        "tests/fixtures/view_row_counts.csv in its own commit and say why.")


# -- Structure and principle ------------------------------------------------

def test_indicators_has_one_row_per_measure(conn):
    assert (conn.execute("SELECT COUNT(*) FROM indicators").fetchone()[0]
            == conn.execute("SELECT COUNT(*) FROM measures").fetchone()[0])


def _has_top_level_order_by(sql):
    """True where a view orders its own rows.

    An ORDER BY inside a parenthesised subquery is *selection* - "the most
    recent year whose value_kind is estimate" is written that way - and says
    nothing about the order the view hands its rows back in. Only an ORDER BY
    at paren depth zero does that, so depth is what this counts.
    """
    depth, lowered = 0, sql.lower()
    i = 0
    while i < len(lowered):
        ch = lowered[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0 and lowered.startswith("order by", i):
            return True
        i += 1
    return False


def test_no_view_orders_its_rows(conn):
    """No ordering is baked into the data - sorting is the reader's action.

    A top-level ORDER BY in a canned view would present one arrangement as the
    natural one, which for a dataset about tax expenditures is exactly the
    judgment this project does not make.
    """
    offenders = [name for name, sql in conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='view'")
        if _has_top_level_order_by(sql)]
    assert not offenders, "views with a top-level ORDER BY: %s" % offenders


def test_every_section_touched_is_a_real_section(conn):
    """The top-level section is cut out of a citation path by string rule."""
    bad = [tuple(r) for r in conn.execute(
        """SELECT DISTINCT p.act, p.citation_path, p.top_section
             FROM measure_resolved_provisions p
            WHERE NOT EXISTS (SELECT 1 FROM sections s
                               WHERE s.act = p.act
                                 AND s.citation_path = p.top_section
                                 AND s.level = 'section')""")]
    assert not bad, "paths whose top-level section does not exist: %s" % bad[:5]


def test_finance_groups_its_objective_categories_twelve_and_ten(conn):
    """Finance's Part 3 grouping, read from each edition's own markup.

    A change in Finance's grouping must fail here rather than silently
    reclassify measures.
    """
    counts = {(r[0], r[1]): r[2] for r in conn.execute(
        """SELECT lang, group_name, COUNT(*) FROM objective_category_groups
            GROUP BY lang, group_name""")}
    assert counts == {("en", "internal"): 12, ("en", "other"): 10,
                      ("fr", "internal"): 12, ("fr", "other"): 10}


def test_a_measure_with_several_total_rows_has_no_cost_figure(conn):
    """Several cost tables means several Totals, and choosing is judgment.

    Five measures publish more than one table. Adding the Totals together
    would be arithmetic Finance did not publish, and picking one would be a
    reading of which table is the measure's own - which for the three donation
    measures would be wrong, since their second table totals a group of
    measures rather than the one being described.
    """
    rows = conn.execute(
        """SELECT cost_latest_estimate, cost_first_estimate, cost_change_abs,
                  cost_figure_row_label
             FROM indicators
            WHERE cost_figure_basis IN ('multiple_total_rows','components_only')""")
    for row in rows:
        assert all(v is None for v in tuple(row))


def test_amending_counts_come_from_the_history_notes(conn):
    """Every section with a note is parsed, and the count excludes the first
    entry, which is the enactment that put the section there."""
    with_note = conn.execute(
        "SELECT COUNT(*) FROM sections WHERE history_note IS NOT NULL").fetchone()[0]
    parsed = conn.execute("SELECT COUNT(*) FROM section_amending_acts").fetchone()[0]
    unparsed = len(list(csv.DictReader(
        open(ROOT / "data" / "amending_acts_unparsed.csv", encoding="utf-8"))))
    assert parsed + unparsed == with_note
    assert conn.execute(
        """SELECT COUNT(*) FROM section_amending_acts
            WHERE amending_entries <> statute_entries - 1""").fetchone()[0] == 0


def test_each_measure_reads_from_exactly_one_edition(conn):
    """A measure present in both editions must not be counted twice."""
    assert conn.execute(
        """SELECT COUNT(*) FROM measure_figure_basis b
            WHERE b.reference_lang IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM measure_references r
                               WHERE r.measure_id = b.measure_id
                                 AND r.lang = b.reference_lang)""").fetchone()[0] == 0
    doubled = [tuple(r) for r in conn.execute(
        """SELECT i.measure_id, i.provisions_cited, both.n
             FROM indicators i
             JOIN (SELECT measure_id, COUNT(*) AS n
                     FROM measure_references
                    GROUP BY measure_id
                   HAVING COUNT(DISTINCT lang) = 2) both
               ON both.measure_id = i.measure_id
            WHERE i.provisions_cited >= both.n""")]
    assert not doubled, (
        "measures whose reference count spans both editions: %s" % doubled[:5])


def test_the_v031_change_record_matches_this_build(conn):
    """Every new_value in the change record must be what the build produces.

    The record compares this build against the released v0.3.0 database, which
    is a build artifact and not in the repository - so a fixture diff would
    only compare the file with itself. This checks the half that can be
    checked: the "after" column has to be the current value, or the record is
    describing a build that no longer exists.
    """
    import csv

    path = ROOT / "data" / "indicator_changes_v0.3.0_to_v0.3.1.csv"
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    assert rows, "the change record is empty"

    bad = []
    for row in rows:
        actual = conn.execute(
            'SELECT "%s" FROM indicators WHERE measure_id=?' % row["column"],
            (int(row["measure_id"]),)).fetchone()[0]
        expected = row["new_value"]
        if actual is None:
            ok = expected == ""
        elif isinstance(actual, float):
            ok = abs(actual - float(expected)) < 1e-6
        else:
            ok = str(actual) == expected
        if not ok:
            bad.append((row["measure_id"], row["column"], expected, actual))
    assert not bad, "change record disagrees with this build: %s" % bad[:5]

    assert {r["fix"] for r in rows} <= {"A", "B", "C", "D", "E", "C/D"}
