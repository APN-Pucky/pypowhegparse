import re
import glob, os
import pandas as pd

def load_counter_file(file):
	pairs=[]
	name = re.compile('(pwgcounters[a-zA-Z0-9-]+?)(\d\d\d\d)?.dat')
	g = name.search(os.path.basename(file))
	if g is not None:
		fname = g.group(1)
		number = int(g.group(2))
	with open(file) as topo_file:
		for line in topo_file:
			pair = re.compile('(.*)=\s+([0-9\.Ee\+-]+)')
			g = pair.search(line)
			if g is not None:
				pairs.append((g.group(1).strip(),float(g.group(2))))
	return pd.DataFrame.from_records(pairs,columns=['proc',number],index="proc").transpose()

def load_counter_folder(folder):
	pairs={}
	for file in glob.glob(folder + "/pwgcounters*.dat"):
		name = re.compile('(pwgcounters[a-zA-Z0-9-]+?)(\d\d\d\d)?.dat')
		g = name.search(file)
		if g is not None:
			fname = g.group(1)
			if fname[-1] == "-":
				fname = fname[0:-1]
			number = int(g.group(2))
			if fname not in pairs.keys():
				pairs[fname] = load_counter_file(file)
			else:
				pairs[fname]=pd.concat([pairs[fname],load_counter_file(file)])
	return pd.concat(pairs.values(),keys =pairs.keys())

