import os
import requests
import time
from datetime import datetime
import ta
import pandas as pd
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

# Get your Telegram bot token and chat ID from environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# List of crypto pairs to monitor
PAIRS = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT']
TIMEFRAME = '1h'
LIMIT = 150

# Define your CoinGecko or Binance API endpoint for Kline data
def get_klines(symbol, interval, limit):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        response = requests.get(url)
        data = response.json()
        df = pd.DataFrame(data, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])
        df['close'] = df['close'].astype(float)
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return None

# Detect structure and simple order block logic
def detect_signal(df):
    if df is None or len(df) < 50:
        return None

    df['ema'] = ta.trend.ema_indicator(df['close'], window=20)
    df['rsi'] = ta.momentum.rsi(df['close'], window=14)

    if df['close'].iloc[-1] > df['ema'].iloc[-1] and df['rsi'].iloc[-1] < 70:
        return 'BUY'
    elif df['close'].iloc[-1] < df['ema'].iloc[-1] and df['rsi'].iloc[-1] > 30:
        return 'SELL'
    else:
        return None

# Send signal to Telegram
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        'chat_id': CHAT_ID,
        'text': message
    }
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Failed to send message: {e}")

def run():
    for pair in PAIRS:
        df = get_klines(pair, TIMEFRAME, LIMIT)
        signal = detect_signal(df)

        if signal:
            entry = df['close'].iloc[-1]
            sl = round(entry * 0.98, 2) if signal == 'BUY' else round(entry * 1.02, 2)
            tp = round(entry * 1.05, 2) if signal == 'BUY' else round(entry * 0.95, 2)
            trend = "UP" if signal == "BUY" else "DOWN"

            message = (
                f"📊 *SMC SIGNAL*\n"
                f"Pair: {pair}\n"
                f"Trend: {trend}\n"
                f"Signal: {signal}\n"
                f"Entry: {entry}\n"
                f"Stop Loss: {sl}\n"
                f"Take Profit: {tp}\n"
                f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
            )
            send_telegram_message(message)

# Main loop
if __name__ == "__main__":
    while True:
        run()
        time.sleep(1800)  # Wait 30 minutes before next scan
