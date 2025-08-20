import time
from datetime import datetime, timezone
from analysis.live_signal import get_live_signal

try:
    import pandas as pd
except Exception:
    pd = None

def to_dt_utc(t):
    """signal['time'] -> timezone-aware UTC datetime"""
    if pd is not None and isinstance(t, pd.Timestamp):
        dt = t.to_pydatetime()
    elif isinstance(t, datetime):
        dt = t
    else:
        # string veya başka bir tip ise
        dt = datetime.strptime(str(t), "%Y-%m-%d %H:%M:%S")
    # tz-aware değilse UTC yap
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt

# Takip edilecek coinler
symbols = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT",
    "XRPUSDT", "AVAXUSDT", "DOGEUSDT", "LINKUSDT", "MATICUSDT"
]

def run():
    print("📡 Çoklu canlı sinyal kontrol sistemi başlatıldı. (1 saatlik / UTC)")

    while True:
        now = datetime.now(timezone.utc)

        # Her saat başı tetikle
        if now.minute == 0 and now.second < 5:
            print(f"\n🕐 1 Saatlik kontrol ({now.strftime('%Y-%m-%d %H:%M')} UTC)")
            for symbol in symbols:
                try:
                    sig = get_live_signal(symbol=symbol, interval="1h")
                    if sig:
                        t_utc = to_dt_utc(sig["time"])
                        print(f"📢 [{symbol}] SİNYAL: {sig['signal']}")
                        print(f"   ├─ İşlem giriş (UTC): {t_utc:%Y-%m-%d %H:%M} @ {sig['price']}")
                        print(f"   ├─ SL: {sig['sl']}")
                        print(f"   └─ TP: {sig['tp']}")
                    else:
                        print(f"🔕 [{symbol}] Şu anda sinyal yok.")
                except Exception as e:
                    print(f"⚠️ [{symbol}] HATA: {e}")

            time.sleep(60)  # aynı sinyali iki kez basmamak için
        time.sleep(1)

if __name__ == "__main__":
    run()
