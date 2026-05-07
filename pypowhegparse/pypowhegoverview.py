#!/usr/bin/python3
from __future__ import annotations

import signal
import argparse
import os
import re
import time
from pathlib import Path
from typing import Callable, Iterable, Sequence

import pandas as pd

from .checklimits import (
    count_warn,
    error_colour_grepc,
    error_spin_grepc,
)
from .counters import load_counter_folder
from .stat import load_stat_folder
from .top import load_top_folder


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
SECTION_WIDTH = 88
FAIL_LABEL = "\033[31m✗ FAIL\033[0m"
WARN_LABEL = "\033[33m⚠ WARN\033[0m"
FAIL_LABEL_WIDTH = len("✗ FAIL")
STATUS_LABEL_WIDTH = max(len("✗ FAIL"), len("⚠ WARN"))
DEFAULT_NEGATIVE_WEIGHT_FRACTION_WARN = 0.1
DEFAULT_NEGATIVE_WEIGHT_FRACTION_FAIL = 0.5
DEFAULT_STAT_RELATIVE_WARN = 0.5
DEFAULT_STAT_RELATIVE_FAIL = 1.0
DEFAULT_FAILING_CHECKS = {
    "WWWWWARN",
    "colour check failures",
    "spin-correlation failures",
}
DEFAULT_WARNING_CHECKS = {"WWWWARN"}
RUN_NUMBER_RE = re.compile(r"-(\d{4})(?:[.-]|$)")
INTERMEDIATE_TOP_RE = re.compile(r"^pwg-xg\d+(?:-\d{4})?-[a-zA-Z0-9-]+grid\.top$")


def _parse_run_number(value: str) -> str:
    stripped = value.strip()
    if not stripped.isdigit():
        raise argparse.ArgumentTypeError(
            "run number must be numeric, for example 0001 or 9999"
        )
    number = int(stripped)
    if number < 0 or number > 9999:
        raise argparse.ArgumentTypeError("run number must be between 0000 and 9999")
    return f"{number:04d}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize POWHEG parser outputs in a terminal-friendly overview and "
            "render relevant top plots."
        )
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="POWHEG run directories to inspect. Defaults to the current directory.",
    )
    parser.add_argument(
        "-f",
        "--folder",
        action="append",
        dest="folders",
        default=[],
        help="Additional POWHEG run directory to inspect.",
    )
    parser.add_argument(
        "--run-number",
        type=_parse_run_number,
        help="Only include files for this run number, for example 0001 or 9999.",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI color output. Also honored when NO_COLOR is set.",
    )
    parser.add_argument(
        "--no-counters",
        action="store_true",
        help="Skip the pwgcounters*.dat summary.",
    )
    parser.add_argument(
        "--no-stat",
        action="store_true",
        help="Skip the pwg*stat.dat summary.",
    )
    parser.add_argument(
        "--no-top",
        action="store_true",
        help="Skip the *grid.top summary and terminal plots.",
    )
    parser.add_argument(
        "--no-top-plots",
        action="store_true",
        help="Skip terminal rendering of selected top plots.",
    )
    parser.add_argument(
        "--no-checklimits",
        action="store_true",
        help="Skip the checklimits summary.",
    )
    parser.add_argument(
        "--top-limit",
        type=int,
        default=6,
        help="Maximum number of relevant top files to render. Use 0 for no limit.",
    )
    parser.add_argument(
        "--top-pvalue-max",
        type=float,
        default=0.05,
        help="Prefer top plots with p-value at or below this threshold.",
    )
    parser.add_argument(
        "--top-sort",
        choices=("pvalue", "chi2"),
        default="pvalue",
        help="How to rank relevant top plots before rendering.",
    )
    parser.add_argument(
        "--top-all",
        action="store_true",
        help="Render every parsed top file instead of only the most relevant ones.",
    )
    parser.add_argument(
        "--top-warn-pvalue-max",
        type=float,
        default=0.05,
        help="Mark a top-plot title as warning when p-value is at or below this threshold.",
    )
    parser.add_argument(
        "--top-fail-pvalue-max",
        type=float,
        default=0.001,
        help="Mark a top-plot title as failure when p-value is at or below this threshold.",
    )
    parser.add_argument(
        "--top-warn-chi2-min",
        type=float,
        default=3.84,
        help="Mark a top-plot title as warning when chi2 is at or above this threshold.",
    )
    parser.add_argument(
        "--top-fail-chi2-min",
        type=float,
        default=10.83,
        help="Mark a top-plot title as failure when chi2 is at or above this threshold.",
    )
    parser.add_argument(
        "--negative-weight-fraction-warn",
        type=float,
        default=DEFAULT_NEGATIVE_WEIGHT_FRACTION_WARN,
        help="Mark a negative weight fraction summary entry as warning above this threshold.",
    )
    parser.add_argument(
        "--negative-weight-fraction-fail",
        type=float,
        default=DEFAULT_NEGATIVE_WEIGHT_FRACTION_FAIL,
        help="Mark a negative weight fraction summary entry as failure above this threshold.",
    )
    parser.add_argument(
        "--stat-relative-warn",
        type=float,
        default=DEFAULT_STAT_RELATIVE_WARN,
        help="Mark a +-stat summary entry as warning above this fraction of its central value.",
    )
    parser.add_argument(
        "--stat-relative-fail",
        type=float,
        default=DEFAULT_STAT_RELATIVE_FAIL,
        help="Mark a +-stat summary entry as failure above this fraction of its central value.",
    )
    parser.add_argument(
        "--warn-level",
        type=int,
        default=5,
        help="Warning level used for warn-threshold checks and optional context output.",
    )
    parser.add_argument(
        "--warn-threshold",
        type=int,
        default=0,
        help="With --strict, fail if the selected warning level occurs more than this many times.",
    )
    parser.add_argument(
        "--ignore-colour",
        action="store_true",
        help="Ignore colour-check failures when computing the strict exit code.",
    )
    parser.add_argument(
        "--ignore-spin",
        action="store_true",
        help="Ignore spin-correlation failures when computing the strict exit code.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when configured warning or error checks fail.",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=140,
        help="Display width used when printing pandas tables.",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=200,
        help="Maximum number of rows to print per table. Use 0 for unlimited.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug output, including cumulative timing summaries.",
    )
    return parser


