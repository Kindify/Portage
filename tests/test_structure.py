"""Acceptance test 2: the structure holds together."""

import pytest


def test_citation_paths_are_unique(conn):
    dupes = conn.execute(
        "SELECT act, citation_path, COUNT(*) n FROM sections "
        "GROUP BY act, citation_path HAVING n > 1"
    ).fetchall()
    assert dupes == [], "duplicate paths: %s" % [tuple(r) for r in dupes[:10]]


def test_every_record_has_a_parent_except_top_level(conn):
    orphans = conn.execute(
        "SELECT citation_path, level, parent_path FROM sections "
        "WHERE parent_path IS NOT NULL AND parent_path != '' AND parent_id IS NULL"
    ).fetchall()
    assert orphans == [], "records whose parent_path does not resolve: %s" % [
        tuple(r) for r in orphans[:10]
    ]


def test_top_level_records_are_sections_or_headings(conn):
    rows = conn.execute(
        "SELECT DISTINCT level FROM sections WHERE parent_path IS NULL OR parent_path = ''"
    ).fetchall()
    assert sorted(r[0] for r in rows) == ["heading", "section"]


import pytest

ACTS = ["ITA", "ITR"]


def test_sections_appear_in_source_order(conn):
    """Section numbers run forwards through the Act.

    Legislative numbering is not decimal. A section numbered 18.21 was inserted
    after 18.2, so it comes *before* 18.3 - the suffix is a sequence, not a
    fraction. Likewise 60.011 precedes 60.02, which precedes 60.022. So the
    first component compares as an integer (9 before 10) and every later
    component compares as a string (\'2\' < \'21\' < \'3\').
    """
    paths = [
        r[0] for r in conn.execute(
            "SELECT citation_path FROM sections "
            "WHERE act='ITA' AND level='section' AND order_index IS NOT NULL "
            "ORDER BY order_index"
        )
    ]

    def key(p):
        parts = p.split(".")
        head = int(parts[0]) if parts[0].isdigit() else -1
        return (head,) + tuple(parts[1:])

    keys = [key(p) for p in paths]
    out_of_order = [
        (paths[i], paths[i + 1]) for i in range(len(keys) - 1) if keys[i] > keys[i + 1]
    ]
    assert out_of_order == [], "sections out of source order: %s" % out_of_order[:5]


@pytest.mark.parametrize("act,expected", [("ITA", 763), ("ITR", 499)])
def test_section_count_matches_the_enacted_body(conn, act, expected):
    """Sections in the <Body>, excluding Schedules.

    The Act's file contains 785 Section elements; the other 22 are inside
    Schedules - "RELATED PROVISIONS" and "AMENDMENTS NOT IN FORCE" - which are
    appended material rather than enacted text. The Regulations have ten
    Schedules, likewise excluded. See README, Known limits.
    """
    n = conn.execute(
        "SELECT COUNT(*) FROM sections WHERE act=? AND level='section'", (act,)
    ).fetchone()[0]
    assert n == expected


def test_addressable_records_carry_a_label(conn):
    """In at least one language. A French-only record has no English label."""
    missing = conn.execute(
        "SELECT citation_path, level FROM sections "
        "WHERE is_addressable=1 "
        "AND COALESCE(label_raw,'')='' AND COALESCE(label_raw_fr,'')=''"
    ).fetchall()
    assert missing == [], "addressable records with no label: %s" % [
        tuple(r) for r in missing[:10]
    ]


def test_fragments_are_not_addressable(conn):
    """A path containing '~' is a derived fragment key, never a citation."""
    bad = conn.execute(
        "SELECT citation_path FROM sections "
        "WHERE is_addressable=1 AND citation_path LIKE '%~c%'"
    ).fetchall()
    assert bad == []


def test_spot_check_samples_are_searchable(conn):
    """A checker must be able to find every sampled row on the official site.

    The first round of hand checks had to skip seven of eighty rows because the
    text was too short to search or was a bare repeal note. That wastes the
    checker's time and tempts a tired checker into marking them passed.
    """
    from portage.build import _is_checkable, _spot_check_sample

    for act in ("ITA", "ITR"):
        for lang in ("en", "fr"):
            sample = _spot_check_sample(conn, act, lang)
            assert sample, "%s %s produced no sample" % (act, lang)
            unusable = [r[0] for r in sample if not _is_checkable(r[3])]
            assert unusable == [], (
                "%s %s sampled rows a checker cannot verify: %s"
                % (act, lang, unusable))
