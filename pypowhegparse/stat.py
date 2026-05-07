import re
import glob
import os
import pandas as pd


STAT_RE = re.compile(r"^(pwg[a-zA-Z0-9-]*?)(?:-(\d{4}))?-stat\.dat$")


def _stat_files(folder, file_filter=None):
    files = sorted(glob.glob(folder + "/pwg*stat.dat"))
    if file_filter is not None:
        files = [file for file in files if file_filter(file)]
    return files


def _stat_file_info(file):
    match = STAT_RE.search(os.path.basename(file))
    if match is None:
        raise ValueError(f"unexpected stat file name: {file}")
    fname = match.group(1)
    if fname.endswith("-"):
        fname = fname[:-1]
    number = int(match.group(2) or "1")
    return f"{fname}-stat", number


def load_stat_file(file):
    pairs = []
    _, number = _stat_file_info(file)
    with open(file) as topo_file:
        for line in topo_file:
            pair = re.compile(r"(.*?)\s+([0-9\.Ee\+-]+)\s+\+-\s+([0-9\.Ee\+-]+)")
            g = pair.search(line)
            if g is not None:
                pairs.append((g.group(1).strip(), float(g.group(2))))
                pairs.append((g.group(1).strip() + "+-stat", float(g.group(3))))
            else:
                pair = re.compile(r"(.*?)\s+([0-9\.Ee\+-]+)")
                g = pair.search(line)
                if g is not None:
                    pairs.append((g.group(1), float(g.group(2))))
    return pd.DataFrame.from_records(
        pairs, columns=["proc", number], index="proc"
    ).transpose()


def load_stat_folder(folder, file_filter=None):
    pairs = {}
    for file in _stat_files(folder, file_filter=file_filter):
        fname, _ = _stat_file_info(file)
        if fname not in pairs.keys():
            pairs[fname] = load_stat_file(file)
        else:
            pairs[fname] = pd.concat([pairs[fname], load_stat_file(file)])
    return pd.concat(pairs.values(), keys=pairs.keys())
