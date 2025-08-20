import time
from datetime import datetime, timezone

try:
    import pandas as pd
except Exception:
    pd = None

from analysis.live_signal import get_live_signal

def to_dt_utc(t):
    """signal['time'] -> timezone-aware UTC datetime"""
    if pd is not None and isinstance(t, pd.Timestamp):
        dt = t.to_pydatetime()
    elif isinstance(t, datetime):
        dt = t
    else:
        # Örn: "2024-08-01 12:00:00" string gelirse
        dt = datetime.strptime(str(t), "%Y-%m-%d %H:%M:%S")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt

# Takip edilecek coinler
symbols = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT",
    "XRPUSDT", "AVAXUSDT", "DOGEUSDT", "LINKUSDT", "MATICUSDT",
]

def run():
    print("📡 Çoklu canlı sinyal kontrol sistemi başlatıldı. (4 saatlik / UTC)")
    print("   Tetik saatleri: 00, 04, 08, 12, 16, 20 (UTC)\n")

    last_run_key = None  # "YYYY-MM-DD HH" formatında tetik anahtarı

    while True:
        now = datetime.now(timezone.utc)

        # Sadece 4 saatlik barların BAŞINDA tetikle
        # (örn. 12:00:xx UTC) — minute == 0 koşulu yeterli
        if now.hour % 4 == 0 and now.minute == 0:
            key = now.strftime("%Y-%m-%d %H")
            if key != last_run_key:
                last_run_key = key
                print(f"\n🕐 4 Saatlik kontrol ({now.strftime('%Y-%m-%d %H:%M')} UTC)")

                for symbol in symbols:
                    try:
                        # Analiz kapanmış barlarda, entry yeni barın open'ı
                        sig = get_live_signal(symbol=symbol, interval="4h")
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

                    # Çok sembolde rate limit’e girmemek için minik bekleme
                    time.sleep(0.2)

                # Aynı saat içinde tekrar tetiklememek için biraz uyut
                time.sleep(70)

        # CPU yakmamak için küçük bekleme
        time.sleep(0.5)

if __name__ == "__main__":
    run()
