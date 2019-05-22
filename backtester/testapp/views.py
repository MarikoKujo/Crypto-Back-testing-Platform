from django.conf import settings as djangoSettings
from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect
from django.template import loader
from django.urls import reverse
import logging

from io import StringIO
from .execute_backtest import execute_backtest, compare
from .get_prefixes import get_prefixes
from .csv_concat import concat_new_csvs
from datetime import datetime, timedelta
from google.cloud import storage

import csv
import pandas as pd
import json
import subprocess, glob, os


# Get an instance of a logger
logger = logging.getLogger('django')

# available trading pairs
assets_list = ['BTCUSDT','ETHBTC','XLMBTC','XRPBTC']

# css class for rendering dataframe to html string
df_class = 'dfstyle'

# for using Google Cloud Storage
GS_CRAWLERDATA_BUCKET_NAME = 'idp_crypto'
GS_RESULTS_BUCKET_NAME = 'idp_backtest_results'
GS_ASSETS_BUCKET_NAME = 'idp_backtest_assets'

# for saving *aggregates.csv
aggr_path = djangoSettings.MEDIA_ROOT
# record file of ingest time
record_file = aggr_path+'last_ingest.txt'



# Create your views here.
def index(request):
	"""Index page of backtester."""

	if not os.path.exists(aggr_path):
		os.makedirs(aggr_path)

	# read the latest date with complete ingestion from file
	try:
		with open(record_file,'r') as record:
			max_to = record.read()
		max_to = max_to[:len('2019-05-01')]
		max_to = datetime.strptime(max_to, '%Y-%m-%d')-timedelta(days=1)
	except:
		try:
			# retrieve latest ingest date from GCS
			client = storage.Client()
			bucket = client.get_bucket(GS_ASSETS_BUCKET_NAME)
			fblob = bucket.get_blob('last_ingest.txt')
			fblob.download_to_filename(record_file)

			with open(record_file,'r') as record:
				max_to = record.read()
			max_to = max_to[:len('2019-05-01')]
			max_to = datetime.strptime(max_to, '%Y-%m-%d')-timedelta(days=1)
		except:
			logger.exception('Cannot read last ingest or convert to datetime')
			# set max_to as yesterday
			max_to = datetime.utcnow().date()-timedelta(days=1)
	
	# max_from should be one day earlier than max_to
	max_from = max_to-timedelta(days=1)

	context = {'assets': assets_list, 
				'max_to': max_to.strftime('%Y-%m-%d'),
				'max_from': max_from.strftime('%Y-%m-%d')}
	# return HttpResponse(loader.get_template('testapp/index.html').render(context, request))
	return render(request, 'testapp/index.html', context)


