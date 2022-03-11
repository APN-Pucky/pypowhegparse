import glob, os
import numpy as np
import pytopdrawer as ptd
from pytopdrawer import TopPlot
from scipy.stats import chisquare

class TopPlotAnalizer:
	def __init__(self,tp:TopPlot):
		self.plot = tp
		self.chi2 = chisquare_top(tp)

class TopPlotsAnalizer:
	def __init__(self,file):
		self.tops = ptd.read(file)
		self.anas = [None]*len(self.tops)
		for i,top in enumerate(self.tops):
			self.anas[i] = TopPlotAnalizer(top)
	
def chisquare_top(top:TopPlot):
	mask = top.xdata() >0 
	chi2 = chisquare(top.ydata()[mask], top.xdata()[mask])
	return chi2




#def analyze_top(top):

def smoothness_test(folder):
	raise Exception("Not implemented")

def chisquare_tops(file):
	for file in glob.glob(folder + "/*.top"):
		tops = ptd.read(file)
		for top in tops:
			chi2 = chisquare_top(top)
			if (chi2.pvalue < 0.95):
				top.show()

def btlgrid_tops(folder):
	for file in glob.glob(folder + "/*btlgrid.top"):
		title = re.compile('(pwg-[a-zA-Z0-9-]+)-(\d*)-?btlgrid.top')

		tops = ptd.read(file)
		for top in tops:
			mask = top.xdata() >0 
			chi2 = chisquare(top.ydata()[mask], top.xdata()[mask])
			if (chi2.pvalue < 0.95):
				top.show()
