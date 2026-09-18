import pathlib
import sqlite3

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
ITA_EN = ROOT / "data" / "ITA-eng.xml"


@pytest.fixture(scope="session")
def built(tmp_path_factory):
    """Build the database once for the whole test session."""
    if not ITA_EN.exists():
        pytest.skip("source XML not present in data/ - see README Setup")
    from portage.build import build

    db = tmp_path_factory.mktemp("build") / "portage.sqlite"
    build(db_path=db)
    return db


@pytest.fixture(scope="session")
def conn(built):
    c = sqlite3.connect(built)
    c.row_factory = sqlite3.Row
    yield c
    c.close()