def ingest(request):
	"""Run as a cron job at 00:35 every day.
	Set cron jobs in cron.yaml file.
	See:
	cloud.google.com/appengine/docs/flexible/python/scheduling-jobs-with-cron-yaml
	"""
	
	if not os.path.exists(aggr_path):
		os.makedirs(aggr_path)

	try:
		# read start time from file
		with open(record_file,'r') as record:
			# time of last ingestion, UTC
			starttime = record.read()
		# remove possible line break char
		starttime = starttime[:len('2019-05-01 00:20:00')]
	except:
		# retrieve latest ingest date from GCS
		try:
			client = storage.Client()
			bucket = client.get_bucket(GS_ASSETS_BUCKET_NAME)
			fblob = bucket.get_blob('last_ingest.txt')
			fblob.download_to_filename(record_file)

			with open(record_file,'r') as record:
				# time of last ingestion, UTC
				starttime = record.read()
			# remove possible line break char
			starttime = starttime[:len('2019-05-01 00:20:00')]
		except:
			logger.exception('Cannot read last ingest time from file correctly')
			# set start time as yesterday, 00:20:00
			starttime = (datetime.utcnow().date()-timedelta(days=1)).strftime('%Y-%m-%d')
			starttime = starttime+' 00:20:00'
	
	# time of now, UTC
	endtime = datetime.utcnow().date().strftime('%Y-%m-%d')+' 00:20:00'

	logger.info('Attempt to ingest data from '+starttime+' to '+endtime)

	try:
		client = storage.Client()
		# set bucket to crawler data bucket
		bucket = client.get_bucket(GS_CRAWLERDATA_BUCKET_NAME)
	except:
		logger.exception('Cannot get crawler data bucket from Google Cloud Storage')
		return HttpResponse(status=502)  # Bad Gateway  # set to 500 to get notified
	# get all possible prefixes of files collected between starttime and endtime
	prefixes = get_prefixes(starttime, end=endtime)
	for prefix in prefixes:
		logger.info(prefix)
		# look up files in bucket using prefix to speed up searching
		fblobs = bucket.list_blobs(prefix=prefix)
		# download *aggregates.csv
		for fblob in fblobs:
			if fblob.name.endswith('aggregates.csv'):
				fblob.download_to_filename(aggr_path+fblob.name)

	logger.info('Downloading completed')

	# current working directory
	cwd = os.getcwd()
	# path of old asset price files
	arranged_path = os.path.join(aggr_path, 'arranged/minute/')
	if not os.path.exists(arranged_path):
		os.makedirs(arranged_path)
	# path for data ingestion
	ingest_path = os.path.join(aggr_path, 'arranged/')
	
	# data preparation
	concat_new_csvs(aggr_path, arranged_path, symbols=assets_list)
	logger.info('Data preparation completed')

	os.chdir(cwd)

	# clean old data and ingest new data
	my_env = os.environ.copy()
	my_env["CSVDIR"] = ingest_path
	# data bundle name. In case change, also change bundle_name in execute_backtest.py
	bname = 'csvdir'
	utc_today = datetime.utcnow().date().strftime('%Y-%m-%d')
	# for testing
	clean_cmd = ['zipline','clean','-b',bname,'--after','2019-05-18']
	# clean_cmd = ['zipline','clean','-b',bname,'--before',utc_today]
	ingest_cmd = ['zipline','ingest','-b',bname]

	# clean old ingestion
	out = subprocess.Popen(clean_cmd, 
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE)
	_, stderr = out.communicate()
	if (stderr is not None) and (stderr != ""):
		logger.warning(stderr)
	# do new ingestion
	out = subprocess.Popen(ingest_cmd,
			env=my_env,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE)
	stdout,stderr = out.communicate()
	logger.info(stdout)
	if (stderr is not None) and (stderr != ""):
		logger.error(stderr)
		# return HttpResponse(status=500)  # Internal Server Error

	try:
		with open(record_file,'w') as record:
			# print(utc_today+' 00:20:00', file=record)
			print(endtime, file=record)
		logger.info('Writing last ingest time to file completed')
	except:
		logger.exception('Cannot write last ingest time to file')

	try:
		# rewrite new ingest time to GCS
		client = storage.Client()
		bucket = client.get_bucket(GS_ASSETS_BUCKET_NAME)
		fblob = bucket.blob('last_ingest.txt')
		fblob.upload_from_filename(record_file)
	except:
		logger.exception('Cannot upload last ingest to GCS')


	# delete downloaded *aggregates.csv files
	os.chdir(aggr_path)
	try:
		for f in glob.glob('*aggregates.csv'):
			os.remove(f)
		logger.info('*aggregates.csv files removed')
	except:
		logger.exception('Cannot remove *aggregates.csv files')

	os.chdir(cwd)

	logger.info('Ingestion of data from '+starttime+' to '+endtime+' completed')
	return HttpResponse(msg)


def export(request):
	"""Export backtest result to .csv file and store in Google Cloud Storage."""
	if request.method == 'POST':
		
		# generate file name
		namestr = request.POST['expname']
		timestr = datetime.now().strftime("%Y%m%d-%H%M%S")
		fname = timestr+'_'+namestr+'.csv'

		try:  # get file string for exporting
			exp_list = request.session['exp_list']
			expidx = int(request.POST['expidx'])
			dfs_json = exp_list[expidx]
			dfs = pd.read_json(dfs_json)
			fstring = dfs.to_csv(index_label='date')
		except:
			logger.exception('Cannot convert to csv file')
			return HttpResponse('Error: Cannot convert to csv file.')

		try:  # export file to storage bucket
			client = storage.Client()
			bucket = client.get_bucket(GS_RESULTS_BUCKET_NAME)
			fblob = bucket.blob(fname)
			fblob.upload_from_string(fstring, content_type='text/csv')
		except:
			logger.exception('Cannot upload to backtest results bucket')
			return HttpResponse('Error: Cannot upload to Google Cloud Storage.')

		return HttpResponse(fname+' successfully exported.')

	# ideally this should not be reached
	return HttpResponseRedirect(reverse('testapp:results'))


