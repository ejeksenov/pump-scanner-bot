import requests
import telebot
import time
from datetime import datetime, timedelta
import pytz
import os

# Переменные окружения
TOKEN = os.environ['BOT_TOKEN']
CHANNEL = os.environ['CHANNEL_NAME']
FINNHUB_API_KEY = os.environ['FINNHUB_KEY']

bot = telebot.TeleBot(TOKEN)
sent_tickers = set()
sent_test_message = False
news_memory = {}  # Хранение новостей: символ -> {time, open_price, headline}

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

def get_quote(symbol):
    try:
        url = f'https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}'
        return requests.get(url).json()
    except:
        return {}

def fetch_news():
    url = f'https://finnhub.io/api/v1/news?category=general&token={FINNHUB_API_KEY}'
    return requests.get(url).json()

def save_news_candidates(news):
    now = datetime.now(pytz.timezone('US/Eastern'))

    for item in news[:25]:
        if 'related' not in item or not item['related']:
            continue

        dt = datetime.fromtimestamp(item['datetime'], tz=pytz.timezone('US/Eastern'))
        if (now - dt).total_seconds() > 1800:  # старше 30 мин — игнор
            continue

        symbols = item['related'].split(',')
        for symbol in symbols:
            symbol = symbol.strip().upper()
            if not symbol.isalpha() or len(symbol) > 5:
                continue
            if symbol in news_memory:
                continue

            quote = get_quote(symbol)
            c, o = quote.get('c'), quote.get('o')
            if not c or not o or c <= 0 or o <= 0:
                continue

            exchange = get_exchange(symbol)
            if exchange not in ['NASDAQ', 'NYSE']:
                continue

            news_memory[symbol] = {
                'time': dt,
                'open_price': o,
                'headline': item['headline']
            }
            print(f"📰 Добавлено в отслеживание: {symbol} ({item['headline']})")

def check_signals():
    now = datetime.now(pytz.timezone('US/Eastern'))
    to_delete = []

    for symbol, data in news_memory.items():
        quote = get_quote(symbol)
        c, v = quote.get('c'), quote.get('v')
        if not c or not v:
            continue

        open_price = data['open_price']
        headline = data['headline']
        time_str = data['time'].strftime('%I:%M %p')
        exchange = get_exchange(symbol)
        if exchange not in ['NASDAQ', 'NYSE']:
            continue

        percent = ((c - open_price) / open_price) * 100
        text = None

        if c > 100:  # лимит
            to_delete.append(symbol)
            continue

        if percent >= 10 and v > 1_000_000:
            text = (
                f"🚨 ${symbol} ПАМП!\\n\\n"
                f"💵 Цена: ${open_price:.2f} → ${c:.2f} ({percent:+.1f}%)\\n"
                f"📊 Объём: {round(v / 1_000_000, 2)}M\\n"
                f"🏛 Биржа: {exchange}\\n"
                f"📰 Новость: {headline}\\n"
                f"🕒 Время: {time_str} EST"
            )
        elif percent >= 3:
            text = (
                f"📈 ${symbol} Сигнал на лонг\\n\\n"
                f"💵 Цена: ${open_price:.2f} → ${c:.2f} ({percent:+.1f}%)\\n"
                f"📊 Объём: {round(v / 1_000_000, 2)}M\\n"
                f"🏛 Биржа: {exchange}\\n"
                f"📰 Новость: {headline}\\n"
                f"🕒 Время: {time_str} EST"
            )

        if text and symbol not in sent_tickers:
            try:
                bot.send_message(CHANNEL, text)
                sent_tickers.add(symbol)
                print(f"✅ Отправлен сигнал: {symbol} ({percent:+.1f}%)")
                to_delete.append(symbol)
                time.sleep(2)
            except Exception as e:
                print(f"❌ Ошибка отправки {symbol}: {e}")

    for s in to_delete:
        news_memory.pop(s, None)

if __name__ == '__main__':
    print("🚀 Бот запущен!")
    while True:
        try:
            if not sent_test_message:
                bot.send_message(CHANNEL, "✅ Pump Scanner бот запущен и отслеживает сигналы.")
                sent_test_message = True
                print("📨 Тестовое сообщение отправлено.")

            if is_trading_hours():
                print("🔁 Проверка новостей и роста...")
                news = fetch_news()
                save_news_candidates(news)
                check_signals()
            else:
                print("⏱ Вне торгового времени (EST)")

            time.sleep(300)
        except Exception as e:
            print("🔥 Главная ошибка:", e)
            time.sleep(60)
