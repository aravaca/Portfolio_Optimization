
import yfinance as yf


import pandas as pd

import yfinance as yf

def get_momentum_batch(tickers, period_days=126):
    # Download 1 year of daily close prices for all tickers at once
    data = yf.download(tickers, period="1y", interval="1d", progress=False)['Close']
    # data is a DataFrame: rows = dates, columns = tickers

    momentum_dict = {}
    for ticker in tickers:
        if ticker not in data.columns:
            momentum_dict[ticker] = None
            continue
        prices = data[ticker].dropna()
        if len(prices) < period_days:
            momentum_dict[ticker] = None
            continue
        momentum = (prices.iloc[-1] / prices.iloc[-period_days]) - 1
        momentum_dict[ticker] = momentum

    return momentum_dict

print(get_momentum_batch(['009830.KS'], 24))