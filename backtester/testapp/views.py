"""Views of backtester app
"""
import csv
import gc
import glob
import json
import logging
import os
import requests
from datetime import datetime, timedelta
from io import StringIO

import pandas as pd
from django.conf import settings as djangoSettings
from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from google.cloud import storage

from .csv_concat import concat_new_csvs
from .execute_backtest import execute_backtest, compare
from .get_prefixes import get_prefixes
from .zipline_commands import *



# Get an instance of a logger
logger = logging.getLogger('django')

# available trading pairs
assets_list = ['BTCUSDT','ETHBTC','XLMBTC','XRPBTC']

# css class for rendering dataframe to html string
df_class = 'dfstyle'

# for using Google Cloud Storage
GS_CRAWLERDATA_BUCKET_NAME = 'idp_crypto'
GS_ASSETS_BUCKET_NAME = 'idp_backtest_assets'
# GS_RESULTS_BUCKET_NAME = 'idp_backtest_results'  # deprecated

# for saving *aggregates.csv
aggr_path = djangoSettings.MEDIA_ROOT
# record file of ingest time
record_name = 'last_ingest.txt'
record_file = aggr_path+record_name



# Create your views here.
def index(request):
	"""Index page of backtester."""

	if not os.path.exists(aggr_path):
		os.makedirs(aggr_path)

	# read the latest date with complete ingestion from file
	try:
		with open(record_file,'r') as record:
			max_to = record.read()
		max_to = max_to[:len('YYYY-MM-DD')]
		max_to = datetime.strptime(max_to, '%Y-%m-%d')-timedelta(days=1)
	except:
		try:
			# retrieve latest ingest date from GCS
			client = storage.Client()
			bucket = client.get_bucket(GS_ASSETS_BUCKET_NAME)
			fblob = bucket.get_blob(record_name)
			fblob.download_to_filename(record_file)

			with open(record_file,'r') as record:
				max_to = record.read()
			max_to = max_to[:len('YYYY-MM-DD')]
			max_to = datetime.strptime(max_to, '%Y-%m-%d')-timedelta(days=1)
		except:
			logger.exception('Cannot read last ingest or convert to datetime')
			error_message = ('Cannot get correct available time range '
						'due to network issue. Please try to refresh the page.')
			# set max_to as yesterday
			max_to = datetime.utcnow().date()-timedelta(days=1)
	
	# max_from should be one day earlier than max_to
	max_from = max_to-timedelta(days=1)

	max_to_str = max_to.strftime('%Y-%m-%d')
	max_from_str = max_from.strftime('%Y-%m-%d')

	# will be used to validate dates in processing view
	request.session['max_to'] = max_to_str
	request.session['max_from'] = max_from_str

	context = {'assets': assets_list, 
				'max_to': max_to_str,
				'max_from': max_from_str}

	if 'error_message' in request.session:
		context['error_message'] = request.session['error_message']
		del request.session['error_message']

	# from django.template import loader
	# return HttpResponse(loader.get_template('testapp/index.html').render(context, request))
	return render(request, 'testapp/index.html', context)



