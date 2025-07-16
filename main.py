import requests
import telebot
import time
from datetime import datetime
import pytz
import os

# --- Настройки из переменных окружения ---
TOKEN = os.environ['BOT_TOKEN']
CHANNEL = os.environ['CHANNEL_NAME']
FINNHUB_API_KEY = os.environ['FINNHUB_KEY']

bot = telebot.TeleBot(TOKEN)
sent_tickers = set()

def is_trading_hours():
    now_est = datetime.now(pytz.timezone('US/Eastern'))
    return 4 <= now_est.hour < 16

def get_exchange(symbol):
    try:
        url = f'https://finnhub.io/api/v1/stock/profile2?symbol={symbol}&token={FINNHUB_API_KEY}'
        res = requests.get(url).json()
        return res.get('exchange', '')
    except:
        return ''

def check_stocks_and_send():
    url = f'https://finnhub.io/api/v1/news?category=general&token={FINNHUB_API_KEY}'
    news = requests.get(url).json()

    for item in news[:25]:
        if 'related' not in item or not item['related']:
            continue

        symbols = item['related'].split(',')
        for symbol in symbols:
            symbol = symbol.strip().upper()

            if not symbol.isalpha() or len(symbol) > 5:
                continue
            if symbol in sent_tickers:
                continue

            exchange = get_exchange(symbol)
            if exchange not in ['NASDAQ', 'NYSE']:
                continue

            quote_url = f'https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}'
            quote = requests.get(quote_url).json()
            c, o, v = quote.get('c'), quote.get('o'), quote.get('v')

            if not c or not o or not v:
                continue
            if c > 10 or v < 1_000_000:
                continue

            percent = ((c - o) / o) * 100 if o > 0 else 0
            dt = datetime.fromtimestamp(item['datetime'], tz=pytz.timezone('US/Eastern'))
            time_str = dt.strftime('%I:%M %p')

            text = (
                f"🚨 ${symbol} ПАМП!\n\n"
                f"💵 Цена: ${o:.2f} → ${c:.2f} ({percent:+.1f}%)\n"
                f"📊 Объём: {round(v / 1_000_000, 2)}M\n"
                f"🏛 Биржа: {exchange}\n"
                f"📰 Новость: {item['headline']}\n"
                f"🕒 Время: {time_str} EST"
            )

            try:
                bot.send_message(CHANNEL, text)
                sent_tickers.add(symbol)
                print(f"✅ Отправлено: {symbol}")
                time.sleep(2)
            except Exception as e:
                print(f"❌ Ошибка отправки {symbol}: {e}")

if __name__ == '__main__':
    while True:
        try:
            if is_trading_hours():
                check_stocks_and_send()
            else:
                print("⏱ Вне торгового времени (EST)")
            time.sleep(300)
        except Exception as e:
            print("🔥 Главная ошибка:", e)
            time.sleep(60)
