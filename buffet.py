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
import math
from queue import Queue
import threading
import time

# pip install -r requirements.txt

country = input('Country (KR, JP, CH, UK 중 선택. 미국 S&P500 및 NASDAQ100 희망 시 US 입력): ').upper() # None or one of the following: KR, US, JP, CH, UK, ETC
num_thread = 20
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

weekend = dt.datetime.today().weekday() - 4 # returns 1 for saturday, 2 for sunday
formattedDate = (dt.datetime.today() - dt.timedelta(days = weekend)).strftime("%Y%m%d") if dt.datetime.today().weekday() >= 5 else dt.datetime.today().strftime("%Y%m%d")

dfKospi = stock.get_market_fundamental(formattedDate)
data = []
data_lock = threading.Lock()

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

system_prompt = """
You are a financial analyst AI trained in Warren Buffett’s investment style. Your task is to analyze a company's long-term competitive advantage (economic moat) 
based on high-quality, trustworthy public information.

When answering:
- Search the web for **the most recent, relevant data**
- Only use **neutral, fact-based, and highly reliable sources** like Bloomberg, Reuters, WSJ, Financial Times, investor relations pages, or annual reports
- Ignore social media, biased blogs, promotional material, and wikipedias.
- Return a single integer as the response output without any text explanation

Analyze whether the company exhibits:
- Brand strength
- Network effects
- Cost leadership
- Switching costs
- Intangible assets (e.g., patents, licensing)
- Dominant market share via efficient scale

Be specific and concise. Use business evidence, not vague impressions. Avoid speculation.
"""

client = OpenAI()

moat = {
    3: "Unbreachable (3)",
    2: "Strong (2)",
    1: "Narrow (1)",
    0: "None (0)"
}

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

def buffet_score (de, cr, pbr, roe, roa, eps, div, bvps, icr):
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
    if div: #bool
        score +=1
    if eps: #bool
        score +=1
    if bvps: #bool
        score +=1
    if icr is not None and icr >= 5:
        score +=1
    # MAX: 9
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
    
    recent_years = sorted(annual_divs.index)[-8:-1] # returns [last year - 9 = 2015, 2016, ..., last year = 2024], # use -11 to start around 10 years ago from now

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
            if math.isnan(interest_expense) or math.isnan(ebit) or not interest_expense:
                continue # Avoid division by zero
            else:
                ratio = round((ebit / abs(interest_expense)), 2)
                break
        except KeyError:
            continue
    return ratio

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


tickers = get_tickers(country, limit, sp500)
# tickers = ['AAPL']

q = Queue()
for ticker in tickers:
    q.put(ticker)