def ingest(request):
	"""Data (collection and) ingestion. 
	Run by user manually after starting the instance every time.
	"""
	
	# path for saving *aggregates.csv
	if not os.path.exists(aggr_path):
		os.makedirs(aggr_path)
	# path of old asset price files
	arranged_path = os.path.join(aggr_path, 'arranged/minute/')
	if not os.path.exists(arranged_path):
		os.makedirs(arranged_path)
	# path for data ingestion
	ingest_path = os.path.join(aggr_path, 'arranged/')
	# data bundle name. In case change, also change bundle_name in execute_backtest.py
	bname = 'csvdir'

	# client for GCS
	client = storage.Client()


	# retrieve latest ingest time from GCS
	try:
		bucket = client.get_bucket(GS_ASSETS_BUCKET_NAME)
		fblob = bucket.get_blob(record_name)
		fblob.download_to_filename(record_file)

		with open(record_file,'r') as record:
			# time of last ingestion, UTC
			starttime = record.read()
		# remove possible line break char
		starttime = starttime[:len('YYYY-MM-DD HH:MM:SS')]
	except:
		logger.exception('Cannot read last ingest time from file correctly')
		return HttpResponse('Error: Connection failed when '
					'trying to access Google Cloud Storage. Please try again.')
	
	# get and ingest data from starttime to endtime
	starttimestamp = datetime.strptime(starttime, '%Y-%m-%d %H:%M:%S')
	endtimestamp = datetime.utcnow()  # actual time
	endtime = endtimestamp.date().strftime('%Y-%m-%d')+' 00:20:00'

	# last ingestion was less than 1 day ago
	if endtimestamp - starttimestamp < timedelta(days=1):
		# check if there is ingestion, if yes, return
		if check_not_empty(bname):
			return HttpResponse('Data is already up to date')

		# if no, check if there are asset files, if no, download them
		download_list = [asset for asset in assets_list 
						if not os.path.isfile(arranged_path+asset+'.csv')]
		try:
			bucket = client.get_bucket(GS_ASSETS_BUCKET_NAME)
			for symbol in download_list:
				fblob = bucket.get_blob(symbol+'.csv')
				fblob.download_to_filename(arranged_path+symbol+'.csv')
		except requests.exceptions.ChunkedEncodingError:
			logger.exception('Network fails')
			return HttpResponse('Error: Connection failed. '
							'Please refresh the page and try to ingest again.')
		except:
			logger.exception('Cannot get assets data from Google Cloud Storage')
			return HttpResponse('Error: Cannot get pricing data from Cloud Storage bucket '
						+GS_ASSETS_BUCKET_NAME)
		
		# do the ingestion, return
		stdout,stderr = run_ingest(ingest_path, bname)
		stdout = stdout.decode("utf-8")
		logger.info(stdout)
		if stderr is not None:
			stderr = stderr.decode("utf-8")
			if stderr != "":
				logger.warning(stderr)
				# return HttpResponse(status=500)  # Internal Server Error, cannot ingest
				# return HttpResponse('Error: Cannot finish ingestion.')
		return HttpResponse('Ingestion completed. Please refresh the page.')

	# else: get new data and ingest
	logger.info('Attempt to ingest data from '+starttime+' to '+endtime)

	try:
		# set bucket to crawler data bucket
		bucket = client.get_bucket(GS_CRAWLERDATA_BUCKET_NAME)
		# get all possible prefixes of files collected between starttime and endtime
		prefixes = get_prefixes(starttime, end=endtime)
		aggr_names = []
		for prefix in prefixes:
			# logger.info(prefix)
			# look up files in bucket using prefix to speed up searching
			fblobs = bucket.list_blobs(prefix=prefix)
			# download *aggregates.csv
			for fblob in fblobs:
				if fblob.name.endswith('aggregates.csv'):
					fblob.download_to_filename(aggr_path+fblob.name)
					aggr_names.append(fblob.name)
	except requests.exceptions.ChunkedEncodingError:
		logger.exception('Network fails')
		return HttpResponse('Error: Connection failed. '
						'Please refresh the page and try to ingest again.')
	except:
		logger.exception('Cannot get crawler data from Google Cloud Storage')
		# return HttpResponse(status=502)  # Bad Gateway  # set to 500 to get notified
		return HttpResponse('Error: Cannot get crawler data from Cloud Storage bucket '
						+GS_CRAWLERDATA_BUCKET_NAME)

	logger.info('Downloading completed')

	# current working directory
	cwd = os.getcwd()
	
	# data preparation
	try:
		concat_new_csvs(aggr_path, aggr_names, arranged_path, symbols=assets_list)
	except requests.exceptions.ChunkedEncodingError:
		logger.exception('Network fails')
		return HttpResponse('Error: Connection failed. '
						'Please refresh the page and try to ingest again.')
	except:
		logger.exception('Cannot concat new csvs')
		return HttpResponse('Error in data preparation. '
						'Please refresh the page and try to ingest again.')
	logger.info('Data preparation completed')

	os.chdir(cwd)
	
	# # clean old data ingestion
	# _, stderr = run_clean(bname, 'after', '2019-05-20')
	# if stderr is not None:
	# 	stderr = stderr.decode("utf-8")
	# 	if stderr != "":
	# 		logger.warning(stderr)
	
	stdout,stderr = run_ingest(ingest_path, bname)
	stdout = stdout.decode("utf-8")
	logger.info(stdout)
	if stderr is not None:
		stderr = stderr.decode("utf-8")
		if stderr != "":
			logger.warning(stderr)
			# return HttpResponse('Error: Cannot finish ingestion.')

	try:
		with open(record_file,'w') as record:
			print(endtime, file=record)
		logger.info('Writing last ingest time to file completed')
	except:
		logger.exception('Cannot write last ingest time to file')

	try:
		# rewrite new ingest time to GCS
		bucket = client.get_bucket(GS_ASSETS_BUCKET_NAME)
		fblob = bucket.blob(record_name)
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

	msg = 'Ingestion of data from '+starttime+' to '+endtime+' completed'
	logger.info(msg)
	
	# force the Garbage Collector to release unreferenced memory
	gc.collect()

	return HttpResponse('Ingestion completed. Please refresh the page.')



