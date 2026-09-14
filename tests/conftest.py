import sys
from pathlib import Path

# Allow `import config`, `import database`, etc. when pytest is run from
# the project root (standard layout, no src/ package).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from database import Database

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> bytes:
    return (FIXTURES_DIR / name).read_bytes()


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "news.db")
