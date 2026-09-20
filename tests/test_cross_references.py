"""Phase 1 step 1: tagged cross-references.

Only references the source marks up as elements are in this table. Nothing here
reads body text to decide anything, so these tests check completeness and
honest linkage rather than extraction quality.
"""

import pytest
from lxml import etree

from conftest import SOURCE_FILES

CASES = [(act, lang, xml) for (act, lang), xml in SOURCE_FILES.items()]
IDS = ["%s-%s" % (act, lang) for act, lang, _ in CASES]


@pytest.mark.parametrize("act,lang,xml", CASES, ids=IDS)
def test_every_tagged_element_becomes_exactly_one_row(conn, act, lang, xml):
    """No reference is dropped, and none is counted twice.

    An early version iterated per owned element, so a reference was counted
    once for every owned ancestor it had - 2,224 elements produced 7,755 rows.
    Counting straight from the XML is what caught it.
    """
    body = etree.parse(str(xml)).getroot().find("Body")
    for tag in ("XRefExternal", "DefinitionRef", "XRefInternal"):
        in_source = sum(1 for _ in body.iter(tag))
        in_db = conn.execute(
            "SELECT COUNT(*) FROM cross_references "
            "WHERE act=? AND lang=? AND ref_kind=?", (act, lang, tag)
        ).fetchone()[0]
        assert in_db == in_source, "%s %s %s" % (act, lang, tag)


def test_no_reference_dangles(conn):
    assert conn.execute(
        "SELECT COUNT(*) FROM cross_references WHERE from_id IS NULL"
    ).fetchone()[0] == 0, "references whose source provision is missing"
    assert conn.execute(
        "SELECT COUNT(*) FROM cross_references "
        "WHERE resolution='unique' AND to_id IS NULL"
    ).fetchone()[0] == 0, "resolved references whose target row is missing"


def test_resolution_states_are_internally_consistent(conn):
    """Each state must mean exactly what docs/reference-rule.md says."""
    checks = [
        ("resolution NOT IN ('unique','ambiguous','unresolved')",
         "unknown resolution state"),
        ("resolution='unique' AND to_citation_path IS NULL",
         "unique resolution with no target"),
        ("resolution='unique' AND candidate_count != 1",
         "unique resolution without exactly one candidate"),
        ("resolution='ambiguous' AND candidate_count < 2",
         "ambiguous resolution with fewer than two candidates"),
        ("resolution='ambiguous' AND to_citation_path IS NOT NULL",
         "ambiguous reference that picked a target anyway"),
        ("resolution='unresolved' AND candidate_count != 0",
         "unresolved reference that had candidates"),
        ("resolution!='unique' AND COALESCE(unresolved_reason,'')=''",
         "non-unique reference that does not say why"),
    ]
    for where, complaint in checks:
        n = conn.execute(
            "SELECT COUNT(*) FROM cross_references WHERE " + where).fetchone()[0]
        assert n == 0, "%s: %d rows" % (complaint, n)


def test_candidates_table_matches_the_counts(conn):
    """Every candidate is recorded, and the count on the reference agrees."""
    bad = conn.execute(
        """SELECT COUNT(*) FROM cross_references x
           WHERE x.candidate_count + x.candidate_count_other != (
               SELECT COUNT(*) FROM definition_ref_candidates c
               WHERE c.ref_id = x.id)""").fetchone()[0]
    assert bad == 0, "candidate counts disagree with definition_ref_candidates"

    orphan = conn.execute(
        """SELECT COUNT(*) FROM definition_ref_candidates c
           LEFT JOIN sections s ON s.id = c.definition_id
           WHERE s.id IS NULL""").fetchone()[0]
    assert orphan == 0, "candidate rows pointing at no section"


def test_ambiguity_is_never_broken_by_choosing(conn):
    """The governing principle: scope questions are not answered here."""
    n = conn.execute(
        "SELECT COUNT(*) FROM cross_references "
        "WHERE candidate_count > 1 AND to_citation_path IS NOT NULL"
    ).fetchone()[0]
    assert n == 0, (
        "%d references with several candidate definitions were resolved to one "
        "anyway - which definition governs at a location is a scope question "
        "this tool does not answer" % n)


def test_every_row_is_tagged_not_extracted(conn):
    """Phase 0's promise: nothing in this table came from reading prose."""
    kinds = {r[0] for r in conn.execute(
        "SELECT DISTINCT method FROM cross_references")}
    assert kinds == {"tagged"}


@pytest.mark.parametrize("act,lang,xml", CASES, ids=IDS)
def test_resolution_is_unique_or_it_is_not_resolution(conn, act, lang, xml):
    """A resolved DefinitionRef points at a term defined in exactly one place.

    The index is re-derived here from the XML rather than read back from the
    extractor, so this is a second opinion and not a restatement. It cannot use
    sections.defined_term_* : that column exists only on <Definition> rows and
    so cannot see terms defined inline in a provision's own text, and it also
    counts the ~fr half of a split pair as a separate site.
    """
    from portage.parse import parse_walker
    from portage.refs import candidate_index

    cur = conn.execute(
        "SELECT act, citation_path, level, defined_term_en, defined_term_fr, "
        "text_en, text_fr FROM sections WHERE act=?", (act,))
    columns = [d[0] for d in cur.description]
    records = [dict(zip(columns, r)) for r in cur.fetchall()]
    walker, _ = parse_walker(xml, act, "u")
    index = candidate_index(walker, records, lang)

    rows = conn.execute(
        "SELECT raw_text, to_citation_path FROM cross_references "
        "WHERE act=? AND lang=? AND ref_kind='DefinitionRef' "
        "AND resolution='unique'", (act, lang)).fetchall()
    assert rows, "expected some resolved definition references for %s %s" % (act, lang)
    for raw, target in rows:
        sites = index.get(" ".join(raw.split()), [])
        assert len(sites) == 1, (
            "%r resolved to %s but is defined in %d places: %s"
            % (raw, target, len(sites), sites[:5]))
        assert sites[0][0] == target


