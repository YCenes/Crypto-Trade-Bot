# Basit engulfing tespiti: gövde bazlı
# Çıktı: [(timestamp, close_price, "bullish"/"bearish"), ...]
def detect_engulfings(df):
    engulfings = []
    for i in range(1, len(df)):
        o1, c1 = df["open"].iloc[i - 1], df["close"].iloc[i - 1]
        o2, c2 = df["open"].iloc[i],     df["close"].iloc[i]
        t2     = df["timestamp"].iloc[i]

        # Bullish: önceki kırmızı (c1<o1), sonraki yeşil (c2>o2) ve
        # ikinci mum gövdesi, ilk gövdeyi tam sarıyor
        if c1 < o1 and c2 > o2 and o2 <= c1 and c2 >= o1:
            engulfings.append((t2, float(c2), "bullish"))

        # Bearish: önceki yeşil (c1>o1), sonraki kırmızı (c2<o2) ve
        # ikinci mum gövdesi, ilk gövdeyi tam sarıyor
        if c1 > o1 and c2 < o2 and o2 >= c1 and c2 <= o1:
            engulfings.append((t2, float(c2), "bearish"))

    return engulfings
