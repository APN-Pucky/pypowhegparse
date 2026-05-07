import pandas as pd
import pytest
import pytopdrawer as ptd

import pypowhegparse as pp

from tests._support import (
    PROCESS_DIRS,
    PROCESS_IDS,
    expected_top_names,
    parse_top_file_name,
    top_files,
)


@pytest.mark.parametrize("process_dir", PROCESS_DIRS, ids=PROCESS_IDS)
def test_load_top_folder_parses_all_grid_files(process_dir):
    files = top_files(process_dir)
    df = pp.load_top_folder(str(process_dir))

    assert files
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert df.index.nlevels == 3
    assert sorted(df.index.get_level_values(0).unique()) == expected_top_names(process_dir)
    assert sorted(df.index.get_level_values(1).unique()) == sorted(
        {parse_top_file_name(file_path)[1] for file_path in files}
    )
    assert df.columns.tolist() == ["pvalue", "chi2", "plot"]
    assert len(df) >= len(files)
    assert df["pvalue"].between(0, 1).all()
    assert df["chi2"].ge(0).all()


@pytest.mark.parametrize("process_dir", PROCESS_DIRS, ids=PROCESS_IDS)
def test_load_top_file_uses_run_number_from_file_name(process_dir):
    file_path = top_files(process_dir)[0]
    _, number = parse_top_file_name(file_path)
    df = pp.load_top_file(str(file_path))

    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert df.index.nlevels == 2
    assert df.index.get_level_values(0).unique().tolist() == [number]
    assert df.columns.tolist() == ["pvalue", "chi2", "plot"]


@pytest.mark.parametrize("process_dir", PROCESS_DIRS, ids=PROCESS_IDS)
def test_load_top_plot_returns_plot_metrics(process_dir):
    file_path = top_files(process_dir)[0]
    plot = next(iter(ptd.read(str(file_path))))
    df = pp.load_top_plot(plot)

    assert isinstance(df, pd.DataFrame)
    assert df.shape == (1, 3)
    assert df.columns.tolist() == ["pvalue", "chi2", "plot"]
    assert 0 <= df.iloc[0]["pvalue"] <= 1
    assert df.iloc[0]["chi2"] >= 0
    assert df.iloc[0]["plot"] is plot
