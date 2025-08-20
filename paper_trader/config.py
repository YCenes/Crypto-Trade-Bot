# paper_trader/config.py

# Hangi sembolleri takip edeceğiz?
SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT",
    "ADAUSDT", "XRPUSDT", "AVAXUSDT", "DOGEUSDT", "LINKUSDT", "DOTUSDT"
]

# Kline aralığı
INTERVAL = "1h"   # "15m" | "1h" | "4h"

# Dosya yolları
DATA_DIR = "paper_trader_data"
SIGNALS_CSV = f"{DATA_DIR}/signals_live.csv"
TRADES_CSV  = f"{DATA_DIR}/trades_live.csv"
EQUITY_CSV  = f"{DATA_DIR}/equity_live.csv"

# Trading parametreleri (backtest ile hizalı)
RR_RATIO = 1.5
SL_BUFFER_PCT = 0.005
MAX_TP_PERCENT = 0.05
MAX_RISK_PCT   = 0.02
MAX_BARS_SINCE_SWING = 50

# Değerlendirme parametreleri (kapatma logic’i)
FEE_ROUNDTRIP = 0.0006
CONSERVATIVE_DOUBLE_HIT = True
TIMEOUT_CLOSE = None          # örn. 10 verirsen 10 bar sonra kapatır
MAX_FUTURE_BARS = 20          # backtest ile aynı ufuk

# Döngü
LOOP_SLEEP_SEC = 5
AFTER_RUN_SLEEP_SEC = 1


# En az risk yüzdesi (entry bazlı). Çok küçük riskli (fee/slippage'a duyarlı) işlemleri elemek için.
MIN_RISK_PCT = 0.001   # %0.10

