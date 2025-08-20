# paper_trader/paper_trader.py
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import argparse
from datetime import datetime, timezone
import pandas as pd

from analysis.live_signal import get_live_signal
from services.binance_service import get_klines
from .config import (
    SYMBOLS, INTERVAL,
    FEE_ROUNDTRIP, CONSERVATIVE_DOUBLE_HIT, TIMEOUT_CLOSE, MAX_FUTURE_BARS,
    LOOP_SLEEP_SEC, AFTER_RUN_SLEEP_SEC
)
from .storage import (
    ensure_data_dir, load_signals, load_trades, save_trades,
    append_signal_row, upsert_trade_row, compute_metrics_from_trades, append_equity_row
)

try:
    from .storage import TRADES_CSV, SIGNALS_CSV, EQUITY_CSV
except Exception:
    TRADES_CSV = "paper_trader_data/trades_live.csv"
    SIGNALS_CSV = "paper_trader_data/signals_live.csv"
    EQUITY_CSV = "paper_trader_data/equity_live.csv"

from .evaluator import evaluate_open_trade


def to_iso_utc(ts):
    if isinstance(ts, pd.Timestamp):
        ts = ts.tz_localize(None) if ts.tzinfo else ts
        return ts.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(ts, str):
        return ts
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def make_trade_id(symbol, entry_time_iso):
    return f"{symbol}-{entry_time_iso}"


def trade_exists(trades_df, trade_id):
    if trades_df.empty:
        return False
    return (trades_df["trade_id"] == trade_id).any()


def signal_already_logged(symbol, entry_time_iso):
    sigs = load_signals()
    if sigs.empty:
        return False
    mask = (sigs["symbol"] == symbol) & (sigs["timestamp_utc"] == entry_time_iso)
    return mask.any()


def has_open_trade_same_direction(trades_df, symbol, side):
    if trades_df.empty:
        return False
    mask = (
        (trades_df["symbol"] == symbol) &
        (trades_df["state"] == "OPEN") &
        (trades_df["side"] == side)
    )
    return mask.any()


