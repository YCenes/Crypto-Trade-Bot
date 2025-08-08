def classify_trend_structure(swing_highs, swing_lows):
    trend_points = []

    # Trend yapısını oluştur (swing high + swing low'ları kronolojik sıraya koy)
    all_points = [(t, v, "high") for t, v in swing_highs] + [(t, v, "low") for t, v in swing_lows]
    all_points.sort(key=lambda x: x[0])  # Tarihe göre sırala

    prev_high = None
    prev_low = None

    for t, v, point_type in all_points:
        if point_type == "high":
            if prev_high is None:
                label = "HH?"
            elif v > prev_high:
                label = "HH"
            else:
                label = "LH"
            prev_high = v

        elif point_type == "low":
            if prev_low is None:
                label = "HL?"
            elif v > prev_low:
                label = "HL"
            else:
                label = "LL"
            prev_low = v

        trend_points.append((t, v, label))

    return trend_points
