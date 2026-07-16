import os
import pandas as pd
import pandas_ta as ta
from binance.client import Client
from dotenv import load_dotenv

load_dotenv()

def check_current_sar():
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_SECRET_KEY")
    client = Client(api_key, api_secret)
    
    symbol = "SOLUSDT"
    print(f"Checking SAR status for {symbol} (1h interval)...")
    
    klines = client.get_historical_klines(symbol, Client.KLINE_INTERVAL_1HOUR, "2 days ago UTC")
    columns = ['ts', 'open', 'high', 'low', 'close', 'vol', 'ct', 'qav', 'tr', 'tbba', 'tbqa', 'ign']
    df = pd.DataFrame(klines, columns=columns)
    for col in ['high', 'low', 'close']:
        df[col] = df[col].astype(float)
        
    psar = df.ta.psar(af0=0.01, af=0.01, max_af=0.1)
    df = pd.concat([df, psar], axis=1)
    
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    l_col = "PSARl_0.01_0.1"
    s_col = "PSARs_0.01_0.1"
    
    current_side = 'LONG (BUY)' if not pd.isna(latest[l_col]) else 'SHORT (SELL)'
    prev_side = 'LONG (BUY)' if not pd.isna(prev[l_col]) else 'SHORT (SELL)'
    
    print(f"Current SAR Side: {current_side}")
    print(f"Previous SAR Side: {prev_side}")
    
    if current_side == prev_side:
        print("Status: No Flip detected. The trend is continuing.")
    else:
        print("Status: FLIP DETECTED! A signal should have triggered.")

if __name__ == "__main__":
    check_current_sar()
