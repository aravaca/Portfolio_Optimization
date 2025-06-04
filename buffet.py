
# SPDX-FileCopyrightText: © 2025 Hyungsuk Choi <chs_3411@naver[dot]com>, University of Maryland 
# SPDX-License-Identifier: MIT

import yfinance as yf
import pandas as pd
from dotenv import load_dotenv
import os
import requests
from pykrx import stock
import datetime as dt
import openpyxl
import math
from queue import Queue
import threading
import time
import polars as pl
import shelve
from bs4 import BeautifulSoup
from urllib.request import urlopen


################ DEPENDENCIES ###########################

# pip install -r requirements.txt

#########################################################


################ PREDETERMINED FIELDS ###################

NUM_THREADS = 20 #5 worked just fine for limit=50
CUTOFF = 5

#########################################################


country = input('Country (KR, JP, CH, US, UK 중 선택): ').upper() 
if country == 'US': 
    country = None 

if not country:
    limit = 100
else:
    limit = int(float(input('Limit: '))) #input always accepts a str

if not country:
    sp500 = input('S&P500? (y/n, n for NASDAQ100): ').lower().strip() == 'y' # False for nasdaq100
else:
    sp500 = True

print('May take up to few minutes...')

today = dt.datetime.today().weekday()
weekend = today - 4 # returns 1 for saturday, 2 for sunday
formattedDate = (dt.datetime.today() - dt.timedelta(days = weekend)).strftime("%Y%m%d") if today >= 5 else dt.datetime.today().strftime("%Y%m%d")

dfKospi = stock.get_market_fundamental(formattedDate, market="ALL")

data = []
data_lock = threading.Lock()

# Load environment variables from .env file
load_dotenv()

# Get the API key
fmp_key = os.getenv("FMP_API_KEY")

def get_tickers(country: str, limit: int, sp500: bool):
    if country is not None:
        return get_tickers_by_country(country, limit, fmp_key) #US, JP, KR
    elif sp500:
        return pl.read_csv("https://datahub.io/core/s-and-p-500-companies/r/constituents.csv")["Symbol"].to_list()
    elif not sp500:
        nasdaq100_url = 'https://en.wikipedia.org/wiki/NASDAQ-100'
        nasdaq100 = pd.read_html(nasdaq100_url, header=0)[4] # Might need to adjust index (5th table on the page)
        return nasdaq100['Ticker'].tolist()
    else:
        raise Exception("No tickers list satisfies the given parameter")

def get_tickers_by_country(country: str, limit: int = 100, apikey: str = 'your_api_key'):
    url = 'https://financialmodelingprep.com/api/v3/stock-screener'
    params = {
        'country': country,
        'limit': limit,
        'type': 'stock',
        'sort': 'marketCap',
        # 'order': 'desc',
        'apikey': apikey,
        'isEtf': False,
        'isFund': False,
        # 'sector' : Consumer Cyclical | Energy | Technology | Industrials | Financial Services | Basic Materials | Communication Services | Consumer Defensive | Healthcare | Real Estate | Utilities | Industrial Goods | Financial | Services | Conglomerates
        # 'exchange' : nyse | nasdaq | amex | euronext | tsx | etf | mutual_fund
    }
    response = requests.get(url, params=params)
    data = response.json()
    return [item['symbol'] for item in data]

