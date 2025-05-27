
import yfinance as yf

ticker = yf.Ticker("012450.KS")
q_fin = ticker.quarterly_financials  # 분기별 손익계산서 데이터프레임

# print(q_fin)
# print(ticker.quarterly_earnings)        # Quarterly earnings
print(ticker.sustainability.loc['totalEsg'])            # ESG scores (if available)
print('buy' in ticker.info['recommendationKey'])