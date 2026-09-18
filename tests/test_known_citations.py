"""Acceptance test 3: known citations resolve to the right text.

The fixtures are the ones listed in CLAUDE.md. Only the English ones apply in
session 2.

A provision's text includes the text of everything nested inside it - its
paragraphs, and the unlabelled Definition records that make up a definitions
subsection like 248(1). `subtree_text` is what a reader means by "the text of
248(1)", so that is what these assertions read.
"""

import pytest


def subtree_text(conn, path, act="ITA"):
    row = conn.execute(
        "SELECT id, order_index FROM sections WHERE act=? AND citation_path=?",
        (act, path),
    ).fetchone()
    assert row is not None, "no record for %s" % path
    ids = {row["id"]}
    frontier = [row["id"]]
    while frontier:
        q = ",".join("?" * len(frontier))
        kids = [
            r[0] for r in conn.execute(
                "SELECT id FROM sections WHERE parent_id IN (%s)" % q, frontier
            )
        ]
        kids = [k for k in kids if k not in ids]
        ids.update(kids)
        frontier = kids
    q = ",".join("?" * len(ids))
    rows = conn.execute(
        "SELECT COALESCE(text_en,'') FROM sections WHERE id IN (%s) ORDER BY order_index" % q,
        list(ids),
    )
    return "".join(r[0] for r in rows)


@pytest.mark.parametrize(
    "path,needle",
    [
        ("245(1)", "tax benefit"),
        ("125(7)", "active business carried on by a corporation"),
        ("248(1)", "active business"),
        ("95(1)", "active business"),
        ("118.02(2)", "before 2025"),
        ("127.44(1)", "2040"),
    ],
)
def test_citation_contains(conn, path, needle):
    assert needle in subtree_text(conn, path), "%r not found in %s" % (needle, path)


def test_87_4_is_its_own_record_under_87(conn):
    row = conn.execute(
        "SELECT parent_path, level, heading_en FROM sections "
        "WHERE act='ITA' AND citation_path='87(4)'"
    ).fetchone()
    assert row is not None, "87(4) has no record"
    assert row["parent_path"] == "87"
    assert row["level"] == "subsection"
    assert row["heading_en"] == "Shares of predecessor corporation"


def test_55_3_b_is_its_own_record_under_55_3(conn):
    row = conn.execute(
        "SELECT parent_path, level FROM sections "
        "WHERE act='ITA' AND citation_path='55(3)(b)'"
    ).fetchone()
    assert row is not None, "55(3)(b) has no record"
    assert row["parent_path"] == "55(3)"
    assert row["level"] == "paragraph"