# buffet's philosophy & my quant ideas
def buffet_score (de, cr, pbr, per, ind_per, roe, ind_roe, roa, ind_roa, eps, div, icr):
    score = 0
    #basic buffet-style filtering
    if de is not None and de <= 0.5:
        score +=1
    if cr is not None and (cr >= 1.5 and cr <= 2.5):
        score +=1

    if pbr is not None and (pbr <= 1.5 and pbr != 0):
        score +=1
    if roe is not None and roe >= 0.08: #8% basic buffet fundamental rate
        score +=1
    if roa is not None and roa >= 0.06: #6% basic buffet fundamental rate
        score +=1
    if div is not None: #cagr = +4~6-10%
        if div >= 0.1:
            score +=1.5
        elif div >= 0.08:
            score +=1
        elif div >= 0.06:
            score +=0.5

    if eps is True:
        score += 1
    if eps is False:
        score -= 1

    elif eps is not None:
        if eps >= 0.1:
            score += 1
        if eps < 0:
            score -= 1
        if eps > 0 and per is not None:
            peg = per / (eps * 100) #peg ratio, underv if less than 1
            if peg <= 1:
                score += 1

    if icr is not None and icr >= 5: #x5
        score +=1

    #my quant ideas 
    if None not in {roe, ind_roe, per, ind_per}:
        if per > ind_per and roe < ind_roe:
            score -=2 # hard pass
        if per != 0 and per < 0.7 * ind_per and roe < ind_roe:
            if pbr is not None and pbr < 1:
                score += 0.5  # deep value + asset backing → worth a shot


    if None not in {roe, ind_roe, per, ind_per, roa, ind_roa}:
        if roe > ind_roe and roa > ind_roa and per != 0:
            if per < ind_per:
                score += 2  # strong fundamentals and value
            elif per <= 1.2 * ind_per:
                score += 1  # great business, slightly overvalued (still reasonable)
            else:
                score += 0.5  # great business, but may be overpriced

    return score

def getFs (item, ticker):
    # for country == 'KR' only
    try:
        return dfKospi.loc[ticker[:6], item] 
    except:
        return None

def has_stable_dividend_growth(ticker):
    stock = yf.Ticker(ticker)
    divs = stock.dividends
    # Ensure we have at least 10 years of data
    if divs.empty:
        return False

    # Get annual total dividends for the past 10 years
    annual_divs = divs.groupby(divs.index.year).sum()
    if len(annual_divs) < 10:
        return False
    
    recent_years = sorted(annual_divs.index)[-11:-1] # returns [last year - 9 = 2015, 2016, ..., last year = 2024], # use -11 to start around 10 years ago from now

    if recent_years[0] < dt.datetime.today().year - 12: # sift out old data
        return False

    last_10_divs = [annual_divs[year] for year in recent_years]
    # print(last_10_divs)

    # Check for stable or increasing dividends
    tolerance = 0.85 # tolerance band to account for crises and minor dividend cuts
    return all(earlier * tolerance <= later for earlier, later in zip(last_10_divs, last_10_divs[1:])) # zip returns [(2015div, 2016div), (2016div, 2017div), ..., (2024div, 2025div)]
    
def has_stable_dividend_growth_cagr(ticker):
    stock = yf.Ticker(ticker)
    divs = stock.dividends
    # Ensure we have at least 10 years of data
    if divs.empty:
        return None

    # Get annual total dividends for the past 10 years
    annual_divs = divs.groupby(divs.index.year).sum()
    if len(annual_divs) < 10:
        return None
    
    recent_years = sorted(annual_divs.index)[-11:-1] # returns [last year - 9 = 2015, 2016, ..., last year = 2024], # use -11 to start around 10 years ago from now

    if dt.datetime.today().year - 1 not in recent_years: # sift out old data
        return None
    
    last_10_divs = [annual_divs[year] for year in recent_years]

    div_start = last_10_divs[0]
    div_end = last_10_divs[-1]
    if len(last_10_divs) == 0 or div_start == 0:
        return None
    else:
        cagr = ((div_end / div_start) ** (1/len(last_10_divs))) - 1
        return cagr
    
def has_stable_eps_growth(ticker):
    ticker = yf.Ticker(ticker)

    # Get annual income statement
    income_stmt = ticker.financials # Annual by default

    # Make sure EPS is in the statement
    if "Diluted EPS" in income_stmt.index:
        eps_series = income_stmt.loc["Diluted EPS"]
        if dt.datetime.today().year - 6 in eps_series.index.year:
            return False
        eps_list = eps_series.sort_index().dropna().tolist() # Sorted from oldest to newest
        tolerance = 0.9
        return all(earlier * tolerance <= later for earlier, later in zip(eps_list, eps_list[1:]))
    else:
        return False