def _title(title: str) -> None:
    print()
    print(title)
    print("=" * min(len(title), SECTION_WIDTH))


def _section(title: str) -> None:
    print()
    print(title)
    print("-" * min(len(title), SECTION_WIDTH))


def _debug_print_timing_summary(
    args: argparse.Namespace,
    timings: list[tuple[str, float]],
    section_name: str,
) -> None:
    if not getattr(args, "debug", False):
        return
    print(f"[debug] Timing summary after {section_name}:")
    for label, elapsed in timings:
        print(f"[debug]   {label:<32} {elapsed:.3f}s")


def _table_to_string(df: pd.DataFrame, width: int, max_rows: int) -> str:
    max_rows_value = None if max_rows <= 0 else max_rows
    with pd.option_context(
        "display.max_rows",
        max_rows_value,
        "display.max_columns",
        None,
        "display.width",
        width,
        "display.expand_frame_repr",
        False,
    ):
        return df.to_string()


def _checklimits_status(check: str, count: int, args: argparse.Namespace) -> str:
    if check == "colour check failures" and args.ignore_colour:
        return "ok"
    if check == "spin-correlation failures" and args.ignore_spin:
        return "ok"
    if check in DEFAULT_FAILING_CHECKS and int(count) > 0:
        return "fail"
    if check in DEFAULT_WARNING_CHECKS and int(count) > 0:
        return "warn"
    return "ok"


def _checklimits_summary_to_string(
    summary: pd.DataFrame, args: argparse.Namespace
) -> str:
    checks = list(summary.index)
    counts = summary["count"].tolist()
    check_width = max(len("check"), *(len(str(check)) for check in checks))
    count_width = max(len("count"), *(len(str(count)) for count in counts))

    lines = [
        f"{' ' * STATUS_LABEL_WIDTH}  {'check':<{check_width}}  {'count':>{count_width}}"
    ]
    for check, count in zip(checks, counts):
        prefix = _status_prefix(_checklimits_status(str(check), int(count), args), args)
        lines.append(f"{prefix}  {check:<{check_width}}  {count:>{count_width}}")
    return "\n".join(lines)


