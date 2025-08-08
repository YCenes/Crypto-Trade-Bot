import requests
import pandas as pd
from datetime import datetime

def get_klines(symbol="BTCUSDT", interval="4h", limit=500):
    url = f"https://api.binance.com/api/v3/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }
    response = requests.get(url, params=params)
    data = response.json()

    klines = []
    for k in data:
        klines.append({
            "timestamp": datetime.fromtimestamp(k[0] / 1000),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
        })

    df = pd.DataFrame(klines)
    return df