def has_stable_eps_growth_quarterly(ticker):
    ticker = yf.Ticker(ticker)

    # Get quarterly earnings data (contains actual EPS in 'Earnings' column)
    quarterly_eps = ticker.quarterly_earnings

    # Make sure there is enough data
    if quarterly_eps is None or quarterly_eps.empty or len(quarterly_eps) < 8:
        return False

    # Sort by date ascending (oldest first)
    quarterly_eps = quarterly_eps.sort_index()

    eps_list = quarterly_eps['Earnings'].dropna().tolist()

    # Define tolerance for stable growth (e.g., each quarter at least 90% of previous)
    tolerance = 0.9

    # Check stable growth: every EPS >= 90% of previous EPS
    return all(earlier * tolerance <= later for earlier, later in zip(eps_list, eps_list[1:]))

def has_stable_eps_growth_cagr(ticker):
    ticker = yf.Ticker(ticker)

    # Get annual income statement
    income_stmt = ticker.financials # Annual by default

    # Make sure EPS is in the statement

    try:
        if "Diluted EPS" in income_stmt.index:
            eps_series = income_stmt.loc["Diluted EPS"]
            if dt.datetime.today().year - 1 not in eps_series.index.year:
                return None
            eps_list = eps_series.sort_index().dropna().tolist() # Sorted from oldest to newest
            eps_start = eps_list[0]
            eps_end = eps_list[-1]
            if len(eps_list) == 0:
                return None
            if eps_start <= 0 or eps_end < 0:
                tolerance = 0.9
                return all(earlier * tolerance <= later for earlier, later in zip(eps_list, eps_list[1:]))
            else:
                cagr = ((eps_end / eps_start) ** (1/len(eps_list))) - 1
                return cagr
        else:
            return None
    except Exception:
        return None


# gets the most recent interest coverage ratio available
def get_interest_coverage_ratio(ticker):
    financials = yf.Ticker(ticker).financials # Annual financials, columns = dates (most recent first)
    ratio = None
    for date in financials.columns:
        if date.year < dt.datetime.today().year - 5: # sift out old data
            return None

        try:
            ebit = financials.loc["Operating Income", date]
            interest_expense = financials.loc["Interest Expense", date]
            if math.isnan(interest_expense) or math.isnan(ebit) or not interest_expense or ebit is None or interest_expense is None:
                continue # Avoid division by zero
            else:
                ratio = round((ebit / abs(interest_expense)), 2)
                break
        except KeyError:
            continue
    return ratio

def bvps_undervalued(bvps, current):
    if not bvps:
        return False
    if bvps > current:
        return True #undervalued
    else:
        return False

def has_stable_book_value_growth(ticker, sector: str):
    ticker = yf.Ticker(ticker)

    # Get annual balance sheet
    balance_sheet = ticker.balance_sheet # Columns are by period (most recent first)

    # Reverse columns to go oldest → newest
    balance_sheet = balance_sheet.iloc[:, ::-1]
    book_values = []

    for date in balance_sheet.columns:
        if date.year < dt.datetime.today().year - 6: # sift out old data
            return False
        
        try:
            book_value = balance_sheet.loc["Common Stock Equity", date]
            outstanding_shares = balance_sheet.loc["Ordinary Shares Number", date]
            if math.isnan(book_value) or math.isnan(outstanding_shares) or not outstanding_shares:
                continue
            else:
                bvps = book_value / outstanding_shares 
                book_values.append(round(bvps, 2))
        except Exception as e:
            continue
            
    if len(book_values) < 2:
        return False
    
    tolerance = 0.85 if sector in {'Industrials', 'Technology', 'Energy', 'Consumer Cyclical', 'Basic Materials'} else 0.9 #set is faster than list in checking O(1) avg
    return all(earlier * tolerance <= later for earlier, later in zip(book_values, book_values[1:]))

def get_esg_score(ticker):
    ans = ''
    ticker = yf.Ticker(ticker)
    esg = ticker.sustainability
    try:
        sust = esg.loc['totalEsg', 'esgScores']
        rateY = esg.loc['esgPerformance', 'esgScores']
        ans = str(sust) + ', ' + str(rateY)
    except Exception:
        return ans
    finally:
        return ans

