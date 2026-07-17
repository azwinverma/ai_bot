import os
import time
import argparse
import requests
import pandas as pd
import pandas_ta_classic as ta
try:
    import ollama
except ImportError:
    ollama = None
import anthropic
import firebase_admin
from firebase_admin import credentials, firestore
from binance.client import Client
from datetime import datetime
from dotenv import load_dotenv
import json
import re

STATE_FILE = "crypto_state.json"

# Load environment variables from .env file
load_dotenv()

# --- FIREBASE INITIALIZATION ---
db = None
try:
    if not firebase_admin._apps:
        # Load credentials from the service_account.json file
        cred = credentials.Certificate('service_account.json')
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase (Firestore) initialized with service account key.")
except Exception as e:
    print(f"Firebase initialization failed (Local mode likely): {e}")

# --- CONFIGURATION ---
DEFAULT_COINS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
SAR_SYMBOL = "SOLUSDT" # Focus for SAR signals
SAR_AF0 = 0.01
SAR_MAX_AF = 0.1

# --- RSI CONFIGURATION ---
RSI_PERIOD = int(os.getenv("RSI_PERIOD", "14"))
RSI_BUY_THRESHOLD = float(os.getenv("RSI_BUY_THRESHOLD", "55"))  # Relaxed default (was 35)
RSI_SELL_THRESHOLD = float(os.getenv("RSI_SELL_THRESHOLD", "45")) # Relaxed default (was 65)

# --- TREND & STRENGTH CONFIGURATION ---
EMA_PERIOD = int(os.getenv("EMA_PERIOD", "200"))        # Long-term trend filter
ADX_PERIOD = int(os.getenv("ADX_PERIOD", "14"))         # Trend strength period
ADX_THRESHOLD = float(os.getenv("ADX_THRESHOLD", "20"))      # Minimum strength to trade (20-25 is standard)
VOLUME_PERIOD = 20      # Period for volume moving average

# --- FILTER TOGGLES ---
USE_EMA_FILTER = os.getenv("USE_EMA_FILTER", "true").lower() == "true"
USE_ADX_FILTER = os.getenv("USE_ADX_FILTER", "true").lower() == "true"
USE_RSI_FILTER = os.getenv("USE_RSI_FILTER", "true").lower() == "true"

# --- HOURLY STATUS MESSAGE ---
# When true, EVERY run sends a Telegram status message (price table + SOL
# indicator readout). A SAR flip alert is appended to that same message.
# Set SEND_STATUS_UPDATE=false to go back to flip-only alerts.
SEND_STATUS_UPDATE = os.getenv("SEND_STATUS_UPDATE", "true").lower() == "true"

# --- INTERVAL MAPS (shared by single-shot and continuous modes) ---
INTERVAL_SECONDS = {
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
    "test": 10,
}

BINANCE_INTERVALS = {
    "15m": Client.KLINE_INTERVAL_15MINUTE,
    "1h": Client.KLINE_INTERVAL_1HOUR,
    "4h": Client.KLINE_INTERVAL_4HOUR,
    "1d": Client.KLINE_INTERVAL_1DAY,
    "test": Client.KLINE_INTERVAL_1MINUTE,
}

# Tags we intentionally use in our messages; everything else is escaped so the
# comparison operators in the filter text (e.g. "30.9 > 20.0", "Vol <= Avg")
# can't be mistaken for HTML tags and break Telegram parsing.
_KEEP_TAGS = ("<pre>", "</pre>", "<b>", "</b>")

def _escape_html_keep_tags(text):
    """HTML-escape the message but preserve our intentional <pre>/<b> tags."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    for tag in _KEEP_TAGS:
        escaped = tag.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = text.replace(escaped, tag)
    return text

def send_telegram_message(text):
    """
    Send a notification to Telegram. Tries HTML (with our tags preserved);
    if Telegram still rejects the entities, falls back to plain text so the
    message is always delivered.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[WARNING] Telegram credentials not found in .env")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    plain = re.sub(r"</?(?:pre|b)>", "", text)  # strip our tags for the fallback
    attempts = [
        {"chat_id": chat_id, "text": _escape_html_keep_tags(text), "parse_mode": "HTML"},
        {"chat_id": chat_id, "text": plain},
    ]
    for payload in attempts:
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                return True
            print(f"Telegram send failed ({response.status_code}): {response.text[:200]}")
        except Exception as e:
            print(f"Error sending Telegram message: {e}")
    return False

