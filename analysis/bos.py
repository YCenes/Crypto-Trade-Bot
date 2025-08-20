# analysis/bos.py

from typing import List, Tuple, Dict, Any
import pandas as pd

# Tip: sinyal formatı (timestamp, value, "BUY"/"SELL")
Signal = Tuple[pd.Timestamp, float, str]

def _last_prior_swing(swing_list: List[Tuple[pd.Timestamp, float]], ts: pd.Timestamp):
    """ ts'ten ÖNCEKİ son swing değerini döndür (yoksa None). """
    for t, v in reversed(swing_list):
        if t < ts:
            return v
    return None

def detect_bos_events(
    df: pd.DataFrame,
    swing_highs: List[Tuple[pd.Timestamp, float]],
    swing_lows: List[Tuple[pd.Timestamp, float]],
    breach_buffer_pct: float = 0.0005  # %0.05 = "net kırılım" toleransı
) -> List[Dict[str, Any]]:
    """
    BoS (Break of Structure) olaylarını bul.
    - Bullish BoS: close > last_swing_high * (1 + buffer) ve önceki close <= eşik
    - Bearish BoS: close < last_swing_low  * (1 - buffer) ve önceki close >= eşik
    """
    events: List[Dict[str, Any]] = []
    if len(df) < 2:
        return events

    for i in range(1, len(df)):
        ts = df["timestamp"].iloc[i]
        close_now = float(df["close"].iloc[i])
        close_prev = float(df["close"].iloc[i-1])

        # Önceki close'a göre "cross" kontrolü yapalım ki aynı bölgeyi defalarca saymayalım.
        last_high = _last_prior_swing(swing_highs, ts)
        last_low  = _last_prior_swing(swing_lows,  ts)

        # Bullish BoS
        if last_high is not None:
            thr_up = last_high * (1.0 + breach_buffer_pct)
            if close_prev <= thr_up and close_now > thr_up:
                events.append({
                    "time": ts,
                    "direction": "BUY",
                    "broken_level": float(last_high),
                    "close": close_now,
                    "index": i
                })

        # Bearish BoS
        if last_low is not None:
            thr_dn = last_low * (1.0 - breach_buffer_pct)
            if close_prev >= thr_dn and close_now < thr_dn:
                events.append({
                    "time": ts,
                    "direction": "SELL",
                    "broken_level": float(last_low),
                    "close": close_now,
                    "index": i
                })

    return events


def build_bos_retest_signals(
    df: pd.DataFrame,
    swing_highs: List[Tuple[pd.Timestamp, float]],
    swing_lows: List[Tuple[pd.Timestamp, float]],
    breach_buffer_pct: float = 0.0005,   # BoS kırılım toleransı
    retest_window_bars: int = 3,         # BoS sonrası şu kadar bar içinde retest arar
    retest_zone_pct: float = 0.0015      # Kırılan seviyenin +/- %0.15'i retest zonu
) -> List[Signal]:
    """
    1) BoS olaylarını tespit et
    2) Her BoS için, ileriye dönük retest ara:
       - Bullish: low <= broken_high*(1+zone) ve close >= broken_high
       - Bearish: high >= broken_low*(1-zone)  ve close <= broken_low
    3) Retest bulunduğunda sinyal zamanı = retest barının timestamp'i.
       (Bizim backtest'te entry = sinyal + 1 bar'ın AÇILIŞI olacak.)
    """
    signals: List[Signal] = []
    if not df["timestamp"].is_monotonic_increasing:
        df = df.sort_values("timestamp").reset_index(drop=True)

    bos_events = detect_bos_events(df, swing_highs, swing_lows, breach_buffer_pct=breach_buffer_pct)

    for ev in bos_events:
        idx_bos = ev["index"]
        direction = ev["direction"]
        level = ev["broken_level"]

        # İleriye dönük retest aralığı
        start = idx_bos + 1
        end   = min(len(df), idx_bos + 1 + retest_window_bars)

        found = False
        for j in range(start, end):
            row = df.iloc[j]
            ts  = row["timestamp"]
            o, h, l, c = float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])

            if direction == "BUY":
                # Kırılan high, artık destek: oraya retest + tekrar üstünde kapanış
                zone_up = level * (1.0 + retest_zone_pct)
                if l <= zone_up and c >= level:
                    signals.append((ts, c, "BUY"))
                    found = True
                    break
            else:
                # Kırılan low, artık direnç: oraya retest + tekrar altında kapanış
                zone_dn = level * (1.0 - retest_zone_pct)
                if h >= zone_dn and c <= level:
                    signals.append((ts, c, "SELL"))
                    found = True
                    break

        # Retest bulunmazsa sinyal yok (BoS tek başına yetmez)
        if not found:
            continue

    # Aynı timestamp üzerine birden fazla sinyal gelirse ilkini koru
    uniq, seen = [], set()
    for t, v, d in signals:
        if t not in seen:
            uniq.append((t, v, d))
            seen.add(t)
    return uniq
