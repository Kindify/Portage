"""Phase 1: the tax expenditure report tables."""

import csv
import re

import pytest

MEASURES_IN_REPORT = 229


def test_every_measure_on_every_page_is_captured(conn):
    """Acceptance test 1: parsed measures equal the Part 3 index count."""
    for lang, column in (("en", "slug_en"), ("fr", "slug_fr")):
        n = conn.execute(
            "SELECT COUNT(*) FROM measures WHERE %s IS NOT NULL" % column
        ).fetchone()[0]
        assert n == MEASURES_IN_REPORT, "%s: %d measures, expected %d" % (
            lang, n, MEASURES_IN_REPORT)


def test_every_measure_has_a_reference_or_is_catalogued(conn, built):
    """Acceptance test 2."""
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    listed = {r["measure"] for r in csv.DictReader(
        open(root / "data" / "measures_without_references.csv", encoding="utf-8"))}
    missing = []
    for row in conn.execute(
            "SELECT id, COALESCE(name_en, name_fr) AS name FROM measures"):
        n = conn.execute(
            "SELECT COUNT(*) FROM measure_references WHERE measure_id=?",
            (row[0],)).fetchone()[0]
        if n == 0 and row[1][:90] not in listed:
            missing.append(row[1])
    assert missing == [], missing[:5]


def test_reference_statuses_are_known_values(conn):
    from portage.measures_build import REF_STATUS

    seen = {r[0] for r in conn.execute(
        "SELECT DISTINCT status FROM measure_references")}
    assert seen <= set(REF_STATUS), seen - set(REF_STATUS)


def test_resolved_references_point_at_a_real_section(conn):
    bad = conn.execute(
        "SELECT COUNT(*) FROM measure_references "
        "WHERE status='resolved' AND section_id IS NULL").fetchone()[0]
    assert bad == 0
    bad = conn.execute(
        """SELECT COUNT(*) FROM measure_references r
           LEFT JOIN sections s ON s.id = r.section_id
           WHERE r.status='resolved'
             AND (s.act != r.instrument OR s.citation_path != r.citation_path)"""
    ).fetchone()[0]
    assert bad == 0


def test_no_cost_is_ever_stored_as_zero_for_a_symbol(conn):
    """"Not in effect", "withheld" and "small" are not zero."""
    bad = conn.execute(
        "SELECT COUNT(*) FROM measure_costs "
        "WHERE value_kind NOT IN ('estimate','projection') "
        "AND value_millions IS NOT NULL").fetchone()[0]
    assert bad == 0, "a published symbol was given a numeric value"


def test_every_cost_token_is_classified(conn, built):
    """Acceptance test 6: a new token fails the build until it is classified."""
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    listed = {r["raw_value"] for r in csv.DictReader(
        open(root / "data" / "cost_tokens.csv", encoding="utf-8"))}
    # Symbols, not numbers: a number is a value, and the catalogue exists to
    # catch an unannounced new symbol.
    seen = {r[0] for r in conn.execute(
        "SELECT DISTINCT raw_value FROM measure_costs") if not re.search(r"\d", r[0])}
    assert seen <= listed, sorted(seen - listed)[:10]
    unclassified = conn.execute(
        "SELECT COUNT(*) FROM measure_costs WHERE value_kind='unclassified'"
    ).fetchone()[0]
    assert unclassified == 0


def test_reorganization_deferral_fixture(conn):
    """Acceptance test 4, from CLAUDE.md."""
    row = conn.execute(
        "SELECT id FROM measures WHERE name_en LIKE 'Deferral for asset transfers%'"
    ).fetchone()
    assert row is not None, "the reorganization deferral measure is missing"
    paths = {r[0] for r in conn.execute(
        "SELECT citation_path FROM measure_references "
        "WHERE measure_id=? AND lang='en' AND status='resolved'", (row[0],))}
    assert paths == {"55", "85", "87", "88"}, paths
    estimates = conn.execute(
        "SELECT COUNT(*) FROM measure_costs WHERE measure_id=? "
        "AND value_millions IS NOT NULL", (row[0],)).fetchone()[0]
    assert estimates == 0, "this measure has no cost estimate for any year"


def test_paragraph_20_1_ss_fixture(conn):
    """Acceptance test 5, from CLAUDE.md."""
    rows = conn.execute(
        "SELECT status, section_id FROM measure_references "
        "WHERE citation_path='20(1)(ss)'").fetchall()
    assert rows, "no reference resolves to 20(1)(ss)"
    for status, section_id in rows:
        assert status == "resolved"
        path = conn.execute(
            "SELECT citation_path FROM sections WHERE id=?", (section_id,)
        ).fetchone()[0]
        assert path == "20(1)(ss)"