def _format_number(value: float) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{float(value):.6g}"


def _no_color_requested(args: argparse.Namespace | None = None) -> bool:
    if args is not None and getattr(args, "no_color", False):
        return True
    no_color = os.environ.get("NO_COLOR")
    return no_color is not None and no_color != ""


def _maybe_strip_ansi(text: str, args: argparse.Namespace | None = None) -> str:
    if _no_color_requested(args):
        return ANSI_RE.sub("", text)
    return text


def _status_prefix(status: str, args: argparse.Namespace | None = None) -> str:
    if status == "fail":
        return _maybe_strip_ansi(FAIL_LABEL, args)
    if status == "warn":
        return _maybe_strip_ansi(WARN_LABEL, args)
    return " " * STATUS_LABEL_WIDTH


def _prefixed_block_lines(
    text: str,
    status: str,
    args: argparse.Namespace | None = None,
) -> list[str]:
    prefix = f"{_status_prefix(status, args)}  "
    return [f"{prefix}{line}" for line in text.splitlines()]


def _metric_label(column: str) -> str:
    label = column.strip()
    if not label.endswith(":"):
        label = f"{label}:"
    return label


def _relative_stat_status(
    column: str,
    mean: float,
    means: pd.Series,
    args: argparse.Namespace | None = None,
) -> str | None:
    normalized = column.strip()
    if "+-stat" not in normalized:
        return None

    relative_warn = getattr(
        args,
        "stat_relative_warn",
        DEFAULT_STAT_RELATIVE_WARN,
    )
    relative_fail = getattr(
        args,
        "stat_relative_fail",
        DEFAULT_STAT_RELATIVE_FAIL,
    )

    central_column = column.replace("+-stat", "", 1)
    central_value = means.get(central_column)
    if central_value is None or pd.isna(central_value):
        stripped_lookup = {str(key).strip(): value for key, value in means.items()}
        central_value = stripped_lookup.get(central_column.strip())
    if central_value is None or pd.isna(central_value):
        return None

    scale = abs(float(central_value))
    if scale == 0:
        relative = float("inf") if mean > 0 else 0.0
    else:
        relative = abs(float(mean)) / scale

    if relative > relative_fail:
        return "fail"
    if relative > relative_warn:
        return "warn"
    return "ok"


def _status_severity(status: str) -> int:
    if status == "fail":
        return 2
    if status == "warn":
        return 1
    return 0


def _promote_status(current: str, candidate: str | None) -> str:
    if candidate is None:
        return current
    if _status_severity(candidate) > _status_severity(current):
        return candidate
    return current


def _paired_relative_stat_status(
    column: str,
    means: pd.Series,
    args: argparse.Namespace | None = None,
) -> str | None:
    normalized = column.strip()
    if "+-stat" in normalized:
        mean = means.get(column)
        if mean is None or pd.isna(mean):
            return None
        return _relative_stat_status(column, mean, means, args)

    stat_column = f"{column}+-stat"
    stat_mean = means.get(stat_column)
    if stat_mean is None or pd.isna(stat_mean):
        stripped_lookup = {str(key).strip(): value for key, value in means.items()}
        stat_mean = stripped_lookup.get(stat_column.strip())
        if stat_mean is None or pd.isna(stat_mean):
            return None
        stat_column = next(
            (
                str(key)
                for key in means.keys()
                if str(key).strip() == f"{column.strip()}+-stat"
            ),
            stat_column,
        )
    return _relative_stat_status(stat_column, stat_mean, means, args)


def _format_summary_value(mean: float, std: float) -> str:
    mean_text = _format_number(mean)
    if pd.isna(std):
        return mean_text
    return f"{mean_text}+-{_format_number(std)}"


