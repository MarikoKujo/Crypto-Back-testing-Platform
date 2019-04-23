from django.shortcuts import get_object_or_404, render
from django.http import HttpResponseRedirect
from django.template import loader
from django.urls import reverse

from io import StringIO
from .execute_backtest import execute_backtest

import csv
import pandas as pd



assets_list = ['BTCUSDT','ETHBTC','XLMBTC','XRPBTC']

# Create your views here.
def index(request):
	context = {'assets': assets_list}
	# return HttpResponse(loader.get_template('testapp/index.html').render(context, request))
	return render(request, 'testapp/index.html', context)

def results(request):
	context = {'assets': assets_list}
	# maybe replace with another template here
	return render(request, 'testapp/index.html', context)

def processing(request):
	# test if .csv file has correct format using try-except or if statement
	# return render(request, 'testapp/index.html', {'assets': assets_list, 
	#               'error_message': "Wrong csv format: timestamp and quantity in two columns."})
	# else: 理论上应该在这里进行运算，得到结果redirect给/results
	# 如何通过HttpResponseRedirect发送参数？
	# use session variables!

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
	for idx,trade in enumerate(trades_list):
		perf = execute_backtest(start_date, end_date, init_capital, trading_pair, 
								commission_method, commission_cost, trade)
		print(perf.tail())
		# try:  # run a backtest
			# perf = execute_backtest(start_date, end_date, init_capital, trading_pair, 
			# 					commission_method, commission_cost, trade)
			# perf_list.append(perf)
		# except:  # cannot finish a backtest
		# 	error_message = 'Failed to run backtest for ' + filename_list[idx]
		# 	context = {'assets': assets_list, 'error_message': error_message}
		# 	return render(request, 'testapp/index.html', context)
	
	return HttpResponseRedirect(reverse('testapp:results'))