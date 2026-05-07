import pandas as pd
import pytest

import pypowhegparse as pp

from tests._support import (
    PROCESS_DIRS,
    PROCESS_IDS,
    expected_stat_names,
    parse_stat_file_name,
    stat_files,
)


@pytest.mark.parametrize("process_dir", PROCESS_DIRS, ids=PROCESS_IDS)
def test_load_stat_folder_parses_all_stat_files(process_dir):
    files = stat_files(process_dir)
    df = pp.load_stat_folder(str(process_dir))

    assert files
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert df.index.nlevels == 2
    assert len(df) == len(files)
    assert sorted(df.index.get_level_values(0).unique()) == expected_stat_names(process_dir)
    assert sorted(df.index.get_level_values(1).unique()) == sorted(
        {parse_stat_file_name(file_path)[1] for file_path in files}
    )
    assert any(column.strip() == "negative weight fraction:" for column in df.columns)
    assert any(column.endswith("+-stat") for column in df.columns)


@pytest.mark.parametrize("process_dir", PROCESS_DIRS, ids=PROCESS_IDS)
def test_load_stat_file_uses_run_number_from_file_name(process_dir):
    file_path = stat_files(process_dir)[0]
    _, number = parse_stat_file_name(file_path)
    df = pp.load_stat_file(str(file_path))

    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert df.index.tolist() == [number]
    assert any(column.strip() == "negative weight fraction:" for column in df.columns)
