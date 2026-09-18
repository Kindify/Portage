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
CATALOGUES = [
    "label_anomalies.csv",
    "definition_key_fallbacks.csv",
    "bilingual_gaps.csv",
    "alignment_unverified.csv",
    "definition_join_suspects.csv",
    "alignment_positional.csv",
]


@pytest.mark.parametrize("name", CATALOGUES)
def test_catalogue_matches_the_fixture(built, name):
    fixture = ROOT / "tests" / "fixtures" / name
    built_file = ROOT / "data" / name
    assert fixture.exists(), "fixture missing: %s" % fixture
    expected = fixture.read_text(encoding="utf-8").splitlines()
    actual = built_file.read_text(encoding="utf-8").splitlines()

    if expected == actual:
        return

    only_new = [l for l in actual if l not in set(expected)]
    only_gone = [l for l in expected if l not in set(actual)]
    raise AssertionError(
        "%s differs from the committed fixture.\n" % name +
        "  %d new, %d gone (totals: fixture %d, build %d)\n"
        "  new:  %s\n  gone: %s\n"
        "If this change is intended, update tests/fixtures/%s "
        "in its own commit and say why."
        % (len(only_new), len(only_gone), len(expected) - 1, len(actual) - 1,
           only_new[:5], only_gone[:5], name)
    )


def test_catalogues_are_deterministic(built, tmp_path):
    """A rebuild produces byte-identical catalogues."""
    first = {n: (ROOT / "data" / n).read_bytes() for n in CATALOGUES}
    from portage.build import build

    build(db_path=tmp_path / "again.sqlite")
    for name in CATALOGUES:
        assert (ROOT / "data" / name).read_bytes() == first[name], name
