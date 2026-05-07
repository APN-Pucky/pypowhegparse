from __future__ import annotations

import re
from pathlib import Path


TESTS_DIR = Path(__file__).parent
PROCESS_DIRS = tuple(
    path
    for path in sorted(TESTS_DIR.iterdir())
    if path.is_dir() and not path.name.startswith((".", "__"))
)
PROCESS_IDS = [path.name for path in PROCESS_DIRS]

COUNTER_RE = re.compile(r"(pwgcounters[a-zA-Z0-9-]*?)(?:-(\d{4}))?\.dat$")
STAT_RE = re.compile(r"(pwg[a-zA-Z0-9-]*?)(?:-(\d{4}))?-stat\.dat$")
TOP_RUN_RE = re.compile(r"(pwg[a-zA-Z0-9-]*?)-(\d{4})-([a-zA-Z0-9-]+?grid)\.top$")
TOP_SERIAL_RE = re.compile(r"(pwg[a-zA-Z0-9-]*?)-([a-zA-Z0-9-]+?grid)\.top$")


def _normalize_prefix(prefix: str) -> str:
    return prefix[:-1] if prefix.endswith("-") else prefix


def counter_files(process_dir: Path) -> list[Path]:
    return sorted(process_dir.glob("pwgcounters*.dat"))


def stat_files(process_dir: Path) -> list[Path]:
    return sorted(process_dir.glob("pwg*stat.dat"))


def top_files(process_dir: Path) -> list[Path]:
    files = []
    for file_path in sorted(process_dir.glob("pwg*grid.top")):
        if TOP_RUN_RE.search(file_path.name) or TOP_SERIAL_RE.search(file_path.name):
            files.append(file_path)
    return files


def checklimits_files(process_dir: Path) -> list[Path]:
    return sorted(process_dir.glob("*checklimits*"))


def parse_counter_file_name(file_path: Path) -> tuple[str, int]:
    match = COUNTER_RE.search(file_path.name)
    assert match is not None, f"unexpected counter file name: {file_path.name}"
    return _normalize_prefix(match.group(1)), int(match.group(2) or "1")


def parse_stat_file_name(file_path: Path) -> tuple[str, int]:
    match = STAT_RE.search(file_path.name)
    assert match is not None, f"unexpected stat file name: {file_path.name}"
    return f"{_normalize_prefix(match.group(1))}-stat", int(match.group(2) or "1")


def parse_top_file_name(file_path: Path) -> tuple[str, int]:
    match = TOP_RUN_RE.search(file_path.name)
    if match is not None:
        name = f"{_normalize_prefix(match.group(1))}-{match.group(3)}"
        return name, int(match.group(2))

    match = TOP_SERIAL_RE.search(file_path.name)
    assert match is not None, f"unexpected top file name: {file_path.name}"
    name = f"{_normalize_prefix(match.group(1))}-{match.group(2)}"
    return name, 1


def expected_counter_names(process_dir: Path) -> list[str]:
    return sorted(
        {
            parse_counter_file_name(file_path)[0]
            for file_path in counter_files(process_dir)
        }
    )


def expected_stat_names(process_dir: Path) -> list[str]:
    return sorted(
        {parse_stat_file_name(file_path)[0] for file_path in stat_files(process_dir)}
    )


def expected_top_names(process_dir: Path) -> list[str]:
    return sorted(
        {parse_top_file_name(file_path)[0] for file_path in top_files(process_dir)}
    )