def get_ai_analysis(symbol, price, side, data=None):
    """
    Get AI-driven market analysis using Claude (Anthropic) or local Ollama (fallback).
    """
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen3:8b")
    
    prompt = f"You are a professional Crypto Trading Analyst. Analyze this signal for {symbol}:\n"
    prompt += f"- Current Price: {price}\n"
    prompt += f"- Signal: SAR indicator flipped to {side.upper()}\n"
    if data and 'rsi' in data:
        prompt += f"- RSI (14): {data['rsi']:.2f} ({'Oversold' if data['rsi'] < 30 else 'Overbought' if data['rsi'] > 70 else 'Neutral'})\n"
    
    if data:
        prompt += f"- 24h Change: {data.get('priceChangePercent')}%\n"
        prompt += f"- 24h Volume: {data.get('volume')}\n"
    
    prompt += "\nProvide a very concise (max 3 sentences) analysis and a recommendation (BUY, SELL, or WAIT)."
    
    # 1. Try Claude first if API Key is available
    if anthropic_key:
        try:
            print(f"Asking Claude ({anthropic_model}) for analysis...")
            # Detect if we should use a local base URL for a proxy (as seen in user's previous setup)
            base_url = os.getenv("ANTHROPIC_BASE_URL")
            if base_url:
                client = anthropic.Anthropic(api_key=anthropic_key, base_url=base_url)
            else:
                client = anthropic.Anthropic(api_key=anthropic_key)

            response = client.messages.create(
                model=anthropic_model,
                max_tokens=300,
                system="You are a technical crypto trading assistant.",
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            print(f"Claude Error: {e}. Falling back to Ollama...")

    # 2. Fallback to Local Ollama
    try:
        print(f"Asking local AI ({ollama_model})...")
        response = ollama.chat(model=ollama_model, messages=[
            {'role': 'system', 'content': 'You are a helpful crypto trading assistant.'},
            {'role': 'user', 'content': prompt},
        ])
        return response['message']['content']
    except Exception as e:
        print(f"Local AI Error: {e}")
        return "AI analysis unavailable at this time."

def get_last_signal_local():
    """Retrieve the last seen SAR side from local JSON file."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
                return data.get(SAR_SYMBOL, {}).get("last_side")
        except Exception as e:
            print(f"Error loading state from local file: {e}")
    return None

def save_signal_local(side):
    """Save the current SAR side to local JSON file."""
    try:
        data = {}
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                try:
                    data = json.load(f)
                except Exception:
                    pass
        
        data[SAR_SYMBOL] = {
            "last_side": side,
            "timestamp": datetime.now().isoformat()
        }
        with open(STATE_FILE, "w") as f:
            json.dump(data, f, indent=4)
        print(f"State saved locally to {STATE_FILE}.")
    except Exception as e:
        print(f"Error saving state to local file: {e}")

def get_last_signal_from_db():
    """Retrieve the last seen SAR side from Firestore with local fallback."""
    if db:
        try:
            doc = db.collection("bot_state").document(SAR_SYMBOL).get()
            if doc.exists:
                return doc.to_dict().get("last_side")
        except Exception as e:
            print(f"Error loading state from Firestore, falling back to local file: {e}")
    else:
        print("Firestore not initialized, loading state from local file.")
    return get_last_signal_local()

def save_signal_to_db(side):
    """Save the current SAR side to Firestore and local fallback."""
    # Always save locally as a backup
    save_signal_local(side)
    
    if db:
        try:
            db.collection("bot_state").document(SAR_SYMBOL).set({
                "last_side": side,
                "timestamp": firestore.SERVER_TIMESTAMP
            })
            print("State saved to Firestore.")
        except Exception as e:
            print(f"Error saving state to Firestore: {e}")

def get_indicator_data(client, symbol, interval):
    """Fetch historical klines and calculate indicators (SAR, RSI, EMA, ADX)."""
    try:
        # Fetch 1000 candles (enough for EMA 200 to stabilize)
        klines = client.get_historical_klines(symbol, interval, limit=1000)
        columns = ['ts', 'open', 'high', 'low', 'close', 'vol', 'ct', 'qav', 'tr', 'tbba', 'tbqa', 'ign']
        df = pd.DataFrame(klines, columns=columns)
        
        # Convert to float
        for col in ['high', 'low', 'close', 'vol']:
            df[col] = df[col].astype(float)
            
        # 1. Calculate PSAR
        psar = df.ta.psar(af0=SAR_AF0, af=SAR_AF0, max_af=SAR_MAX_AF)
        
        # 2. Calculate RSI
        rsi = df.ta.rsi(length=RSI_PERIOD)
        
        # 3. Calculate EMA (Trend Filter)
        ema = df.ta.ema(length=EMA_PERIOD)
        
        # 4. Calculate ADX (Strength Filter)
        adx = df.ta.adx(length=ADX_PERIOD)
        
        # 5. Calculate Volume SMA
        vol_sma = df['vol'].rolling(window=VOLUME_PERIOD).mean()
        vol_sma.name = f"VOL_SMA_{VOLUME_PERIOD}"
        
        # Merge back
        df = pd.concat([df, psar, rsi, ema, adx, vol_sma], axis=1)
        return df
    except Exception as e:
        print(f"Error calculating indicators for {symbol}: {e}")
        return None

def check_signals(df, last_side):
    """
    Detect SAR flip and evaluate Trend (EMA), Strength (ADX), and Volume filters.
    Always returns: (new_side, signal_text) on a flip, including filter results in the signal_text.
    """
    if df is None or len(df) < 3:
        return last_side, None

    # Evaluate the last *closed* candle (iloc[-2]), not the still-forming one
    # (iloc[-1]). SAR/RSI on an unclosed candle can flicker and flip back before
    # the candle closes, producing premature/false signals.
    latest = df.iloc[-2]
    
    # Column names
    l_col = f"PSARl_{SAR_AF0}_{SAR_MAX_AF}"
    rsi_col = f"RSI_{RSI_PERIOD}"
    ema_col = f"EMA_{EMA_PERIOD}"
    adx_col = f"ADX_{ADX_PERIOD}"
    vol_sma_col = f"VOL_SMA_{VOLUME_PERIOD}"
    
    current_side = 'buy' if not pd.isna(latest[l_col]) else 'sell'
    current_rsi = latest[rsi_col]
    current_ema = latest[ema_col]
    current_adx = latest[adx_col]
    current_price = latest['close']
    current_vol = latest['vol']
    avg_vol = latest[vol_sma_col]
    
    if last_side and current_side != last_side:
        time_str = datetime.now().strftime("%H:%M:%S")
        
        # 1. Trend Filter: Trade with the major trend
        is_bullish = current_price > current_ema
        
        # 2. Strength Filter: Avoid choppy/sideways markets
        is_trending = current_adx > ADX_THRESHOLD
        
        # 3. Volume Filter: Reversal should have momentum
        is_vol_spike = current_vol > (avg_vol * 1.1) # 10% above average
        
        if current_side == 'buy':
            # Evaluate EMA
            ema_passed = is_bullish
            ema_detail = f"Above EMA {EMA_PERIOD} (Bullish)" if is_bullish else f"Below EMA {EMA_PERIOD} (Bearish)"
            
            # Evaluate ADX
            adx_passed = is_trending
            adx_detail = f"{current_adx:.1f} > {ADX_THRESHOLD} (Strong Trend)" if is_trending else f"{current_adx:.1f} <= {ADX_THRESHOLD} (Weak/Sideways)"
            
            # Evaluate RSI
            rsi_passed = current_rsi <= RSI_BUY_THRESHOLD
            rsi_detail = f"{current_rsi:.1f} <= {RSI_BUY_THRESHOLD} (Bullish/Neutral)" if rsi_passed else f"{current_rsi:.1f} > {RSI_BUY_THRESHOLD} (Overbought/Bearish)"
            
            # Evaluate Volume
            vol_passed = is_vol_spike
            vol_detail = f"Vol {current_vol:.0f} > Avg {avg_vol:.0f} (Spike)" if is_vol_spike else f"Vol {current_vol:.0f} <= Avg {avg_vol:.0f} (Low Vol)"
            
            # Format icons
            ema_icon = "✅" if ema_passed else "❌"
            adx_icon = "✅" if adx_passed else "❌"
            rsi_icon = "✅" if rsi_passed else "❌"
            vol_icon = "✅" if vol_passed else "❌"
            
            # Overall recommendation status
            passed_all = ema_passed and adx_passed and rsi_passed
            status_text = "✅ <b>PASSED ALL FILTERS</b>" if passed_all else "⚠️ <b>SOME FILTERS FAILED</b>"
            
            msg = (f"🚀 <b>SAR BUY SIGNAL: {SAR_SYMBOL}</b>\n"
                   f"Price: {current_price}\n"
                   f"SAR: Flipped BUY\n"
                   f"Time: {time_str}\n\n"
                   f"📊 <b>Technical Filters:</b>\n"
                   f"{ema_icon} <b>EMA Trend:</b> {ema_detail}\n"
                   f"{adx_icon} <b>ADX Strength:</b> {adx_detail}\n"
                   f"{rsi_icon} <b>RSI Indicator:</b> {rsi_detail}\n"
                   f"{vol_icon} <b>Volume Spike:</b> {vol_detail}\n\n"
                   f"Filter Status: {status_text}")
            
            # Print filter status to console
            print(f"[SIGNAL EVAL] Flipped BUY - EMA: {ema_icon}, ADX: {adx_icon}, RSI: {rsi_icon}, VOL: {vol_icon}")
            return current_side, msg
            
        else:
            # Evaluate EMA
            ema_passed = not is_bullish
            ema_detail = f"Below EMA {EMA_PERIOD} (Bearish)" if not is_bullish else f"Above EMA {EMA_PERIOD} (Bullish)"
            
            # Evaluate ADX
            adx_passed = is_trending
            adx_detail = f"{current_adx:.1f} > {ADX_THRESHOLD} (Strong Trend)" if is_trending else f"{current_adx:.1f} <= {ADX_THRESHOLD} (Weak/Sideways)"
            
            # Evaluate RSI
            rsi_passed = current_rsi >= RSI_SELL_THRESHOLD
            rsi_detail = f"{current_rsi:.1f} >= {RSI_SELL_THRESHOLD} (Bearish/Neutral)" if rsi_passed else f"{current_rsi:.1f} < {RSI_SELL_THRESHOLD} (Oversold/Bullish)"
            
            # Evaluate Volume
            vol_passed = is_vol_spike
            vol_detail = f"Vol {current_vol:.0f} > Avg {avg_vol:.0f} (Spike)" if is_vol_spike else f"Vol {current_vol:.0f} <= Avg {avg_vol:.0f} (Low Vol)"
            
            # Format icons
            ema_icon = "✅" if ema_passed else "❌"
            adx_icon = "✅" if adx_passed else "❌"
            rsi_icon = "✅" if rsi_passed else "❌"
            vol_icon = "✅" if vol_passed else "❌"
            
            # Overall recommendation status
            passed_all = ema_passed and adx_passed and rsi_passed
            status_text = "✅ <b>PASSED ALL FILTERS</b>" if passed_all else "⚠️ <b>SOME FILTERS FAILED</b>"
            
            msg = (f"⚠️ <b>SAR SELL SIGNAL: {SAR_SYMBOL}</b>\n"
                   f"Price: {current_price}\n"
                   f"SAR: Flipped SELL\n"
                   f"Time: {time_str}\n\n"
                   f"📊 <b>Technical Filters:</b>\n"
                   f"{ema_icon} <b>EMA Trend:</b> {ema_detail}\n"
                   f"{adx_icon} <b>ADX Strength:</b> {adx_detail}\n"
                   f"{rsi_icon} <b>RSI Indicator:</b> {rsi_detail}\n"
                   f"{vol_icon} <b>Volume Spike:</b> {vol_detail}\n\n"
                   f"Filter Status: {status_text}")
            
            # Print filter status to console
            print(f"[SIGNAL EVAL] Flipped SELL - EMA: {ema_icon}, ADX: {adx_icon}, RSI: {rsi_icon}, VOL: {vol_icon}")
            return current_side, msg
        
    return current_side, None

def derive_recommendation(df):
    """
    Rule-based BUY / SELL / WAIT recommendation from the last CLOSED candle,
    using the same signals as the alerts: SAR direction, EMA200 trend, ADX
    strength and RSI. Returns (recommendation, reason) or None.
    """
    if df is None or len(df) < 3:
        return None

    latest = df.iloc[-2]
    l_col = f"PSARl_{SAR_AF0}_{SAR_MAX_AF}"
    sar_side = 'buy' if not pd.isna(latest[l_col]) else 'sell'
    price = latest['close']
    rsi = latest[f"RSI_{RSI_PERIOD}"]
    adx = latest[f"ADX_{ADX_PERIOD}"]
    ema = latest[f"EMA_{EMA_PERIOD}"]

    is_bullish = price > ema
    is_trending = adx > ADX_THRESHOLD

    # Weak/sideways trend → SAR whipsaws → don't act.
    if not is_trending:
        return "WAIT", f"ADX {adx:.1f} ≤ {ADX_THRESHOLD:.0f} (weak/sideways — SAR unreliable)"

    if sar_side == 'buy':
        if is_bullish and rsi <= RSI_BUY_THRESHOLD:
            return "BUY", f"SAR buy, price above EMA{EMA_PERIOD}, RSI {rsi:.1f} supportive"
        return "WAIT", f"SAR buy but trend/RSI not aligned (RSI {rsi:.1f}, {'bullish' if is_bullish else 'bearish'} vs EMA)"
    else:
        if (not is_bullish) and rsi >= RSI_SELL_THRESHOLD:
            return "SELL", f"SAR sell, price below EMA{EMA_PERIOD}, RSI {rsi:.1f} supportive"
        return "WAIT", f"SAR sell but trend/RSI not aligned (RSI {rsi:.1f}, {'bullish' if is_bullish else 'bearish'} vs EMA)"

def get_binance_data(client, symbols):
    """Fetch current price and 24h volume for symbols."""
    data = {}
    for symbol in symbols:
        try:
            ticker = client.get_ticker(symbol=symbol)
            data[symbol] = {
                "price": ticker["lastPrice"],
                "volume": ticker["volume"],
                "priceChangePercent": ticker["priceChangePercent"]
            }
        except Exception as e:
            print(f"Error fetching data for {symbol}: {e}")
    return data

def format_notification(data):
    """Format the tracking data for console log."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report = f"\n--- Crypto Update ({now}) ---\n"
    report += f"{'Symbol':<10} | {'Price':<12} | {'24h Change %':<12} | {'24h Volume':<15}\n"
    report += "-" * 60 + "\n"
    for symbol, info in data.items():
        report += f"{symbol:<10} | {info['price']:<12} | {info['priceChangePercent']:>11}% | {info['volume']:<15}\n"
    return report

def main():
    parser = argparse.ArgumentParser(description="Binance SAR Signal & tracking Bot")
    parser.add_argument("--interval", type=str, choices=["15m", "1h", "4h", "1d", "test"], default="1h", 
                        help="Check interval")
    parser.add_argument("--coins", type=str, nargs="+", default=DEFAULT_COINS,
                        help="Coins to track in console")
    parser.add_argument("--once", action="store_true",
                        help="Run a single check and exit (for cron / GitHub Actions). "
                             "State is persisted in Firestore, so scheduled runs continue seamlessly.")
    parser.add_argument("--status-only", action="store_true",
                        help="Send only the status table + recommendation; skip SAR flip "
                             "detection entirely. Leaves saved state untouched, so the "
                             "frequent flip-alert schedule stays the sole owner of it.")

    args = parser.parse_args()

    print(f"Starting Crypto Tracking Bot with SAR Signals...")
    print(f"Interval: {args.interval}")
    print(f"Signal Coin: {SAR_SYMBOL} (SAR Params: {SAR_AF0}/{SAR_MAX_AF})")

    # Single-shot mode: one check, then exit (scheduled by GitHub Actions).
    if args.once:
        run_once(args.interval, args.coins, status_only=args.status_only)
        return

    # Continuous mode: resume state and loop forever.
    last_side = get_last_signal_from_db()
    if last_side:
        print(f"Resuming state from Firestore: {last_side}")

    # Startup Message
    send_telegram_message(f"🤖 <b>Bot Started</b>\nMonitoring {SAR_SYMBOL} for SAR signals every {args.interval}.")

    run_bot(args.interval, args.coins)

def _make_client():
    """
    Build a Binance client from env credentials.

    Binance's main API (api.binance.com) geo-blocks many cloud IPs, including
    GitHub Actions runners ("Service unavailable from a restricted location").
    This bot only needs PUBLIC market data (klines + 24h ticker), which Binance
    also serves — WITHOUT geo restrictions — from the data-only mirror
    `data-api.binance.vision`. We point the client there by default so the same
    code runs locally and in the cloud. Override with BINANCE_BASE_URL if needed.
    """
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_SECRET_KEY")
    # No {} placeholders, so python-binance's `.format(base_endpoint, tld)` is a no-op.
    Client.API_URL = os.getenv("BINANCE_BASE_URL", "https://data-api.binance.vision/api")
    return Client(api_key, api_secret, requests_params={"timeout": 10})

def check_and_notify(client, coins_list, b_interval, last_side, status_only=False):
    """
    Run a single check cycle: refresh the price table, evaluate the SAR signal on
    the last closed candle, and send an HOURLY Telegram status message (price
    table + SOL indicator readout). When SAR flips, the flip alert (filter
    breakdown + AI insight) is appended to that same message.
    Returns the new SAR side so the caller can persist / carry it forward.

    status_only=True sends just the table + recommendation and skips flip
    detection. The two live on separate schedules (flips every 5 min, status
    hourly), so the status run must not consume a flip: whichever run detects
    one writes the new side to state, and the other would then never report it.
    """
    # 1. General price table (console + Telegram status)
    data = get_binance_data(client, coins_list)
    table = format_notification(data) if data else ""
    if table:
        print(table)

    # 2. Check Signals with Indicators
    df = get_indicator_data(client, SAR_SYMBOL, b_interval)
    if status_only:
        new_side, signal_msg = last_side, None
    else:
        new_side, signal_msg = check_signals(df, last_side)

    # Extract latest *closed* candle values for logging / AI context
    latest_rsi = latest_adx = latest_ema = None
    if df is not None and len(df) >= 2:
        latest = df.iloc[-2]
        latest_rsi = latest[f"RSI_{RSI_PERIOD}"]
        latest_adx = latest[f"ADX_{ADX_PERIOD}"]
        latest_ema = latest[f"EMA_{EMA_PERIOD}"]
        print(f"[{SAR_SYMBOL}] RSI: {latest_rsi:.1f} | ADX: {latest_adx:.1f} | EMA: {latest_ema:.2f}")

    # 3. Rule-based recommendation (BUY / SELL / WAIT) from the closed candle
    rec = derive_recommendation(df)
    rec_line = ""
    if rec:
        icon = {"BUY": "🟢", "SELL": "🔴", "WAIT": "🟡"}.get(rec[0], "🎯")
        rec_line = f"{icon} <b>Recommendation: {rec[0]}</b>\n{rec[1]}"
        print(f"[RECOMMENDATION] {rec[0]} — {rec[1]}")

    indicator_line = ""
    if latest_rsi is not None:
        indicator_line = (f"\n[{SAR_SYMBOL}] RSI: {latest_rsi:.1f} | "
                          f"ADX: {latest_adx:.1f} | EMA: {latest_ema:.2f}")

    # 4. On a SAR flip, build the signal alert (filters + AI insight)
    flip_block = ""
    if signal_msg:
        print(f"[SIGNAL] {signal_msg.replace('<b>','').replace('</b>','')}")

        # Fetch additional data for AI analysis
        all_data = get_binance_data(client, [SAR_SYMBOL])
        coin_data = all_data.get(SAR_SYMBOL)
        if coin_data and latest_rsi is not None:
            coin_data['rsi'] = latest_rsi

        # Get AI Analysis
        ai_insight = get_ai_analysis(SAR_SYMBOL, coin_data['price'] if coin_data else "Unknown", new_side, coin_data)
        flip_block = signal_msg + f"\n\n🤖 <b>AI Insight:</b>\n{ai_insight}"

        # Update persistent state
        save_signal_to_db(new_side)

    # 5. Assemble and send. The recommendation leads every message; the hourly
    #    status table follows (if enabled); the flip alert is appended on a flip.
    send_status = (status_only or SEND_STATUS_UPDATE) and bool(table)
    parts = []
    if send_status or flip_block:
        if rec_line:
            parts.append(rec_line)
        if send_status:
            parts.append(f"<pre>{table}{indicator_line}</pre>")
        if flip_block:
            parts.append(flip_block)

    telegram_msg = "\n\n".join(parts)
    if telegram_msg:
        send_telegram_message(telegram_msg)

    return new_side

def run_once(interval_str, coins_list, status_only=False):
    """
    Single check-and-exit cycle. Ideal for scheduled runs (GitHub Actions / cron)
    where the process starts, checks once, and exits. State is read from and
    written to Firestore, so hourly runs continue seamlessly across invocations.
    """
    client = _make_client()
    b_interval = BINANCE_INTERVALS.get(interval_str, Client.KLINE_INTERVAL_1HOUR)
    print(f"Single-shot run: {interval_str} interval.")
    last_side = None if status_only else get_last_signal_from_db()
    try:
        check_and_notify(client, coins_list, b_interval, last_side,
                         status_only=status_only)
    except Exception as e:
        print(f"Single-shot run error: {e}")
        send_telegram_message(f"⚠️ <b>Signal check failed</b>\nError: {e}")

def _seconds_until_next_close(period_seconds, buffer_seconds=20):
    """
    Seconds to wait until just after the next candle close.

    Sleeping a flat period_seconds instead would drift: each cycle starts a
    little later than the last (the check itself takes seconds), so checks
    creep away from the close and eventually read a candle that is still open.
    Anchoring to the wall clock keeps every wake-up just past a real boundary.
    """
    now = time.time()
    return (period_seconds - (now % period_seconds)) + buffer_seconds

def run_bot(interval_str, coins_list):
    """Continuous execution engine (loops forever). Used for always-on hosting / threads."""
    client = _make_client()
    period = INTERVAL_SECONDS.get(interval_str, 3600)
    b_interval = BINANCE_INTERVALS.get(interval_str, Client.KLINE_INTERVAL_1HOUR)

    print(f"Engine Starting: {interval_str} interval.")

    last_side = get_last_signal_from_db()

    consecutive_errors = 0
    while True:
        # Per-cycle, NOT around the loop: a transient network blip or Binance
        # 5xx must not end the process. This engine is meant to run unattended
        # for weeks, where exiting on the first hiccup means silent death until
        # someone notices the missing messages.
        try:
            last_side = check_and_notify(client, coins_list, b_interval, last_side)
            consecutive_errors = 0
        except Exception as e:
            consecutive_errors += 1
            print(f"Cycle error ({consecutive_errors}): {e}")
            # Alert once on the first failure only. Telegram-spamming every
            # cycle during an outage would bury the flip alerts that matter.
            if consecutive_errors == 1:
                try:
                    send_telegram_message(f"⚠️ <b>Signal check failed</b>\nError: {e}\nRetrying next candle.")
                except Exception:
                    pass
            # Rebuild the client — a poisoned session survives otherwise.
            try:
                client = _make_client()
            except Exception:
                pass

        wait = _seconds_until_next_close(period)
        print(f"Next check in {wait/60:.1f} min (aligned to {interval_str} close)...")
        time.sleep(wait)

if __name__ == "__main__":
    main()