def get_percentage_change(ticker):
    ticker = yf.Ticker(ticker)

    # Get last 2 days of price data
    data = ticker.history(period="2d")

    # Check if we have at least 2 days and prev_close is not zero
    if len(data) >= 2:
        prev_close = data['Close'].iloc[-2]
        last_close = data['Close'].iloc[-1]

        if prev_close != 0:
            percent_change = ((last_close - prev_close) / prev_close) * 100
            if percent_change >= 0:
                return (f" (+{percent_change:.2f}%)")  # e.g., (-6.20%)
            else:
                return (f" ({percent_change:.2f}%)")  # e.g., (-6.20%)
        else:
            return ' ()'
    else:
        return ' ()'

# FullRatio의 산업별 PER 페이지 URL
url = 'https://fullratio.com/pe-ratio-by-industry'
headers = {'User-Agent': 'Mozilla/5.0'}

response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.text, 'html.parser')

# 테이블 찾기 (이때 table이 None인지 체크)
table = soup.find('table')
if table is None:
    raise Exception("테이블을 찾을 수 없습니다. 구조가 바뀌었거나 JS로 로딩될 수 있습니다.")

# tbody가 있는 경우
tbody = table.find('tbody')
if tbody:
    rows = tbody.find_all('tr')
else:
    rows = table.find_all('tr')[1:] # 헤더 제외

# 각 행에서 데이터 추출
per_data = []
for row in rows:
    cols = row.find_all('td')
    if len(cols) >= 2:
        industry = cols[0].text.strip()
        pe_ratio = cols[1].text.strip()
        per_data.append({'Industry': industry, 'P/E Ratio': pe_ratio})

# 결과 출력
df_per = pl.DataFrame(per_data)

url_roe = 'https://fullratio.com/roe-by-industry'
headers_roe = {'User-Agent': 'Mozilla/5.0'}

response_roe = requests.get(url_roe, headers=headers_roe)
soup_roe = BeautifulSoup(response_roe.text, 'html.parser')

# 테이블 찾기 (이때 table이 None인지 체크)
table_roe = soup_roe.find('table')
if table_roe is None:
    raise Exception("테이블을 찾을 수 없습니다. 구조가 바뀌었거나 JS로 로딩될 수 있습니다.")

# tbody가 있는 경우
tbody_roe = table_roe.find('tbody')
if tbody_roe:
    rows_roe = tbody_roe.find_all('tr')
else:
    rows_roe = table_roe.find_all('tr')[1:] # 헤더 제외

# 각 행에서 데이터 추출
roe_data = []
for row in rows_roe:
    cols_roe = row.find_all('td')
    if len(cols_roe) >= 2:
        industry_roe = cols_roe[0].text.strip()
        roe_num = cols_roe[1].text.strip()
        roe_data.append({'Industry': industry_roe, 'ROE': roe_num})

# 결과 출력
df_roe = pl.DataFrame(roe_data)
#
#
url_roa = 'https://fullratio.com/roa-by-industry'
headers_roa = {'User-Agent': 'Mozilla/5.0'}

response_roa = requests.get(url_roa, headers=headers_roa)
soup_roa = BeautifulSoup(response_roa.text, 'html.parser')

# 테이블 찾기 (이때 table이 None인지 체크)
table_roa = soup_roa.find('table')
if table_roa is None:
    raise Exception("테이블을 찾을 수 없습니다. 구조가 바뀌었거나 JS로 로딩될 수 있습니다.")

# tbody가 있는 경우
tbody_roa = table_roa.find('tbody')
if tbody_roa:
    rows_roa = tbody_roa.find_all('tr')
else:
    rows_roa = table_roa.find_all('tr')[1:] # 헤더 제외

# 각 행에서 데이터 추출
roa_data = []
for row in rows_roa:
    cols_roa = row.find_all('td')
    if len(cols_roa) >= 2:
        industry_roa = cols_roa[0].text.strip()
        roa_num = cols_roa[1].text.strip()
        roa_data.append({'Industry': industry_roa, 'ROA': roa_num})

df_roa = pl.DataFrame(roa_data)
#

def get_industry_roe(ind):
    if country is None:
        try:
            if ind is not None:
                ans = float(df_roe.filter(pl.col('Industry') == ind).select("ROE").item())
                return ans/100.0
            else:
                return 0.08
        except Exception:
            return 0.08
    else:
        return 0.08

