import pypowhegparse as ppp

ppp.print_stats(".")

for s in ppp.inspect_warn_grep(".",2)[0]:
	print(s)

ppp.chisquare_tops(".")