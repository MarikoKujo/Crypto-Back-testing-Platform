import gc
import time
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
		display_data = outperf[[trading_pair,'total returns']]  # date as index
		# export_data.insert(loc=2, column='orders', value=perf['orders'].values)

		# orders_set = []
		# for idx,daily_orders in enumerate(perf['orders']):
		# 	daily_order_dicts = []
		# 	for order in daily_orders:
		# 		if order['status'] == 1:  # order is filled
		# 			tran = next((t for t in perf['transactions'][idx] 
		# 					if t['order_id'] == order['id']), None)
		# 			price = tran['price'] if tran is not None else 'not available'
		# 			# use list of tuples if sequence of keys matters
		# 			order_dict = {'created' : order['created'].strftime("%Y-%m-%d %H:%M:%S"),
		# 					'amount' : order['amount'],
		# 					'filled' : order['dt'].strftime("%Y-%m-%d %H:%M:%S"),
		# 					'price' : price}
		# 			daily_order_dicts.append(order_dict)

		# 	orders_set.append(daily_order_dicts)
		trans_detail = []
		trans_ids = []
		trans_dicts_display = []
		new_id = -1
		for idx, daily_trans in enumerate(perf['transactions']):
			daily_trans_dicts_display = []
			daily_trans_ids = []
			for trans in daily_trans:
				order_id = trans['order_id']
				order_of_trans = next((o for o in perf['orders'][idx]
							if o['id'] == order_id), None)
				if order_of_trans is not None:
					created = order_of_trans['created'].strftime("%Y-%m-%d %H:%M:%S")
				else:
					created = 'not available'

				new_id += 1
				daily_trans_ids.append(new_id)

				trans_dict = {'transaction_id': new_id,
						'order_created': created,
						'amount': trans['amount'],
						'transaction_time': trans['dt'].strftime("%Y-%m-%d %H:%M:%S"),
						trading_pair: trans['price']}
				trans_detail.append(trans_dict)

				trans_dict_display = {'id': new_id,
						'order_created': created,
						'amount': trans['amount'],
						'time': trans_dict['transaction_time'],
						'price': trans['price']}
				daily_trans_dicts_display.append(trans_dict_display)
			
			trans_ids.append(daily_trans_ids)
			trans_dicts_display.append(daily_trans_dicts_display)


		exp_daily = display_data.copy(deep=True)
		exp_daily.insert(loc=1, column='transaction_id', value=trans_ids)
		exp_daily.rename(columns={'total returns':'total_returns'}, inplace=True)
		# index of exp_daily will be named 'date' in export view in views.py

		exp_detail = pd.DataFrame(trans_detail)
		# use index=False when convert to csv in export view in views.py

		display_data.insert(loc=1, column='transactions', 
										value=trans_dicts_display)

		return [exp_daily, exp_detail, display_data]



	start_all = time.time()  # start time of backtest

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
	
	end_all = time.time()  # end time of backtest
	duration = "{:.2f} s".format(end_all - start_all)

	return [res_overview, graph_div, daily_details, export_data, duration]


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
