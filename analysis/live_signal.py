# analysis/live_signal.py
from typing import Optional, Dict, Any, Tuple
import pandas as pd

from services.binance_service import get_klines
from analysis.swing_points import detect_swing_points
from analysis.trend_structure import classify_trend_structure


def _find_last_swing_before(time_ref, arr: list) -> Tuple[Optional[float], Optional[pd.Timestamp]]:
    """arr: [(timestamp, value), ...]"""
    for t, v in reversed(arr):
        if t <= time_ref:
            return float(v), t
    return None, None


def get_live_signal(
    symbol: str = "BTCUSDT",
    interval: str = "1h",
    limit: int = 500,

    # Backtest ile hizalı sabitler
    rr_ratio: float = 1.5,
    sl_buffer_pct: float = 0.005,     # entry * %0.5
    max_tp_percent: float = 0.05,     # TP tavanı ±%5
    max_risk_pct: float = 0.02,       # risk %2 üstü trade açma
    max_bars_since_swing: int = 50,   # swing çok eskiyse alma

    # Backtest'te olmayanları varsayılan kapalı tutuyoruz
    min_tp_percent: float = 0.0,      # 0 → min TP mesafesi uygulanmaz
    min_risk_pct: float = 0.0,        # 0 → min risk filtresi uygulanmaz
    use_tick_quantize: bool = False,  # False → tick-size'e yuvarlama yok

    # 🔥 HTF (üst zaman dilimi) trend filtresi
    use_htf_filter: bool = True,
    htf_interval: str = "4h",
    htf_lookback: int = 3,
    htf_max_bars_since_swing: int = 300,  # HTF swing tazelik limiti (bar)
) -> Optional[Dict[str, Any]]:
    """
    Repaint yok:
      - Analiz yalnızca kapanmış barlarda (df[:-1])
      - Entry yeni barın OPEN'ı
      - HL → BUY:  SL = swing_low - buffer
      - LH → SELL: SL = swing_high + buffer
      - TP = RR*risk, sonra max_tp_percent ile sınırla
      - risk% > max_risk_pct ise sinyal verme
      - swing tazeliği kontrolü: HL/LH teyidine kadar olan SON uygun swing
      - (opsiyonel) min_tp_percent / min_risk_pct / tick quantize
      - (opsiyonel) HTF trend filtresi: 1h sinyal 4h yönüyle uyumlu değilse sinyal verme
    """
    # --- opsiyonel tick helpers ---
    tick = None
    def _round_to_tick(x: float, _tick: Optional[float]):  # raporlama amaçlı
        return float(round(x / _tick) * _tick) if (_tick and _tick > 0) else float(x)
    def _floor_to_tick(x: float, _tick: Optional[float]):
        if not _tick or _tick <= 0: return float(x)
        import math
        return float(math.floor(x / _tick) * _tick)
    def _ceil_to_tick(x: float, _tick: Optional[float]):
        if not _tick or _tick <= 0: return float(x)
        import math
        return float(math.ceil(x / _tick) * _tick)

    if use_tick_quantize:
        try:
            from services.binance_filters import get_price_tick, floor_to_tick, ceil_to_tick, round_to_tick
            tick = get_price_tick(symbol)
            _floor_to_tick = floor_to_tick
            _ceil_to_tick  = ceil_to_tick
            _round_to_tick = round_to_tick
        except Exception:
            pass  # fallback no-op

    # --- LTF (1h) veri ---
    df = get_klines(symbol=symbol, interval=interval, limit=limit)
    if df is None or len(df) < 30:
        return None

    closed_df = df.iloc[:-1].copy()   # sadece kapanmış barlarda analiz
    live_bar  = df.iloc[-1]
    entry_price = float(live_bar["open"])
    entry_time  = live_bar["timestamp"]

    try:
        closed_df = (
            closed_df.sort_values("timestamp")
                     .drop_duplicates(subset=["timestamp"])
                     .reset_index(drop=True)
        )
    except Exception:
        pass

    lookback = 3
    if len(closed_df) < 2*lookback + 5:
        return None

    swing_highs, swing_lows = detect_swing_points(closed_df, lookback=lookback)
    swing_highs = sorted(swing_highs, key=lambda x: x[0]) if swing_highs else []
    swing_lows  = sorted(swing_lows,  key=lambda x: x[0]) if swing_lows  else []

    trend_points = classify_trend_structure(swing_highs, swing_lows)
    if not trend_points:
        return None

    # LTF son teyitli HL/LH
    last_point_time, _val, last_label = trend_points[-1]

    # --- HTF (4h) TREND FİLTRESİ ---
    if use_htf_filter:
        cutoff_time = closed_df["timestamp"].iloc[-1]  # yalnızca LTF'in son kapanışına kadar HTF bak
        htf_df = get_klines(symbol=symbol, interval=htf_interval, limit=max(200, min(limit, 1000)))
        if htf_df is None or len(htf_df) < 20:
            return None  # HTF verisi yoksa sinyal üretme (korumacı)
        htf_closed = htf_df[htf_df["timestamp"] <= cutoff_time].copy()
        if len(htf_closed) < 10:
            return None

        try:
            htf_closed = (
                htf_closed.sort_values("timestamp")
                          .drop_duplicates(subset=["timestamp"])
                          .reset_index(drop=True)
            )
        except Exception:
            pass

        h_swing_highs, h_swing_lows = detect_swing_points(htf_closed, lookback=htf_lookback)
        h_swing_highs = sorted(h_swing_highs, key=lambda x: x[0]) if h_swing_highs else []
        h_swing_lows  = sorted(h_swing_lows,  key=lambda x: x[0]) if h_swing_lows  else []
        h_trend = classify_trend_structure(h_swing_highs, h_swing_lows)
        if not h_trend:
            return None

        # HTF son teyit: HL → BUY bias, LH → SELL bias
        h_last_t, _h_val, h_last_label = h_trend[-1]

        # HTF swing tazeliği (opsiyonel, geniş limit)
        idx_map_htf = {t: i for i, t in enumerate(htf_closed["timestamp"].tolist())}
        if (cutoff_time in idx_map_htf) and (h_last_t in idx_map_htf):
            if (idx_map_htf[cutoff_time] - idx_map_htf[h_last_t]) > htf_max_bars_since_swing:
                return None

        # Gate: 1h BUY sadece HTF HL ile; 1h SELL sadece HTF LH ile
        if last_label == "HL" and h_last_label != "HL":
            return None
        if last_label == "LH" and h_last_label != "LH":
            return None

    # --- LTF index map (tazelik) ---
    idx_map = {t: i for i, t in enumerate(closed_df["timestamp"].tolist())}

    def cap_buy_tp(raw_tp: float) -> float:
        return min(raw_tp, entry_price * (1.0 + max_tp_percent))

    def cap_sell_tp(raw_tp: float) -> float:
        return max(raw_tp, entry_price * (1.0 - max_tp_percent))

    raw_tp = None
    tp_capped = False
    effective_rr = None

    if last_label == "HL":
        direction = "BUY"
        swing, swing_t = _find_last_swing_before(last_point_time, swing_lows)
        if swing is None:
            return None

        # tazelik: swing → HL arası bar sayısı
        hl_idx    = idx_map.get(last_point_time)
        swing_idx = idx_map.get(swing_t)
        if hl_idx is not None and swing_idx is not None:
            if (hl_idx - swing_idx) > max_bars_since_swing:
                return None

        sl_unq = float(swing - entry_price * sl_buffer_pct)
        sl     = _floor_to_tick(sl_unq, tick) if use_tick_quantize else sl_unq
        risk   = entry_price - sl
        if risk <= 0:
            return None

        risk_pct = risk / entry_price
        if risk_pct > max_risk_pct:
            return None
        if min_risk_pct > 0.0 and risk_pct < min_risk_pct:
            return None

        raw_tp = entry_price + rr_ratio * risk
        tp     = float(cap_buy_tp(raw_tp))
        if min_tp_percent > 0.0:
            min_tp = entry_price * (1.0 + min_tp_percent)
            tp = max(tp, min_tp)
            if tp > entry_price * (1.0 + max_tp_percent):
                return None
        tp = _ceil_to_tick(tp, tick) if use_tick_quantize else tp

        tp_capped = (abs(tp - raw_tp) > 1e-12)
        effective_rr = (tp - entry_price) / risk

    elif last_label == "LH":
        direction = "SELL"
        swing, swing_t = _find_last_swing_before(last_point_time, swing_highs)
        if swing is None:
            return None

        lh_idx    = idx_map.get(last_point_time)
        swing_idx = idx_map.get(swing_t)
        if lh_idx is not None and swing_idx is not None:
            if (lh_idx - swing_idx) > max_bars_since_swing:
                return None

        sl_unq = float(swing + entry_price * sl_buffer_pct)
        sl     = _ceil_to_tick(sl_unq, tick) if use_tick_quantize else sl_unq
        risk   = sl - entry_price
        if risk <= 0:
            return None

        risk_pct = risk / entry_price
        if risk_pct > max_risk_pct:
            return None
        if min_risk_pct > 0.0 and risk_pct < min_risk_pct:
            return None

        raw_tp = entry_price - rr_ratio * risk
        tp     = float(cap_sell_tp(raw_tp))
        if min_tp_percent > 0.0:
            min_tp = entry_price * (1.0 - min_tp_percent)
            tp = min(tp, min_tp)
            if tp < entry_price * (1.0 - max_tp_percent):
                return None
        tp = _floor_to_tick(tp, tick) if use_tick_quantize else tp

        tp_capped = (abs(tp - raw_tp) > 1e-12)
        effective_rr = (entry_price - tp) / risk

    else:
        return None

    return {
        "signal": direction,
        "price": _round_to_tick(float(entry_price), tick) if use_tick_quantize else float(entry_price),
        "time":  entry_time,
        "sl":    float(sl),
        "tp":    float(tp),
        # Telemetry
        "rr_ratio": float(rr_ratio),
        "effective_rr": float(effective_rr),
        "sl_buffer_pct": float(sl_buffer_pct),
        "max_tp_percent": float(max_tp_percent),
        "max_risk_pct": float(max_risk_pct),
        "min_tp_percent": float(min_tp_percent),
        "min_risk_pct": float(min_risk_pct),
        "tp_capped": bool(tp_capped),
        "use_tick_quantize": bool(use_tick_quantize),
        "use_htf_filter": bool(use_htf_filter),
        "htf_interval": htf_interval,
    }
