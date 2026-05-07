from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

from .checklimits import (
    count_warn,
    error_colour_grep,
    error_spin_grep,
    inspect_warn_grep,
)
from .counters import load_counter_folder
from .stat import load_stat_folder
from .top import load_top_folder


SECTION_WIDTH = 88
FAIL_LABEL = "\033[31m✗ FAIL\033[0m"
WARN_LABEL = "\033[33m⚠ WARN\033[0m"
FAIL_LABEL_WIDTH = len("✗ FAIL")
STATUS_LABEL_WIDTH = max(len("✗ FAIL"), len("⚠ WARN"))
DEFAULT_NEGATIVE_WEIGHT_FRACTION_WARN = 0.1
DEFAULT_NEGATIVE_WEIGHT_FRACTION_FAIL = 0.5
DEFAULT_FAILING_CHECKS = {
    "WWWWWARN",
    "colour check failures",
    "spin-correlation failures",
}
DEFAULT_WARNING_CHECKS = {"WWWWARN"}


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
        "--show-warn-context",
        action="store_true",
        help="Print excerpts around checklimits warnings at --warn-level.",
    )
    parser.add_argument(
        "--warn-context-limit",
        type=int,
        default=3,
        help="Maximum number of warning excerpts to print. Use 0 for no limit.",
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
    return parser


def _title(title: str) -> None:
    print()
    print(title)
    print("=" * min(len(title), SECTION_WIDTH))


def _section(title: str) -> None:
    print()
    print(title)
    print("-" * min(len(title), SECTION_WIDTH))


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
        prefix = _status_prefix(_checklimits_status(str(check), int(count), args))
        lines.append(f"{prefix}  {check:<{check_width}}  {count:>{count_width}}")
    return "\n".join(lines)


def _format_number(value: float) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{float(value):.6g}"


def _status_prefix(status: str) -> str:
    if status == "fail":
        return FAIL_LABEL
    if status == "warn":
        return WARN_LABEL
    return " " * STATUS_LABEL_WIDTH


def _metric_label(column: str) -> str:
    label = column.strip()
    if not label.endswith(":"):
        label = f"{label}:"
    return label


def _metric_status(
    column: str,
    mean: float,
    means: pd.Series,
    args: argparse.Namespace | None = None,
) -> str:
    normalized = column.strip()
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

    if "negative weight fraction" in normalized:
        if mean > negative_weight_fraction_fail:
            return "fail"
        if mean > negative_weight_fraction_warn:
            return "warn"

    if normalized == "NaN exception" and mean > 0:
        return "warn"

    if "cross section error estimate:" in normalized:
        estimate_column = column.replace(" error estimate:", " estimate:")
        estimate = means.get(estimate_column)
        if estimate is not None and pd.notna(estimate) and mean > estimate:
            return "fail"

    return "ok"


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
                f"{_status_prefix(status)}  {_metric_label(column):<{label_width}}  "
                f"{_format_number(mean)}+-{_format_number(std)}"
            )
        lines.append("")
    return "\n".join(lines).rstrip(), warning_count, failure_count


def _bytes_to_lines(lines: Iterable[bytes]) -> list[str]:
    return [line.decode("utf-8", errors="replace") for line in lines if line]


def _safe_load_dataframe(loader, folder: Path) -> pd.DataFrame | None:
    try:
        return loader(str(folder))
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


