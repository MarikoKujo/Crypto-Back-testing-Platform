import gc
from datetime import datetime

import pandas as pd
import plotly.plotly as pltly
import plotly.graph_objs as go
import plotly.offline
import zipline
from trading_calendars import get_calendar
from zipline.api import symbol, order, record, get_datetime, set_commission, commission


timezone = 'UTC'
# data bundle name. In case change, also change bname in views.py
bundle_name = 'csvdir'

def execute_backtest(start_dt, end_dt, init_cap,
					trading_pair, commission_method, commission_c, trades):
	"""Execute a backtest and provide various performance analysis.

	Parameters:
	start_dt : string, start date of backtest
	end_dt : string, end date of backtest
	init_cap : string, amount of capital base
	trading_pair : string, one of the pre-set trading pairs
	commission_method : string, pershare or pertrade
	commission_c : string, numeric value for setting commission
	trades : dict {pd.Timestamp : float}, trading signals including timestamps 
			and corresponding trading amount

	Returns:
	perf : pd.DataFrame, the overall results of a backtest, only used as param 
			for nested functions
	[res_overview, graph_div, daily_details, export_data] : list
	"""

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
		"""Set initialization params for a backtest"""
		# trading pair
		context.asset = symbol(trading_pair)
		# trading signals, dict, timestamp:amount
		context.trades = trades
		
		# transaction cost
		if commission_is_per_share:
			context.set_commission(commission.PerShare(cost=commission_cost, min_trade_cost=0))
		else:
			context.set_commission(commission.PerTrade(cost=commission_cost))

	def handle_data(context, data):
		"""This function will be executed every minute to check
		if an order should be placed now, and place the order if so."""
		# quant = 0 if timestamp of now is not in context.trades
		quant = context.trades.get(get_datetime(), 0)
		if quant != 0:
			order(context.asset, quant)  # place an order
		# use "_asset" as a temporary placeholder col name for actual trading pair
		record(_asset=data.current(context.asset,'price'))



	def get_results_overview(perf):
		"""Results overview section - summary statistics.

		Parameters:
		perf : pd.DataFrame, the overall results of a backtest

		Returns:
		results : dict
		"""
		if commission_is_per_share:
			transaction_cost = sum([abs(t['amount'])*commission_cost 
								for tlist in perf['transactions'] for t in tlist])
			gross_ret = (perf['portfolio_value'][-1]+transaction_cost-init_capital)/init_capital
		else:
			# comm per trade
			transaction_cost = sum([len(t) for t in perf['transactions']])*commission_cost
			gross_ret = (perf['portfolio_value'][-1]+transaction_cost-init_capital)/init_capital

		results = {}
		results['total_returns'] = "{:.2f}".format((perf['algorithm_period_return'][-1])*100)+"%"
		results['volatility'] = "{:.2f}".format(perf['algo_volatility'][-1])
		results['sharpe_ratio'] = "{:.2f}".format(perf['sharpe'][-1])
		results['number_of_trades'] = "{:d}".format(len(trades))
		results['mean_daily_returns'] = "{:.2f}".format((perf['returns'].mean(skipna=True))*100)+"%"
		results['gross_returns'] = "{:.2f}".format(gross_ret*100)+"%"

		return results

	def draw_graph(perf):
		"""Results overview section - graph of price vs. return.

		Parameters:
		perf : pd.DataFrame, the overall results of a backtest

		Returns:
		plot_div : string, the html code of plot.ly graph, which can be
					directly embedded into html code. Works together with
					<script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
		"""
		asset = go.Scatter(x=perf.index, y=perf[trading_pair], name='Underlying')
		returns = go.Scatter(x=perf.index, y=perf['algorithm_period_return'], 
							name='Cumulative trading return', yaxis='y2')
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

	def get_daily_details(perf):
		"""Daily details section.

		Parameters:
		perf : pd.DataFrame, the overall results of a backtest

		Returns:
		outperf : pd.DataFrame, the daily details of a backtest's results
		"""
		# select rows for printing
		outperf = perf[[trading_pair,'algorithm_period_return','returns',
						'portfolio_value','algo_volatility','sharpe']]
		# percentages: store as decimals, display as percentages in UI (possibly)
		outperf.columns = [trading_pair,'total returns','daily returns',
						'portfolio value','volatility','sharpe ratio']
		# convert datetime to date
		outperf.index = outperf.index.date
		return outperf

	def export_csv(outperf, perf):
		"""Export to file section.
		The exported dataframe contains date index, asset price, total returns, 
		trading signals.
		Note that this function only returns a dataframe which will be rendered 
		to csv file later, NOT a csv file.

		Parameters:
		outperf : pd.DataFrame, the DataFrame in daily details section
		perf : pd.DataFrame, the overall results of a backtest

		Returns:
		export_data : pd.DataFrame, the DataFrame to be converted to csv file
		"""
		export_data = outperf[[trading_pair,'total returns']]
		# export_data.insert(loc=2, column='orders', value=perf['orders'].values)
		tradeset = []
		for d in outperf.index:
			# appending daily trading signals (timestamps are converted to strings)
			tradeset.append([(t.strftime("%Y-%m-%d %H:%M:%S"),a) for t,a in trades.items() 
							if pd.to_datetime(t).date() == d])
		export_data.insert(loc=2, column='trading data', value=tradeset)
		return export_data


	# run backtest
	perf = zipline.run_algorithm(start=start_date,
						end=end_date,
						initialize=initialize,
						capital_base=init_capital,
						handle_data=handle_data,
						data_frequency='minute',
						bundle=bundle_name,
						trading_calendar=get_calendar('AOC'))  # AlwaysOpenCalendar

	gc.collect()

	# replace _asset column name with name of trading pair
	perf.rename(columns={'_asset':trading_pair}, inplace=True)

	# get results to display
	res_overview = get_results_overview(perf)  # dict
	graph_div = draw_graph(perf)  # div string
	daily_details = get_daily_details(perf)  # pd.DataFrame
	export_data = export_csv(daily_details, perf)  #pd.DataFrame

	gc.collect()
	
	return [res_overview, graph_div, daily_details, export_data]


def compare(results, filename_list):
	"""Comparison section.

	Parameters:
	results : list, each item is a dict of overview results from a set of strategies
		result : dict, item of results, a return value of get_results_overview()
	filename_list : list, name of uploaded strategies files

	Returns:
	comp : pd.DataFrame, comparison of the given results with highlights
	"""

	def max_yellow(s):
		"""Color maximum in each row to yellow"""
		is_max = s == s.max()
		return ['background-color: yellow' if v else '' for v in is_max]

	comp = pd.DataFrame(data=results, index=filename_list)
	# rearrange sequence of columns
	cols_sequence = ['total_returns','mean_daily_returns','gross_returns',
				'number_of_trades','volatility','sharpe_ratio']
	comp = comp[cols_sequence]
	comp.columns = ['total returns','mean daily returns','gross returns',
				'number of trades','volatility','sharpe ratio']

	# comp = comp.style.apply(max_yellow)
	return comp
