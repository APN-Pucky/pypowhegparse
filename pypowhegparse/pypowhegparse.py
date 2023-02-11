#!/usr/bin/python3
import argparse
import pytopdrawer
import pypowhegparse as ppp
import numpy as np
import sys 
from smpl import plot


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('-f','--folder', type=str,help="url/file/string",default=".")
	parser.add_argument('-w','--warn', type=int,help="level of warnings to fail",default=3)
	parser.add_argument('-wt','--warn-threshold', type=int,help="number of warnings to fail",default=0)
	parser.add_argument('-ic','--ignore-colour', type=bool,default=False)
	parser.add_argument('-is','--ignore-spin', type=bool,default=False)

	args = parser.parse_args()
	exit_code = 0

	err = ppp.error_colour_grep(args.folder)
	if len(err)> 0 and not args.ignore_colour:
		for s in err:
			print(s)
		exit_code=1

	err = ppp.error_spin_grep(args.folder)
	if len(err)> 0 and not args.ignore_spin:
		for s in err:
			print(s)
		exit_code=1

	warn = ppp.inspect_warn_grep(args.folder,args.warn)
	if len(warn) > args.warn_threshold:
		print("Checklimits warning stats:")
		print("-"*50)
		ppp.print_stats(args.folder)
		print("-"*50)
		print()
		print("WWWARN:")
		print("-"*50)

		for a in warn:
			print()
			for s in a:
				print(s)
			print()
		print("-"*50)
	sys.exit(exit_code)

main()