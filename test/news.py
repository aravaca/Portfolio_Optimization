import requests
import json
from dotenv import load_dotenv
import os

load_dotenv()

# Get the API key
api_key = os.getenv("NEWSAPI_API_KEY")

# Endpoint
url = 'https://newsapi.org/v2/everything'

moat_keywords = [
    "brand strength",
    "pricing power",
    "economies of scale",
    "dominant",
    "switching costs",
    "patent",
    "leader",
    "recurring revenue",
    "sustainable",
    "competitive",
    "cost leadership",
    "customer loyalty",
    "network",
    "margin",
    "exclusive",
    "regulatory",
]

# Combine keywords using OR, then prepend company name
moat_query = " AND (" + " OR ".join(f'"{key}"' for key in moat_keywords) + ")"
print(moat_query)

# Parameters for Bloomberg finance news
params = {
    'q': 'Hyundai' + moat_query, #company name
    'domains': 'bloomberg.com,reuters.com,wsj.com,cnbc.com,marketwatch.com,finance.yahoo.com,'
    'hankyung.com,mk.co.kr,yna.co.kr,mt.co.kr,edaily.co.kr,asiae.co.kr,'
    'ft.com,economist.com,asia.nikkei.com',
    # 'language': 'en',
    'pageSize': 1, # number of articles to return
    'sortBy': 'relevance',
    'apiKey': api_key
}

# Make the request
response = requests.get(url, params=params)

# Parse the JSON response
data = response.json()

# Structured output
for i, article in enumerate(data.get('articles', []), start=1):
    print(f"{i}. {article['title']}")
    print(f" Source: {article['source']['name']}")
    print(f" Published At: {article['publishedAt']}")
    print(f" Description: {article['description']}")
    # print(f" Content: {article['content']}")
    print(f" URL: {article['url']}\n")