def process_ticker_quantitatives():
    while not q.empty():
        ticker = q.get()
        try:
            info = yf.Ticker(ticker).info
            name = info.get("longName") or info.get("shortName", ticker)
            sector = info.get("sector", None)
            currentPrice = info.get("currentPrice", None)
            debtToEquity = info.get('debtToEquity', None) # < 0.5
            debtToEquity = debtToEquity/100 if debtToEquity is not None else None
            currentRatio = info.get('currentRatio', None) # > 1.5 && < 2.5
            pbr = info.get('priceToBook', None) # 저pbr종목은 저평가된 자산 가치주로 간주. 장기 수익률 설명력 높음 < 1.5 (=being traded at 1.5 times its book value (asset-liab))
            if not pbr and country == 'KR': pbr = getFs('PBR', ticker)

            roe = info.get('returnOnEquity', None) # 수익성 높은 기업 선별. 고roe + 저pbr 조합은 가장 유명한 퀀트 전략. > 8% (0.08) && consistent/incr over the last 10y
            roa = info.get('returnOnAssets', None) # > 6% (0.06) 
            per = info.get('trailingPE', None) # 저per 종목 선별, price investors are willing to pay for $1 of a company's earnings, 
            if not per and country == 'KR': per = getFs('PER', ticker) # high per expects future growth but could be overvalued. low per could be undervalued or company in trouble
            
            eps_growth = has_stable_eps_growth(ticker) # earnings per share, the higher the better, # 저per 종목 선별, Buffet looks for stable EPS growth
            div_growth = has_stable_dividend_growth(ticker) # Buffet looks for stable dividend growth for at least 10 years
            bvps_growth = has_stable_book_value_growth(ticker, sector)
            icr = get_interest_coverage_ratio(ticker)
            quantitative_buffet_score = buffet_score(debtToEquity, currentRatio, pbr, roe, roa, eps_growth, div_growth, bvps_growth, icr)

            ## FOR extra 10 score:::
            # MOAT -> sustainable competitive advantage that protects a company from its competitors, little to no competition, dominant market share, customer loyalty 
            # KEY: sustainable && long-term durability
            # ex) brand power(Coca-Cola), network effect(Facebook, Visa), cost advantage(Walmart, Costco), high switching costs(Adobe),
            # regulatory advantage(gov protection), patients(Pfizer, Intel)

            user_prompt = f"""
            Search the web using trusted financial and business sources to evaluate the economic moat of the following company 
            and only return an integer based on it as the output:
            
            Company: {name}
            Sector: {sector}
            These are the recent metrics of the company {name} (ignore the metrics that are 0 or missing):
            - ROE: {roe}
            - ROA: {roa}
            - PBR: {pbr}
            - PER: {per}

            Search for the following:
            - Notable Assets: e.g. Patents, Ecosystem, Strong Brand
            - Customer Base: e.g. Mass market, Enterprises, Government
            - Consistency & Durability: e.g. Is the advantage sustainable over decades? Is it resilient through market cycles?
            - Cash Flow and Free Cash Flow
            - Customer Loyalty & Pricing Power: e.g. Do customers prefer the product despite higher prices?
            - Management Quality: e.g. Buffett prefers companies with "able and honest" managers who act in shareholders' interests and allocate capital wisely.

            Analyze the following based on recent metrics and search result:
            1. Type of moat(s)
            2. How durable the moat is
            3. Key risks or threats
            4. Final verdict: Unbreachable (Extremely rare, this level suggests an almost insurmountable advantage, often due to monopolistic control, 
            proprietary technology, or network effects.)/ Strong (The company possesses strong, sustainable competitive advantages that are difficult to replicate.) / 
            Narrow (The company has some advantages, but competitors can erode them over time./ 
            No moat (The company has little to no lasting competitive advantage, making it vulnerable to competition.) — with justification

            **Return one of the following integers as the final output:**  
            - `3` if the company has a **Unbreachable** moat  
            - `2` if the company has a **Strong** moat  
            - `1` if the company has a **Narrow** moat
            - `0` if the company has a **No** moat or no moat  

            The final output must be a single integer with no additional text. 
            """.strip()

            response = client.responses.create(
            model="gpt-4o",
            instructions=system_prompt,
            input=user_prompt,
            tools=[{
                "type": "web_search_preview",
                "user_location": {
                    "type": "approximate",
                    "country": "KR",
                    "city": "Seoul",
                    "region": "Seoul",
                }
            }],
            )

            try:
                moat_score = int(response.output_text)
            except Exception as e:
                moat_score = 0

            result = {
                "Ticker": ticker,
                "Name": name,
                "Sector": sector,
                "Price": currentPrice,
                "D/E": debtToEquity,
                "CR": currentRatio,
                "PBR": pbr,
                "ROE": roe,
                "ROA": roa,
                "PER": per,
                "ICR": icr,
                "EPS Growth": eps_growth,
                "Div Growth": div_growth ,
                "BVPS Growth": bvps_growth,
                "B-Score": quantitative_buffet_score,
                "Moat": moat[moat_score],
                "Total(12)": quantitative_buffet_score + moat_score
            }
            with data_lock:
                data.append(result)
        except Exception as e:
            data.append({
                "Ticker": ticker,
                "Name": '',
                "Sector": '',
                "Price": 0,
                "D/E": 0,
                "CR": 0,
                "PBR": 0,
                "ROE": 0,
                "ROA": 0,
                "PER": 0,
                "ICR": 0,
                "EPS Growth": False,
                "Div Growth":  False,
                "BVPS Growth": False,
                "B-Score": 0,
                "Moat": 0,
                "Total(12)": 0

            })
        finally:
            q.task_done()
            time.sleep(0.5)
    

# Use multithreading to speed up
num_threads = 10

threads = []
for _ in range(num_threads):
    t = threading.Thread(target=process_ticker_quantitatives)
    t.start()
    threads.append(t)

for t in threads:
    t.join()

df = pd.DataFrame(data)
# df.dropna(subset=["D/E", "CR", "PBR", "ROE", "ROA", "PER", "ICR"], inplace = True)

df_sorted = df.sort_values(by = "Total(12)", ascending = False)

if country: 
    df_sorted.to_excel("result_" + country + ".xlsx", index=False)

elif sp500:
    df_sorted.to_excel("sp500.xlsx", index=False)
else:
    df_sorted.to_excel("nasdaq100.xlsx", index=False)

