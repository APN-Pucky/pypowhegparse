import re
import glob
import os
import pandas as pd


def _stat_files(folder, file_filter=None):
    files = sorted(glob.glob(folder + "/pwg*stat.dat"))
    if file_filter is not None:
        files = [file for file in files if file_filter(file)]
    return files


def load_stat_file(file):
    pairs = []
    name = re.compile("(pwg[a-zA-Z0-9-]+?)(\d\d\d\d)?-stat.dat")
    g = name.search(os.path.basename(file))
    if g is not None:
        fname = g.group(1)
        number = int(g.group(2))
    with open(file) as topo_file:
        for line in topo_file:
            pair = re.compile("(.*?)\s+([0-9\.Ee\+-]+)\s+\+-\s+([0-9\.Ee\+-]+)")
            g = pair.search(line)
            if g is not None:
                pairs.append((g.group(1).strip(), float(g.group(2))))
                pairs.append((g.group(1).strip() + "+-stat", float(g.group(3))))
            else:
                pair = re.compile("(.*?)\s+([0-9\.Ee\+-]+)")
                g = pair.search(line)
                if g is not None:
                    pairs.append((g.group(1), float(g.group(2))))
    return pd.DataFrame.from_records(
        pairs, columns=["proc", number], index="proc"
    ).transpose()


def load_stat_folder(folder, file_filter=None):
    pairs = {}
    for file in _stat_files(folder, file_filter=file_filter):
        name = re.compile("(pwg[a-zA-Z0-9-]+?)(\d\d\d\d)?-stat.dat")
        g = name.search(file)
        if g is not None:
            fname = g.group(1)
            if fname[-1] == "-":
                fname = fname[0:-1]
            fname = fname + "-stat"
            number = int(g.group(2))
            if fname not in pairs.keys():
                pairs[fname] = load_stat_file(file)
            else:
                pairs[fname] = pd.concat([pairs[fname], load_stat_file(file)])
    return pd.concat(pairs.values(), keys=pairs.keys())
