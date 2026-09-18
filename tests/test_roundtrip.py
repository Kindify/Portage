"""Acceptance test 1: the database reproduces the source text exactly.

CLAUDE.md allows "a documented, minimal whitespace normalization". None is
applied. The comparison is byte-for-byte on the raw text, because a test that
normalises is a test that cannot see certain classes of loss.
"""

from portage.parse import source_text

from conftest import ITA_EN


def test_roundtrip_is_exact(conn):
    rebuilt = "".join(
        r[0] for r in conn.execute(
            "SELECT COALESCE(text_en,'') FROM sections WHERE act='ITA' ORDER BY order_index"
        )
    )
    expected = source_text(ITA_EN)
    assert len(rebuilt) == len(expected), (
        "length differs by %d characters" % (len(rebuilt) - len(expected))
    )
    if rebuilt != expected:
        i = next(k for k, (a, b) in enumerate(zip(rebuilt, expected)) if a != b)
        raise AssertionError(
            "first divergence at character %d\n  database: %r\n  source  : %r"
            % (i, rebuilt[i - 100:i + 140], expected[i - 100:i + 140])
        )


def test_no_text_is_silently_dropped(conn):
    """Guards the failure mode that actually happened during session 2.

    The parser and the round-trip target once shared a blind spot - both skipped
    every <Label> - so the round-trip passed while the formula variable names
    were missing from the database. This checks the total against the raw XML by
    a third route that shares no code with either.
    """
    from lxml import etree

    from portage.parse import METADATA, OWNERS

    body = etree.parse(str(ITA_EN)).getroot().find("Body")
    all_text = len("".join(body.itertext()))
    in_columns = 0
    for tag in METADATA:
        for el in body.iter(tag):
            if any(a.tag in METADATA for a in el.iterancestors()):
                continue
            if el.getparent().tag in OWNERS:
                in_columns += len("".join(el.itertext()))

    stored = conn.execute(
        "SELECT SUM(LENGTH(COALESCE(text_en,''))) FROM sections WHERE act='ITA'"
    ).fetchone()[0]
    assert stored == all_text - in_columns
