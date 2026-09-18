import pathlib
import sqlite3

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
ITA_EN = ROOT / "data" / "ITA-eng.xml"
ITA_FR = ROOT / "data" / "ITA-fra.xml"
ITR_EN = ROOT / "data" / "ITR-eng.xml"
ITR_FR = ROOT / "data" / "ITR-fra.xml"

#: (act, language) -> source file. Every instrument in the build.
SOURCE_FILES = {
    ("ITA", "en"): ITA_EN,
    ("ITA", "fr"): ITA_FR,
    ("ITR", "en"): ITR_EN,
    ("ITR", "fr"): ITR_FR,
}


@pytest.fixture(scope="session")
def built(tmp_path_factory):
    """Build the database once for the whole test session."""
    if not all(f.exists() for f in SOURCE_FILES.values()):
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