def get_industry_roa(ind):
    if country is None:
        try:
            if ind is not None:
                ans = float(df_roa.filter(pl.col('Industry') == ind).select("ROA").item())
                return ans/100.0
            return 0.06
        except Exception:
            return 0.06
    else:
        return 0.06

    

def get_industry_per(ind, ticker):
    if country is None: #country == US
        spy = yf.Ticker('SPY')
        spy_info = spy.info
        per = spy_info.get('trailingPE')
        try: 
            if ind is not None:
                ans = float(df_per.filter(pl.col('Industry') == ind).select("P/E Ratio").item())
                return ans
            return per
        except Exception:
            return per
    elif country == 'KR':
        try:
            url = f"https://finance.naver.com/item/main.nhn?code={ticker[:6]}"
            headers = {'User-Agent': 'Mozilla/5.0'}
            res = requests.get(url, headers=headers)
            soup = BeautifulSoup(res.text, 'html.parser')

            # 동일업종 PER이 들어있는 박스 찾기
            aside = soup.select_one('div.aside_invest_info')
            if aside:
                rows = aside.select('table tr')
                for row in rows:
                    if '동일업종 PER' in row.text:
                        per_text = row.select_one('td em').text
                        return float(per_text.replace(',', ''))
            return None
        except Exception:
            return None

    elif country == 'JP':
        ewj = yf.Ticker('EWJ')
        info = ewj.info
        per = info.get('trailingPE')
        return per
    else:
        vt = yf.Ticker('VT')
        info = vt.info
        per = info.get('trailingPE')
        return per


tickers = get_tickers(country, limit, sp500)

# block of code that gets rid of preferred stocks
if country == 'KR':
    for ticker in tickers:
        if ticker[5] != '0': 
            tickers.remove(ticker)

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

momentum_3m = get_momentum_batch(tickers, 63)
momentum_6m = get_momentum_batch(tickers, 126)
momentum_12m = get_momentum_batch(tickers, 240)

def momentum_score(short, mid, long):
   
    def score_momentum(mom, good_thresh, bad_thresh):
        if mom is None:
            return 0
        if mom >= good_thresh:
            return 1
        elif mom <= bad_thresh:
            return -1
        else:
            return 0
    
    weights = {'short': 0.3, 'mid': 0.5, 'long': 1.2}
    thresholds = {
        'short': (0.05, -0.05),   # +5% / -5%
        'mid': (0.10, -0.05),     # +10% / -5%
        'long': (0.15, 0.0)       # +15% / 0%
    }
    
    total_score = 0
    total_score += score_momentum(short, *thresholds['short']) * weights['short']
    total_score += score_momentum(mid, *thresholds['mid']) * weights['mid']
    total_score += score_momentum(long, *thresholds['long']) * weights['long']
    
    return round(total_score/(sum(weights.values())),2)

def classify_cyclicality(industry):
    """
    Classify a ticker as 'cyclical', 'defensive', or 'neutral' based on its industry.

    Returns:
      - 'cyclical' if industry matches cyclical keywords
      - 'defensive' if industry matches defensive keywords
      - 'neutral' if no clear match
      - None if industry info unavailable or error
    """

    cyclical_keywords = [
    "auto", "apparel", "footwear", "home improvement", "internet retail", "leisure", "lodging",
    "restaurant", "specialty retail", "textile", "travel", "coal", "oil", "gas", "renewable",
    "asset management", "bank", "capital markets", "credit services", "insurance",
    "mortgage", "real estate", "aerospace", "defense", "air freight", "airline",
    "building", "conglomerate", "construction", "electrical equipment", "engineering",
    "industrial", "machinery", "marine", "railroad", "waste", "chemical", "container",
    "metal", "paper", "advertising", "broadcasting", "cable", "casino", "communication",
    "gaming", "interactive media", "movies", "publishing", "radio", "recreational",
    "software", "semiconductor", "information technology", "it services"
    ]


    defensive_keywords = [
    "beverages", "confectioner", "food", "household", "packaged", "personal product",
    "tobacco", "biotech", "healthcare", "health", "medical device", "pharma",
    "utility", "power producer", "utilities", 
    ]

    try:
        if not industry:
            return None  # No industry info

        industry_lower = industry.lower()

        # Check cyclical
        for kw in cyclical_keywords:
            if kw in industry_lower:
                return "cyclical"

        # Check defensive
        for kw in defensive_keywords:
            if kw in industry_lower:
                return "defensive"

        # If no matches, neutral
        return "neutral"

    except Exception as e:
        return None

