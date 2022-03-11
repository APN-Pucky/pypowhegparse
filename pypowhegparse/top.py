import glob, os
import numpy as np
import pandas as pd
import re
import pytopdrawer as ptd
from pytopdrawer import TopPlot
from scipy.stats import chisquare
from scipy.stats import chi2

def load_top_plot(plot:TopPlot):
	pairs = [
		("plot",plot),
		("pvalue",pvalue_top(plot)),
		("chi2",chisquare_top(plot)),
	]
	return pd.DataFrame.from_records(pairs,columns=['title',plot.title.text],index="title").transpose()

def load_top_file(file):
	pairs={}
	for top in ptd.read(file):
		name = re.compile('(pwg[a-zA-Z0-9-]+?)(\d\d\d\d)?-([a-zA-Z0-9-]+?grid).top')
		g = name.search(file)
		if g is not None:
			fname = g.group(1)
			if fname[-1] == "-":
				fname = fname[0:-1]
			fname = fname + "-" + g.group(3)
			number = int(g.group(2))
		if number not in pairs.keys():
			pairs[number] = load_top_plot(top)
		else:
			pairs[number]=pairs[number].append(load_top_plot(top))
	return pd.concat(pairs.values(),keys =pairs.keys())

def load_top_folder(folder): # names
	pairs={}
	for file in glob.glob(folder + "/pwg*.top"):
		name = re.compile('(pwg[a-zA-Z0-9-]+?)(\d\d\d\d)?-([a-zA-Z0-9-]+?grid).top')
		g = name.search(file)
		if g is not None:
			fname = g.group(1)
			if fname[-1] == "-":
				fname = fname[0:-1]
			fname = fname + "-" + g.group(3)
			number = int(g.group(2))
		if fname not in pairs.keys():
			pairs[fname] = load_top_file(file)
		else:
			pairs[fname]=pairs[fname].append(load_top_file(file))
	return pd.concat(pairs.values(),keys =pairs.keys())

	
def pvalue_top(top:TopPlot):
	return chi2.sf(chisquare_top(top),1)
def chisquare_top(top:TopPlot):
	mask = top.xdata() >0 
	return np.sum((top.ydata()[mask]- top.xdata()[mask])**2/top.xdata()[mask])

	#chi2 = chisquare(top.ydata()[mask], top.xdata()[mask])
	# return chi2




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
