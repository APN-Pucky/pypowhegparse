import pytest
import pandas as pd
from pathlib import Path

import pypowhegparse as pp

TESTS_DIR = Path(__file__).parent
PROCESS_DIRS = [
    TESTS_DIR / "directphoton",
    TESTS_DIR / "directphotonjj",
    TESTS_DIR / "Zj",
    TESTS_DIR / "Z2jet",
]
PROCESS_IDS = [d.name for d in PROCESS_DIRS]


@pytest.mark.parametrize("folder", PROCESS_DIRS, ids=PROCESS_IDS)
def test_load_counter_folder(folder):
    df = pp.load_counter_folder(str(folder))
    assert isinstance(df, pd.DataFrame)
    assert not df.empty


@pytest.mark.parametrize("folder", PROCESS_DIRS, ids=PROCESS_IDS)
def test_load_stat_folder(folder):
    df = pp.load_stat_folder(str(folder))
    assert isinstance(df, pd.DataFrame)
    assert not df.empty


@pytest.mark.parametrize("folder", PROCESS_DIRS, ids=PROCESS_IDS)
def test_load_top_folder(folder):
    df = pp.load_top_folder(str(folder))
    assert isinstance(df, pd.DataFrame)
    assert not df.empty


@pytest.mark.parametrize("folder", PROCESS_DIRS, ids=PROCESS_IDS)
def test_count_warn(folder):
    count = pp.count_warn(str(folder))
    assert isinstance(count, int)
    assert count >= 0
