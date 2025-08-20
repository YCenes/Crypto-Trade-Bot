from typing import List, Tuple, Dict, Any, Optional
import pandas as pd
import numpy as np
from bisect import bisect_right

# df: timestamp, open, high, low, close (sıralı)
# signals: List[Tuple[timestamp, value, "BUY"/"SELL"]]

def _atr_from_df(df: pd.DataFrame, period: int = 14) -> float:
    """Basit ATR hesaplayıcı (rolling SMA). df: high, low, close"""
    if df is None or len(df) == 0:
        return 0.0
    h = df["high"].astype(float).values
    l = df["low"].astype(float).values
    c = df["close"].astype(float).values
    tr = np.zeros_like(c)
    tr[0] = h[0] - l[0]
    for i in range(1, len(c)):
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i-1]), abs(l[i] - c[i-1]))
    if len(tr) < period:
        return float(np.mean(tr))
    return float(pd.Series(tr).rolling(period).mean().iloc[-1])


def run_backtest(
    signals: List[Tuple[Any, float, str]],
    df: pd.DataFrame,
    swing_highs: List[Tuple[Any, float]],
    swing_lows: List[Tuple[Any, float]],
    rr_ratio: float = 1.5,
    max_future_bars: int = 20,
    # canlı kurallarla hizalı sabitler:
    sl_buffer_pct: float = 0.005,     # sabit buffer (entry * %0.5)
    max_tp_percent: float = 0.05,     # TP tavanı (±%5)
    max_risk_pct: float = 0.02,       # risk % sınırı (örn. %2)
    use_atr_buffer: bool = False,     # ATR destekli buffer
    atr_period: int = 14,
    atr_mult: float = 0.50,           # buffer'a eklenecek ATR çarpanı (örn. 0.5 * ATR)
    max_bars_since_swing: int = 50,   # swing çok eski ise alma
    conservative_double_hit: bool = True,
    timeout_close: Optional[int] = None,
    fee_roundtrip: float = 0.0006,

    # 🔥 HTF (üst zaman dilimi) trend filtresi
    use_htf_filter: bool = False,
    symbol: Optional[str] = None,
    htf_interval: str = "4h",
    htf_lookback: int = 3,
    htf_max_bars_since_swing: int = 300,
) -> List[Dict[str, Any]]:
    """
    Backtest fonksiyonu (canlı kurallarıyla hizalı + opsiyonel HTF filtre):
    - Entry: sinyal mumundan sonraki barın OPEN’ı
    - SL: swing ± (entry*sl_buffer_pct + ATR*atr_mult [opsiyonel])
    - TP: RR ile, sonra max_tp_percent ile sınırla
    - Gap açılışı, double-hit, timeout, max_future_bars
    - (opsiyonel) HTF filtre: 1h BUY ancak 4h HL, 1h SELL ancak 4h LH ise
    - Telemetry: effective_rr, tp_capped
    """
    results: List[Dict[str, Any]] = []

    # yardımcı: timestamp -> index map
    ts_to_idx = {t: i for i, t in enumerate(df["timestamp"].tolist())}

    # sinyallerde aynı timestamp tekrarını filtrele (ilkini al)
    unique_signals = []
    seen_ts = set()
    for t, v, side in signals:
        if t not in seen_ts:
            unique_signals.append((t, v, side))
            seen_ts.add(t)

    # swing listelerini zaman sırasına sok
    swing_highs = sorted(swing_highs, key=lambda x: x[0]) if swing_highs else []
    swing_lows  = sorted(swing_lows,  key=lambda x: x[0]) if swing_lows  else []

    # -------------------------------------------------
    # HTF trend ön-hazırlık (tek sefer)
    # -------------------------------------------------
    htf_times = []
    htf_labels = []
    htf_ts_all = []
    idx_map_htf = {}
    if use_htf_filter:
        if symbol is None:
            raise ValueError("use_htf_filter=True iken run_backtest(symbol=...) belirtmelisin.")
        try:
            from services.binance_service import get_klines
            from analysis.swing_points import detect_swing_points as _detect
            from analysis.trend_structure import classify_trend_structure as _classify
            # yeterli uzunlukta 4h veri çek (LTF penceresini kapsasın)
            htf_df = get_klines(symbol=symbol, interval=htf_interval, limit=1000)
            if htf_df is not None and len(htf_df) >= 20:
                htf_df = htf_df.sort_values("timestamp").drop_duplicates(subset=["timestamp"]).reset_index(drop=True)
                h_swing_highs, h_swing_lows = _detect(htf_df, lookback=htf_lookback)
                h_trend = _classify(sorted(h_swing_highs, key=lambda x: x[0]),
                                    sorted(h_swing_lows,  key=lambda x: x[0]))
                if h_trend:
                    h_trend = sorted(h_trend, key=lambda x: x[0])
                    htf_times  = [t for (t, _v, _lab) in h_trend]
                    htf_labels = [lab for (_t, _v, lab) in h_trend]
                    htf_ts_all = htf_df["timestamp"].tolist()
                    idx_map_htf = {t: i for i, t in enumerate(htf_ts_all)}
        except Exception:
            # HTF verisi alınamazsa filtre devre dışı bırakılır (fail-open)
            use_htf_filter = False

    def _get_htf_bias(cutoff_ts) -> Optional[str]:
        """
        cutoff_ts: Entry'den bir bar önceki LTF kapanış zamanı (1h).
        HTF trend listesinde cutoff_ts'ye en yakın ve ona eşit/önceki trend etiketini döndürür.
        """
        if not (use_htf_filter and htf_times):
            return None
        # htf_times sıralı → bisect ile cutoff'tan küçük/eşit son trend
        pos = bisect_right(htf_times, cutoff_ts) - 1
        if pos < 0:
            return None
        lab = htf_labels[pos]

        # tazelik kontrolü (opsiyonel)
        # cutoff'un HTF index'ini bul (HTF serisinde cutoff'tan küçük/eşit son bar)
        pos_cut = bisect_right(htf_ts_all, cutoff_ts) - 1
        if pos_cut >= 0:
            if (pos_cut - idx_map_htf.get(htf_times[pos], pos)) > htf_max_bars_since_swing:
                return None
        return lab

    # -------------------------------------------------
    # Ana döngü
    # -------------------------------------------------
    for entry_time_raw, _, direction in unique_signals:
        # entry bar: sinyal mumundan bir sonraki bar
        if entry_time_raw not in ts_to_idx:
            continue
        entry_bar_idx = ts_to_idx[entry_time_raw]
        if entry_bar_idx + 1 >= len(df):
            continue

        idx_entry = entry_bar_idx + 1
        entry_row = df.iloc[idx_entry]
        entry_price = float(entry_row["open"])
        entry_time = entry_row["timestamp"]

        # analiz için kapanmış barlar (repaint yok): sinyal mumu dahil, entry mumu hariç
        closed_df = df.iloc[:idx_entry].copy()
        ltf_cutoff = closed_df["timestamp"].iloc[-1]  # HTF filtresi için referans

        # --- HTF filtresi (opsiyonel) ---
        if use_htf_filter:
            htf_bias = _get_htf_bias(ltf_cutoff)
            if htf_bias is None:
                # HTF veri/teyit yok veya çok eski → korumacı: sinyal alma
                continue
            if direction == "BUY" and htf_bias != "HL":
                continue
            if direction == "SELL" and htf_bias != "LH":
                continue

        # ATR hesapla (opsiyonel)
        atr_val = _atr_from_df(closed_df[["high", "low", "close"]], period=atr_period) if use_atr_buffer else 0.0

        # buffer hesaplayıcı
        def buffer_abs() -> float:
            base = entry_price * sl_buffer_pct
            if use_atr_buffer and atr_val > 0:
                return base + atr_mult * atr_val
            return base

        # swing tazeliği için index map
        idx_map_closed = {t: i for i, t in enumerate(closed_df["timestamp"].tolist())}

        # SL & TP kur (aynı canlı mantığı)
        raw_tp = None
        tp_capped = False
        effective_rr = None

        if direction == "BUY":
            # entry_time'a kadar olan son swing-low
            swing, swing_t = None, None
            for t, v in reversed(swing_lows):
                if t <= entry_time:
                    swing, swing_t = float(v), t
                    break
            if swing is None:
                continue

            # swing tazeliği kontrolü
            if (entry_time in idx_map_closed) and (swing_t in idx_map_closed):
                if (idx_map_closed[entry_time] - idx_map_closed[swing_t]) > max_bars_since_swing:
                    continue

            sl = float(swing - buffer_abs())
            risk = entry_price - sl
            if risk <= 0:
                continue
            if (risk / entry_price) > max_risk_pct:
                continue

            raw_tp = entry_price + rr_ratio * risk
            tp_cap = entry_price * (1.0 + max_tp_percent)
            tp = float(min(raw_tp, tp_cap))
            tp_capped = (tp != raw_tp)
            effective_rr = (tp - entry_price) / risk

        else:  # SELL
            # entry_time'a kadar olan son swing-high
            swing, swing_t = None, None
            for t, v in reversed(swing_highs):
                if t <= entry_time:
                    swing, swing_t = float(v), t
                    break
            if swing is None:
                continue

            if (entry_time in idx_map_closed) and (swing_t in idx_map_closed):
                if (idx_map_closed[entry_time] - idx_map_closed[swing_t]) > max_bars_since_swing:
                    continue

            sl = float(swing + buffer_abs())
            risk = sl - entry_price
            if risk <= 0:
                continue
            if (risk / entry_price) > max_risk_pct:
                continue

            raw_tp = entry_price - rr_ratio * risk
            tp_floor = entry_price * (1.0 - max_tp_percent)
            tp = float(max(raw_tp, tp_floor))
            tp_capped = (tp != raw_tp)
            effective_rr = (entry_price - tp) / risk

        # future barlar (NOT: backtest t0 bar içini atlar)
        future_df = df.iloc[idx_entry + 1 : idx_entry + 1 + max_future_bars].copy()
        if future_df.empty:
            continue

        result = "NONE"
        exit_price = None
        exit_reason = ""
        bars_held = 0

        for i, (_, row) in enumerate(future_df.iterrows(), start=1):
            row_open = float(row["open"])
            row_high = float(row["high"])
            row_low  = float(row["low"])
            bars_held = i

            # 1) Açılışta gap kontrolü
            if direction == "BUY":
                if row_open >= tp:
                    result, exit_price, exit_reason = "WIN", tp, "OPEN_GAP_TP"; break
                if row_open <= sl:
                    result, exit_price, exit_reason = "LOSS", sl, "OPEN_GAP_SL"; break
            else:  # SELL
                if row_open <= tp:
                    result, exit_price, exit_reason = "WIN", tp, "OPEN_GAP_TP"; break
                if row_open >= sl:
                    result, exit_price, exit_reason = "LOSS", sl, "OPEN_GAP_SL"; break

            # 2) Bar içinde SL/TP
            if direction == "BUY":
                hit_sl = (row_low <= sl)
                hit_tp = (row_high >= tp)
            else:
                hit_sl = (row_high >= sl)
                hit_tp = (row_low  <= tp)

            if hit_sl and hit_tp:
                if conservative_double_hit:
                    result, exit_price, exit_reason = "LOSS", sl, "SL_HIT"
                else:
                    result, exit_price, exit_reason = "WIN", tp, "TP_HIT"
                break
            elif hit_sl:
                result, exit_price, exit_reason = "LOSS", sl, "SL_HIT"; break
            elif hit_tp:
                result, exit_price, exit_reason = "WIN", tp, "TP_HIT"; break

            # 3) Timeout (opsiyonel)
            if timeout_close is not None and bars_held >= timeout_close:
                exit_price = float(row["close"])
                exit_reason = "TIMEOUT"
                break

        # 4) max_future_bars sınırı: kapanmadıysa bar kapanışından çıkar
        if result == "NONE":
            last_row = future_df.iloc[-1]
            exit_price = float(last_row["close"])
            exit_reason = "MAX_BARS"

        # PnL / R / fee
        if direction == "BUY":
            pnl_percent = (exit_price - entry_price) / entry_price * 100.0
            denom = (entry_price - sl)
            r_multiple  = (exit_price - entry_price) / denom if denom != 0 else 0.0
        else:
            pnl_percent = (entry_price - exit_price) / entry_price * 100.0
            denom = (sl - entry_price)
            r_multiple  = (entry_price - exit_price) / denom if denom != 0 else 0.0

        pnl_percent -= (fee_roundtrip * 100.0)

        if result == "NONE":
            result = "WIN" if pnl_percent > 0 else "LOSS"

        results.append({
            "entry_time": entry_time,
            "direction": direction,
            "entry_price": float(entry_price),
            "sl": float(sl),
            "tp": float(tp),
            "tp_capped": bool(tp_capped),
            "effective_rr": float(effective_rr) if effective_rr is not None else None,
            "exit_price": float(exit_price),
            "exit_reason": exit_reason,
            "bars_held": bars_held,
            "pnl_percent": float(pnl_percent),
            "result": result,
        })

    return results