def _parser_input_summary(
    folder: Path,
    counter_df: pd.DataFrame | None,
    stat_df: pd.DataFrame | None,
    top_df: pd.DataFrame | None,
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
            len(list(folder.glob("pwgcounters*.dat"))),
            len(counter_df) if counter_df is not None else 0,
            len(counter_df.index.get_level_values(0).unique())
            if counter_df is not None
            else 0,
        ),
        (
            "stat files",
            len(list(folder.glob("pwg*stat.dat"))),
            len(stat_df) if stat_df is not None else 0,
            len(stat_df.index.get_level_values(0).unique())
            if stat_df is not None
            else 0,
        ),
        (
            "grid top files",
            len(list(folder.glob("pwg*grid.top"))),
            parsed_top_files,
            parsed_top_groups,
        ),
        ("checklimits files", len(list(folder.glob("*checklimits*"))), 0, 0),
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
) -> tuple[pd.DataFrame, list[str], list[str], list[list[str]]]:
    warn_rows = [
        ("WARN", count_warn(str(folder), 1)),
        ("WWARN", count_warn(str(folder), 2)),
        ("WWWARN", count_warn(str(folder), 3)),
        ("WWWWARN", count_warn(str(folder), 4)),
        ("WWWWWARN", count_warn(str(folder), 5)),
    ]
    colour_lines = _bytes_to_lines(error_colour_grep(str(folder)))
    spin_lines = _bytes_to_lines(error_spin_grep(str(folder)))
    summary = pd.DataFrame.from_records(
        [
            *warn_rows,
            ("colour check failures", len(colour_lines)),
            ("spin-correlation failures", len(spin_lines)),
        ],
        columns=["check", "count"],
    ).set_index("check")

    warn_contexts = []
    for block in inspect_warn_grep(str(folder), warn_level):
        lines = _bytes_to_lines(block)
        if lines:
            warn_contexts.append(lines)
    return summary, colour_lines, spin_lines, warn_contexts


def _print_warn_contexts(contexts: list[list[str]], args: argparse.Namespace) -> None:
    if not contexts:
        print("No warning excerpts matched the selected level.")
        return

    context_limit = (
        args.warn_context_limit if args.warn_context_limit > 0 else len(contexts)
    )
    for index, block in enumerate(contexts[:context_limit], start=1):
        print(f"[warning excerpt {index}]")
        for line in block:
            print(line)
        print()


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
    counter_df = (
        None if args.no_counters else _safe_load_dataframe(load_counter_folder, folder)
    )
    stat_df = None if args.no_stat else _safe_load_dataframe(load_stat_folder, folder)
    top_df = None if args.no_top else _safe_load_dataframe(load_top_folder, folder)

    _title(f"POWHEG Overview: {folder}")
    print(
        _table_to_string(
            _parser_input_summary(folder, counter_df, stat_df, top_df),
            args.width,
            args.max_rows,
        )
    )

    warn_summary = None
    colour_lines: list[str] = []
    spin_lines: list[str] = []
    warn_contexts: list[list[str]] = []
    summary_warning_count = 0
    summary_failure_count = 0

    if not args.no_checklimits:
        warn_summary, colour_lines, spin_lines, warn_contexts = _checklimits_summary(
            folder,
            args.warn_level,
        )
        _section("Checklimits Summary")
        print(_checklimits_summary_to_string(warn_summary, args))
        checklimits_warnings, checklimits_failures = _checklimits_status_counts(
            warn_summary,
            args,
        )
        summary_warning_count += checklimits_warnings
        summary_failure_count += checklimits_failures
        if args.show_warn_context:
            _section(f"Warning Context (level {args.warn_level})")
            _print_warn_contexts(warn_contexts, args)

    if counter_df is not None:
        _section("Counter Summary")
        counter_summary, counter_warnings, counter_failures = _mean_std_summary(
            counter_df,
            args,
        )
        summary_warning_count += counter_warnings
        summary_failure_count += counter_failures
        print(counter_summary)
    elif not args.no_counters:
        _section("Counter Summary")
        print("No pwgcounters*.dat files were parsed.")

    if stat_df is not None:
        _section("Stat Summary")
        stat_summary, stat_warnings, stat_failures = _mean_std_summary(stat_df, args)
        summary_warning_count += stat_warnings
        summary_failure_count += stat_failures
        print(stat_summary)
    elif not args.no_stat:
        _section("Stat Summary")
        print("No pwg*stat.dat files were parsed.")

    if top_df is not None:
        if not args.no_top_plots:
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
                        f"{_status_prefix(top_status)}  "
                        f"[{row.top_file} run {row.run} | {row.plot_title} | "
                        f"pvalue={row.pvalue:.6g} chi2={row.chi2:.6g}]"
                    )
                    print(row.plot.terminal_plot_str())
    elif not args.no_top:
        _section("Relevant Top Plots")
        print("No *grid.top files were parsed.")

    exit_code = 0
    if summary_failure_count > 0:
        exit_code = 1
    if args.strict and summary_warning_count > 0:
        exit_code = 1
    if _strict_exit_code(args, warn_summary) > 0:
        exit_code = 1
    return exit_code


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    exit_code = 0
    for folder in _resolve_folders(args):
        exit_code = max(exit_code, _report_for_folder(folder, args))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
