"""Anomalies are catalogued, not counted.

The build writes data/label_anomalies.csv. This compares it line by line with
the fixture committed in tests/fixtures/. Any difference fails, including one
that leaves the total unchanged - an anomaly moving from one provision to
another is exactly what a count would hide.

Changing the fixture is a deliberate commit with a stated reason. See
docs/decisions.md, "Anomalies are catalogued, never counted".
"""

import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "label_anomalies.csv"
BUILT = ROOT / "data" / "label_anomalies.csv"


def test_label_anomalies_match_the_fixture(built):
    assert FIXTURE.exists(), "fixture missing: %s" % FIXTURE
    expected = FIXTURE.read_text(encoding="utf-8").splitlines()
    actual = BUILT.read_text(encoding="utf-8").splitlines()

    if expected == actual:
        return

    only_new = [l for l in actual if l not in set(expected)]
    only_gone = [l for l in expected if l not in set(actual)]
    raise AssertionError(
        "label anomaly catalogue differs from the committed fixture.\n"
        "  %d new, %d gone (totals: fixture %d, build %d)\n"
        "  new:  %s\n  gone: %s\n"
        "If this change is intended, update tests/fixtures/label_anomalies.csv "
        "in its own commit and say why."
        % (len(only_new), len(only_gone), len(expected) - 1, len(actual) - 1,
           only_new[:5], only_gone[:5])
    )


def test_catalogue_is_deterministic(built, tmp_path):
    """A rebuild produces a byte-identical catalogue."""
    first = BUILT.read_bytes()
    from portage.build import build

    build(db_path=tmp_path / "again.sqlite")
    assert BUILT.read_bytes() == first
