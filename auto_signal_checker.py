import time
from datetime import datetime, timedelta
from analysis.live_signal import get_live_signal

def run():
    print("📡 Canlı sinyal kontrol sistemi başlatıldı.")
    
    while True:
        now = datetime.utcnow()
        if now.minute == 0 and now.second < 5:  # Her saat başı
            print("\n🕐 Saat başı kontrol ediliyor...")
            signal = get_live_signal()

            if signal:
                signal_time = datetime.strptime(signal['time'], "%Y-%m-%d %H:%M:%S")
                entry_time = signal_time + timedelta(hours=1)

                print(f"📢 SİNYAL: {signal['signal']} ({signal_time.strftime('%Y-%m-%d %H:%M')} mumu kapanışında tespit edildi)")
                print(f"   ├─ İşlem giriş: {entry_time.strftime('%Y-%m-%d %H:%M')} @ {signal['price']}")
                print(f"   ├─ SL: {signal['sl']}")
                print(f"   └─ TP: {signal['tp']}")
            else:
                print("🔕 Şu anda sinyal yok.")
            
            time.sleep(60)  # Aynı sinyali tekrar yazmamak için

        time.sleep(1)  # CPU'yu yormamak için

if __name__ == "__main__":
    run()