def _metric_status(
    column: str,
    mean: float,
    means: pd.Series,
    args: argparse.Namespace | None = None,
) -> str:
    normalized = column.strip()
    status = "ok"
    negative_weight_fraction_warn = getattr(
        args,
        "negative_weight_fraction_warn",
        DEFAULT_NEGATIVE_WEIGHT_FRACTION_WARN,
    )
    negative_weight_fraction_fail = getattr(
        args,
        "negative_weight_fraction_fail",
        DEFAULT_NEGATIVE_WEIGHT_FRACTION_FAIL,
    )

    status = _promote_status(status, _paired_relative_stat_status(column, means, args))

    if "negative weight fraction" in normalized:
        if mean > negative_weight_fraction_fail:
            status = _promote_status(status, "fail")
        if mean > negative_weight_fraction_warn:
            status = _promote_status(status, "warn")

    if normalized == "NaN exception" and mean > 0:
        status = _promote_status(status, "warn")

    if "cross section error estimate:" in normalized:
        estimate_column = column.replace(" error estimate:", " estimate:")
        estimate = means.get(estimate_column)
        if estimate is not None and pd.notna(estimate) and mean > estimate:
            status = _promote_status(status, "fail")

    return status


def _mean_std_summary(
    df: pd.DataFrame,
    args: argparse.Namespace | None = None,
) -> tuple[str, int, int]:
    label_width = 0
    for group_name in df.index.get_level_values(0).unique():
        group_df = df.xs(group_name)
        means = group_df.mean(numeric_only=True)
        for column in group_df.columns:
            mean = means.get(column)
            if pd.isna(mean):
                continue
            label_width = max(label_width, len(_metric_label(column)))

    lines: list[str] = []
    warning_count = 0
    failure_count = 0
    for group_name in df.index.get_level_values(0).unique():
        lines.append(f"[{group_name}]")
        group_df = df.xs(group_name)
        means = group_df.mean(numeric_only=True)
        stds = group_df.std(numeric_only=True)
        for column in group_df.columns:
            mean = means.get(column)
            if pd.isna(mean):
                continue
            std = stds.get(column)
            status = _metric_status(column, mean, means, args)
            if status == "warn":
                warning_count += 1
            if status == "fail":
                failure_count += 1
            lines.append(
                f"{_status_prefix(status, args)}  {_metric_label(column):<{label_width}}  "
                f"{_format_summary_value(mean, std)}"
            )
        lines.append("")
    return "\n".join(lines).rstrip(), warning_count, failure_count


def _bytes_to_lines(lines: Iterable[bytes]) -> list[str]:
    return [line.decode("utf-8", errors="replace") for line in lines if line]


def _extract_run_number(file_path: str | Path) -> str | None:
    match = RUN_NUMBER_RE.search(Path(file_path).name)
    if match is not None:
        return match.group(1)

    name = Path(file_path).name
    if (
        name.startswith("pwgcounters")
        and name.endswith(".dat")
        or name.startswith("pwg")
        and (name.endswith("-stat.dat") or name.endswith("grid.top"))
        or "checklimits" in name
    ):
        return "0001"
    return None


def _build_file_filter(
    args: argparse.Namespace,
) -> Callable[[str], bool] | None:
    if args.run_number is None:
        return None
    return lambda file_path: _extract_run_number(file_path) == args.run_number


def _combine_file_filters(
    *filters: Callable[[str], bool] | None,
) -> Callable[[str], bool] | None:
    active_filters = [file_filter for file_filter in filters if file_filter is not None]
    if not active_filters:
        return None
    return lambda file_path: all(
        file_filter(file_path) for file_filter in active_filters
    )


def _is_intermediate_top_file(file_path: str | Path) -> bool:
    return INTERMEDIATE_TOP_RE.match(Path(file_path).name) is not None


def _build_top_file_filter(
    args: argparse.Namespace,
) -> Callable[[str], bool] | None:
    return _combine_file_filters(
        _build_file_filter(args),
        lambda file_path: not _is_intermediate_top_file(file_path),
    )


def _safe_load_dataframe(
    loader, folder: Path, file_filter=None, **kwargs
) -> pd.DataFrame | None:
    try:
        return loader(str(folder), file_filter=file_filter, **kwargs)
    except ValueError as exc:
        if "No objects to concatenate" in str(exc):
            return None
        raise


def _resolve_folders(args: argparse.Namespace) -> list[Path]:
    raw_paths = [*args.paths, *args.folders]
    if not raw_paths:
        raw_paths = ["."]
    folders = []
    seen = set()
    for raw_path in raw_paths:
        path = Path(raw_path).expanduser()
        normalized = str(path.resolve())
        if normalized in seen:
            continue
        seen.add(normalized)
        folders.append(path)
    return folders


