# 📊 Buffett-Style Quant Stock Screener (Global + Korean Markets)

This Python program screens and scores stocks using **Buffett-style value investing principles**. It gathers the most recent financial data from:

- 🇺🇸 **Yahoo Finance (yfinance)**  
- 🌏 **FMP API (Financial Modeling Prep)**  
- 🇰🇷 **Naver Finance** and **KRX (KOSPI/KOSDAQ)**  

The program (buffett.py) computes scores based on profitability, valuation, debt, and other fundamentals and exports results to a **clean Excel file**, providing practical insight to investors.

*** The repository also includes sharpe.ipynb and sortino.ipynb, which allow for the maximization of Sharpe and Sortino ratios for a group of stocks to optimize a portfolio.

Please note that this program only analyzes a business's financials and doesn't provide a complete assessment of its overall quality.  For a thorough understanding, you should supplement this information with your own research, including relevant financial news, to make informed investment decisions.

---

## ⚙️ Features

- ✅ Gathers tickers from multiple global markets (US, KR, JP, CH, UK)
- ✅ Uses multithreading for fast data retrieval on hundreds of tickers
- ✅ Scores each stock based on Buffett-style logic:
  - Undervalued companies with great profitability
  - Low debt-to-equity
  - Strong ROE & ROA
  - Healthy dividend yields
  - Reasonable valuation (P/E, P/B, PEG)
  - Sector-relative fundamentals
- ✅ Exports results to Excel for easy analysis
- ✅ Includes analyst forecast (although Buffet didn't really care about this)
- ✅ Includes ESG scores (only if available)


---

## 🚀 Getting Started

### 1. Clone the Repository

```bash
gh repo clone aravaca/Portfolio_Optimization
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```
### 3. Set Up API Keys
```bash
touch .env
```
```ini
FMP_API_KEY=your_api_key_here
```

### 4. Scoring Logic (Buffett Style)

The program assigns a score to each stock based on Warren Buffett’s value investing criteria, with some additional quant insights:

| Metric              | Rule / Threshold                                               | Score Impact        |
|---------------------|----------------------------------------------------------------|---------------------|
| Debt-to-Equity      | ≤ 0.5                                                          | +1                  |
| Current Ratio       | Between 1.5 and 2.5                                            | +1                  |
| Price-to-Book (P/B) | ≤ 1.5                                                          | +1                  |
| Return on Equity    | ≥ 8-10%                                                           | +1                  |
| Return on Assets    | ≥ 5-6%                                                           | +1                  |
| Dividend Trend      | Positive 10Y growth ≥ 10% → +1.5, ≥ 8% → +1, ≥ 6% → +0.5       | +0.5 ~ +1.0        |
| EPS Trend           | Positive 3Y CAGR or strong growth                              | -1 ~ +1             |
| PEG Ratio           | PEG < 1 (if EPS & PER available)                               | +1                  |
| Interest Coverage   | ≥ 5x                                                           | +1                  |
| Industry Comparison | High PER & low ROE → -2~-3; low PER & strong ROE → +1~+2          | -2 ~ +2             |
| Momentum (3m,6m,12m)| Scores based on designated weights on each time window         | -1 ~ +1             |
| Cyclicity (optional)| Scores based on whether the stock is cyclical, defensive, or politically-themed | -1 ~ +1             |

Higher scores indicate better Buffett-style value candidates. You can add your own quant ideas on top of these basic conditions.

## 🌍 Supported Markets

You can choose from the following countries when prompted:

| Code | Country            | Description                     |
|------|--------------------|---------------------------------|
| US   | United States      | S&P 500 or NASDAQ-100           |
| KR   | South Korea        | KOSPI + KOSDAQ via KRX/Naver    |
| JP   | Japan              | Top Japanese stocks via FMP     |
| CH   | China              | Top Chinese stocks via FMP      |
| UK   | United Kingdom     | Top UK stocks via FMP           |

📌 *If you input 'US' as country, you will be asked to choose between S&P 500 and NASDAQ-100 listed stocks.*

##  Usage
```bash
python buffett.py
```
**Predetermined fields**
```
NUM_THREADS = 20 #number of multithreading processors (try 10~20 to not hog your system)
CUTOFF = 5 #only tickers that scored above CUTOFF will appear on excel
kw_list = [] #수혜주/경기주/방어주 산업군 키워드 리스트
```
**Limit** should be the number of tickers to process. 
100 tickers take less than a minute and going over 500 could take up to a few minutes.
```vbnet
Country (KR, JP, CH, US, UK 중 선택): KR
Limit: 50 
May take up to few minutes...
```

## Built With
**yfinance**...for data retrieval on global and Korean markets

**FMP API**...for data retrieval on global and Korean markets (free API required)

**Naver Finance**...for data retrieval on Korean markets

**pykrx**...for data retrieval on Korean markets

**Polars**...for faster data processing and aggregation compared to pandas. Utilizes multithreading and is memory-efficient on large datasets unlike pandas

**BeautifulSoup**...for web scraping from Naver Finance and FullRatio


## 📁 Output
**result_KR_20250602.xlsx** 


## 📄 License

This project is licensed under the **MIT License**.  
You are free to use, modify, and distribute this code for personal or commercial purposes.

---

## 🙌 Acknowledgements

- Inspired by **Warren Buffett's** value investing philosophy  
- Financial data sources:
  - [Yahoo Finance](https://finance.yahoo.com)
  - [Financial Modeling Prep](https://financialmodelingprep.com)
  - [Naver Finance](https://finance.naver.com)
  - [KRX via pykrx](https://github.com/sharebook-kr/pykrx)
  - [FullRatio](https://fullratio.com/)
- Built using Python and multithreading for performance

---

## ✍️ Author

© 2025 **Hyungsuk Choi** <chs_3411@naver[dot]com>, University of Maryland 
[GitHub Profile](https://github.com/aravaca) 


