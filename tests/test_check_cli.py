import pypowhegparse.pypowhegcheck as check


def test_check_reports_fail_only_lines_by_default(capsys):
    exit_code = check.main(["tests/directphoton", "--no-top-plots"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "POWHEG Check: tests/directphoton" in captured.out
    assert "Checklimits Summary" in captured.out
    assert "0001 \x1b[31m✗ FAIL\x1b[0m  colour check failures" in captured.out
    assert "0001 \x1b[31m✗ FAIL\x1b[0m  spin-correlation failures" in captured.out
    assert "\n0001 \x1b[33m⚠ WARN\x1b[0m  " not in captured.out


def test_check_strict_includes_warning_lines(capsys):
    exit_code = check.main(["tests/Zj", "--strict", "--no-top-plots"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Counter Summary" in captured.out
    assert (
        "0001 \x1b[33m⚠ WARN\x1b[0m  [pwgcounters-st4] NaN exception:" in captured.out
    )
    assert (
        "0002 \x1b[33m⚠ WARN\x1b[0m  [pwgcounters-st4] NaN exception:" in captured.out
    )


def test_check_prints_top_plots_only_for_first_matching_run(capsys):
    exit_code = check.main(["tests/Z2jet", "--top-limit", "1", "--top-pvalue-max", "1"])
    captured = capsys.readouterr()
    lines = captured.out.splitlines()

    assert exit_code == 1
    assert "Relevant Top Plots" in captured.out
    assert any(
        (
            "0001 \x1b[31m✗ FAIL\x1b[0m  [" in line
            or "0001 \x1b[33m⚠ WARN\x1b[0m  [" in line
        )
        and " run 1 | dim=" in line
        for line in lines
    )
    assert " run 2 |" not in captured.out
    assert any(
        (
            line.startswith("0001 \x1b[31m✗ FAIL\x1b[0m  ")
            or line.startswith("0001 \x1b[33m⚠ WARN\x1b[0m  ")
        )
        and "┌" in line
        for line in lines
    )


def test_check_no_color_flag_disables_ansi_but_keeps_symbols(capsys):
    exit_code = check.main(["tests/directphoton", "--no-top-plots", "--no-color"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "\x1b[" not in captured.out
    assert "0001 ✗ FAIL  " in captured.out


def test_check_handles_serial_powheg_outputs(capsys):
    exit_code = check.main(["tests/regression-test", "--no-top-plots"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "POWHEG Check: tests/regression-test" in captured.out
    assert "0001 \x1b[31m✗ FAIL\x1b[0m" in captured.out