def _matching_folder_files(
    folder: Path,
    pattern: str,
    file_filter=None,
) -> list[Path]:
    files = sorted(folder.glob(pattern))
    if file_filter is not None:
        files = [file_path for file_path in files if file_filter(str(file_path))]
    return files


def _parser_input_summary(
    folder: Path,
    counter_df: pd.DataFrame | None,
    stat_df: pd.DataFrame | None,
    top_df: pd.DataFrame | None,
    file_filter=None,
    top_file_filter=None,
) -> pd.DataFrame:
    parsed_top_files = 0
    parsed_top_plots = 0
    parsed_top_groups = 0
    if top_df is not None:
        parsed_top_files = len(top_df.index.droplevel(2).unique())
        parsed_top_plots = len(top_df)
        parsed_top_groups = len(top_df.index.get_level_values(0).unique())

    rows = [
        (
            "counter files",
            len(_matching_folder_files(folder, "pwgcounters*.dat", file_filter)),
            len(counter_df) if counter_df is not None else 0,
            len(counter_df.index.get_level_values(0).unique())
            if counter_df is not None
            else 0,
        ),
        (
            "stat files",
            len(_matching_folder_files(folder, "pwg*stat.dat", file_filter)),
            len(stat_df) if stat_df is not None else 0,
            len(stat_df.index.get_level_values(0).unique())
            if stat_df is not None
            else 0,
        ),
        (
            "grid top files",
            len(
                _matching_folder_files(
                    folder,
                    "pwg*grid.top",
                    top_file_filter if top_file_filter is not None else file_filter,
                )
            ),
            parsed_top_files,
            parsed_top_groups,
        ),
        (
            "checklimits files",
            len(_matching_folder_files(folder, "*checklimits*", file_filter)),
            0,
            0,
        ),
    ]
    summary = pd.DataFrame.from_records(
        rows,
        columns=["parser_input", "matching_files", "loaded_rows", "loaded_groups"],
    ).set_index("parser_input")
    summary.loc["grid top files", "loaded_rows"] = parsed_top_plots
    return summary


def _top_numeric_frame(top_df: pd.DataFrame) -> pd.DataFrame:
    return top_df[["pvalue", "chi2"]].astype(float)


def _representative_top_plots(top_df: pd.DataFrame) -> pd.DataFrame:
    numeric = _top_numeric_frame(top_df).copy()
    numeric["_source_order"] = range(len(numeric))
    numeric["top_file"] = top_df.index.get_level_values(0)
    numeric["run"] = top_df.index.get_level_values(1)
    numeric["plot_title"] = [
        str(title).strip() for title in top_df.index.get_level_values(2)
    ]
    numeric["plot"] = top_df["plot"].to_numpy()
    return numeric.drop_duplicates(["top_file", "plot_title"], keep="first")


def _select_relevant_top_plots(
    top_df: pd.DataFrame, args: argparse.Namespace
) -> pd.DataFrame:
    representative_plots = _representative_top_plots(top_df)
    file_scores = representative_plots.groupby("top_file").agg(
        min_pvalue=("pvalue", "min"),
        max_chi2=("chi2", "max"),
        first_run=("run", "first"),
        first_source_order=("_source_order", "min"),
    )

    if args.top_sort == "chi2":
        ranked_files = file_scores.sort_values(
            ["max_chi2", "min_pvalue", "first_source_order"],
            ascending=[False, True, True],
            kind="mergesort",
        )
    else:
        ranked_files = file_scores.sort_values(
            ["min_pvalue", "max_chi2", "first_source_order"],
            ascending=[True, False, True],
            kind="mergesort",
        )

    if args.top_all:
        selected_files = ranked_files.index.tolist()
    else:
        selected_files = ranked_files[
            ranked_files["min_pvalue"] <= args.top_pvalue_max
        ].index.tolist()
        if not selected_files:
            selected_files = ranked_files.index.tolist()

        if args.top_limit > 0:
            selected_files = selected_files[: args.top_limit]

    selected = representative_plots[
        representative_plots["top_file"].isin(selected_files)
    ].copy()
    file_order = {top_file: index for index, top_file in enumerate(selected_files)}
    selected["_file_order"] = selected["top_file"].map(file_order)
    selected = selected.sort_values(["_file_order", "_source_order"], kind="mergesort")
    return selected.drop(columns=["_source_order", "_file_order"])


