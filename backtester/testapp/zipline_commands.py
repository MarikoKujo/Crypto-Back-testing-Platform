import os
import subprocess

def run_ingest(ingest_path, bundle_name):
	my_env = os.environ.copy()
	my_env["CSVDIR"] = ingest_path

	ingest_cmd = ['zipline','ingest','-b',bundle_name]

	# do new ingestion
	out = subprocess.Popen(ingest_cmd,
			env=my_env,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE)

	return out.communicate()

def check_not_empty(bundle_name):
	"""Check if there is data ingestion in the given bundle."""
	check_cmd = ['zipline','bundles']
	out = subprocess.Popen(check_cmd, 
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE)
	stdout,_ = out.communicate()
	stdout = stdout.decode("utf-8")
	if ((stdout is not None) and (bundle_name in stdout) 
			and (bundle_name+' <no ingestions>' not in stdout)):
		return True
	else:
		return False

def run_clean(bundle_name, b_or_a, date):
	# clean_cmd = ['zipline','clean','-b',bundle_name,'--after','2019-05-18']
	clean_cmd = ['zipline','clean','-b',bundle_name,'--'+b_or_a,date]
	# clean old ingestion
	out = subprocess.Popen(clean_cmd, 
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE)
	return out.communicate()