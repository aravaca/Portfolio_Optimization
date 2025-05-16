import yfinance as yf
import pandas as pd
import openai
from openai import OpenAI
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Get the API key
api_key = os.getenv("OPENAI_API_KEY")

# Use it with OpenAI
openai.api_key = api_key

# tickers = pd.read_csv("https://datahub.io/core/s-and-p-500-companies/r/constituents.csv")["Symbol"].tolist()
tickers = ['AAPL', 'MSFT', 'NVDA', 'GOOG', 'AMZN', 'META', 'BRK-B', 'AVGO', 'TSM', 'WMT', 'LLY', 'JPM']
data = []

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

for ticker in tickers:
    info = yf.Ticker(ticker).info
    debtToEquity = info.get('debtToEquity', None) # < 0.5
    debtToEquity = debtToEquity/100 if debtToEquity is not None else None
    currentRatio = info.get('currentRatio', None) # > 1.5 && < 2.5
    pbr = info.get('priceToBook', None) # 저pbr종목은 저평가된 자산 가치주로 간주. 장기 수익률 설명력 높음 < 1.5
    roe = info.get('returnOnEquity', None) # 수익성 높은 기업 선별. 고roe + 저pbr 조합은 가장 유명한 퀀트 전략. > 8% (0.08) && consistent/incr over the last 10y
    roa = info.get('returnOnAssets', None) # > 6% (0.06) 
    per = info.get('trailingPE', None) # 저per 종목 선별
    # eps_growth = get_eps_stability(ticker, 5).get("EPS CAGR") # 저per 종목 선별, Buffet looks for stable EPS growth
    # div_growth = dividend_cagr_fmp(ticker, "60ZVxqQtumzWp4LVs4PmJOjiNSnbGThu", 10) # Buffet looks for stable dividend growth for at least 10 years
    # MOAT -> sustainable competitive advantage that protects a company from its competitors, little to no competition, dominant market share, customer loyalty 
    # KEY: sustainable && long-term durability
    # ex) brand power(Coca-Cola), network effect(Facebook, Visa), cost advantage(Walmart, Costco), high switching costs(Adobe),
    # regulatory advantage(gov protection), patients(Pfizer, Intel)

    data.append({
        "Ticker": ticker,
        "D/E": debtToEquity,
        "C/R": currentRatio,
        "PBR": pbr,
        "ROE": roe,
        "ROA": roa,
        # "EPS Growth": eps_growth,
        # "Div Growth": div_growth,
        "PER": per,
    })

df = pd.DataFrame(data)
df.dropna(subset=["D/E", "C/R", "PBR", "ROE", "ROA", "PER"], inplace = True)

df_sorted = df.sort_values(by = "ROE", ascending = False)
print(df_sorted)

