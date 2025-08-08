def detect_engulfing(df):
    engulfings = []

    for i in range(1, len(df)):
        prev = df.iloc[i - 1]
        curr = df.iloc[i]

        # Bullish Engulfing: önce düşüş, sonra yükseliş + gövdesini yutmuş
        if prev["close"] < prev["open"] and curr["close"] > curr["open"]:
            if curr["close"] > prev["open"] and curr["open"] < prev["close"]:
                engulfings.append((curr["timestamp"], curr["close"], "bullish"))

        # Bearish Engulfing: önce yükseliş, sonra düşüş + gövdesini yutmuş
        elif prev["close"] > prev["open"] and curr["close"] < curr["open"]:
            if curr["open"] > prev["close"] and curr["close"] < prev["open"]:
                engulfings.append((curr["timestamp"], curr["close"], "bearish"))

    return engulfings
