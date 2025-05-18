import yfinance as yf
import pandas as pd
import openai
from openai import OpenAI
from dotenv import load_dotenv
import os
import requests
from pykrx import stock
import datetime as dt
import openpyxl

# pip install -r requirements.txt

country = input('Country (KR, JP, CH, UK 중 선택. 미국 S&P500 및 NASDAQ100 기업의 재무건전성 분석 희망시 US 입력): ').upper() # None or one of the following: KR, US, JP, CH, UK, ETC
if country == 'US': 
    country = None 

if not country:
    limit = 100
else:
    limit = int(float(input('Limit: ')))

if not country:
    sp500 = input('S&P500? (y/n, n for NASDAQ100): ').lower().strip() == 'y' # False for nasdaq100
else:
    sp500 = True

print('May take up to few minutes...')

weekend = dt.datetime.today().weekday() - 4 # returns 1 for saturday, 2 for sunday
formattedDate = (dt.datetime.today() - dt.timedelta(days = weekend)).strftime("%Y%m%d") if dt.datetime.today().weekday() >= 5 else dt.datetime.today().strftime("%Y%m%d")

dfKospi = stock.get_market_fundamental(formattedDate)

data = []

# Set Pandas to display all columns and rows
pd.set_option('display.max_rows', None)  # To display all rows
# pd.set_option('display.max_columns', None)  # To display all columns
pd.set_option('display.max_colwidth', None)  # To prevent truncation of column values

# Load environment variables from .env file
load_dotenv()

# Get the API key
api_key = os.getenv("OPENAI_API_KEY")
fmp_key = os.getenv("FMP_API_KEY")

# Use it with OpenAI
openai.api_key = api_key

def get_tickers(country: str, limit: int, sp500: bool):
    if country is not None:
        return get_tickers_by_country(country, limit, fmp_key) #US, JP, KR
    elif sp500:
        return pd.read_csv("https://datahub.io/core/s-and-p-500-companies/r/constituents.csv")["Symbol"].tolist()
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



# system_prompt = """
# You are a financial analyst AI specialized in company fundamentals, long-term growth, and competitive advantages. 
# Your task is to extract and summarize key financial growth data and insights in a structured format for investment 
# analysis utilizing available and highly reliable financial sources on the internet.
# Respond only with clean, structured Python list syntax. Avoid explanations or headings.
# """

# user_prompt = """
# Give me the following about Apple Inc:

# 1. 10-year dividend growth rate (as decimal or percent),
# 2. 5-year EPS growth rate (as decimal or percent),
# 3. Brief description of the company's strongest moat (e.g. brand, ecosystem, scale, IP),
# 4. 1~2 investment insights based on recent financial trends or durable competitive advantages.

# Return everything as a clean Python list like:
# [div_growth_10y, eps_growth_5y, "moat summary", "investment insight"]
# """


# client = OpenAI()

# response = client.responses.create(
#     model="gpt-4o",
#     instructions=system_prompt,
#     input=user_prompt,
# )

# print(response.output_text)

def buffet_score (de, cr, pbr, roe, roa, eps, div):
    score = 0
    if de is not None and de <= 0.5:
        score += 1
    if cr is not None and (cr >= 1.5 and cr <= 2.5):
        score +=1
    if pbr is not None and (pbr <= 1.5 and pbr != 0):
        score +=1
    if roe is not None and roe >= 0.08:
        score +=1
    if roa is not None and roa >= 0.06:
        score +=1
    if div:
        score +=1
    if eps:
        score +=1
    # MAX: 7 
    return score

def getFs (item, ticker):
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
    
    recent_years = sorted(annual_divs.index)[-11:-1] # returns [last year - 9 = 2015, 2016, ..., last year = 2024]
    if recent_years[0] < dt.datetime.today().year - 12: # sift out old data
        return False

    last_10_divs = [annual_divs[year] for year in recent_years]
    # print(last_10_divs)

    # Check for stable or increasing dividends
    tolerance = 0.85 # tolerance band to account for crises and minor dividend cuts
    return all(earlier * tolerance <= later for earlier, later in zip(last_10_divs, last_10_divs[1:])) # zip returns [(2015div, 2016div), (2016div, 2017div), ..., (2024div, 2025div)]
    

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


tickers = get_tickers(country, limit, sp500)
# tickers = ['AAPL']

for ticker in tickers:
    info = yf.Ticker(ticker).info
    name = info.get("longName", "N/A")
    sector = info.get("sector", "N/A")
    currentPrice = info.get("currentPrice", "N/A")
    debtToEquity = info.get('debtToEquity', None) # < 0.5
    debtToEquity = debtToEquity/100 if debtToEquity is not None else None
    currentRatio = info.get('currentRatio', None) # > 1.5 && < 2.5
    pbr = info.get('priceToBook', None) # 저pbr종목은 저평가된 자산 가치주로 간주. 장기 수익률 설명력 높음 < 1.5 (=being traded at 1.5 times its book value (asset-liab))
    if pbr is None and country == 'KR': pbr = getFs('PBR', ticker)

    roe = info.get('returnOnEquity', None) # 수익성 높은 기업 선별. 고roe + 저pbr 조합은 가장 유명한 퀀트 전략. > 8% (0.08) && consistent/incr over the last 10y
    roa = info.get('returnOnAssets', None) # > 6% (0.06) 
    per = info.get('trailingPE', None) # 저per 종목 선별, price investors are willing to pay for $1 of a company's earnings, 
    if per is None and country == 'KR': per = getFs('PER', ticker) # high per expects future growth but could be overvalued. low per could be undervalued or company in trouble
    
    eps_growth = has_stable_eps_growth(ticker) # earnings per share, the higher the better
    div_growth = has_stable_dividend_growth(ticker) # Buffet looks for stable dividend growth for at least 10 years
    quantitative_buffet_score = buffet_score(debtToEquity, currentRatio, pbr, roe, roa, eps_growth, div_growth)
    # eps_growth = get_eps_stability(ticker, 5).get("EPS CAGR") # 저per 종목 선별, Buffet looks for stable EPS growth
    # MOAT -> sustainable competitive advantage that protects a company from its competitors, little to no competition, dominant market share, customer loyalty 
    # KEY: sustainable && long-term durability
    # ex) brand power(Coca-Cola), network effect(Facebook, Visa), cost advantage(Walmart, Costco), high switching costs(Adobe),
    # regulatory advantage(gov protection), patients(Pfizer, Intel)

    data.append({
        "Ticker": ticker,
        "Name": name,
        "Sector": sector,
        "Price": currentPrice,
        "D/E": debtToEquity,
        "C/R": currentRatio,
        "PBR": pbr,
        "ROE": roe,
        "ROA": roa,
        "PER": per,
        "EPS Growth": eps_growth,
        "Div Growth": div_growth ,
        "B-Score": quantitative_buffet_score ,
    })

df = pd.DataFrame(data)
df.dropna(subset=["D/E", "C/R", "PBR", "ROE", "ROA", "PER"], inplace = True)

df_sorted = df.sort_values(by = "B-Score", ascending = False)

# print(df_sorted) 
df_sorted.to_excel("result.xlsx", index=False)

