import zipline
from zipline.api import symbol, order, record, get_datetime, set_commission, commission
from trading_calendars import get_calendar

from datetime import datetime
import time

import pandas as pd
import plotly.plotly as pltly
import plotly.graph_objs as go
from plotly.offline import download_plotlyjs, plot


timezone = 'UTC'

def execute_backtest(start_dt, end_dt, init_cap,
					trading_pair, commission_method, commission_c, trades):

	start_date = pd.to_datetime(start_dt).tz_localize(timezone)
	end_date = pd.to_datetime(end_dt).tz_localize(timezone)
	init_capital = float(init_cap)
	
	if commission_method == 'pershare':
		commission_is_per_share = True
		# commission ratio number is entered as a percentage
		commission_cost = float(commission_c) / 100
	else:  # commission_method == 'pertrade'
		commission_is_per_share = False
		commission_cost = float(commission_c)
	


	def initialize(context):
		# trading pair
		context.asset = symbol(trading_pair)
		# trading signals, dict, timestamp:amount
		context.trades = trades
		
		# transaction cost
		if commission_is_per_share:
			context.set_commission(commission.PerShare(cost=commission_cost, min_trade_cost=0))
		else:
			context.set_commission(commission.PerTrade(cost=commission_cost))

	def handle_data(context, data):  # will be executed every minute
		# quant = 0 if timestamp of now is not in context.trades
		quant = context.trades.get(get_datetime(), 0)
		if quant != 0:
			order(context.asset, quant)
		record(_asset=data.current(context.asset,'price'))



	# results overview section: overall statistics
	def get_results_overview(perf):
		if commission_is_per_share:
			transaction_cost = sum([abs(t['amount'])*commission_cost for tlist in perf['transactions'] for t in tlist])
			gross_ret = (perf['portfolio_value'][-1]+transaction_cost-init_capital)/init_capital
		else:
			# comm per trade
			transaction_cost = sum([len(t) for t in perf['transactions']])*commission_cost
			gross_ret = (perf['portfolio_value'][-1]+transaction_cost-init_capital)/init_capital

		results = {}
		results['Total returns'] = "{:.2f}".format(perf['algorithm_period_return'][-1])*100)+"%"
		results['Volatility'] = "{:.2f}".format(perf['algo_volatility'][-1])
		results['Sharpe ratio'] = "{:.2f}".format(perf['sharpe'][-1])
		results['Number of trades'] = "{:d}".format(len(trades))
		results['Mean daily returns'] = "{:.2f}".format((perf['returns'].mean(skipna=True))*100))+"%"
		results['Gross returns'] = "{:.2f}".format(gross_ret*100)+"%"

		return results

	# results overview section: graph of price vs. return
	def draw_graph(perf):
		asset = go.Scatter(x=perf.index, y=perf[trading_pair], name='Underlying')
		returns = go.Scatter(x=perf.index, y=perf['algorithm_period_return'], name='Cumulative trading return', yaxis='y2')
		data = [asset, returns]
		layout = go.Layout(
			yaxis=dict(title=trading_pair),
			yaxis2=dict(
				title='cumulative trading return',
				titlefont=dict(color='red'),
				tickfont=dict(color='red'),
				overlaying='y',
				side='right'
			)
		)
		pyfig = go.Figure(data=data, layout=layout)
		# a string with only the div required to create the data
		plot_div = plotly.offline.plot(pyfig, include_plotlyjs=False, output_type='div')
		return plot_div

	# daily details section
	def get_daily_details(perf):
		# select rows for printing
		outperf = perf[[trading_pair,'algorithm_period_return','returns','portfolio_value','algo_volatility','sharpe']]
		# percentages: store as decimals, display as percentages in UI (possibly)
		outperf.columns = [trading_pair,'total returns','daily returns','portfolio value','volatility','sharpe ratio']
		# convert datetime to date
		outperf.index = outperf.index.date
		return outperf

	# export to file section
	def export_csv(outperf, perf):
		export_data = outperf[[trading_pair,'total returns']]
		export_data.insert(loc=2, column='orders', value=perf['orders'].values)
		tradeset = []
		for d in outperf.index:
			tradeset.append([(t,a) for t,a in trades.items() if pd.to_datetime(t).date() == d])
		export_data.insert(loc=3, column='trading data', value=tradeset)
		return export_data


	startall = time.time() 
	perf = zipline.run_algorithm(start=start_date,
						end=end_date,
						initialize=initialize,
						capital_base=init_capital,
						handle_data=handle_data,
						data_frequency='minute',
						bundle='csvdir',
						trading_calendar=get_calendar('AOC')),
	endall = time.time()
	print(endall-startall)

	perf = perf[0]
	perf.rename(columns={'_asset':trading_pair}, inplace=True)

	res_overview = get_results_overview(perf)  # dict
	graph_div = draw_graph(perf)  # div string
	daily_details = get_daily_details(perf)  # pd.DataFrame
	export_data = export_csv(daily_details, perf)  #pd.DataFrame

	
	return res_overview, graph_div, daily_details, export_data
