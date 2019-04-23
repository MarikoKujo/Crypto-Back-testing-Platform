import zipline
from zipline.api import symbol, order, record, get_datetime, set_commission, commission
from trading_calendars import get_calendar

from datetime import datetime
import time

import pandas as pd


timezone = 'UTC'

def execute_backtest(start_dt, end_dt, init_cap,
					trading_pair, commission_method, commission_c, trades):

	start_date = pd.to_datetime(start_dt).tz_localize(timezone)
	end_date = pd.to_datetime(end_dt).tz_localize(timezone)
	init_capital = float(init_cap)
	
	commission_is_per_share = True if commission_method == 'pershare' else False
	commission_cost = float(commission_c)


	def initialize(context):
		# trading pair
		context.asset = symbol(trading_pair)
		
		context.trades = trades
		
		# transaction cost
		if commission_is_per_share:
			context.set_commission(commission.PerShare(cost=commission_cost, min_trade_cost=0))
		else:
			context.set_commission(commission.PerTrade(cost=commission_cost))

	def handle_data(context, data):
		quant = context.trades.get(get_datetime(), 0)  # quant = 0 if timestamp of now is not in context.trades
		if quant != 0:
			order(context.asset, quant)
		record(_asset=data.current(context.asset,'price'))

	# results_overview
	# do we need to ingest data again?? try and test
	def results_overview(perf):


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
	print endall-startall

	perf = perf[0]
	perf.rename(columns={'_asset':trading_pair}, inplace=True)
	
	return perf
