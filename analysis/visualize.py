import matplotlib.pyplot as plt

def plot_ohlc(df, title="OHLC", swing_highs=None, swing_lows=None):
    plt.figure(figsize=(12, 5))
    plt.plot(df["timestamp"], df["close"], label="Close Price", color="blue")

    # Swing High'lar
    if swing_highs:
        sh_times, sh_vals = zip(*swing_highs)
        plt.scatter(sh_times, sh_vals, color="red", label="Swing High", marker="^")

    # Swing Low'lar
    if swing_lows:
        sl_times, sl_vals = zip(*swing_lows)
        plt.scatter(sl_times, sl_vals, color="green", label="Swing Low", marker="v")

    plt.title(title)
    plt.xlabel("Zaman")
    plt.ylabel("Fiyat")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()


def plot_trend_structure(df, trend_points, title="Trend Structure"):
    plt.figure(figsize=(12, 5))
    plt.plot(df["timestamp"], df["close"], label="Close Price", color="blue")

    for t, v, label in trend_points:
        color = "green" if "HL" in label or "HH" in label else "red"
        plt.scatter(t, v, color=color, label=label, marker="o")
        plt.text(t, v, label, fontsize=8, ha="center", va="bottom")

    plt.title(title)
    plt.xlabel("Zaman")
    plt.ylabel("Fiyat")
    plt.grid(True)
    plt.tight_layout()
    plt.show()


def plot_engulfing(df, engulfings, title="Engulfing Patterns"):
    plt.figure(figsize=(12, 5))
    plt.plot(df["timestamp"], df["close"], label="Close Price", color="blue")

    for t, v, pattern in engulfings:
        color = "green" if pattern == "bullish" else "red"
        plt.scatter(t, v, color=color, marker="D", label=pattern)

    plt.title(title)
    plt.xlabel("Zaman")
    plt.ylabel("Fiyat")
    plt.grid(True)
    plt.tight_layout()
    plt.show()


def plot_signals(df, signals, title="Al/Sat Sinyalleri"):
    plt.figure(figsize=(12, 5))
    plt.plot(df["timestamp"], df["close"], label="Close Price", color="blue")

    for t, v, s_type in signals:
        color = "green" if s_type == "BUY" else "red"
        marker = "^" if s_type == "BUY" else "v"
        plt.scatter(t, v, color=color, marker=marker, label=s_type)

    plt.title(title)
    plt.xlabel("Zaman")
    plt.ylabel("Fiyat")
    plt.grid(True)
    plt.tight_layout()
    plt.show()

