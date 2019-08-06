#
# Copyright 2013 Quantopian, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Modifications copyright 2019 Technical University of Munich

import pandas as pd
from trading_calendars import get_calendar
# import request


def get_benchmark_returns(symbol):
    """
    Get a Series of benchmark returns from IEX associated with `symbol`.
    Default is `SPY`.

    Parameters
    ----------
    symbol : str
        Benchmark symbol for which we're getting the returns.

    The data is provided by IEX (https://iextrading.com/), and we can
    get up to 5 years worth of data.
    """
    # r = requests.get(
    #     'https://api.iextrading.com/1.0/stock/{}/chart/5y'.format(symbol)
    # )
    # data = r.json()

    # df = pd.DataFrame(data)

    # df.index = pd.DatetimeIndex(df['date'])
    # df = df['close']

    # return df.sort_index().tz_localize('UTC').pct_change(1).iloc[1:]

    # YOUDAN ZHANG MODIFIED changed benchmark download to dummy data

    cal = get_calendar('NYSE')
    first_date = pd.to_datetime('2018-10-23').tz_localize('UTC')
    last_date = pd.to_datetime('today').tz_localize('UTC')
    dates = cal.sessions_in_range(first_date, last_date)

    data = pd.DataFrame(0.0, index=dates, columns=['close'])
    data = data['close']

    return data.sort_index().iloc[1:]