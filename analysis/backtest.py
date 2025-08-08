def run_backtest(signals, df, swing_highs, swing_lows, rr_ratio=1.5, max_future_bars=20):
    results = []

    # Tekrarlayan timestamp'lerde sinyal varsa sadece ilkini al
    unique_signals = []
    used_timestamps = set()
    for s in signals:
        if s[0] not in used_timestamps:
            unique_signals.append(s)
            used_timestamps.add(s[0])

    for entry_time, _, direction in unique_signals:
        # Entry index
        entry_index = df.index[df["timestamp"] == entry_time]
        if len(entry_index) == 0 or entry_index[0] + 1 >= len(df):
            continue

        idx = entry_index[0] + 1
        entry_price = df.iloc[idx]["open"]  # ➜ Gerçekçi entry price
        entry_time = df.iloc[idx]["timestamp"]  # ➜ Gerçekçi entry time
        future_df = df.iloc[idx + 1:idx + 1 + max_future_bars]

        # Swing noktası
        swing = None
        if direction == "BUY":
            for t, v in reversed(swing_lows):
                if t < entry_time:
                    swing = v
                    break
        else:  # SELL
            for t, v in reversed(swing_highs):
                if t < entry_time:
                    swing = v
                    break

        if swing is None:
            continue

        # 🔄 Dinamik SL buffer ve TP pip değeri (coin fiyatına göre)
        sl_buffer_pct = 0.005     # %0.5
        tp_fixed_pct = 0.01       # %1
        sl_buffer = entry_price * sl_buffer_pct
        tp_fixed = entry_price * tp_fixed_pct

        # SL belirle
        sl = swing - sl_buffer if direction == "BUY" else swing + sl_buffer

        # TP belirle
        if direction == "BUY":
            risk = entry_price - sl
            if risk <= 0:
                continue
            tp = entry_price + (risk * rr_ratio)
        else:
            risk = sl - entry_price
            if risk <= 0:
                continue
            tp = entry_price - (risk * rr_ratio)

        result = "NONE"
        exit_price = None

        for _, row in future_df.iterrows():
            if direction == "BUY":
                hit_sl = row["low"] <= sl
                hit_tp = row["high"] >= tp

                if hit_sl and hit_tp:
                    result = "LOSS" if abs(sl - row["open"]) < abs(tp - row["open"]) else "WIN"
                    exit_price = sl if result == "LOSS" else tp
                    break
                elif hit_sl:
                    result = "LOSS"
                    exit_price = sl
                    break
                elif hit_tp:
                    result = "WIN"
                    exit_price = tp
                    break

            else:  # SELL
                hit_sl = row["high"] >= sl
                hit_tp = row["low"] <= tp

                if hit_sl and hit_tp:
                    result = "LOSS" if abs(sl - row["open"]) < abs(tp - row["open"]) else "WIN"
                    exit_price = sl if result == "LOSS" else tp
                    break
                elif hit_sl:
                    result = "LOSS"
                    exit_price = sl
                    break
                elif hit_tp:
                    result = "WIN"
                    exit_price = tp
                    break


        if result != "NONE":
            # Yüzdelik PnL hesapla
            if direction == "BUY":
                pnl_percent = (exit_price - entry_price) / entry_price * 100
            else:  # SELL
                pnl_percent = (entry_price - exit_price) / entry_price * 100

            results.append({
                "entry_time": entry_time,
                "direction": direction,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "result": result,
                "sl": sl,
                "tp": tp,
                "pnl_percent": pnl_percent
                
                
            })

    return results
