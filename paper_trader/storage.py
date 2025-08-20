# paper_trader/storage.py
import os
import pandas as pd
from .config import DATA_DIR, SIGNALS_CSV, TRADES_CSV, EQUITY_CSV

SIGNALS_COLUMNS = [
    "signal_id","timestamp_utc","symbol","interval","side",
    "entry_price","sl","tp","rr_ratio","sl_buffer_pct",
    "status","note"
]
TRADES_COLUMNS = [
    "trade_id","open_time_utc","close_time_utc","symbol","interval","side",
    "entry_price","sl","tp","exit_price","exit_reason","bars_held",
    "fee_roundtrip","risk_abs","r_multiple","pnl_percent","result","state"
]
EQUITY_COLUMNS = [
    "timestamp_utc","equity_index","trades_closed","win_rate","profit_factor","pnl_percent_cum"
]

def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(SIGNALS_CSV):
        pd.DataFrame(columns=SIGNALS_COLUMNS).to_csv(SIGNALS_CSV, index=False)
    if not os.path.exists(TRADES_CSV):
        pd.DataFrame(columns=TRADES_COLUMNS).to_csv(TRADES_CSV, index=False)
    if not os.path.exists(EQUITY_CSV):
        pd.DataFrame(columns=EQUITY_COLUMNS).to_csv(EQUITY_CSV, index=False)

def load_signals() -> pd.DataFrame:
    return pd.read_csv(SIGNALS_CSV) if os.path.exists(SIGNALS_CSV) else pd.DataFrame(columns=SIGNALS_COLUMNS)

def load_trades() -> pd.DataFrame:
    return pd.read_csv(TRADES_CSV) if os.path.exists(TRADES_CSV) else pd.DataFrame(columns=TRADES_COLUMNS)

def save_trades(df: pd.DataFrame) -> None:
    df = df.copy()
    # tip normalize
    for c in ["bars_held"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    df.to_csv(TRADES_CSV, index=False)

def append_signal_row(row: dict) -> None:
    df = load_signals()
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    df.to_csv(SIGNALS_CSV, index=False)

def upsert_trade_row(row: dict) -> None:
    df = load_trades()
    if "trade_id" in df.columns and (df["trade_id"] == row["trade_id"]).any():
        idx = df.index[df["trade_id"] == row["trade_id"]][0]
        for k, v in row.items():
            df.at[idx, k] = v
    else:
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    save_trades(df)

def compute_metrics_from_trades() -> dict:
    df = load_trades()
    ts = pd.Timestamp.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    if df.empty:
        return {
            "timestamp_utc": ts, "equity_index": 100.0,
            "trades_closed": 0, "win_rate": 0.0,
            "profit_factor": 0.0, "pnl_percent_cum": 0.0
        }

    closed = df[df["state"] == "CLOSED"].copy()
    trades_closed = len(closed)
    if trades_closed == 0:
        return {
            "timestamp_utc": ts, "equity_index": 100.0,
            "trades_closed": 0, "win_rate": 0.0,
            "profit_factor": 0.0, "pnl_percent_cum": 0.0
        }

    wins = closed[closed["result"] == "WIN"]
    losses = closed[closed["result"] == "LOSS"]

    win_rate = 100.0 * len(wins) / trades_closed if trades_closed else 0.0
    sum_win_r = wins["r_multiple"].astype(float).sum() if not wins.empty else 0.0
    sum_loss_r = -losses["r_multiple"].astype(float).sum() if not losses.empty else 0.0
    profit_factor = (sum_win_r / sum_loss_r) if sum_loss_r > 0 else float("inf")

    pnl_percent_cum = closed["pnl_percent"].astype(float).sum()
    equity_index = 100.0 + pnl_percent_cum

    return {
        "timestamp_utc": ts,
        "equity_index": float(equity_index),
        "trades_closed": int(trades_closed),
        "win_rate": float(win_rate),
        "profit_factor": float(profit_factor if profit_factor != float("inf") else 9999.0),
        "pnl_percent_cum": float(pnl_percent_cum),
    }

def append_equity_row(metrics: dict) -> None:
    df = pd.read_csv(EQUITY_CSV) if os.path.exists(EQUITY_CSV) else pd.DataFrame(columns=EQUITY_COLUMNS)
    df = pd.concat([df, pd.DataFrame([metrics])], ignore_index=True)
    df.to_csv(EQUITY_CSV, index=False)
