import os
import tempfile
from pathlib import Path


MPLCONFIGDIR = Path(tempfile.gettempdir()) / "pypowhegparse-mplconfig"
MPLCONFIGDIR.mkdir(exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPLCONFIGDIR))
