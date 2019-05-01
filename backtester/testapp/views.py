from django.shortcuts import get_object_or_404, render
from django.http import HttpResponseRedirect
from django.template import loader
from django.urls import reverse

from io import StringIO
from .execute_backtest import execute_backtest, compare

import csv
import pandas as pd


df_class = 'dfstyle'  # css class to apply to dataframe in html
assets_list = ['BTCUSDT','ETHBTC','XLMBTC','XRPBTC']  # available trading pairs

# Create your views here.
def index(request):
	context = {'assets': assets_list}
	# return HttpResponse(loader.get_template('testapp/index.html').render(context, request))
	return render(request, 'testapp/index.html', context)

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
		# else: 
		#	deal with file larger than 2.5M here, maybe need to write to disk in chunks
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
	
	# get backtest results and performance analysis
	perf_list = []
	res_overview_list = []
	for idx,trade in enumerate(trades_list):
		perf = execute_backtest(start_date, end_date, init_capital, trading_pair, 
							commission_method, commission_cost, trade)
		# render two dataframes to html strings to store in session json
		print('backtest and analysis %d done' % idx)
		perf[2] = perf[2].to_html(classes=df_class)
		print('convert perf2 done')
		perf[3] = perf[3].to_html(classes=df_class)
		print('convert perf3 done')
		perf_list.append(perf)  # (res_overview, graph_div, daily_details, export_data)
		res_overview_list.append(perf[0])


	# get comparison of overview results from all strategies
	compare_results = compare(res_overview_list, filename_list)
	# render dataframe to html string to store in session json
	# compare_results = compare_results.set_table_attributes('class="dfstyle"')
	# compare_results = compare_results.render()
	compare_results = compare_results.to_html(classes=df_class)

	# save all results to request.session
	request.session['perf'] = perf_list
	request.session['compare'] = compare_results
	# save params to request.session
	request.session['start_date'] = start_date
	request.session['end_date'] = end_date
	request.session['init_capital'] = init_capital
	request.session['trading_pair'] = trading_pair
	request.session['filename_list'] = filename_list
	
	return HttpResponseRedirect(reverse('testapp:results'))