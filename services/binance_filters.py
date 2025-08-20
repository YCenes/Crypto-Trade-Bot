# services/binance_filters.py
import math
import threading
from typing import Optional
import requests

# (opsiyonel) config override
try:
    from paper_trader.config import PRICE_TICKS
except Exception:
    PRICE_TICKS = {}

_EXINFO_CACHE = {}
_LOCK = threading.Lock()

def _fetch_price_tick(symbol: str) -> Optional[float]:
    url = f"https://api.binance.com/api/v3/exchangeInfo?symbol={symbol.upper()}"
    r = requests.get(url, timeout=(3, 10))
    r.raise_for_status()
    data = r.json()
    sym = data["symbols"][0]
    for f in sym.get("filters", []):
        if f.get("filterType") == "PRICE_FILTER":
            tick = float(f.get("tickSize"))
            # Bazı sembollerde 0.00000000 gibi olabilir; 0’dan büyük en küçük
            return tick if tick > 0 else None
    return None

def get_price_tick(symbol: str) -> Optional[float]:
    s = symbol.upper()
    # 1) Config override
    if s in PRICE_TICKS:
        return float(PRICE_TICKS[s])

    # 2) Cache
    with _LOCK:
        if s in _EXINFO_CACHE:
            return _EXINFO_CACHE[s]
    # 3) Fetch
    try:
        tick = _fetch_price_tick(s)
    except Exception:
        tick = None
    with _LOCK:
        _EXINFO_CACHE[s] = tick
    return tick

def round_to_tick(value: float, tick: Optional[float]) -> float:
    if not tick or tick <= 0:
        return float(value)
    return round(value / tick) * tick

def floor_to_tick(value: float, tick: Optional[float]) -> float:
    if not tick or tick <= 0:
        return float(value)
    return math.floor(value / tick) * tick

def ceil_to_tick(value: float, tick: Optional[float]) -> float:
    if not tick or tick <= 0:
        return float(value)
    return math.ceil(value / tick) * tick
