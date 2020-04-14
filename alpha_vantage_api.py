
import datetime
import os
import time
from pathlib import Path

from threading import Thread, Event
import pytz

from alpha_vantage.timeseries import TimeSeries
from alpha_vantage.techindicators import TechIndicators
import pandas as pd
import logging

def get_alpha_key():
    key_path = Path() / "key"
    if key_path.exists():
        with open(key_path, 'r') as f:
            key = f.read()
        return key
    else:
        raise FileExistsError("There is no file named 'key' in the project directory. Please add it with your Alpha Vantage API key.")

KEY = get_alpha_key()
ts = TimeSeries(KEY, output_format='pandas')
ti = TechIndicators(KEY)

PATH_TO_SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
PATH_TO_ROOT_DIR = os.path.normpath(os.path.join(PATH_TO_SCRIPT_DIR, '..'))

REQ_TYPES = ["symbol", "last", "daily", "daily_adj", "intraday", "market_times"]
INTERVALS = ["1min", "5min", "15min", "30min", "60min"]


def get_data(symbol, mode="daily", adjusted=False, interval='15min', outputsize='compact'):
    """ Get data from Alpha_vantage API.


    :param symbol:
        the symbol for the equity we want to get its data
    :param mode: str
        Available modes:
        - "daily"
        - "daily" and adjusted
        - "intraday"
        - "last" : last end point of the security
    :param adjusted: bool
        if true return the adjusted data. Covering up to 20 years of data.
    :param interval: str
        time interval between two conscutive values,
        supported values are '1min', '5min', '15min', '30min', '60min'
        (default '15min')
    !:param outputsize: str
        The size of the call, supported values are
        'compact' and 'full'; the first returns the last 100 points in the
        data series, and 'full' returns the full-length intraday times
        series, commonly above 1MB (default 'compact')
    :return:
        data: pandas.DataFrame
            Time series with timestamps(index) ['01. symbol', '02. open', '03. high', '04. low', '05. price',
       '06. volume', '07. latest trading day', '08. previous close',
       '09. change', '10. change percent']
        meta_data: dict
            Dictionnay including: '1.information', '2. Symbol', '3. Last refreshed', '4. Output Size', '5. Time Zone'
    """

    ping = 0
    while ping < 3:
        try:
            if mode == "daily" and not adjusted:
                data, meta_data = ts.get_daily(symbol=symbol, outputsize=outputsize)
            elif mode == "intraday" and not adjusted:
                data, meta_data = ts.get_intraday(symbol=symbol, interval=interval, outputsize=outputsize)
            elif mode == "daily" and adjusted:
                data, meta_data = ts.get_daily_adjusted(symbol=symbol, outputsize=outputsize)
            elif mode == "last":
                data, meta_data = ts.get_quote_endpoint(symbol=symbol)
            break
        except Exception as e:
            logging.error("An issue occured during Alpha Vantage API call (get_data)")
            logging.error(repr(e))
            ping += 1
            time.sleep(1)
    if ping == 3:
        raise ConnectionError("Impossible to connect to Alpha Vantage API.")
    return data, meta_data


def save_data(df, symbol, mode=None):
    """ Save pandas.DataFrame in csv file.

    :param df: pandas.DataFrame
        Input DataFrame to export in .csv format
    :param file_name: str
        Name of the file
    :param timestamped: bool
        If yes, add a timestamp at the end of the file name
    """
    if mode is not None:
        name = symbol + "_" + mode
    else:
        name = symbol
    directory = PATH_TO_ROOT_DIR + "\\data\\csv\\"
    if isinstance(df, pd.DataFrame):
        try:
            df.to_csv(directory + name + ".csv")
        except Exception as e:
            raise e
    else:
        raise TypeError("Inputs of save_results are not pandas.DataFrame")


def symbol_search(symbol):
    """ Search best matching symbols and market information based on keyword. Select best match and return it as a dict.

    :param symbol: str
        Symbol to search
    :return:
        res: dict
            Results of the research including the following fields:
                -'1. symbol',
                -'2. name',
                -'3. type',
                -'4. region',
                -'5. marketOpen',
                -'6. marketClose',
                -'7. timezone',
                -'8. currency',
                -'9. matchScore'
    """
    ping = 0
    while ping < 3:
        try:
            res, meta_res = ts.get_symbol_search(symbol)
            if len(res) > 1:
                res = res.loc[res.index == res['9. matchScore'].astype(float).idxmax()].to_dict('list')

            # remove array type in values
            res = dict((k, v[0]) for k, v in res.items())
            break
        except Exception as e:
            logging.error("An issue occured during Alpha Vantage API call (symbol search)")
            logging.error(repr(e))
            ping += 1
            time.sleep(1)

    return res


def get_open_close_mkt_time(symbol):
    """ Return open and close time in UTC format.

    :param symbol: str
        Asset symbol
    :return:
        t_open, t_close: datetime.time
    """
    info = symbol_search(symbol)
    open = list(map(int, info['5. marketOpen'].split(":")))
    close = list(map(int, info['6. marketClose'].split(":")))
    tz = int(info['7. timezone'][-3:])

    t_open = datetime.time(open[0] - tz, open[1], tzinfo=pytz.UTC)
    t_close = datetime.time(close[0] - tz, close[1], tzinfo=pytz.UTC)
    return t_open, t_close