@pytest.mark.parametrize("act,lang,xml", CASES, ids=IDS)
def test_xrefinternal_is_still_absent(conn, act, lang, xml):
    """The source tags no provision-to-provision references.

    This is why the table cannot be a reference graph, and it is the whole
    reason pattern extraction is needed later. If Justice Canada ever starts
    tagging them, this test fails and the plan should change.
    """
    body = etree.parse(str(xml)).getroot().find("Body")
    n = sum(1 for _ in body.iter("XRefInternal"))
    expected = 1 if (act == "ITA" and lang == "fr") else 0
    assert n == expected, (
        "XRefInternal count changed for %s %s: found %d, expected %d. "
        "If the source now tags internal references, revisit PLAN.md."
        % (act, lang, n, expected))


def test_candidate_kinds_and_scopes_are_known_values(conn):
    kinds = {r[0] for r in conn.execute(
        "SELECT DISTINCT candidate_kind FROM definition_ref_candidates")}
    assert kinds <= {"definition_record", "inline_defined_term"}, kinds
    scopes = {r[0] for r in conn.execute(
        "SELECT DISTINCT candidate_scope FROM definition_ref_candidates")}
    assert scopes <= {"same_instrument", "other_instrument"}, scopes


def test_other_instrument_candidates_never_change_resolution(conn):
    """They are recorded so a reader can see them, and that is all.

    Which instrument's definition governs is a legal question, so a reference
    with no same-instrument candidate stays unresolved however many
    other-instrument candidates it has.
    """
    leaked = conn.execute(
        "SELECT COUNT(*) FROM cross_references "
        "WHERE candidate_count = 0 AND resolution != 'unresolved'"
    ).fetchone()[0]
    assert leaked == 0, (
        "%d references resolved with no same-instrument candidate" % leaked)

    # And the count columns must agree with the rows actually stored.
    for column, scope in (("candidate_count", "same_instrument"),
                          ("candidate_count_other", "other_instrument")):
        bad = conn.execute(
            """SELECT COUNT(*) FROM cross_references x
               WHERE x.%s != (
                   SELECT COUNT(*) FROM definition_ref_candidates c
                   WHERE c.ref_id = x.id AND c.candidate_scope = ?)"""
            % column, (scope,)).fetchone()[0]
        assert bad == 0, "%s disagrees with the candidates table" % column


def test_other_instrument_candidates_point_at_the_other_instrument(conn):
    bad = conn.execute(
        """SELECT COUNT(*) FROM cross_references x
           JOIN definition_ref_candidates c ON c.ref_id = x.id
           WHERE c.candidate_scope = 'other_instrument' AND c.act = x.act"""
    ).fetchone()[0]
    assert bad == 0


@pytest.mark.parametrize("act,lang,xml", CASES, ids=IDS)
def test_inline_candidates_are_found_by_nesting_not_by_prose(conn, act, lang, xml):
    """An inline definition site is a DefinedTerm element outside <Definition>.

    Re-derived from the XML by that structural test alone. If the extractor ever
    started looking for "means" or any other wording, its inline sites would no
    longer match this set.
    """
    from portage.parse import parse_walker
    from portage.refs import inline_term_index

    walker, _ = parse_walker(xml, act, "u")
    expected = {p for sites in inline_term_index(walker, lang).values()
                for p, _kind in sites}

    stored = {r[0] for r in conn.execute(
        """SELECT DISTINCT c.citation_path FROM definition_ref_candidates c
           JOIN cross_references x ON x.id = c.ref_id
           WHERE x.act=? AND x.lang=? AND c.candidate_kind='inline_defined_term'
             AND c.candidate_scope='same_instrument'""", (act, lang))}
    assert stored <= expected, sorted(stored - expected)[:5]


def test_bare_section_number_never_resolves(conn):
    """Phase 1 reference-grammar fixture: ITA French 93(5.2)(a).

    The only XRefInternal in the corpus. Its text is "51", and the prose around
    it reads "l'article 51 de la Loi de 2012 apportant des modifications
    techniques" - section 51 of a *different* Act. A bare section number with no
    instrument qualifier must never resolve, here or in the reference grammar
    Phase 1 will write for the tax expenditure report.
    """
    row = conn.execute(
        "SELECT raw_text, resolution, to_citation_path, unresolved_reason "
        "FROM cross_references "
        "WHERE act='ITA' AND lang='fr' AND from_citation_path='93(5.2)(a)' "
        "AND ref_kind='XRefInternal'").fetchone()
    assert row is not None, "the XRefInternal fixture has gone missing"
    assert row["raw_text"] == "51"
    assert row["resolution"] == "unresolved"
    assert row["to_citation_path"] is None, (
        "a bare section number with no instrument qualifier resolved to %s - "
        "it means section 51 of another Act entirely" % row["to_citation_path"])
    assert "no instrument qualifier" in (row["unresolved_reason"] or "")
