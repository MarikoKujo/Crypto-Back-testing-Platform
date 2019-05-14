import pandas as pd
import glob, os  # for reading (and moving) csv files

default_symbols = ['BTCUSDT','ETHBTC','XLMBTC','XRPBTC']

def concat_new_csvs(csv_path, arranged_path, symbols=default_symbols):
	dataset = [[] for symbol in symbols]  # init an empty list
	must_have_cols = ['symbol','eventTime','openPrice',
					'highPrice','lowPrice','price','volume']
	
	os.chdir(csv_path)

	# sort csv files by asset type and remove unwanted columns
	for f in glob.glob('*aggregates.csv'):
		part = pd.read_csv(f)

		# a file must contain all cols in must_have_cols, otherwise it is a defect
		# ignore defects for now. maybe log the filenames later
		if any(col not in part.columns for col in must_have_cols):
			continue

		# keep OHLCV columns, date column and symbol column, drop the rest ones
		part = part[must_have_cols]
		# seperate dataset according to assets, drop symbol column
		for idx,sym in enumerate(symbols):
			dataset[idx].append((part[part.symbol==sym]).drop(columns=['symbol']))

	# for every asset: change column names, deal with (possibly) wrong timestamps, 
	# and concat to old asset file
	for idx,symbol in enumerate(symbols):
		# concat data for every single asset
		data = pd.concat(dataset[idx], ignore_index=True)
		print('concat %s ok' % symbol)
		
		# this part is moved from the above cell considering time performance
		# change column names
		data.columns = ['date','open','high','low','close','volume']
		# change time format to <YYYY-MM-DD HH:TT:SS> to use dt.floor() directly
		data['date'] = pd.to_datetime(data['date'])
		# remove seconds in timestamps to get data in minute frequency
		data['date'] = data.date.dt.floor('min')
		
		# deal with (possibly) wrong timestamps
		# to compare to the 1st row, set the initial as time of 1st row minus 1min
		row1_date = data.at[0,'date'] - pd.Timedelta('1 min')
		okay = pd.Timedelta('1 min')
		too_far = pd.Timedelta('3 min')  # too_close = 0
		count = 0
		for row2 in data.itertuples():  # should work faster than iterrows
			if row2.date == row1_date:  # duplicate timestamps: the latter one += 1 min
				data.at[row2.Index,'date'] += okay
			else:
				time_diff = row2.date - row1_date
				# diff = 2, 3, or diff < 0
				if not (time_diff == okay or time_diff > too_far):
					data.at[row2.Index, 'date'] = row1_date + okay
			row1_date = data.at[row2.Index,'date']
				
		# concat to old file
		try:
			old = pd.read_csv(arranged_path+symbol+'.csv')
		except FileNotFoundError:
			data.to_csv(os.path.join(arranged_path,symbol+'.csv'), 
				index=False, float_format='%.10f')
			return

		old['date'] = pd.to_datetime(old['date'])
		# drop the last rows if timestamps are not continuous
		while old.iloc[-1,0] >= data.iloc[0,0]:
			old = old[:-1]
		# concat and rewrite
		old = pd.concat([old,data], ignore_index=True)
		old.to_csv(os.path.join(arranged_path,symbol+'.csv'), 
					index=False, float_format='%.10f')
		print('asset %s ok' % symbol)