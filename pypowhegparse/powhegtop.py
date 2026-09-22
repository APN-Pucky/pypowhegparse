#!/usr/bin/python3
import argparse
import math
import pytopdrawer
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("topfile", type=str, help="url/file/string")
    parser.add_argument(
        "-ns", "--noshow", action="store_true", help="do not show the plot"
    )
    parser.add_argument(
        "-ho", "--horizontal", action="store_true", help="horizontal layout"
    )
    parser.add_argument("-v", "--vertical", action="store_true", help="vertical layout")
    parser.add_argument("-s", "--size", type=int, help="size of the plot", default=4)
    parser.add_argument("-o", "--output", help="output file", type=str, default=None)
    parser.add_argument(
        "-t", "--text", action="store_true", help="print plots as text to stdout"
    )
    args = parser.parse_args()
    tops = pytopdrawer.read(args.topfile, True, False)
    # Text first so we get fast results
    if args.text:
        for top in tops:
            print(top)
    if args.output or not args.noshow:
        N = len(tops)
        cols = math.ceil(math.sqrt(N))  # Round up to ensure enough space
        rows = math.ceil(N / cols)  # Calculate rows based on columns
        if args.horizontal:
            rows = 1
            cols = N
        if args.vertical:
            rows = N
            cols = 1
        fig, axes = plt.subplots(
            rows, cols, figsize=(cols * args.size, rows * args.size), squeeze=False
        )
        axes = axes.flatten()
        for ti, top in enumerate(tops):
            top.plot(axes=axes[ti])
        for a in axes[N:]:
            a.set_visible(False)
        if args.output is not None:
            fig.savefig(args.output)
        if not args.noshow:
            plt.show()
