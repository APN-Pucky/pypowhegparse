import pandas as pd

def multi_describe(ddf):
	pairs={}
	for f in ddf.index.get_level_values(0).unique():
		pairs[f] = ddf.xs(f).describe()
	return pd.concat(pairs.values(),keys=pairs.keys())