def results(request):
	"""Display backtest results."""
	if 'perf' not in request.session:
		return HttpResponseRedirect(reverse('testapp:index'))

	context = {'assets': assets_list}
	context['perf'] = request.session['perf']
	context['compare'] = request.session['compare']
	context['start_date'] = request.session['start_date']
	context['end_date'] = request.session['end_date']
	context['init_capital'] = request.session['init_capital']
	context['trading_pair'] = request.session['trading_pair']
	context['filename_list'] = request.session['filename_list']

	return render(request, 'testapp/result.html', context)


def processing(request):
	"""Run backtests."""
	if request.method != 'POST':  # this page should not be accessed without POST data
		return HttpResponseRedirect(reverse('testapp:index'))

	trades_list = []
	filename_list = []
	trades = {}
	# read uploaded csv files and convert to dicts
	for afile in request.FILES.getlist('strategies'):
		if not afile.multiple_chunks():
			try:  # read trading signals and convert to a dict
				file_text = afile.read().decode('utf-8')
				reader = csv.reader(StringIO(file_text), delimiter=',')
				signals_list = list(reader)
				trades = dict([(pd.to_datetime(sig[0]).tz_localize('UTC'), 
							float(sig[1])) for sig in signals_list])
				
			except KeyboardInterrupt:  # just in case
				return HttpResponseRedirect(reverse('testapp:index'))
			except:  # cannot convert csv file to dict correctly
				error_message = 'Invalid csv: ' + afile.name
				context = {'assets': assets_list, 'error_message': error_message}
				return render(request, 'testapp/index.html', context)
		else:  # for now refuse file > 5 MB
			error_message = "Single file should not be larger than 5 MB"
			context = {'assets': assets_list, 'error_message': error_message}
			return render(request, 'testapp/index.html', context)
		# else: 
		#	deal with file larger than 5M here, maybe need to write to disk in chunks
		#	try to readline and feed into StringIO using loop? avoid disk manipulation

		# chop '.csv' suffix from filename before displaying
		if afile.name.endswith('.csv'):
			filename_list.append(afile.name[:-len('.csv')])
		else:
			filename_list.append(afile.name)
		trades_list.append(trades)

	# get other parameters for backtesting
	# these params are common for all strategy files
	start_date = request.POST['from']
	end_date = request.POST['to']
	init_capital = request.POST['capital']
	trading_pair = request.POST['tradingpair']
	commission_method = request.POST['comm']
	commission_cost = request.POST['commamount']
	
	# display non-truncated dataframe in html
	pd.set_option('display.max_colwidth', -1)

	# get backtest results and performance analysis
	exp_list = []
	perf_list = []
	res_overview_list = []
	for idx,trade in enumerate(trades_list):
		try:
			# perf : [res_overview, graph_div, daily_details, export_data]
			# list : [dict, string(html_div), pd.DataFrame, pd.DataFrame]
			perf = execute_backtest(start_date, end_date, init_capital, trading_pair, 
								commission_method, commission_cost, trade)
		except:
			error_message = "Cannot complete backtest for strategy {0}".format(idx)
			logger.exception(error_message)
			context = {'assets': assets_list, 'error_message': error_message}
			return render(request, 'testapp/index.html', context)

		# render export_data dataframe to json string to store in session
		# this string can be rendered back to original dataframe for downloading purpose
		exp_list.append(perf[3].to_json())

		# render two dataframes to html strings to store in session
		perf[2] = perf[2].to_html(classes=df_class, max_rows=50)  # daily_details
		perf[3] = perf[3].to_html(classes=df_class, max_rows=50)  # export_data
		perf_list.append(perf)  # [res_overview, graph_div, daily_details, export_data]
		
		# will be used as param for compare() for results comparison
		res_overview_list.append(perf[0])


	# get comparison of overview results from all strategies
	compare_results = compare(res_overview_list, filename_list)
	# render dataframe to html string to store in session json
	compare_results = compare_results.to_html(classes=df_class)

	# save all results to request.session
	request.session['perf'] = perf_list
	request.session['compare'] = compare_results
	request.session['exp_list'] = exp_list
	# save params to request.session
	request.session['start_date'] = start_date
	request.session['end_date'] = end_date
	request.session['init_capital'] = init_capital
	request.session['trading_pair'] = trading_pair
	request.session['filename_list'] = filename_list

	# Redirect to results display page
	return HttpResponseRedirect(reverse('testapp:results'))