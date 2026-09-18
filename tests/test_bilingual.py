import pytest

"""Bilingual joining: never forced, and never silently asserted.

Session 1 established that English and French genuinely structure some
provisions differently. These tests check that the build represents that
honestly rather than pairing text by position or by a shared label alone.
"""


def test_51_1_is_not_paired_across_the_divergence(conn):
    """ITA 51(1) is the reference case.

    English lists eight paragraphs, (a) to (f); French lists six, a) to d), and
    the contents are offset rather than relettered - English (a) is one of the
    opening conditions, French a) is one of the rules. Nothing under 51(1) may
    be presented as a verified translation pair.
    """
    rows = conn.execute(
        "SELECT citation_path, bilingual_gap, alignment_unverified FROM sections "
        "WHERE act='ITA' AND parent_path='51(1)' AND level='paragraph'"
    ).fetchall()
    assert rows, "no paragraphs found under 51(1)"

    both = [
        r["citation_path"] for r in conn.execute(
            "SELECT citation_path FROM sections WHERE act='ITA' "
            "AND parent_path LIKE '51(1)%' AND level='paragraph' "
            "AND text_en IS NOT NULL AND text_fr IS NOT NULL")
    ]
    assert both == [], (
        "51(1)(a) to (d) must never carry text_en and text_fr on the same row - "
        "English (a) is a condition, French a) is a rule: %s" % both
    )

    paths = {r["citation_path"] for r in rows}
    for english_only in ("51(1)(d.1)", "51(1)(d.2)", "51(1)(e)", "51(1)(f)"):
        assert english_only in paths
    for french_only in ("51(1)(b.1)", "51(1)(b.2)"):
        assert french_only in paths


def test_gaps_have_exactly_one_language(conn):
    bad = conn.execute(
        "SELECT citation_path FROM sections WHERE bilingual_gap=1 "
        "AND text_en IS NOT NULL AND text_fr IS NOT NULL"
    ).fetchall()
    assert bad == [], "rows flagged as gaps that in fact have both languages"


def test_single_language_rows_are_flagged(conn):
    missed = conn.execute(
        "SELECT citation_path FROM sections WHERE bilingual_gap=0 "
        "AND (text_en IS NULL OR text_fr IS NULL)"
    ).fetchall()
    assert missed == [], "single-language rows not flagged: %s" % [
        r[0] for r in missed[:10]
    ]


def _divergence_from_source(act="ITA"):
    """Derive the divergent paths straight from the two XML files.

    Independent of the build, so these tests do not restate the build's own
    logic back to itself.
    """
    from collections import defaultdict

    from portage.parse import parse

    from conftest import SOURCE_FILES

    def children(path, addressable):
        recs, _ = parse(path, act, "u")
        out = defaultdict(list)
        for r in recs:
            if bool(r["is_addressable"]) is not addressable or not r["parent_path"]:
                continue
            if r["level"] == "definition":
                continue  # keyed by term, not position
            out[r["parent_path"]].append(r["citation_path"])
        return {k: tuple(v) for k, v in out.items()}

    result = {}
    for addressable in (True, False):
        en = children(SOURCE_FILES[(act, "en")], addressable)
        fr = children(SOURCE_FILES[(act, "fr")], addressable)
        suspect = set()
        for parent in set(en) & set(fr):
            if en[parent] != fr[parent]:
                suspect |= set(en[parent]) & set(fr[parent])
        result["split" if addressable else "flagged"] = suspect
    return result


@pytest.mark.parametrize("act", ["ITA", "ITR"])
def test_divergent_addressable_rows_are_split(conn, act):
    """Each language stands alone, with a pointer to its counterpart."""
    expected = _divergence_from_source(act)["split"]
    assert expected, "expected some divergent addressable paths"

    for path in sorted(expected):
        en = conn.execute(
            "SELECT text_en, text_fr, same_path_counterpart FROM sections "
            "WHERE act=? AND citation_path=?", (act, path)).fetchone()
        fr = conn.execute(
            "SELECT text_en, text_fr, same_path_counterpart FROM sections "
            "WHERE act=? AND citation_path=?", (act, path + "~fr")).fetchone()
        assert en is not None and fr is not None, path
        assert not (en["text_en"] and en["text_fr"]), (
            "%s carries both languages on one row" % path)
        assert not (fr["text_en"] and fr["text_fr"]), path
        assert en["same_path_counterpart"] == path + "~fr", path
        assert fr["same_path_counterpart"] == path, path


@pytest.mark.parametrize("act", ["ITA", "ITR"])
def test_only_fragments_keep_the_unverified_flag(conn, act):
    div = _divergence_from_source(act)
    flagged = {
        r[0] for r in conn.execute(
            "SELECT citation_path FROM sections "
            "WHERE act=? AND alignment_unverified=1", (act,))
    }
    assert flagged == div["flagged"], (
        "flag should cover exactly the divergent fragments: %d missing, %d spurious"
        % (len(div["flagged"] - flagged), len(flagged - div["flagged"])))
    addressable = conn.execute(
        "SELECT COUNT(*) FROM sections "
        "WHERE act=? AND alignment_unverified=1 AND is_addressable=1", (act,)
    ).fetchone()[0]
    assert addressable == 0, "addressable rows should be split, not flagged"