def _top_plot_status(row, args: argparse.Namespace) -> str:
    pvalue = float(row.pvalue)
    chi2 = float(row.chi2)

    if pvalue <= args.top_fail_pvalue_max or chi2 >= args.top_fail_chi2_min:
        return "fail"
    if pvalue <= args.top_warn_pvalue_max or chi2 >= args.top_warn_chi2_min:
        return "warn"
    return "ok"


def _checklimits_summary(
    folder: Path,
    warn_level: int,
    file_filter=None,
) -> tuple[pd.DataFrame, list[str], list[str], list[list[str]]]:
    warn_rows = [
        ("WARN", count_warn(str(folder), 1, file_filter=file_filter)),
        ("WWARN", count_warn(str(folder), 2, file_filter=file_filter)),
        ("WWWARN", count_warn(str(folder), 3, file_filter=file_filter)),
        ("WWWWARN", count_warn(str(folder), 4, file_filter=file_filter)),
        ("WWWWWARN", count_warn(str(folder), 5, file_filter=file_filter)),
    ]
    colour_lines = error_colour_grepc(str(folder), file_filter=file_filter)
    spin_lines = error_spin_grepc(str(folder), file_filter=file_filter)
    summary = pd.DataFrame.from_records(
        [
            *warn_rows,
            ("colour check failures", colour_lines),
            ("spin-correlation failures", spin_lines),
        ],
        columns=["check", "count"],
    ).set_index("check")

    return summary


def _checklimits_status_counts(
    summary: pd.DataFrame | None,
    args: argparse.Namespace,
) -> tuple[int, int]:
    if summary is None:
        return 0, 0
    warning_count = 0
    failures = 0
    for check, row in summary.iterrows():
        status = _checklimits_status(str(check), int(row["count"]), args)
        if status == "warn":
            warning_count += 1
        if status == "fail":
            failures += 1
    return warning_count, failures


def _strict_exit_code(
    args: argparse.Namespace,
    warn_summary: pd.DataFrame | None,
) -> int:
    if not args.strict:
        return 0

    if warn_summary is not None and args.warn_level >= 1:
        warn_label = "W" * args.warn_level + "ARN"
        if warn_label in warn_summary.index:
            if int(warn_summary.loc[warn_label, "count"]) > args.warn_threshold:
                return 1
    return 0