def test_definition_paragraph_resolves_to_the_definition_key(conn):
    """"paragraph (a.3) of definition of X in subsection 127(9)".

    Resolving this as 127(a.3) - a provision that does not exist - is what the
    rule was written to prevent.
    """
    rows = conn.execute(
        "SELECT lang, citation_path, status FROM measure_references "
        "WHERE citation_path LIKE '127(9)\"investment tax credit\"%'").fetchall()
    assert rows, "the definition-paragraph reference did not resolve"
    for lang, path, status in rows:
        assert status == "resolved", (lang, path, status)
    assert conn.execute(
        "SELECT COUNT(*) FROM measure_references WHERE citation_path='127(a.3)'"
    ).fetchone()[0] == 0


def test_bilingual_pairs_agree_on_references_and_costs(conn):
    """Acceptance test 7: a joined pair must match on what it was joined by.

    Scoped to join_method='content'. The categorical pairs were joined
    precisely because references and cost values gave nothing to match on, so
    requiring them to match there would assert something never claimed.
    """
    for measure_id, in conn.execute(
            "SELECT id FROM measures WHERE join_method='content'"):
        sets = {}
        for lang in ("en", "fr"):
            sets[lang] = {r[0] for r in conn.execute(
                "SELECT citation_path FROM measure_references "
                "WHERE measure_id=? AND lang=? AND citation_path IS NOT NULL",
                (measure_id, lang))}
        assert sets["en"] == sets["fr"], (measure_id, sets)
        values = {}
        for lang in ("en", "fr"):
            values[lang] = sorted(
                (r[0], r[1]) for r in conn.execute(
                    "SELECT year, value_millions FROM measure_costs "
                    "WHERE measure_id=? AND lang=? AND value_millions IS NOT NULL",
                    (measure_id, lang)))
        assert values["en"] == values["fr"], measure_id


def _csv_values(path):
    import re
    out = {}
    with open(path, encoding="cp1252", newline="") as f:
        for row in csv.DictReader(f):
            measure = (row.get("MEASURE") or row.get("MESURE") or "").strip()
            detail = (row.get("DETAILS") or row.get("DÉTAILS") or "").strip()
            for year in range(2020, 2028):
                raw = (row.get(str(year)) or "").strip()
                if not re.fullmatch(r"-?[\d,   ]+(\.\d+)?", raw):
                    continue
                if not any(ch.isdigit() for ch in raw):
                    continue
                out[(measure, detail, year)] = float(re.sub(r"[,   ]", "", raw))
    return out


def test_costs_match_finance_open_data(conn, built):
    """Every HTML cost cell with a counterpart in the OGL CSV must match.

    This is the only check on Phase 1's numbers that does not come from the
    pages we parsed: the CSV is Finance's own summary of the same report,
    published separately under the Open Government Licence. It catches a
    misread column or a dropped thousands separator in a way that re-reading
    our own parse never could.
    """
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    published = _csv_values(root / "data" / "finance" / "2026" / "data-tables-e.csv")
    assert published, "the open data CSV produced no numbers"

    parsed = {}
    for name, label, year, value in conn.execute(
            """SELECT m.name_en, c.row_label, c.year, c.value_millions
               FROM measure_costs c JOIN measures m ON m.id = c.measure_id
               WHERE c.lang='en' AND c.value_millions IS NOT NULL"""):
        parsed[((name or "").strip(), (label or "").strip(), year)] = value

    common = set(parsed) & set(published)
    assert len(common) > 400, (
        "only %d cells could be compared - the join to the CSV has broken"
        % len(common))
    mismatches = [(k, parsed[k], published[k]) for k in sorted(common)
                  if abs(parsed[k] - published[k]) > 1e-9]
    assert mismatches == [], mismatches[:5]


def test_join_methods_are_known_values(conn):
    seen = {r[0] for r in conn.execute("SELECT DISTINCT join_method FROM measures")}
    assert seen <= {"content", "content_categorical", None}, seen


def test_only_joined_measures_have_a_join_method(conn):
    bad = conn.execute(
        "SELECT COUNT(*) FROM measures "
        "WHERE (join_method IS NULL) != (bilingual_gap = 1)").fetchone()[0]
    assert bad == 0


