
import yfinance as yf


import pandas as pd

import yfinance as yf

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
    "mortgage", "real estate", "aerospace", "defense", "freight", "logistics", "airline",
    "building", "conglomerate", "construction", "electrical equipment", "engineering",
    "industrial", "machinery", "marine", "railroad", "waste", "chemical", "container",
    "metal", "paper", "advertising", "broadcasting", "cable", "casino", "communication",
    "gaming", "interactive media", "movies", "publishing", "radio", "recreational",
    "software", "semiconductor", "information technology", "it services", "steel"
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

    
print(classify_cyclicality('pharmace'))