q = Queue()
for ticker in tickers:
    q.put(ticker)

def process_ticker_quantitatives():
    while not q.empty():
        ticker = q.get()
        try:

            info = yf.Ticker(ticker).info
            name = info.get("longName") or info.get("shortName", ticker)
            # sector = info.get("sector", None)
            industry = info.get("industry", None)
            currentPrice = info.get("currentPrice", None)
            percentage_change = get_percentage_change(ticker)
            target_mean = info.get('targetMeanPrice', 0)
            if target_mean != 0 and currentPrice != 0 and currentPrice is not None and target_mean is not None:
                target_incr = ((target_mean - currentPrice) / currentPrice) * 100
                upside = str(round(target_incr)) + '%' if target_incr < 0 else '+' + str(round(target_incr)) + '%'
            else: 
                upside = 'N/A'
            
            debtToEquity = info.get('debtToEquity', None) # < 0.5
            debtToEquity = debtToEquity/100 if debtToEquity is not None else None
            currentRatio = info.get('currentRatio', None) # 초점: 회사의 단기 유동성, > 1.5 && < 2.5
            
            pbr = info.get('priceToBook', None) # 초점: 자산가치, 저pbr종목은 저평가된 자산 가치주로 간주. 장기 수익률 설명력 높음 < 1.5 (=being traded at 1.5 times its book value (asset-liab))
            if not pbr and country == 'KR': pbr = getFs('PBR', ticker) # 주가가 그 기업의 자산가치에 비해 과대/과소평가되어 있다는 의미. 낮으면 자산활용력 부족
            per = info.get('trailingPE', None) # 초점: 수익성, over/undervalue? 저per 종목 선별, 10-20전후(혹은 산업평균)로 낮고 높음 구분. 주가가 그 기업의 이익에 비해 과대/과소평가되어 있다는 의미
            if not per and country == 'KR': per = getFs('PER', ticker) # high per expects future growth but could be overvalued(=버블). 
                                                                       # low per could be undervalued or company in trouble, IT, 바이오 등 성장산업은 자연스레 per이 높게 형성
                                                                       # 저per -> 수익성 높거나 주가가 싸다 고pbr -> 자산은 적은데 시장에서 비싸게 봐준다
            industry_per = get_industry_per(industry, ticker)
            industry_roe = get_industry_roe(industry)
            industry_roa = get_industry_roa(industry)

            roe = info.get('returnOnEquity', None) # 수익성 높은 기업 선별. 고roe + 저pbr 조합은 가장 유명한 퀀트 전략. > 8% (0.08) 주주 입장에서 수익성
            roa = info.get('returnOnAssets', None) # > 6% (0.06), 기업 전체 효율성
            #ROE가 높고 ROA는 낮다면? → 부채를 많이 이용해 수익을 낸 기업일 수 있음. ROE와 ROA 모두 높다면? → 자산과 자본 모두 효율적으로 잘 운용하고 있다는 의미.
            #A = L + E
            
            eps_growth = has_stable_eps_growth_cagr(ticker) # earnings per share, the higher the better, Buffet looks for stable EPS growth
            # eps_growth_quart = has_stable_eps_growth_quarterly(ticker) 
            div_growth = has_stable_dividend_growth_cagr(ticker) # Buffet looks for stable dividend growth for at least 10 years
            # bvps_growth = bvps_undervalued(info.get('bookValue', None), currentPrice)
            
            icr = get_interest_coverage_ratio(ticker)

            short_momentum = momentum_3m[ticker]
            mid_momentum = momentum_6m[ticker]
            long_momentum = momentum_12m[ticker]

            cyclicality = 0
            # ACTIVATE THE CODE BELOW TO SCORE CYCLICALITY DEPENDING ON CURRENT MACROECON SITUATION
            # classification = classify_cyclicality(industry)
            # if classification == 'defensive':
            #     cyclicality +=1
            # elif classification == 'cyclical':
            #     cyclicality -=0.5


            quantitative_buffet_score = buffet_score(debtToEquity, currentRatio, pbr, per, industry_per, roe, industry_roe, roa, industry_roa, eps_growth, div_growth, icr) + momentum_score(short_momentum, mid_momentum, long_momentum) + cyclicality

            rec = info.get('recommendationKey', None)
            if country is None:
                esg = get_esg_score(ticker)
            else:
                esg = ''

            ## FOR extra 10 score:::
            # MOAT -> sustainable competitive advantage that protects a company from its competitors, little to no competition, dominant market share, customer loyalty 
            # KEY: sustainable && long-term durability
            # ex) brand power(Coca-Cola), network effect(Facebook, Visa), cost advantage(Walmart, Costco), high switching costs(Adobe),
            # regulatory advantage(gov protection), patients(Pfizer, Intel)

            result = {
                "Ticker": ticker,
                "Name": name,
                "Industry": industry,
                "Price": f"{currentPrice:,.0f}" + percentage_change if country == 'KR' or country == 'JP' else f"{currentPrice:,.2f}" + percentage_change,
                "D/E": round(debtToEquity, 2) if debtToEquity is not None else None,
                "CR": round(currentRatio, 2) if currentRatio is not None else None,
                "PBR": round(pbr,2) if pbr is not None else None,
                "PER": round(per,2) if per is not None else None,
                "ROE": str(round(roe*100,2)) + '%' if roe is not None else None,
                "ROA": str(round(roa*100,2)) + '%' if roa is not None else None,
                "ICR": icr,
                "EPS CAGR": eps_growth if isinstance(eps_growth, bool) else (f"{eps_growth:.2%}" if eps_growth is not None else None), #use this instead of operating income incrs for quart/annual 
                "DIV CAGR": f"{div_growth:.2%}" if div_growth is not None else None,
                "B-Score": round(quantitative_buffet_score, 1),
                'Analyst Forecast': rec + '(' + upside + ')',
                'Momentum': "/".join(f"{m:.1%}" if m is not None else "None" for m in (short_momentum, mid_momentum, long_momentum)),
                'ESG': esg,
            }

            with shelve.open("company_cache") as cache:
                cache[name] = quantitative_buffet_score

            with data_lock:
                if quantitative_buffet_score >= CUTOFF:
                    data.append(result)
                    with shelve.open("ticker_cache") as cache:
                        cache[ticker] = name

        except Exception as e:
            if "429" in str(e):
                print("Too many requests! Waiting 10 seconds...")
                time.sleep(10)
            # data.append({
            #     "Ticker": ticker,
            #     "Name": '',
            #     "Industry": '',
            #     "Price": '',
            #     "D/E": 0,
            #     "CR": 0,
            #     "PBR": 0,
            #     "PER": 0,
            #     "ROE": 0,
            #     "ROA": 0,
            #     "ICR": 0,
            #     "EPS CAGR": '',
            #     "DIV CAGR": '',
            #     "B-Score": 0.0,
            #     'Analyst Forecast': '',
            #     'Momentum': '',
            #     'ESG': '',
            # })

        finally:
            q.task_done()
            time.sleep(2)
    

threads = []

for _ in range(NUM_THREADS):
    t = threading.Thread(target=process_ticker_quantitatives)
    t.start()
    threads.append(t)

for t in threads:
    t.join()

df = pl.DataFrame(data)
# df.dropna(subset=["D/E", "CR", "P/B", "ROE", "ROA", "PER", "ICR"], inplace = True)

df_sorted = df.sort("B-Score", descending = True)

if country: 
    df_sorted.to_pandas().to_excel(f"result_{country}_{formattedDate}.xlsx", index=False)

elif sp500:
    df_sorted.to_pandas().to_excel(f"sp500_{formattedDate}.xlsx", index=False)
else:
    df_sorted.to_pandas().to_excel(f"nasdaq100_{formattedDate}.xlsx", index=False)
