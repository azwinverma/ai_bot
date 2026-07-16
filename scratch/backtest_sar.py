import os
import pandas as pd
import pandas_ta_classic as ta
from binance.client import Client
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration (matching crypto_tracker.py)
SAR_SYMBOL = "SOLUSDT"
SAR_AF0 = 0.01
SAR_MAX_AF = 0.1

def backtest_sar(interval="1h", days=30):
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_SECRET_KEY")
    client = Client(api_key, api_secret)
    
    print(f"Fetching {days} days of data for {SAR_SYMBOL} at {interval} interval...")
    
    # Fetch historical data
    start_str = f"{days} days ago UTC"
    klines = client.get_historical_klines(SAR_SYMBOL, interval, start_str)
    
    columns = ['ts', 'open', 'high', 'low', 'close', 'vol', 'ct', 'qav', 'tr', 'tbba', 'tbqa', 'ign']
    df = pd.DataFrame(klines, columns=columns)
    
    # Convert types
    for col in ['high', 'low', 'close', 'open']:
        df[col] = df[col].astype(float)
    
    df['timestamp'] = pd.to_datetime(df['ts'], unit='ms')
    
    # Calculate PSAR
    psar = df.ta.psar(af0=SAR_AF0, af=SAR_AF0, max_af=SAR_MAX_AF)
    df = pd.concat([df, psar], axis=1)
    
    l_col = f"PSARl_{SAR_AF0}_{SAR_MAX_AF}"
    s_col = f"PSARs_{SAR_AF0}_{SAR_MAX_AF}"
    
    # Logic from crypto_tracker.py
    df['side'] = df.apply(lambda row: 'buy' if not pd.isna(row[l_col]) else 'sell', axis=1)
    
    # Detect flips
    df['prev_side'] = df['side'].shift(1)
    df['signal'] = df.apply(lambda row: row['side'] if row['side'] != row['prev_side'] and row['prev_side'] is not None else None, axis=1)
    
    signals = df[df['signal'].notna()].copy()
    
    print(f"\n--- Backtest Results for {SAR_SYMBOL} ({interval}) ---")
    print(f"{'Time':<20} | {'Signal':<6} | {'Price':<10} | {'Next Flip Price':<15} | {'Profit %'}")
    print("-" * 75)
    
    total_profit = 0
    trade_count = 0
    
    for i in range(len(signals) - 1):
        curr = signals.iloc[i]
        nxt = signals.iloc[i+1]
        
        profit = 0
        if curr['signal'] == 'buy':
            profit = (nxt['close'] - curr['close']) / curr['close'] * 100
        else:
            profit = (curr['close'] - nxt['close']) / curr['close'] * 100
            
        total_profit += profit
        trade_count += 1
        
        print(f"{str(curr['timestamp']):<20} | {curr['signal'].upper():<6} | {curr['close']:<10.2f} | {nxt['close']:<15.2f} | {profit:>8.2f}%")
        
    if trade_count > 0:
        print("-" * 75)
        print(f"Total Trades: {trade_count}")
        print(f"Total Profit/Loss: {total_profit:.2f}%")
        print(f"Average per trade: {total_profit/trade_count:.2f}%")
    else:
        print("No signals found in this period.")

if __name__ == "__main__":
    # Test on 1h and 4h intervals
    backtest_sar(interval="1h", days=14)
    print("\n" + "="*80 + "\n")
    backtest_sar(interval="4h", days=30)