def test_definitions_are_keyed_by_term_not_position(conn):
    """248(1) definition 1 is a different definition in each file.

    So a positional key would mis-pair them. The term-based key must put
    "active business" on the same row in both languages.
    """
    row = conn.execute(
        "SELECT text_en, text_fr, defined_term_en, defined_term_fr FROM sections "
        "WHERE act='ITA' AND citation_path='248(1)\"active business\"'"
    ).fetchone()
    assert row is not None, "248(1) \"active business\" has no record"
    assert row["defined_term_en"] == "active business"
    assert row["text_en"] and row["text_fr"], "should carry both languages"
    assert "entreprise exploitée activement" in (row["defined_term_fr"] or "")


@pytest.mark.parametrize("act", ["ITA", "ITR"])
def test_definition_joins_are_symmetric(conn, act):
    """No joined definition may have the two files disagreeing about a term.

    Derived from the XML rather than from the build's own suspect list, so it
    does not restate the build's logic back to itself.
    """
    from portage.parse import parse

    from conftest import ITA_EN, ITA_FR

    from conftest import SOURCE_FILES

    en_recs, _ = parse(SOURCE_FILES[(act, "en")], act, "u")
    fr_recs, _ = parse(SOURCE_FILES[(act, "fr")], act, "u")
    en = {r["citation_path"]: r for r in en_recs if r["level"] == "definition"}
    fr = {r["citation_path"]: r for r in fr_recs if r["level"] == "definition"}

    asymmetric = {
        p for p in set(en) & set(fr)
        if en[p]["defined_term_en"] != fr[p]["defined_term_en"]
        or en[p]["defined_term_fr"] != fr[p]["defined_term_fr"]
    }

    joined = {
        r[0] for r in conn.execute(
            "SELECT citation_path FROM sections WHERE act=? AND level='definition' "
            "AND text_en IS NOT NULL AND text_fr IS NOT NULL", (act,)
        )
    }
    leaked = joined & asymmetric
    assert leaked == set(), (
        "definitions joined although the two files disagree about a term: %s"
        % sorted(leaked)[:5]
    )


def test_join_suspects_are_split_not_dropped(conn):
    """Every unjoined suspect keeps both records - nothing is lost."""
    import csv
    import pathlib

    root = pathlib.Path(__file__).resolve().parent.parent
    rows = list(csv.DictReader(
        open(root / "data" / "definition_join_suspects.csv", encoding="utf-8")))
    assert rows, "expected some suspects"
    for row in rows:
        act, path = row["act"], row["citation_path"]
        en = conn.execute(
            "SELECT text_en, text_fr FROM sections WHERE act=? AND citation_path=?",
            (act, path)).fetchone()
        fr = conn.execute(
            "SELECT text_en, text_fr FROM sections WHERE act=? AND citation_path=?",
            (act, path + "~fr")).fetchone()
        assert en is not None, "english record missing for %s" % path
        assert fr is not None, "french record missing for %s" % path
        assert en["text_en"] and not en["text_fr"], path
        assert fr["text_fr"] and not fr["text_en"], path


def test_every_row_has_an_alignment_status(conn):
    missing = conn.execute(
        "SELECT COUNT(*) FROM sections WHERE alignment IS NULL").fetchone()[0]
    assert missing == 0


def test_alignment_status_agrees_with_the_data(conn):
    """The status must describe what is actually on the row."""
    both = "text_en IS NOT NULL AND text_fr IS NOT NULL"
    bad = conn.execute(
        "SELECT COUNT(*) FROM sections WHERE alignment='single' AND " + both
    ).fetchone()[0]
    assert bad == 0, "rows marked single that carry both languages"

    bad = conn.execute(
        "SELECT COUNT(*) FROM sections WHERE alignment IN "
        "('verified','positional','unverified') AND NOT (" + both + ")"
    ).fetchone()[0]
    assert bad == 0, "rows marked as joined that do not carry both languages"

    bad = conn.execute(
        "SELECT COUNT(*) FROM sections WHERE alignment='split' "
        "AND same_path_counterpart IS NULL").fetchone()[0]
    assert bad == 0, "split rows must point at their counterpart"


def test_positional_rows_are_exactly_the_ordinal_keyed_joins(conn):
    """'positional' means joined on a key this project invented.

    A verified row must never be one whose path ends in an ordinal we assigned,
    and a positional row must always be one - otherwise the status is telling a
    reader something the key does not support.
    """
    from portage.build import ORDINAL_KEYS

    like = " OR ".join("citation_path LIKE '%" + k + "%'" for k in ORDINAL_KEYS)
    leaked = conn.execute(
        "SELECT citation_path FROM sections WHERE alignment='verified' AND ("
        + like + ")").fetchall()
    assert leaked == [], (
        "rows called verified although they are joined on an ordinal we "
        "assigned: %s" % [r[0] for r in leaked[:5]])

    wrong = conn.execute(
        "SELECT citation_path FROM sections WHERE alignment='positional' AND NOT ("
        + like + ")").fetchall()
    assert wrong == [], [r[0] for r in wrong[:5]]


def test_definitions_are_never_positional_when_they_have_a_term(conn):
    """A definition with a real term is keyed by it, not by position."""
    bad = conn.execute(
        "SELECT citation_path FROM sections WHERE level='definition' "
        "AND alignment='positional' AND defined_term_en IS NOT NULL "
        "AND citation_path NOT LIKE '%~d%'").fetchall()
    assert bad == [], [r[0] for r in bad[:5]]
