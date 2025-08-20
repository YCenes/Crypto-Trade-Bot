# ✅ main.py (GÜNCEL – gerçekçi backtest + repaint'siz live signal)

from services.binance_service import get_klines
from analysis.swing_points import detect_swing_points
from analysis.trend_structure import classify_trend_structure
from analysis.backtest import run_backtest
from analysis.visualize import plot_signals
from analysis.live_signal import get_live_signal

def compute_r_multiple(row):
    """
    Sonuç satırında r_multiple yoksa dinamik hesaplar.
    BUY:  (exit - entry) / (entry - SL)
    SELL: (entry - exit) / (SL - entry)
    """
    try:
        direction = row["direction"]
        entry = float(row["entry_price"])
        sl    = float(row["sl"])
        exitp = float(row["exit_price"])
        denom = (entry - sl) if direction == "BUY" else (sl - entry)
        if denom == 0:
            return 0.0
        return ((exitp - entry) / denom) if direction == "BUY" else ((entry - exitp) / denom)
    except Exception:
        return 0.0

# -------------------------------------------------
# 1) Veri al
# -------------------------------------------------
symbol = "ETHUSDT"
interval = "1h"
limit = 500

print(f"Veri alınıyor: {symbol} - {interval} - {limit} mum")
df = get_klines(symbol=symbol, interval=interval, limit=limit)

# -------------------------------------------------
# 2) Swing noktaları
# -------------------------------------------------
swing_highs, swing_lows = detect_swing_points(df, lookback=3)

# -------------------------------------------------
# 3) Trend yapısı (HH/HL/LH/LL)
# -------------------------------------------------
trend_points = classify_trend_structure(swing_highs, swing_lows)

# -------------------------------------------------
# 4) Sinyal üret (HL → BUY, LH → SELL)
#    Not: t = HL/LH teyit barının zamanı. Backtest girişini bir sonraki barın OPEN’ından alır.
# -------------------------------------------------
signals = []
for t, v, label in trend_points:
    if label == "HL":
        signals.append((t, v, "BUY"))
    elif label == "LH":
        signals.append((t, v, "SELL"))

print(f"Toplam sinyal: {len(signals)}")

# -------------------------------------------------
# 5) Backtest (canlı kurallarla hizalı)
#    - Double-hit: önce SL (konservatif)
#    - Gap/slippage: bar OPEN SL/TP’yi aştıysa OPEN’dan fill
#    - Komisyon: round-trip %0.06
#    - Timeout: istersen int ver (örn. 10); None ise kullanılmaz
#    - TP tavanı ve risk yüzdesi sınırı eklendi
# -------------------------------------------------
results = run_backtest(
    signals=signals,
    df=df,
    swing_highs=swing_highs,
    swing_lows=swing_lows,
    rr_ratio=2.0,
    max_future_bars=20,
    sl_buffer_pct=0.005,
    max_tp_percent=0.05,
    max_risk_pct=0.02,
    use_atr_buffer=False,
    atr_period=14,
    atr_mult=0.50,
    max_bars_since_swing=50,
    conservative_double_hit=True,
    timeout_close=None,
    fee_roundtrip=0.0006,

    # ✅ HTF filtresi
    use_htf_filter=True,
    symbol=symbol,          # önemli!
    htf_interval="4h",
    htf_lookback=3,
    htf_max_bars_since_swing=300,
)

# -------------------------------------------------
# 6) Sonuçları yazdır (zengin metrikler)
# -------------------------------------------------
total_trades = len(results)
wins     = sum(1 for r in results if r["result"] == "WIN")
losses   = sum(1 for r in results if r["result"] == "LOSS")
timeouts = sum(1 for r in results if r.get("exit_reason") == "TIMEOUT")
win_rate = (wins / total_trades * 100.0) if total_trades else 0.0

# R metrikleri (r_multiple yoksa dinamik hesapla)
r_list = []
for r in results:
    r_mult = r.get("r_multiple")
    if r_mult is None:
        r_mult = compute_r_multiple(r)
        r["r_multiple"] = r_mult
    r_list.append(r_mult)

sum_win_r  = sum(r["r_multiple"] for r in results if r["result"] == "WIN")
sum_loss_r = -sum(r["r_multiple"] for r in results if r["result"] == "LOSS")  # pozitifle
profit_factor = (sum_win_r / sum_loss_r) if sum_loss_r > 0 else float("inf")
avg_r = (sum(r_list) / total_trades) if total_trades else 0.0

total_pnl_percent = sum(r["pnl_percent"] for r in results)

print(f"Toplam İşlem: {total_trades}")
print(f"Kazanılan: {wins}, Kaybedilen: {losses}, Timeout: {timeouts}")
print(f"Win Rate: {win_rate:.2f}% | Profit Factor: {profit_factor:.2f} | Avg R: {avg_r:.2f}R")
print(f"Toplam Yüzdelik Kar/Zarar (PnL%): {total_pnl_percent:.2f}%")

for r in results:
    # telemetry (opsiyonel göstergeler)
    tp_cap_flag = f" | TPcapped:{r['tp'] != r.get('tp', r['tp'])}" if "tp_capped" not in r else f" | TPcapped:{r['tp_capped']}"
    eff_rr_flag = f" | effRR:{r.get('effective_rr'):.2f}" if r.get("effective_rr") is not None else ""
    print(
        f"[{r['direction']}] Entry:{r['entry_price']:.4f} @ {r['entry_time']} "
        f"| SL:{r['sl']:.4f} | TP:{r['tp']:.4f} "
        f"| Exit:{r['exit_price']:.4f} ({r['exit_reason']}) "
        f"| R:{r['r_multiple']:.2f} | PnL:{r['pnl_percent']:.2f}% → {r['result']}"
        f"{eff_rr_flag}{tp_cap_flag}"
    )

# -------------------------------------------------
# 7) 📡 Canlı Sinyal (repaint’siz; backtest ile aynı interval)
# -------------------------------------------------
live = get_live_signal(symbol=symbol, interval=interval)
if live:
    extras = []
    if "effective_rr" in live: extras.append(f"effRR:{live['effective_rr']:.2f}")
    if "tp_capped" in live:    extras.append(f"TPcapped:{live['tp_capped']}")
    extra_str = (" | " + " ".join(extras)) if extras else ""
    print(f"📢 CANLI SİNYAL: {live['signal']} @ {live['price']:.4f} ({live['time']}) | SL:{live['sl']:.4f} | TP:{live['tp']:.4f}{extra_str}")
else:
    print("Şu anda canlı sinyal yok.")

# -------------------------------------------------
# 8) Grafik (sinyalleri göster)
# -------------------------------------------------
plot_signals(df, signals, title=f"{symbol} {interval} – Backtest Sinyalleri")
