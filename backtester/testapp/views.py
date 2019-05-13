from django.conf import settings as djangoSettings
from django.shortcuts import get_object_or_404, render
from django.http import HttpResponse, HttpResponseRedirect
from django.template import loader
from django.urls import reverse

from io import StringIO
from .execute_backtest import execute_backtest, compare
from .get_prefixes import get_prefixes
from datetime import datetime
from google.cloud import storage

import csv
import pandas as pd
import json
import subprocess


# available trading pairs
assets_list = ['BTCUSDT','ETHBTC','XLMBTC','XRPBTC']

# css class for rendering dataframe to html string
df_class = 'dfstyle'

# for using Google Cloud Storage
GS_RESULTS_BUCKET_NAME = 'idp_backtest_results'
GS_CRAWLERDATA_BUCKET_NAME = 'idp_crypto'

# for saving #-aggregates.csv
aggr_path = djangoSettings.MEDIA_ROOT



# Create your views here.
def index(request):
	context = {'assets': assets_list}
	# return HttpResponse(loader.get_template('testapp/index.html').render(context, request))
	return render(request, 'testapp/index.html', context)

def ingest(request):
	# ingest!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
	# out = subprocess.Popen(['zipline','bundles'],
	# 			stdout=subprocess.PIPE,
	# 			stderr=subprocess.STDOUT)
	# stdout,stderr = out.communicate()
	# print(stdout)  # it works!

	# client = storage.Client()
	# bucket = client.get_bucket(GS_RESULTS_BUCKET_NAME)
	# fblob = bucket.get_blob('20190507-002944_file1.csv')

	# print(fblob.time_created) # timestamp in utc
	# print(fblob.name)
	# fblob.download_to_filename(aggr_path+'checkitout.csv')
	starttime = "2018-12-03 00:26:00"
	print(get_prefixes(starttime, end="2018-12-04 00:20:00"))
	
	return HttpResponse('lala')

def export(request):
	if request.method == 'POST':
		
		# !!!!!important: wrap things up with try-catch

		# generate file name
		namestr = request.POST['expname']
		timestr = datetime.now().strftime("%Y%m%d-%H%M%S")
		fname = timestr+'_'+namestr+'.csv'

		# # get file string for exporting
		# exp_list = request.session['exp_list']
		# expidx = int(request.POST['expidx'])
		# dfs_json = exp_list[expidx]
		# dfs = pd.read_json(dfs_json)
		# fstring = dfs.to_csv(index_label=False)

		# # export file to storage bucket
		# client = storage.Client()
		# bucket = client.get_bucket(GS_RESULTS_BUCKET_NAME)
		# fblob = bucket.blob(fname)
		# fblob.upload_from_string(fstring, content_type='text/csv')

		return HttpResponse(fname+' successfully exported.')

	# ideally this should not be reached
	return render(request, 'testapp/result.html', context)

def results(request):
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
		print(afile.name)
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
		# perf : [res_overview, graph_div, daily_details, export_data]
		# list : [dict, string(html_div), pd.DataFrame, pd.DataFrame]
		perf = execute_backtest(start_date, end_date, init_capital, trading_pair, 
							commission_method, commission_cost, trade)
		print('backtest and analysis %d done' % idx)

		# render export_data dataframe to json string to store in session
		# this string can be rendered back to original dataframe for downloading purpose
		exp_list.append(perf[3].to_json())

		# render two dataframes to html strings to store in session
		perf[2] = perf[2].to_html(classes=df_class)  # daily_details
		perf[3] = perf[3].to_html(classes=df_class)  # export_data
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

	
	return HttpResponseRedirect(reverse('testapp:results'))