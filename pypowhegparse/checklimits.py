import subprocess

def inspect_warn_loop(folder,level=1):
	raise Exception ("Unimplemented")

def error_colour_grep(folder):
	p = subprocess.run("grep -H colour check fails " +folder + "/*checklimits*", shell=True, capture_output=True)
	lines = p.stdout.split(b'\n')
	return lines

def error_spin_grep(folder):
	p = subprocess.run("grep -H spin correlated amplitude wrong " +folder + "/*checklimits*", shell=True, capture_output=True)
	lines = p.stdout.split(b'\n')
	return lines
	

def inspect_warn_grep(folder,level=1):
	after = 10
	before = 10
	sumd = before + after
	arg = []
	p = subprocess.run("grep -A "+str(after)+" -B "+str(before)+" -H " +"W"*level + "ARN " +folder + "/*checklimits*", shell=True, capture_output=True)
	lines = p.stdout.split(b'\n')
	return [[lines[j*sumd+i] for i in range(sumd)] for j in range(int(len(lines)/sumd))]



def search_for_warn_loop(folder,level=1):
	raise Exception ("Unimplemented")

def search_for_warn_grep(folder,level=1):
	arg = []
	p = subprocess.run("grep " +"W"*level + "ARN " +folder + "/*checklimits*", shell=True, capture_output=True)
	return p.stdout.split(b'\n')


def search_for_warn(folder,level=1,grep=True):
	if grep:
		return search_for_warn_grep(folder,level)
	else:
		return search_for_warn_loop(folder,level)

def count_warn(folder,level=1,grep=True):
	if grep:
		return len(search_for_warn_grep(folder,level))-1
	else:
		return len(search_for_warn_loop(folder,level))-1

def print_stats(folder,grep=True):
	print("#WARN    = ", count_warn(folder ,1))
	print("#WWARN   = ", count_warn(folder,2))
	print("#WWWARN  = ", count_warn(folder ,3))
	print("#WWWWARN = ", count_warn(folder ,4))

def print_warn_grep(folder,level=3):
	for a in inspect_warn_grep(folder,3):
		print()
		for s in a:
			print(s)
		print()