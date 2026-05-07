import glob
import numpy as np
import os
import pandas as pd
import re
import pytopdrawer as ptd
from pytopdrawer import TopPlot
from scipy.stats import chi2


TOP_RUN_RE = re.compile(r"^(pwg[a-zA-Z0-9-]*?)-(\d{4})-([a-zA-Z0-9-]+?grid)\.top$")
TOP_SERIAL_RE = re.compile(r"^(pwg[a-zA-Z0-9-]*?)-([a-zA-Z0-9-]+?grid)\.top$")


def _top_files(folder, file_filter=None, first_only=False):
    files = sorted(glob.glob(folder + "/pwg*.top"))
    if file_filter is not None:
        files = [file for file in files if file_filter(file)]

    # Keep one file per logical top-file family, preferring no run number,
    # then 0001, 0002, ...
    if first_only and files:
        selected = {}
        for file in files:
            basename = os.path.basename(file)

            run_match = TOP_RUN_RE.search(basename)
            if run_match is not None:
                fname = run_match.group(1)
                if fname.endswith("-"):
                    fname = fname[:-1]
                key = f"{fname}-{run_match.group(3)}"
                priority = int(run_match.group(2))
            else:
                serial_match = TOP_SERIAL_RE.search(basename)
                if serial_match is not None:
                    fname = serial_match.group(1)
                    if fname.endswith("-"):
                        fname = fname[:-1]
                    key = f"{fname}-{serial_match.group(2)}"
                    priority = 0
                else:
                    # Unknown names are kept as-is and not merged.
                    key = basename
                    priority = 0

            current = selected.get(key)
            if current is None or (priority, file) < (current[0], current[1]):
                selected[key] = (priority, file)

        files = sorted(file for _, file in selected.values())

    return files


def _top_file_info(file):
    basename = os.path.basename(file)
    match = TOP_RUN_RE.search(basename)
    if match is not None:
        fname = match.group(1)
        if fname.endswith("-"):
            fname = fname[:-1]
        number = int(match.group(2))
        return f"{fname}-{match.group(3)}", number

    match = TOP_SERIAL_RE.search(basename)
    if match is None:
        raise ValueError(f"unexpected top file name: {file}")
    fname = match.group(1)
    if fname.endswith("-"):
        fname = fname[:-1]
    return f"{fname}-{match.group(2)}", 1


def load_top_plot(plot: TopPlot):
    pairs = [
        ("pvalue", pvalue_top(plot)),
        ("chi2", chisquare_top(plot)),
        ("plot", plot),
    ]
    return pd.DataFrame.from_records(
        pairs, columns=["title", plot.title.text], index="title"
    ).transpose()


def load_top_file(file):
    pairs = {}
    fname, number = _top_file_info(file)
    for top in ptd.read(file):
        if number not in pairs.keys():
            pairs[number] = load_top_plot(top)
        else:
            pairs[number] = pd.concat([pairs[number], load_top_plot(top)])
    return pd.concat(pairs.values(), keys=pairs.keys())


def load_top_folder(folder, file_filter=None, first_only=False):  # names
    pairs = {}
    for file in _top_files(folder, file_filter=file_filter, first_only=first_only):
        try:
            fname, _ = _top_file_info(file)
        except ValueError:
            continue
        if fname not in pairs.keys():
            pairs[fname] = load_top_file(file)
        else:
            pairs[fname] = pd.concat([pairs[fname], load_top_file(file)])
    return pd.concat(pairs.values(), keys=pairs.keys())


def pvalue_top(top: TopPlot):
    return chi2.sf(chisquare_top(top), 1)


def chisquare_top(top: TopPlot):
    mask = top.xdata() > 0
    return np.sum((top.ydata()[mask] - top.xdata()[mask]) ** 2 / top.xdata()[mask])

    # chi2 = chisquare(top.ydata()[mask], top.xdata()[mask])
    # return chi2


# def analyze_top(top):


def smoothness_test(folder):
    raise Exception("Not implemented")


def chisquare_tops(folder, p_min=0.33):
    for file in glob.glob(folder + "/*.top"):
        tops = ptd.read(file)
        for top in tops:
            p = pvalue_top(top)
            if p < p_min:
                print("p=", p)
                top.show()


def btlgrid_tops(folder, p_min=0.95):
    for file in glob.glob(folder + "/*btlgrid.top"):
        tops = ptd.read(file)
        for top in tops:
            p = pvalue_top(top)
            if p < p_min:
                print("p=", p)
                top.show()
