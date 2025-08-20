import argparse
import os
import time
from datetime import datetime

import pandas as pd
import matplotlib.pyplot as plt

# CSV konumu
DATA_DIR = os.path.join(os.getcwd(), "data")
EQUITY_CSV = os.path.join(DATA_DIR, "equity_live.csv")

def load_equity_df():
    if not os.path.exists(EQUITY_CSV):
        print(f"Bulunamadı: {EQUITY_CSV}")
        return pd.DataFrame(columns=["timestamp_utc","equity_index","trades_closed","win_rate","profit_factor","pnl_percent_cum"])
    df = pd.read_csv(EQUITY_CSV, parse_dates=["timestamp_utc"])
    df = df.sort_values("timestamp_utc")
    return df

def plot_once(df, title_extra=""):
    plt.figure(figsize=(10, 5))
    if not df.empty:
        plt.plot(df["timestamp_utc"], df["equity_index"])
    plt.title(f"Equity Curve {title_extra}".strip())
    plt.xlabel("Time (UTC)")
    plt.ylabel("Equity Index")
    plt.grid(True)
    plt.tight_layout()
    # tarih etiketleri okunaklı olsun
    plt.gcf().autofmt_xdate()

def run_watch(interval=30, save_png=False):
    print(f"🔁 İzleme modu: her {interval} sn’de bir yenilenecek. Çıkmak için Ctrl+C.")
    plt.ion()  # interactive
    fig = None

    last_mtime = 0
    while True:
        try:
            if os.path.exists(EQUITY_CSV):
                mtime = os.path.getmtime(EQUITY_CSV)
            else:
                mtime = 0

            # dosya değiştiyse veya ilk çalışmada güncelle
            if mtime != last_mtime:
                last_mtime = mtime
                df = load_equity_df()

                plt.clf()
                title_extra = ""
                if not df.empty:
                    wr = df["win_rate"].iloc[-1] if "win_rate" in df.columns else 0.0
                    pf = df["profit_factor"].iloc[-1] if "profit_factor" in df.columns else 0.0
                    title_extra = f"(WR:{wr:.2f}%  PF:{pf:.2f})"
                plot_once(df, title_extra=title_extra)
                plt.pause(0.01)

                if save_png:
                    os.makedirs(DATA_DIR, exist_ok=True)
                    out_path = os.path.join(DATA_DIR, "equity_curve.png")
                    plt.savefig(out_path, dpi=150)
                    print(f"[{datetime.utcnow():%Y-%m-%d %H:%M:%S} UTC] PNG kaydedildi: {out_path}")

            time.sleep(interval)
        except KeyboardInterrupt:
            print("\nİzleme sonlandırıldı.")
            break

def run_once(save_png=False):
    df = load_equity_df()
    title_extra = ""
    if not df.empty:
        wr = df["win_rate"].iloc[-1] if "win_rate" in df.columns else 0.0
        pf = df["profit_factor"].iloc[-1] if "profit_factor" in df.columns else 0.0
        title_extra = f"(WR:{wr:.2f}%  PF:{pf:.2f})"
    plot_once(df, title_extra=title_extra)

    if save_png:
        os.makedirs(DATA_DIR, exist_ok=True)
        out_path = os.path.join(DATA_DIR, "equity_curve.png")
        plt.savefig(out_path, dpi=150)
        print(f"PNG kaydedildi: {out_path}")

    plt.show()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Equity curve plotter")
    parser.add_argument("--watch", action="store_true", help="Grafiği periyodik olarak yenile")
    parser.add_argument("--interval", type=int, default=30, help="Yenileme aralığı (saniye)")
    parser.add_argument("--save-png", action="store_true", help="Grafiği PNG olarak data/equity_curve.png'ye kaydet")
    args = parser.parse_args()

    if args.watch:
        run_watch(interval=args.interval, save_png=args.save_png)
    else:
        run_once(save_png=args.save_png)
