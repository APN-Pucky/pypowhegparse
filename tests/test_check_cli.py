import pypowhegparse.pypowhegcheck as check


def test_check_reports_fail_only_lines_by_default(capsys):
    exit_code = check.main(["tests/directphoton", "--no-top-plots"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "POWHEG Check: tests/directphoton" in captured.out
    assert "Checklimits Summary" in captured.out
    assert "0001 FAIL: colour check failures" in captured.out
    assert "0001 FAIL: spin-correlation failures" in captured.out
    assert "\n0001 WARN:" not in captured.out


def test_check_strict_includes_warning_lines(capsys):
    exit_code = check.main(["tests/Zj", "--strict", "--no-top-plots"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Counter Summary" in captured.out
    assert "0001 WARN: [pwgcounters-st4] NaN exception:" in captured.out
    assert "0002 WARN: [pwgcounters-st4] NaN exception:" in captured.out


def test_check_prints_top_plots_only_for_first_matching_run(capsys):
    exit_code = check.main(["tests/Z2jet", "--top-limit", "1", "--top-pvalue-max", "1"])
    captured = capsys.readouterr()
    lines = captured.out.splitlines()

    assert exit_code == 1
    assert "Relevant Top Plots" in captured.out
    assert "0001 FAIL: [pwg-rmngrid run 1 |" in captured.out
    assert "0002 FAIL: [pwg-rmngrid run 2 |" not in captured.out
    assert any(line.startswith("0001 FAIL:") and "┌" in line for line in lines)
