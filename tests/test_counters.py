import pandas as pd
import pytest

import pypowhegparse as pp

from tests._support import (
    PROCESS_DIRS,
    PROCESS_IDS,
    counter_files,
    expected_counter_names,
    parse_counter_file_name,
)


@pytest.mark.parametrize("process_dir", PROCESS_DIRS, ids=PROCESS_IDS)
def test_load_counter_folder_parses_all_counter_files(process_dir):
    files = counter_files(process_dir)
    df = pp.load_counter_folder(str(process_dir))

    assert files
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert df.index.nlevels == 2
    assert len(df) == len(files)
    assert sorted(df.index.get_level_values(0).unique()) == expected_counter_names(process_dir)
    assert sorted(df.index.get_level_values(1).unique()) == sorted(
        {parse_counter_file_name(file_path)[1] for file_path in files}
    )
    assert "setrandom time (sec)" in df.columns


@pytest.mark.parametrize("process_dir", PROCESS_DIRS, ids=PROCESS_IDS)
def test_load_counter_file_uses_run_number_from_file_name(process_dir):
    file_path = counter_files(process_dir)[0]
    _, number = parse_counter_file_name(file_path)
    df = pp.load_counter_file(str(file_path))

    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert df.index.tolist() == [number]
    assert "setrandom time (sec)" in df.columns
