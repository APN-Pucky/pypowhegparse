import re
import glob
import os
import pandas as pd


COUNTER_RE = re.compile(r"^(pwgcounters[a-zA-Z0-9-]*?)(?:-(\d{4}))?\.dat$")


def _counter_files(folder, file_filter=None):
    files = sorted(glob.glob(folder + "/pwgcounters*.dat"))
    if file_filter is not None:
        files = [file for file in files if file_filter(file)]
    return files


def _counter_file_info(file):
    match = COUNTER_RE.search(os.path.basename(file))
    if match is None:
        raise ValueError(f"unexpected counter file name: {file}")
    fname = match.group(1)
    if fname.endswith("-"):
        fname = fname[:-1]
    number = int(match.group(2) or "1")
    return fname, number


def load_counter_file(file):
    pairs = []
    _, number = _counter_file_info(file)
    with open(file) as topo_file:
        for line in topo_file:
            pair = re.compile(r"(.*)=\s+([0-9\.Ee\+-]+)")
            g = pair.search(line)
            if g is not None:
                pairs.append((g.group(1).strip(), float(g.group(2))))
    return pd.DataFrame.from_records(
        pairs, columns=["proc", number], index="proc"
    ).transpose()


def load_counter_folder(folder, file_filter=None):
    pairs = {}
    for file in _counter_files(folder, file_filter=file_filter):
        fname, _ = _counter_file_info(file)
        if fname not in pairs.keys():
            pairs[fname] = load_counter_file(file)
        else:
            pairs[fname] = pd.concat([pairs[fname], load_counter_file(file)])
    return pd.concat(pairs.values(), keys=pairs.keys())
