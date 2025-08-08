# ✅ main.py (GÜNCELLENMİŞ)

from services.binance_service import get_klines
from analysis.swing_points import detect_swing_points
from analysis.trend_structure import classify_trend_structure
from analysis.signals import generate_signals
from analysis.backtest import run_backtest
from analysis.visualize import plot_signals

# 1. Veri al
symbol = "BTCUSDT"
interval = "4h"
limit = 500

print(f"Veri alınıyor: {symbol} - {interval} - {limit} mum")
df = get_klines(symbol=symbol, interval=interval, limit=limit)

# 2. Swing noktaları
swing_highs, swing_lows = detect_swing_points(df, lookback=3)

# 3. Trend yapısı (HH/HL/LH/LL)
trend_points = classify_trend_structure(swing_highs, swing_lows)

# 4. Sinyal üret (HL için BUY, LH için SELL - ENGULFING YOK)
signals = []
for t, v, label in trend_points:
    if label == "HL":
        signals.append((t, v, "BUY"))
    elif label == "LH":
        signals.append((t, v, "SELL"))

print(f"Toplam sinyal: {len(signals)}")

# 5. Backtest
results = run_backtest(
    signals,
    df,
    swing_highs,
    swing_lows,
    rr_ratio=1.7,      # RR oranı
    max_future_bars=20
)

# 6. Sonuçları yazdır
print(f"Toplam İşlem: {len(results)}")
wins = sum(1 for r in results if r["result"] == "WIN")
losses = len(results) - wins
win_rate = (wins / len(results)) * 100 if results else 0


print(f"Kazanılan: {wins}, Kaybedilen: {losses}")
print(f"Win Rate: {win_rate:.2f}%")
total_percent = sum(r["pnl_percent"] for r in results)
print(f"Toplam Yüzdelik Kar/Zarar (PnL%): {total_percent:.2f}%")

for r in results:
    print(f"[{r['direction']}] Entry: {r['entry_price']} @ {r['entry_time']} | SL: {r['sl']} | TP: {r['tp']} | Exit: {r['exit_price']} | PNL: ({r['pnl_percent']:.2f}%) → {r['result']}")

# 7. Grafik çiz (sinyalleri göster)
plot_signals(df, signals, title="Backtest Sinyalleri")
