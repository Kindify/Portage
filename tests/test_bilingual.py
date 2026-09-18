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

    asserted = [
        r["citation_path"] for r in rows
        if not r["bilingual_gap"] and not r["alignment_unverified"]
    ]
    assert asserted == [], (
        "these paths under 51(1) are presented as verified bilingual pairs, but "
        "the two languages structure the provision differently: %s" % asserted
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


def test_unverified_flag_covers_divergent_parents(conn):
    """Every joined row under a divergent parent is flagged.

    Derived here straight from the two XML files rather than from the database,
    so it does not simply restate the build's own logic back to itself.
    """
    from collections import defaultdict

    from portage.parse import parse

    from conftest import ITA_EN, ITA_FR

    def children(path, addressable):
        recs, _ = parse(path, "ITA", "u")
        out = defaultdict(list)
        for r in recs:
            if bool(r["is_addressable"]) is addressable and r["parent_path"]:
                out[r["parent_path"]].append(r["citation_path"])
        return {k: tuple(v) for k, v in out.items()}

    expected = set()
    for addressable in (True, False):
        en = children(ITA_EN, addressable)
        fr = children(ITA_FR, addressable)
        for parent in set(en) & set(fr):
            if en[parent] != fr[parent]:
                expected |= set(en[parent]) & set(fr[parent])

    flagged = {
        r[0] for r in conn.execute(
            "SELECT citation_path FROM sections "
            "WHERE act='ITA' AND alignment_unverified=1"
        )
    }
    assert flagged == expected, (
        "flag does not match the divergence in the source files: "
        "%d missing, %d spurious"
        % (len(expected - flagged), len(flagged - expected))
    )


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


def test_definition_joins_are_symmetric(conn):
    """No joined definition may have the two files disagreeing about a term.

    Derived from the XML rather than from the build's own suspect list, so it
    does not restate the build's logic back to itself.
    """
    from portage.parse import parse

    from conftest import ITA_EN, ITA_FR

    en_recs, _ = parse(ITA_EN, "ITA", "u")
    fr_recs, _ = parse(ITA_FR, "ITA", "u")
    en = {r["citation_path"]: r for r in en_recs if r["level"] == "definition"}
    fr = {r["citation_path"]: r for r in fr_recs if r["level"] == "definition"}

    asymmetric = {
        p for p in set(en) & set(fr)
        if en[p]["defined_term_en"] != fr[p]["defined_term_en"]
        or en[p]["defined_term_fr"] != fr[p]["defined_term_fr"]
    }

    joined = {
        r[0] for r in conn.execute(
            "SELECT citation_path FROM sections WHERE act='ITA' AND level='definition' "
            "AND text_en IS NOT NULL AND text_fr IS NOT NULL"
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
        path = row["citation_path"]
        en = conn.execute(
            "SELECT text_en, text_fr FROM sections WHERE act='ITA' AND citation_path=?",
            (path,)).fetchone()
        fr = conn.execute(
            "SELECT text_en, text_fr FROM sections WHERE act='ITA' AND citation_path=?",
            (path + "~fr",)).fetchone()
        assert en is not None, "english record missing for %s" % path
        assert fr is not None, "french record missing for %s" % path
        assert en["text_en"] and not en["text_fr"], path
        assert fr["text_fr"] and not fr["text_en"], path
