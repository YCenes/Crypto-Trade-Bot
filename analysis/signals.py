from datetime import timedelta

def generate_signals(trend_points, engulfings):
    signals = []

    for i in range(len(trend_points)):
        t_time, t_value, label = trend_points[i]

        for e_time, e_value, e_type in engulfings:
            time_diff = e_time - t_time

            if timedelta(0) <= time_diff <= timedelta(hours=2):
                if label == "HL" and e_type == "bullish":
                    signals.append((e_time, e_value, "BUY"))

                elif label == "LH" and e_type == "bearish":
                    signals.append((e_time, e_value, "SELL"))

    return signals
