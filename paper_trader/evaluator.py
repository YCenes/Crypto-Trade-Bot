# paper_trader/evaluator.py
from typing import Dict, Any, Optional
import math
import pandas as pd
from datetime import datetime


def _safe_float(x):
    try:
        return float(x)
    except Exception:
        return math.nan


def _fmt_ts(ts) -> str:
    # pd.Timestamp / datetime / str → "YYYY-MM-DD HH:MM:SS"
    if isinstance(ts, pd.Timestamp):
        ts = ts.tz_localize(None) if ts.tzinfo else ts
        return ts.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(ts, datetime):
        return ts.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(ts, str):
        return ts
    return ""


def evaluate_open_trade(
    trade: Dict[str, Any],
    closed_bar,            # dict-like: open/high/low/close/timestamp  (bir önceki KAPANMIŞ bar)
    new_open: float,       # yeni barın OPEN
    fee_roundtrip: float,
    conservative_double_hit: bool,
    timeout_close: Optional[int],     # None ya da int
    max_future_bars: int,
    new_open_time=None,    # yeni barın timestamp'i (OPEN_GAP_* için close_time yazmak üzere)
) -> Dict[str, Any]:
    """
    Backtest ile hizalı canlı kapatma sırası:
    - Yeni barın OPEN’ında gap kontrolü (OPEN_GAP_TP/SL) → close_time = new_open_time
    - (UYUM İÇİN) Entry’den hemen sonraki ilk değerlendirmede (bars_held == 0) kapanmış bar içini kontrol ETME.
      Sadece sayaç artır ve açık bırak. Böylece backtest’te “t0 bar aralığı atlanır” davranışı taklit edilir.
    - Sonraki değerlendirmelerde kapanmış bar içinde SL/TP (double-hit: konservatif ise SL)
    - Her tetiklemede bars_held += 1
    - Timeout/MAX_BARS varsa kapanıştan kapat (close_time = closed_bar.timestamp)
    - PnL / R / fee hesapla
    """
    if trade.get("state") == "CLOSED":
        return trade

    side = trade["side"]
    entry = _safe_float(trade["entry_price"])
    sl    = _safe_float(trade["sl"])
    tp    = _safe_float(trade["tp"])
    bars_held = int(trade.get("bars_held", 0))

    # 1) Yeni bar OPEN → gap kontrolü
    if side == "BUY":
        if new_open >= tp:
            return _close_trade(trade, tp, "OPEN_GAP_TP", fee_roundtrip, exit_time=new_open_time)
        elif new_open <= sl:
            return _close_trade(trade, sl, "OPEN_GAP_SL", fee_roundtrip, exit_time=new_open_time)
    else:  # SELL
        if new_open <= tp:
            return _close_trade(trade, tp, "OPEN_GAP_TP", fee_roundtrip, exit_time=new_open_time)
        elif new_open >= sl:
            return _close_trade(trade, sl, "OPEN_GAP_SL", fee_roundtrip, exit_time=new_open_time)

    # ✅ Backtest uyumu: Entry’den sonraki İLK değerlendirmede bar içi kontrol yapma
    if bars_held == 0:
        trade["bars_held"] = 1
        return trade

    # 2) Kapanmış bar içinde SL/TP (double-hit kuralıyla)
    bar_high = float(closed_bar["high"])
    bar_low  = float(closed_bar["low"])
    bar_time = closed_bar.get("timestamp")
    hit_sl = hit_tp = False

    if side == "BUY":
        hit_sl = (bar_low  <= sl)
        hit_tp = (bar_high >= tp)
    else:
        hit_sl = (bar_high >= sl)
        hit_tp = (bar_low  <= tp)

    if hit_sl and hit_tp:
        exit_price, exit_reason = (sl, "SL_HIT") if conservative_double_hit else (tp, "TP_HIT")
        return _close_trade(trade, exit_price, exit_reason, fee_roundtrip, exit_time=bar_time)
    elif hit_sl:
        return _close_trade(trade, sl, "SL_HIT", fee_roundtrip, exit_time=bar_time)
    elif hit_tp:
        return _close_trade(trade, tp, "TP_HIT", fee_roundtrip, exit_time=bar_time)

    # 3) Timeout / max_future_bars
    bars_held += 1
    trade["bars_held"] = bars_held

    if timeout_close is not None and bars_held >= int(timeout_close):
        exit_price = float(closed_bar["close"])
        return _close_trade(trade, exit_price, "TIMEOUT", fee_roundtrip, exit_time=bar_time)

    if max_future_bars is not None and bars_held >= int(max_future_bars):
        exit_price = float(closed_bar["close"])
        return _close_trade(trade, exit_price, "MAX_BARS", fee_roundtrip, exit_time=bar_time)

    # açık kal
    return trade


def _close_trade(trade: Dict[str, Any], exit_price: float, exit_reason: str,
                 fee_roundtrip: float, exit_time=None) -> Dict[str, Any]:
    side = trade["side"]
    entry= float(trade["entry_price"])
    sl   = float(trade["sl"])

    # side-aware PnL / R
    if side == "BUY":
        pnl_percent = (exit_price - entry) / entry * 100.0
        denom = (entry - sl)
        r_multiple  = (exit_price - entry) / denom if denom != 0 else 0.0
    else:
        pnl_percent = (entry - exit_price) / entry * 100.0
        denom = (sl - entry)
        r_multiple  = (entry - exit_price) / denom if denom != 0 else 0.0

    pnl_percent -= (fee_roundtrip * 100.0)

    trade.update({
        "exit_price": float(exit_price),
        "exit_reason": exit_reason,
        "pnl_percent": float(pnl_percent),
        "r_multiple": float(r_multiple),
        "result": "WIN" if pnl_percent > 0 else ("LOSS" if pnl_percent < 0 else "FLAT"),
        "state": "CLOSED",
        "close_time_utc": trade.get("close_time_utc") or _fmt_ts(exit_time),
    })
    return trade
