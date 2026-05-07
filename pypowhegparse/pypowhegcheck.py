#!/usr/bin/python3
from __future__ import annotations

import argparse
import io
import re
import signal
from contextlib import redirect_stdout
from pathlib import Path
from typing import Sequence

from . import pypowhegoverview as overview


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
STATUS_LINE_RE = re.compile(r"^(✗ FAIL|⚠ WARN)\s{2}(.*)$")
SECTION_LABELS = {
    "Checklimits Summary": "checklimits",
    "Counter Summary": "counters",
    "Stat Summary": "stats",
    "Relevant Top Plots": "top",
}
SECTION_ORDER = (
    ("checklimits", "Checklimits Summary"),
    ("counters", "Counter Summary"),
    ("stats", "Stat Summary"),
    ("top", "Relevant Top Plots"),
)


def build_parser() -> argparse.ArgumentParser:
    parser = overview.build_parser()
    parser.description = (
        "Loop over available POWHEG runs and show only the warning/failure lines "
        "from the overview output."
    )
    return parser


def _title(title: str) -> None:
    print()
    print(title)
    print("=" * min(len(title), overview.SECTION_WIDTH))


def _section(title: str) -> None:
    print()
    print(title)
    print("-" * min(len(title), overview.SECTION_WIDTH))


def _strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def _status_and_content(line: str) -> tuple[str, str] | None:
    match = STATUS_LINE_RE.match(_strip_ansi(line))
    if match is None:
        return None
    label, content = match.groups()
    return ("fail" if "FAIL" in label else "warn", content)


def _should_include_status(status: str, args: argparse.Namespace) -> bool:
    return status == "fail" or (args.strict and status == "warn")


def _extract_section_matches(
    output: str,
    args: argparse.Namespace,
) -> dict[str, list[tuple[str, str]]]:
    matches = {key: [] for key in SECTION_LABELS.values()}
    current_section = None
    current_group = None

    for line in output.splitlines():
        if line in SECTION_LABELS:
            current_section = SECTION_LABELS[line]
            current_group = None
            continue

        if current_section in {"counters", "stats"}:
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                current_group = stripped
                continue

        parsed = _status_and_content(line)
        if parsed is None or current_section is None:
            continue

        status, content = parsed
        if not _should_include_status(status, args):
            continue

        if current_section in {"counters", "stats"} and current_group is not None:
            content = f"{current_group} {content}"

        matches[current_section].append((status, content))

    return matches


def _format_match_line(run_number: str, status: str, content: str) -> str:
    return f"{run_number} {status.upper()}: {content}"


def _build_overview_args(
    args: argparse.Namespace,
    run_number: str,
    include_top_plots: bool,
) -> argparse.Namespace:
    overview_args = argparse.Namespace(**vars(args))
    overview_args.paths = []
    overview_args.folders = []
    overview_args.run_number = run_number
    if not include_top_plots:
        overview_args.no_top_plots = True
    return overview_args


def _capture_overview_output(
    folder: Path,
    args: argparse.Namespace,
    run_number: str,
    include_top_plots: bool,
) -> tuple[str, int]:
    overview_args = _build_overview_args(args, run_number, include_top_plots)
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        exit_code = overview._report_for_folder(folder, overview_args)
    return buffer.getvalue(), exit_code


def _discover_run_numbers(folder: Path, args: argparse.Namespace) -> list[str]:
    file_filter = overview._build_file_filter(args)
    run_numbers = set()

    for pattern in (
        "pwgcounters*.dat",
        "pwg*stat.dat",
        "pwg*grid.top",
        "*checklimits*",
    ):
        for file_path in overview._matching_folder_files(folder, pattern, file_filter):
            run_number = overview._extract_run_number(file_path)
            if run_number is not None:
                run_numbers.add(run_number)

    return sorted(run_numbers)


def _report_for_folder(folder: Path, args: argparse.Namespace) -> int:
    run_numbers = _discover_run_numbers(folder, args)
    _title(f"POWHEG Check: {folder}")

    if not run_numbers:
        print("No run numbers matched the current selection.")
        return 0

    section_lines = {key: [] for key, _ in SECTION_ORDER}
    saw_warning = False
    saw_failure = False
    top_recorded = args.no_top or args.no_top_plots

    for run_number in run_numbers:
        include_top_plots = not top_recorded
        output, _ = _capture_overview_output(
            folder,
            args,
            run_number,
            include_top_plots=include_top_plots,
        )
        matches = _extract_section_matches(output, args)

        for section_key in ("checklimits", "counters", "stats"):
            for status, content in matches[section_key]:
                if status == "warn":
                    saw_warning = True
                if status == "fail":
                    saw_failure = True
                section_lines[section_key].append(
                    _format_match_line(run_number, status, content)
                )

        if not top_recorded and matches["top"]:
            for status, content in matches["top"]:
                if status == "warn":
                    saw_warning = True
                if status == "fail":
                    saw_failure = True
                section_lines["top"].append(
                    _format_match_line(run_number, status, content)
                )
            top_recorded = True

    printed_section = False
    for section_key, section_title in SECTION_ORDER:
        lines = section_lines[section_key]
        if not lines:
            continue
        _section(section_title)
        for line in lines:
            print(line)
        printed_section = True

    if not printed_section:
        if args.strict:
            print("No FAIL or WARN lines matched the current selection.")
        else:
            print("No FAIL lines matched the current selection.")

    if saw_failure:
        return 1
    if args.strict and saw_warning:
        return 1
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    exit_code = 0
    for folder in overview._resolve_folders(args):
        exit_code = max(exit_code, _report_for_folder(folder, args))
    return exit_code


if __name__ == "__main__":
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    raise SystemExit(main())
