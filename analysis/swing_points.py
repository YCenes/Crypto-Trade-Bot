def detect_swing_points(df, lookback=2):
    swing_highs = []
    swing_lows = []

    for i in range(lookback, len(df) - lookback):
        is_swing_high = all(df["high"].iloc[i] > df["high"].iloc[i - j] and df["high"].iloc[i] > df["high"].iloc[i + j] for j in range(1, lookback + 1))
        is_swing_low = all(df["low"].iloc[i] < df["low"].iloc[i - j] and df["low"].iloc[i] < df["low"].iloc[i + j] for j in range(1, lookback + 1))

        if is_swing_high:
            swing_highs.append((df["timestamp"].iloc[i], df["high"].iloc[i]))

        if is_swing_low:
            swing_lows.append((df["timestamp"].iloc[i], df["low"].iloc[i]))

    return swing_highs, swing_lows
