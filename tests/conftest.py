import os
import tempfile
from pathlib import Path

import pytest


MPLCONFIGDIR = Path(tempfile.gettempdir()) / "pypowhegparse-mplconfig"
MPLCONFIGDIR.mkdir(exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPLCONFIGDIR))


@pytest.fixture(autouse=True)
def _clear_no_color(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