def _report_for_folder(folder: Path, args: argparse.Namespace) -> int:
    report_start = time.perf_counter()
    timings: list[tuple[str, float]] = []
    file_filter = _build_file_filter(args)
    top_file_filter = _build_top_file_filter(args)

    counter_start = time.perf_counter()
    counter_df = (
        None
        if args.no_counters
        else _safe_load_dataframe(load_counter_folder, folder, file_filter=file_filter)
    )
    timings.append(("load_counter_folder", time.perf_counter() - counter_start))

    stat_start = time.perf_counter()
    stat_df = (
        None
        if args.no_stat
        else _safe_load_dataframe(load_stat_folder, folder, file_filter=file_filter)
    )
    timings.append(("load_stat_folder", time.perf_counter() - stat_start))

    top_start = time.perf_counter()
    top_df = (
        None
        if args.no_top
        else _safe_load_dataframe(
            load_top_folder, folder, file_filter=top_file_filter, first_only=True
        )
    )
    timings.append(("load_top_folder", time.perf_counter() - top_start))

    title = f"POWHEG Overview: {folder}"
    if args.run_number is not None:
        title = f"{title} [run {args.run_number}]"
    _title(title)
    parser_input_start = time.perf_counter()
    print(
        _table_to_string(
            _parser_input_summary(
                folder,
                counter_df,
                stat_df,
                top_df,
                file_filter=file_filter,
                top_file_filter=top_file_filter,
            ),
            args.width,
            args.max_rows,
        )
    )
    timings.append(("parser_input_summary", time.perf_counter() - parser_input_start))
    _debug_print_timing_summary(args, timings, "Parser Input")

    warn_summary = None
    summary_warning_count = 0
    summary_failure_count = 0

    if not args.no_checklimits:
        checklimits_start = time.perf_counter()
        warn_summary = _checklimits_summary(
            folder,
            args.warn_level,
            file_filter=file_filter,
        )
        _section("Checklimits Summary")
        print(_checklimits_summary_to_string(warn_summary, args))
        checklimits_warnings, checklimits_failures = _checklimits_status_counts(
            warn_summary,
            args,
        )
        summary_warning_count += checklimits_warnings
        summary_failure_count += checklimits_failures
        timings.append(("checklimits_summary", time.perf_counter() - checklimits_start))
        _debug_print_timing_summary(args, timings, "Checklimits Summary")

    if counter_df is not None:
        counter_summary_start = time.perf_counter()
        _section("Counter Summary")
        counter_summary, counter_warnings, counter_failures = _mean_std_summary(
            counter_df,
            args,
        )
        summary_warning_count += counter_warnings
        summary_failure_count += counter_failures
        print(counter_summary)
        timings.append(("counter_summary", time.perf_counter() - counter_summary_start))
        _debug_print_timing_summary(args, timings, "Counter Summary")
    elif not args.no_counters:
        counter_summary_start = time.perf_counter()
        _section("Counter Summary")
        print("No pwgcounters*.dat files were parsed.")
        timings.append(("counter_summary", time.perf_counter() - counter_summary_start))
        _debug_print_timing_summary(args, timings, "Counter Summary")

    if stat_df is not None:
        stat_summary_start = time.perf_counter()
        _section("Stat Summary")
        stat_summary, stat_warnings, stat_failures = _mean_std_summary(stat_df, args)
        summary_warning_count += stat_warnings
        summary_failure_count += stat_failures
        print(stat_summary)
        timings.append(("stat_summary", time.perf_counter() - stat_summary_start))
        _debug_print_timing_summary(args, timings, "Stat Summary")
    elif not args.no_stat:
        stat_summary_start = time.perf_counter()
        _section("Stat Summary")
        print("No pwg*stat.dat files were parsed.")
        timings.append(("stat_summary", time.perf_counter() - stat_summary_start))
        _debug_print_timing_summary(args, timings, "Stat Summary")

    if top_df is not None:
        if not args.no_top_plots:
            top_section_start = time.perf_counter()
            selected_top_df = _select_relevant_top_plots(top_df, args)
            _section("Relevant Top Plots")
            if selected_top_df.empty:
                print("No top plots matched the current selection.")
            else:
                for row in selected_top_df.itertuples(index=False):
                    top_status = _top_plot_status(row, args)
                    if top_status == "warn":
                        summary_warning_count += 1
                    if top_status == "fail":
                        summary_failure_count += 1
                    print()
                    print(
                        f"{_status_prefix(top_status, args)}  "
                        f"[{row.top_file} run {row.run} | {row.plot_title} | "
                        f"pvalue={row.pvalue:.6g} chi2={row.chi2:.6g}]"
                    )
                    for line in _prefixed_block_lines(
                        _maybe_strip_ansi(row.plot.terminal_plot_str(), args),
                        top_status,
                        args,
                    ):
                        print(line)
            timings.append(
                ("relevant_top_plots", time.perf_counter() - top_section_start)
            )
            _debug_print_timing_summary(args, timings, "Relevant Top Plots")
    elif not args.no_top:
        top_section_start = time.perf_counter()
        _section("Relevant Top Plots")
        print("No *grid.top files were parsed.")
        timings.append(("relevant_top_plots", time.perf_counter() - top_section_start))
        _debug_print_timing_summary(args, timings, "Relevant Top Plots")

    timings.append(("folder_report_total", time.perf_counter() - report_start))
    _debug_print_timing_summary(args, timings, "Folder Report")

    exit_code = 0
    if summary_failure_count > 0:
        exit_code = 1
    if args.strict and summary_warning_count > 0:
        exit_code = 1
    if _strict_exit_code(args, warn_summary) > 0:
        exit_code = 1
    return exit_code


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    parser = build_parser()
    args = parser.parse_args(argv)

    exit_code = 0
    for folder in _resolve_folders(args):
        exit_code = max(exit_code, _report_for_folder(folder, args))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
