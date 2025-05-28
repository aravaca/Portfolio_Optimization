
import yfinance as yf


ticker = yf.Ticker("012450.KS")

# Get last 2 days of price data
data = ticker.history(period="2d")

# Check if we have at least 2 days and prev_close is not zero
if len(data) >= 2:
    prev_close = data['Close'].iloc[-2]
    last_close = data['Close'].iloc[-1]

    if prev_close != 0:
        percent_change = ((last_close - prev_close) / prev_close) * 100
        print(f"{percent_change:.2f}%")  # e.g., -6.20%
    else:
        print("Previous close is zero. Cannot compute percentage change.")
else:
    print("Not enough data to calculate percentage change.")


# ticker = yf.Ticker("AAPL")
# q_fin = ticker.quarterly_financials  # 분기별 손익계산서 데이터프레임

# print(q_fin)
# print(ticker.quarterly_earnings)        # Quarterly earnin
# print(ticker.sustainability.loc['esgPerformance', 'esgScores'])
# print(ticker.sustainability)# ESG scores (if available)
# print('buy' in ticker.info['recommendationKey'])

# print(type(yf.download('005935.KS', period="5d")["Close"].iloc[-1, 0]))

            # try:
            #     sust = ticker.sustainability.get('totalEsg', None)
            #     rateY = ticker.sustainability.get('ratingYear', None)
            # except Exception:
            #     sust = ''
            #     rateY = ''
