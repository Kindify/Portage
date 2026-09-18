"""Acceptance test 1: the database reproduces both source texts exactly.

CLAUDE.md allows "a documented, minimal whitespace normalization". None is
applied, in either language. The comparison is byte-for-byte, because a test
that normalises is a test that cannot see certain classes of loss.
"""

import pytest

from portage.parse import source_text

from conftest import ITA_EN, ITA_FR


@pytest.mark.parametrize(
    "col,order,xml",
    [("text_en", "order_index", ITA_EN), ("text_fr", "order_index_fr", ITA_FR)],
    ids=["english", "french"],
)
def test_roundtrip_is_exact(conn, col, order, xml):
    rebuilt = "".join(
        r[0] for r in conn.execute(
            "SELECT COALESCE(%s,'') FROM sections "
            "WHERE act='ITA' AND %s IS NOT NULL ORDER BY %s" % (col, order, order)
        )
    )
    expected = source_text(xml)
    assert len(rebuilt) == len(expected), (
        "length differs by %d characters" % (len(rebuilt) - len(expected))
    )
    if rebuilt != expected:
        i = next(k for k, (a, b) in enumerate(zip(rebuilt, expected)) if a != b)
        raise AssertionError(
            "first divergence at character %d\n  database: %r\n  source  : %r"
            % (i, rebuilt[i - 100:i + 140], expected[i - 100:i + 140])
        )


@pytest.mark.parametrize("xml,col", [(ITA_EN, "text_en"), (ITA_FR, "text_fr")],
                         ids=["english", "french"])
def test_no_text_is_silently_dropped(conn, xml, col):
    """Guards the failure mode that actually happened in session 2.

    The parser and the round-trip target once shared a blind spot - both skipped
    every <Label> - so the round-trip passed while the formula variable names
    were missing. This checks the total against the raw XML by a third route
    that shares no code with either.
    """
    from lxml import etree

    from portage.parse import METADATA, OWNERS

    body = etree.parse(str(xml)).getroot().find("Body")
    all_text = len("".join(body.itertext()))
    in_columns = 0
    for tag in METADATA:
        for el in body.iter(tag):
            if any(a.tag in METADATA for a in el.iterancestors()):
                continue
            if el.getparent().tag in OWNERS:
                in_columns += len("".join(el.itertext()))

    stored = conn.execute(
        "SELECT SUM(LENGTH(COALESCE(%s,''))) FROM sections WHERE act='ITA'" % col
    ).fetchone()[0]
    assert stored == all_text - in_columns
