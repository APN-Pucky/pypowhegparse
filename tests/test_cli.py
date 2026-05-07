from pathlib import Path

try:
    import pypowhegparse.cli as cli
except ModuleNotFoundError:
    import pypowhegparse.pypowhegoverview as cli


def test_cli_prints_default_overview_without_top_plots(capsys):
    exit_code = cli.main(["tests/Z2jet", "--no-top-plots"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "POWHEG Overview: tests/Z2jet" in captured.out
    assert "Checklimits Summary" in captured.out
    assert "check" in captured.out
    assert "\x1b[33m⚠ WARN\x1b[0m  WWWWARN" not in captured.out
    assert "WWWWWARN" in captured.out
    assert "\x1b[31m✗ FAIL\x1b[0m" not in captured.out
    assert "Counter Summary" in captured.out
    assert "Stat Summary" in captured.out
    assert "[pwgcounters-st1]" in captured.out
    assert "        setrandom time (sec):" in captured.out
    assert "\x1b[33m⚠ WARN\x1b[0m  negative weight fraction:" in captured.out
    assert "pwgcounters-st1 count" not in captured.out
    assert "Top Summary" not in captured.out


def test_cli_renders_selected_terminal_top_plots(capsys):
    exit_code = cli.main(["tests/Z2jet", "--top-limit", "1", "--top-pvalue-max", "1"])
    captured = capsys.readouterr()
    lines = captured.out.splitlines()

    assert exit_code == 1
    assert "Relevant Top Plots" in captured.out
    assert "top_file  run" not in captured.out
    assert "dim=" in captured.out
    assert "┌" in captured.out
    assert (
        "\x1b[31m✗ FAIL\x1b[0m  [pwg-rmngrid run 1 | dim=          10 | pvalue="
        in captured.out
    )
    assert any(
        line.startswith("\x1b[31m✗ FAIL\x1b[0m  ") and "┌" in line for line in lines
    )


def test_cli_relevant_top_plots_use_first_run_and_all_dimensions_for_selected_files():
    args = cli.build_parser().parse_args(
        ["tests/Z2jet", "--top-limit", "1", "--top-pvalue-max", "1"]
    )
    top_df = cli.load_top_folder("tests/Z2jet")
    selected = cli._select_relevant_top_plots(top_df, args)

    first_runs = {}
    for top_file, run, plot_title in top_df.index:
        key = (top_file, str(plot_title).strip())
        first_runs.setdefault(key, run)

    assert selected["top_file"].nunique() == 1
    assert not selected[["top_file", "plot_title"]].duplicated().any()
    for row in selected.itertuples(index=False):
        assert row.run == first_runs[(row.top_file, row.plot_title)]

    selected_top_file = selected["top_file"].iloc[0]
    representative_titles = [
        plot_title
        for top_file, run, plot_title in top_df.index
        if top_file == selected_top_file
        and run == first_runs[(top_file, str(plot_title).strip())]
    ]
    assert selected["plot_title"].tolist() == [
        str(plot_title).strip() for plot_title in representative_titles
    ]


def test_cli_strict_mode_reports_non_zero_for_detected_failures(capsys):
    exit_code = cli.main(
        [
            "tests/directphoton",
            "--no-top-plots",
            "--strict",
            "--warn-threshold",
            "0",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "\x1b[31m✗ FAIL\x1b[0m  colour check failures" in captured.out
    assert "\x1b[31m✗ FAIL\x1b[0m  spin-correlation failures" in captured.out


def test_cli_warns_on_wwwwarn_and_returns_nonzero_without_strict(capsys):
    exit_code = cli.main(["tests/directphoton", "--no-top-plots"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "\x1b[33m⚠ WARN\x1b[0m  WWWWARN" in captured.out
    assert "\x1b[31m✗ FAIL\x1b[0m  WWWWWARN" in captured.out


def test_cli_warns_on_nan_exception_in_counter_summary(capsys):
    exit_code = cli.main(["tests/Zj", "--no-top-plots"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "\x1b[33m⚠ WARN\x1b[0m  NaN exception:" in captured.out
    assert "50+-35.3553" in captured.out


def test_cli_no_color_flag_disables_ansi_but_keeps_symbols(capsys):
    exit_code = cli.main(["tests/directphoton", "--no-top-plots", "--no-color"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "\x1b[" not in captured.out
    assert "✗ FAIL" in captured.out


def test_cli_no_color_env_var_disables_ansi(monkeypatch, capsys):
    monkeypatch.setenv("NO_COLOR", "1")

    exit_code = cli.main(["tests/directphoton", "--no-top-plots"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "\x1b[" not in captured.out
    assert "✗ FAIL" in captured.out


def test_summary_formatter_marks_failures_and_warnings():
    df = cli.pd.DataFrame(
        {
            "negative weight fraction:": [0.6, 0.7],
            "btilde cross section estimate:": [10.0, 10.0],
            "btilde cross section error estimate:": [12.0, 12.0],
            "NaN exception": [1.0, 0.0],
        },
        index=cli.pd.MultiIndex.from_tuples(
            [("group", 1), ("group", 2)],
            names=["proc", "run"],
        ),
    )

    summary, warning_count, failure_count = cli._mean_std_summary(df)

    assert warning_count == 1
    assert failure_count == 2
    assert "\x1b[31m✗ FAIL\x1b[0m  negative weight fraction:" in summary
    assert "0.65+-0.0707107" in summary
    assert "\x1b[31m✗ FAIL\x1b[0m  btilde cross section error estimate:" in summary
    assert "12+-0" in summary
    assert "\x1b[33m⚠ WARN\x1b[0m  NaN exception:" in summary
    assert "0.5+-0.707107" in summary


def test_summary_formatter_marks_large_relative_stat_values():
    df = cli.pd.DataFrame(
        {
            "signal": [10.0, 10.0],
            "signal+-stat": [6.0, 6.0],
            "background": [10.0, 10.0],
            "background+-stat": [12.0, 12.0],
        },
        index=cli.pd.MultiIndex.from_tuples(
            [("group", 1), ("group", 2)],
            names=["proc", "run"],
        ),
    )

    summary, warning_count, failure_count = cli._mean_std_summary(df)

    assert warning_count == 1
    assert failure_count == 1
    assert "\x1b[33m⚠ WARN\x1b[0m  signal+-stat:" in summary
    assert "\x1b[31m✗ FAIL\x1b[0m  background+-stat:" in summary


def test_stat_relative_thresholds_are_adjustable():
    df = cli.pd.DataFrame(
        {
            "signal": [10.0, 10.0],
            "signal+-stat": [6.0, 6.0],
        },
        index=cli.pd.MultiIndex.from_tuples(
            [("group", 1), ("group", 2)],
            names=["proc", "run"],
        ),
    )
    args = cli.build_parser().parse_args(
        [
            "--stat-relative-warn",
            "0.7",
            "--stat-relative-fail",
            "1.2",
        ]
    )

    summary, warning_count, failure_count = cli._mean_std_summary(df, args)

    assert warning_count == 0
    assert failure_count == 0
    assert "\x1b[33m⚠ WARN\x1b[0m" not in summary
    assert "\x1b[31m✗ FAIL\x1b[0m" not in summary


def test_negative_weight_fraction_thresholds_are_adjustable():
    df = cli.pd.DataFrame(
        {
            "negative weight fraction:": [0.2, 0.2],
        },
        index=cli.pd.MultiIndex.from_tuples(
            [("group", 1), ("group", 2)],
            names=["proc", "run"],
        ),
    )
    args = cli.build_parser().parse_args(
        [
            "--negative-weight-fraction-warn",
            "0.3",
            "--negative-weight-fraction-fail",
            "0.6",
        ]
    )

    summary, warning_count, failure_count = cli._mean_std_summary(df, args)

    assert warning_count == 0
    assert failure_count == 0
    assert "\x1b[33m⚠ WARN\x1b[0m" not in summary
    assert "\x1b[31m✗ FAIL\x1b[0m" not in summary


def test_summary_formatter_aligns_value_column():
    df = cli.pd.DataFrame(
        {
            "short": [1.0, 3.0],
            "much longer label": [2.0, 4.0],
        },
        index=cli.pd.MultiIndex.from_tuples(
            [("group", 1), ("group", 2)],
            names=["proc", "run"],
        ),
    )

    summary, warning_count, failure_count = cli._mean_std_summary(df)
    metric_lines = [line for line in summary.splitlines() if ":" in line]

    assert warning_count == 0
    assert failure_count == 0
    assert len(metric_lines) == 2
    value_columns = [
        line.index("2+-") if "2+-" in line else line.index("3+-")
        for line in metric_lines
    ]
    assert value_columns[0] == value_columns[1]


def test_top_plot_status_thresholds_are_adjustable():
    args = cli.build_parser().parse_args(
        [
            "--top-warn-pvalue-max",
            "0.2",
            "--top-fail-pvalue-max",
            "0.01",
            "--top-warn-chi2-min",
            "2",
            "--top-fail-chi2-min",
            "6",
        ]
    )
    ok_row = cli.pd.Series({"pvalue": 0.3, "chi2": 1.0})
    warn_row = cli.pd.Series({"pvalue": 0.15, "chi2": 1.0})
    fail_row = cli.pd.Series({"pvalue": 0.02, "chi2": 8.0})

    assert cli._top_plot_status(ok_row, args) == "ok"
    assert cli._top_plot_status(warn_row, args) == "warn"
    assert cli._top_plot_status(fail_row, args) == "fail"


def test_prefixed_block_lines_repeat_status_on_each_line():
    block = "first\nsecond"

    warn_lines = cli._prefixed_block_lines(block, "warn")
    fail_lines = cli._prefixed_block_lines(block, "fail")

    assert warn_lines == [
        "\x1b[33m⚠ WARN\x1b[0m  first",
        "\x1b[33m⚠ WARN\x1b[0m  second",
    ]
    assert fail_lines == [
        "\x1b[31m✗ FAIL\x1b[0m  first",
        "\x1b[31m✗ FAIL\x1b[0m  second",
    ]


def test_cli_strict_returns_nonzero_on_warning_only(capsys):
    exit_code = cli.main(["tests/Zj", "--no-top-plots", "--strict"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "\x1b[33m⚠ WARN\x1b[0m  NaN exception:" in captured.out
    assert "50+-35.3553" in captured.out


def test_cli_handles_missing_powheg_outputs(tmp_path, capsys):
    exit_code = cli.main([str(tmp_path), "--no-top-plots"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert f"POWHEG Overview: {tmp_path}" in captured.out
    assert "No pwgcounters*.dat files were parsed." in captured.out
    assert "No pwg*stat.dat files were parsed." in captured.out
    assert "Relevant Top Plots" in captured.out
    assert "No *grid.top files were parsed." in captured.out


def test_single_run_overview_omits_na_std_suffix(capsys):
    exit_code = cli.main(["tests/Z2jet", "--run-number", "0001", "--no-top-plots"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "+-n/a" not in captured.out


def test_run_number_filter_is_applied_across_folder_parsers():
    args = cli.build_parser().parse_args(["tests/Z2jet", "--run-number", "1"])
    file_filter = cli._build_file_filter(args)

    assert args.run_number == "0001"
    assert file_filter is not None

    counter_df = cli.load_counter_folder("tests/Z2jet", file_filter=file_filter)
    stat_df = cli.load_stat_folder("tests/Z2jet", file_filter=file_filter)
    top_df = cli.load_top_folder("tests/Z2jet", file_filter=file_filter)

    assert set(counter_df.index.get_level_values(1)) == {1}
    assert set(stat_df.index.get_level_values(1)) == {1}
    assert set(top_df.index.get_level_values(1)) == {1}

    total_warn = cli.count_warn("tests/Z2jet", 2)
    run_warn = cli.count_warn("tests/Z2jet", 2, file_filter=file_filter)
    assert run_warn > 0
    assert run_warn < total_warn


def test_overview_run_number_filter_updates_summary_counts(capsys):
    args = cli.build_parser().parse_args(["tests/Z2jet", "--run-number", "0001"])
    file_filter = cli._build_file_filter(args)
    folder = Path("tests/Z2jet")
    counter_df = cli.load_counter_folder(str(folder), file_filter=file_filter)
    stat_df = cli.load_stat_folder(str(folder), file_filter=file_filter)
    top_df = cli.load_top_folder(str(folder), file_filter=file_filter)
    summary = cli._parser_input_summary(
        folder,
        counter_df,
        stat_df,
        top_df,
        file_filter=file_filter,
    )

    assert int(summary.loc["counter files", "matching_files"]) == 3
    assert int(summary.loc["stat files", "matching_files"]) == 3
    assert int(summary.loc["checklimits files", "matching_files"]) == 1

    exit_code = cli.main(["tests/Z2jet", "--run-number", "0001", "--no-top-plots"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "POWHEG Overview: tests/Z2jet [run 0001]" in captured.out
