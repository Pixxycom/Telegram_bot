import os
import time
import threading
import requests
from flask import Flask, request
import telebot

BOT_TOKEN = os.getenv("BOT_TOKEN")  # ✅ Secure: Token comes from environment
CHAT_ID = "6301144768"  # You can keep this hardcoded
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")
PORT = int(os.environ.get("PORT", 5000))

COINS = ["bitcoin", "ethereum", "binancecoin", "solana", "ripple"]
TIMEFRAMES = {"15m": 15, "1h": 60}

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

last_signal_time = {}

def fetch_price(coin_id):
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        return data[coin_id]["usd"]
    except Exception as e:
        print(f"Error fetching price for {coin_id}: {e}")
        return None

def fetch_price_history(coin_id):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days=1"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        prices = data.get("prices", [])
        return prices
    except Exception as e:
        print(f"Error fetching price history for {coin_id}: {e}")
        return []

def detect_order_block(prices):
    if len(prices) < 3:
        return None
    p1, p2, p3 = prices[-3][1], prices[-2][1], prices[-1][1]
    if p2 < p1 and p2 < p3:
        return "bullish"
    elif p2 > p1 and p2 > p3:
        return "bearish"
    return None

def detect_support_resistance(prices):
    vals = [p[1] for p in prices]
    if not vals:
        return None, None
    return min(vals), max(vals)

def analyze_coin(coin):
    prices = fetch_price_history(coin)
    if not prices:
        return None

    prices_1h = prices[::4]
    prices_15m = prices

    ob_1h = detect_order_block(prices_1h)
    ob_15m = detect_order_block(prices_15m)
    support, resistance = detect_support_resistance(prices_1h)
    current_price = fetch_price(coin)

    if not all([ob_1h, ob_15m, support, resistance, current_price]):
        return None

    if ob_1h != ob_15m:
        return None

    if ob_1h == "bullish" and current_price <= support * 1.01:
        entry = current_price
        sl = support * 0.98
        risk = entry - sl
        tp = entry + risk * 1.2
        return {
            "type": "LONG",
            "coin": coin,
            "entry": entry,
            "stop_loss": sl,
            "take_profit": tp,
        }

    if ob_1h == "bearish" and current_price >= resistance * 0.99:
        entry = current_price
        sl = resistance * 1.02
        risk = sl - entry
        tp = entry - risk * 2.5
        return {
            "type": "SHORT",
            "coin": coin,
            "entry": entry,
            "stop_loss": sl,
            "take_profit": tp,
        }
    return None

def send_signal(signal):
    coin = signal["coin"].upper()
    msg = (f"📢 *{signal['type']} Signal for {coin}*\n"
           f"Entry: ${signal['entry']:.2f}\n"
           f"Stop Loss: ${signal['stop_loss']:.2f}\n"
           f"Take Profit: ${signal['take_profit']:.2f}\n"
           "_Trade carefully and manage risk._")
    try:
        bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
        print(f"Signal sent for {coin}")
    except Exception as e:
        print(f"Failed to send signal for {coin}: {e}")

def signal_loop():
    while True:
        for coin in COINS:
            key = f"last_signal_{coin}"
            last_sent = last_signal_time.get(key, 0)
            if time.time() - last_sent < 1800:
                continue
            signal = analyze_coin(coin)
            if signal:
                send_signal(signal)
                last_signal_time[key] = time.time()
        time.sleep(60)

@bot.message_handler(commands=["start"])
def start_handler(message):
    bot.reply_to(message, "Hello! Crypto SMC Bot is online and analyzing market signals.")

@bot.message_handler(commands=["help"])
def help_handler(message):
    bot.reply_to(message, "This bot analyzes 5 crypto coins using Smart Money Concepts and sends signals with Entry, Stop Loss, and Take Profit.")

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/")
def index():
    return "Crypto SMC Bot is running."

if __name__ == "__main__":
    bot.remove_webhook()
    if RENDER_URL:
        bot.set_webhook(url=f"{RENDER_URL}/{BOT_TOKEN}")
        print(f"Webhook set to {RENDER_URL}/{BOT_TOKEN}")
    else:
        print("RENDER_EXTERNAL_URL not set, webhook not set")

    thread = threading.Thread(target=signal_loop, daemon=True)
    thread.start()

    app.run(host="0.0.0.0", port=PORT)
