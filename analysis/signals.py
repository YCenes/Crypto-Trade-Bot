# ✅ analysis/signals.py
from datetime import timedelta

def generate_signals(trend_points, engulfings):
    signals = []

    for t_time, t_value, label in trend_points:
        for e_time, e_value, e_type in engulfings:
            time_diff = e_time - t_time
            if timedelta(0) <= time_diff <= timedelta(hours=2):
                if label == "HL" and e_type == "bullish":
                    signals.append((e_time, e_value, "BUY"))
                elif label == "LH" and e_type == "bearish":
                    signals.append((e_time, e_value, "SELL"))

    return signals