def on_bar_open():
    trades_df = load_trades()
    print(f"[DEBUG] load_trades(): {len(trades_df)} satır (kaynak: {TRADES_CSV})")

    for symbol in SYMBOLS:
        df = get_klines(symbol=symbol, interval=INTERVAL, limit=50)
        if df is None or len(df) < 2:
            print(f"[DEBUG] {symbol}: kline eksik (len<2), atlandı")
            continue

        closed_bar = df.iloc[-2]      # bir önceki kapanmış bar
        live_bar   = df.iloc[-1]      # yeni bar
        new_open   = float(live_bar["open"])
        new_open_time = live_bar["timestamp"]

        # --- Açık işlemleri değerlendir ---
        open_mask = (trades_df["symbol"] == symbol) & (trades_df["state"] == "OPEN")
        open_idx_list = trades_df[open_mask].index.tolist()

        if open_idx_list:
            print(f"[DEBUG] {symbol}: {len(open_idx_list)} OPEN trade değerlendiriliyor")

        for idx in open_idx_list:
            trade  = trades_df.loc[idx].to_dict()
            before = trade.get("state", "UNKNOWN")
            updated = evaluate_open_trade(
                trade=trade,
                closed_bar=closed_bar,
                new_open=new_open,
                fee_roundtrip=FEE_ROUNDTRIP,
                conservative_double_hit=CONSERVATIVE_DOUBLE_HIT,
                timeout_close=TIMEOUT_CLOSE,
                max_future_bars=MAX_FUTURE_BARS,
                new_open_time=new_open_time,   # gap çıkışlarının zamanı için
            )

            trades_df.loc[idx] = pd.Series(updated)
            upsert_trade_row(updated)

            after = updated.get("state", "UNKNOWN")
            if before != after or updated.get("exit_reason"):
                print(f"[DEBUG] {symbol}: {trade.get('trade_id')} {before}→{after} "
                      f"reason={updated.get('exit_reason')} exit={updated.get('exit_price')}")

        if open_idx_list:
            trades_df = load_trades()
            print(f"[DEBUG] {symbol}: evaluate sonrası reload → {len(trades_df)} satır")

        # --- Yeni sinyal var mı? (BACKTEST PARAMLARIYLA) ---
        sig = get_live_signal(
    symbol=symbol,
    interval=INTERVAL,
    rr_ratio=1.5,
    sl_buffer_pct=0.005,
    max_tp_percent=0.05,
    max_risk_pct=0.02,
    max_bars_since_swing=50,
    min_tp_percent=0.0,        # hâlâ kapalı (istersen açarız)
    min_risk_pct=0.0,          # hâlâ kapalı
    use_tick_quantize=False,   # backtest uyumu için kapalı
    use_htf_filter=True,       # ✅ 4h trend filtresi aktif
    htf_interval="4h",
    htf_lookback=3,
    htf_max_bars_since_swing=300,
    )
        
        if not sig:
            print(f"[DEBUG] {symbol}: sinyal yok")
            continue

        if has_open_trade_same_direction(trades_df, symbol, sig["signal"]):
            print(f"[DEBUG] {symbol}: aynı yönde OPEN mevcut, sinyal atlandı")
            continue

        entry_time_iso = to_iso_utc(sig["time"])
        trade_id = make_trade_id(symbol, entry_time_iso)

        # Sinyali kaydet
        if not signal_already_logged(symbol, entry_time_iso):
            append_signal_row({
                "signal_id": trade_id,
                "timestamp_utc": entry_time_iso,
                "symbol": symbol,
                "interval": INTERVAL,
                "side": sig["signal"],
                "entry_price": float(sig["price"]),
                "sl": float(sig["sl"]),
                "tp": float(sig["tp"]),
                "rr_ratio": float(sig.get("rr_ratio", 1.5)),
                "sl_buffer_pct": float(sig.get("sl_buffer_pct", 0.005)),
                "status": "opened",
                "note": ""
            })
            print(f"[DEBUG] {symbol}: signals_live.csv → {trade_id} yazıldı ({SIGNALS_CSV})")
        else:
            print(f"[DEBUG] {symbol}: sinyal zaten kayıtlı ({trade_id})")

        # Aynı trade daha önce hiç yoksa ekle
        if trade_exists(trades_df, trade_id):
            print(f"[DEBUG] {symbol}: trade_exists=True ({trade_id}) → upsert yapılmadı")
        else:
            entry = float(sig["price"])
            sl    = float(sig["sl"])
            side  = sig["signal"]
            # risk_abs: rapor/metrik için faydalı (backtest mantığını bozmaz)
            risk_abs = max(entry - sl, 0.0) if side == "BUY" else max(sl - entry, 0.0)

            new_row = {
                "trade_id": trade_id,
                "open_time_utc": entry_time_iso,
                "close_time_utc": "",
                "symbol": symbol,
                "interval": INTERVAL,
                "side": side,
                "entry_price": entry,
                "sl": sl,
                "tp": float(sig["tp"]),
                "exit_price": "",
                "exit_reason": "",
                "bars_held": 0,
                "fee_roundtrip": FEE_ROUNDTRIP,
                "risk_abs": risk_abs,
                "r_multiple": "",
                "pnl_percent": "",
                "result": "",
                "state": "OPEN"
            }
            upsert_trade_row(new_row)
            trades_df = load_trades()
            print(f"[DEBUG] {symbol}: trades_live.csv → {trade_id} eklendi → {TRADES_CSV}")

    trades_df = load_trades()
    save_trades(trades_df)

    metrics = compute_metrics_from_trades()
    append_equity_row(metrics)

    print(f"[{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC] "
          f"EquityIndex:{metrics['equity_index']:.2f}  "
          f"Closed:{metrics['trades_closed']}  WinRate:{metrics['win_rate']:.2f}%  "
          f"PF:{metrics['profit_factor']:.2f}  PnLcum:{metrics['pnl_percent_cum']:.2f}%  "
          f"(files: trades={TRADES_CSV}, signals={SIGNALS_CSV}, equity={EQUITY_CSV})")


def loop_forever():
    print(f"📡 Paper trader başladı. ({INTERVAL} / UTC; bar başında tek tetik)")
    if INTERVAL == "4h":
        print("   Saatler: 00, 04, 08, 12, 16, 20 (UTC)")
    elif INTERVAL == "1h":
        print("   Saatler: Her saatin başında (UTC)")
    elif INTERVAL == "15m":
        print("   Saatler: Her 15 dakikanın başında (UTC)")

    ensure_data_dir()
    last_run_key = None

    while True:
        now = datetime.now(timezone.utc)
        run_this_bar = False

        if INTERVAL == "4h":
            if now.hour % 4 == 0 and now.minute == 0:
                run_this_bar = True
                key = now.strftime("%Y-%m-%d %H")
        elif INTERVAL == "1h":
            if now.minute == 0:
                run_this_bar = True
                key = now.strftime("%Y-%m-%d %H")
        elif INTERVAL == "15m":
            if now.minute % 15 == 0:
                run_this_bar = True
                key = now.strftime("%Y-%m-%d %H:%M")

        if run_this_bar and key != last_run_key:
            last_run_key = key
            on_bar_open()
            time.sleep(AFTER_RUN_SLEEP_SEC)

        time.sleep(LOOP_SLEEP_SEC)


def run_once():
    print("▶️ Tek seferlik tetik (laboratuvar testi).")
    ensure_data_dir()
    on_bar_open()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Tek sefer çalıştır ve çık")
    args = parser.parse_args()

    if args.once:
        run_once()
    else:
        loop_forever()