def test_categorical_pairs_agree_on_ccofog_codes(conn):
    """CCOFOG codes are numeric and identical in both editions.

    Checked here on the categorical pairs specifically, because those were
    joined without using references or cost values - if the categorical
    signature were matching the wrong measures, the codes would diverge.
    """
    import re

    def codes(value):
        return set(re.findall(r"\b\d{2,5}(?:\.\d+)*\b", value or ""))

    rows = conn.execute(
        "SELECT name_en, ccofog_2014_code_en, ccofog_2014_code_fr FROM measures "
        "WHERE join_method='content_categorical'").fetchall()
    assert rows, "expected some categorical pairs"
    for name, en, fr in rows:
        assert codes(en) == codes(fr), name


def test_category_map_is_unambiguous(conn, built):
    """A French term maps to at most one English term.

    Terms that pair two ways in the evidence are excluded from the map and
    listed separately, never resolved by picking the commoner one.
    """
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    seen = {}
    for row in csv.DictReader(
            open(root / "data" / "finance_category_map.csv", encoding="utf-8")):
        key = (row["field"], row["term_fr"])
        assert key not in seen, key
        seen[key] = row["term_en"]


def test_french_dotted_labels_are_not_read_as_section_numbers():
    """Regression: the two failures from the first precision sample.

    "d) à d.6)" resolved to ITA section 6 and "c.1) [-c.4)]" to ITA section 4,
    because a French paragraph label written without its opening bracket was
    matched by the section pattern. Both were found by hand, not by any test
    here, which is the whole argument for the precision sample.
    """
    from portage.measure_refs import extract

    rows = extract("Loi de l'impôt sur le revenu, alinéas 149(1)(c) et d) à d.6)",
                   "fr", {})
    paths = [r["citation_path"] for r in rows]
    assert paths == ["149(1)(c)", "149(1)(d)", "149(1)(d.6)"], paths
    assert "6" not in paths

    rows = extract(
        "Loi de l'impôt sur le revenu, alinéas 81(1)(c.1) [-c.4)], paragraphe 81(6)",
        "fr", {})
    paths = [r["citation_path"] for r in rows]
    assert paths == ["81(1)(c.1)", "81(1)(c.4)", "81(6)"], paths
    assert "4" not in paths


def test_french_normalisation_leaves_no_unmatched_bracket(conn):
    """The normaliser's contract, checked over every French reference.

    A ")" with no unclosed "(" to its left is a bare label that has not been
    rewritten - and an unrewritten label is what the section pattern then
    misreads as a number. This is the general form of the two failures found by
    hand, and unlike a list of known-bad strings it catches the next variant
    too: "38a.2)" was still broken after the first fix and this found it.
    """
    from portage.measure_refs import normalise_french_labels

    offenders = []
    for (raw,) in conn.execute(
            "SELECT DISTINCT legal_reference_fr FROM measures "
            "WHERE legal_reference_fr IS NOT NULL"):
        normalised = normalise_french_labels(raw)
        depth = 0
        for ch in normalised:
            if ch == "(":
                depth += 1
            elif ch == ")":
                if depth == 0:
                    offenders.append(raw[:100])
                    break
                depth -= 1
    assert offenders == [], offenders[:5]


def test_english_and_french_agree_on_resolved_paths(conn):
    """A measure's two editions must cite the same provisions.

    The French mis-parse produced different path sets, which is why those
    measures fell out of the content join and were never covered by the
    pair-agreement test - they had become singles. Comparing the corpus as a
    whole closes that gap.
    """
    en = {r[0] for r in conn.execute(
        "SELECT citation_path FROM measure_references "
        "WHERE lang='en' AND status='resolved'")}
    fr = {r[0] for r in conn.execute(
        "SELECT citation_path FROM measure_references "
        "WHERE lang='fr' AND status='resolved'")}
    only_fr = sorted(fr - en)
    assert only_fr == [], (
        "paths resolved from French but never from English - the usual cause "
        "is a French label read as a section number: %s" % only_fr[:8])


def test_definition_of_term_in_a_bare_section_resolves():
    """"definition of X in section 248" -> 248"X".

    No reference in the 2026 edition uses this form; the rule exists so that an
    edition that does is not silently misread.
    """
    from portage.measure_refs import extract

    rows = extract(
        'Income Tax Act, definition of "taxable Canadian property" in section 248')
    paths = [r["citation_path"] for r in rows]
    assert '248"taxable Canadian property"' in paths, paths