def getdata(request):
	"""Download ingested data file."""

	if 'pair' not in request.GET:
		return HttpResponseRedirect(reverse('testapp:index'))

	asset = request.GET['pair']
	asset_data = aggr_path+'arranged/minute/'+asset+'.csv'

	try:
		with open(asset_data, 'rb') as data:
			response = HttpResponse(data.read(), content_type='text/csv')
			response['Content-Disposition'] = 'attachment; filename='+asset+'.csv'
			return response
	except:
		if not os.path.isfile(asset_data):
			if asset not in assets_list:
				error_message = 'Requested trading pair is not available.'
			else:
				error_message = 'File does not exist. Please ingest data before downloading.'
		else:
			error_message = 'Error in reading data.'
		request.session['error_message'] = error_message
		return HttpResponseRedirect(reverse('testapp:index'))



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

		response = HttpResponse(fstring, content_type='text/csv')
		response['Content-Disposition'] = 'attachment; filename="'+fname+'"'
		return response

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

	# validate dates: format, range, end date is larger than start date
	start_date = request.POST['from']
	try:
		val_from = datetime.strptime(start_date, '%Y-%m-%d')
	except ValueError:
		error_message = 'Incorrect start date format, should be YYYY-MM-DD.'
		request.session['error_message'] = error_message
		return HttpResponseRedirect(reverse('testapp:index'))
	max_from = datetime.strptime(request.session['max_from'], '%Y-%m-%d')
	min_from = datetime(2018, 10, 24)
	if not min_from <= val_from <= max_from:
		error_message = 'Invalid start date. Please check the valid range in the calendar.'
		request.session['error_message'] = error_message
		return HttpResponseRedirect(reverse('testapp:index'))

	end_date = request.POST['to']
	try:
		val_to = datetime.strptime(end_date, '%Y-%m-%d')
	except ValueError:
		error_message = 'Incorrect end date format, should be YYYY-MM-DD.'
		request.session['error_message'] = error_message
		return HttpResponseRedirect(reverse('testapp:index'))
	max_to = datetime.strptime(request.session['max_to'], '%Y-%m-%d')
	min_to = datetime(2018, 10, 25)
	if not min_to <= val_to <= max_to:
		error_message = 'Invalid end date. Please check the valid range in the calendar.'
		request.session['error_message'] = error_message
		return HttpResponseRedirect(reverse('testapp:index'))

	if not val_from < val_to:
		error_message = 'Start date should be earlier than end date.'
		request.session['error_message'] = error_message
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
				request.session['error_message'] = error_message
				return HttpResponseRedirect(reverse('testapp:index'))
		else:  # for now refuse file > 5 MB
			error_message = "Single file should not be larger than 5 MB"
			request.session['error_message'] = error_message
			return HttpResponseRedirect(reverse('testapp:index'))
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
			# perf : [res_overview, graph_div, daily_details, export_data, duration]
			# list : [dict, string(html_div), pd.DataFrame, pd.DataFrame, string]
			perf = execute_backtest(start_date, end_date, init_capital, trading_pair, 
								commission_method, commission_cost, trade)
		except (FileNotFoundError, ValueError) as e:
			error_message = "Cannot complete backtest for strategy {0}.".format(idx+1)
			logger.exception(error_message)
			suggestion = (" There may be something wrong with data ingestion. "
					"Please refresh the page and try to ingest again.")
			request.session['error_message'] = error_message + suggestion
			return HttpResponseRedirect(reverse('testapp:index'))

		except:
			error_message = "Cannot complete backtest for strategy {0}. ".format(idx+1)
			logger.exception(error_message)
			suggestion = ("Please visit "
					"https://console.cloud.google.com/appengine/versions?"
					"project=cryptos-211011&serviceId=backtester&versionssize=50"
					" to restart the server and then try to ingest data again.")
			request.session['error_message'] = error_message + suggestion
			return HttpResponseRedirect(reverse('testapp:index'))

		# render export_data dataframe to json string to store in session
		# this string can be rendered back to original dataframe for downloading purpose
		exp_list.append(perf[3].to_json())

		# render two dataframes to html strings to store in session
		perf[2] = perf[2].to_html(classes=df_class)  #, max_rows=50)  # daily_details
		perf[3] = perf[3].to_html(classes=df_class)  #, max_rows=50)  # export_data
		perf_list.append(perf)  # [res_overview,graph_div,daily_details,export_data,duration]
		
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

	gc.collect()

	# Redirect to results display page
	return HttpResponseRedirect(reverse('testapp:results'))