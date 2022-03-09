import glob, os
import numpy as np
import pytopdrawer as ptd
from scipy.stats import chisquare


def smoothness_test(folder):
	raise Exception("Not implemented")

def chisquare_tops(folder):
	for file in glob.glob(folder + "/*.top"):
		tops = ptd.read(file)
		for top in tops:
			mask = top.xdata() >0 
			chi2 = chisquare(top.ydata()[mask], top.xdata()[mask])
			if (chi2.pvalue < 0.95):
				top.show()
