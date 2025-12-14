import requests
from bs4 import BeautifulSoup
import re
import telebot
import time
import hashlib
import threading
from telebot import types
from dotenv import load_dotenv
import os

# ==============================
# Settings
# ==============================
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/91.0.4472.124 Safari/537.36"
}
CHECK_INTERVAL = 300  # 5 минут

# ==============================
# Containers
# ==============================
user_filters = {}           # {chat_id: [ {brand, model, min_engine, max_engine, ...}, {...} ]}
seen_links_per_user = {}    # {chat_id: set(links)}

# ==============================
# Кнопки
# ==============================
def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Добавить авто", "📋 Мои авто")
    return kb

# ==============================
# Helpers
# ==============================
def extract_data(html):
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for tr in soup.find_all("tr"):
        if not tr.get("id", "").startswith("tr_"):
            continue
        try:
            tds = tr.find_all("td")
            if len(tds) >= 8:
                model = tds[3].get_text(strip=True)
                year = tds[4].get_text(strip=True)
                engine_text = tds[5].get_text(strip=True)
                mileage_text = re.sub(r'\D', '', tds[6].get_text(strip=True))
                price = re.sub(r'\D', '', tds[7].get_text(strip=True))
                link = "https://www.ss.com" + tr.find("a", href=True).get('href')

                rows.append([model, year, engine_text, mileage_text, price, link])
        except (IndexError, AttributeError):
            continue
    return rows


def parse_all_pages(brand, max_pages=100):
    seen_hashes = set()
    all_ads = []
    page = 1

    while page <= max_pages:
        url = f"https://www.ss.com/lv/transport/cars/{brand}/page{page}.html"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"Ошибка загрузки страницы {page}: {e}")
            break

        html = resp.text
        hash_value = hashlib.md5(html.encode("utf-8")).hexdigest()

        if hash_value in seen_hashes:
            break
        seen_hashes.add(hash_value)

        ads = extract_data(html)
        if not ads:
            break

        all_ads.extend(ads)
        page += 1
        time.sleep(0.1)

    return all_ads


def filter_ads(ads, filters):
    result = []
    for ad in ads:
        model, year, engine_text, mileage_text, price, link = ad

        # фильтр по модели
        if filters.get("model"):
            model_filter = filters["model"].lower()
            if filters["brand"] == "bmw" and model_filter.isdigit() and len(model_filter) == 1:
                if not model.strip() or not model[0].isdigit():
                    continue
                if model[0] != model_filter:
                    continue
            else:
                if model_filter not in model.lower():
                    continue

        # фильтр по году
        try:
            year_val = int(year)
        except:
            year_val = 0
        if filters["min_year"] and year_val < filters["min_year"]:
            continue
        if filters["max_year"] and year_val > filters["max_year"]:
            continue

        # фильтр по двигателю
        try:
            engine_size = float(re.sub(r'[^0-9.,]', '', engine_text).replace(',', '.'))
        except:
            engine_size = 0.0
        if filters["min_engine"] and engine_size < filters["min_engine"]:
            continue
        if filters["max_engine"] and engine_size > filters["max_engine"]:
            continue

        # фильтр по пробегу
        try:
            mileage = int(mileage_text)
        except:
            mileage = 0
        if filters["max_mileage"] and mileage > filters["max_mileage"]:
            continue

        # фильтр по цене
        try:
            price_val = int(price)
        except:
            price_val = 0
        if filters["min_price"] and price_val < filters["min_price"]:
            continue
        if filters["max_price"] and price_val > filters["max_price"]:
            continue

        result.append(ad)
    return result


def send_to_tg_chat(chat_id, ad):
    model, year, engine, mileage, price, link = ad
    message = (
        f"🚗 <b>{model}</b>\n"
        f"Год: {year}\n"
        f"Двигатель: {engine}\n"
        f"Пробег: {mileage} тыс. км\n"
        f"Цена: {price} €\n"
        f"<a href='{link}'>Смотреть объявление</a>"
    )
    bot.send_message(chat_id, message, parse_mode="HTML")


def check_new_ads_for_user(chat_id, first_run=False):
    all_ads = []
    for filters in user_filters.get(chat_id, []):
        brand = filters["brand"]
        ads = parse_all_pages(brand)
        ads = filter_ads(ads, filters)

        for ad in ads:
            link = ad[-1]
            if first_run or link not in seen_links_per_user[chat_id]:
                seen_links_per_user[chat_id].add(link)
                send_to_tg_chat(chat_id, ad)

    if not first_run:
        bot.send_message(chat_id, "Новых объявлений нет.", reply_markup=main_menu())


# ==============================
# Bot logic
# ==============================
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user_filters[chat_id] = []
    seen_links_per_user[chat_id] = set()
    bot.send_message(chat_id, "Привет! Я буду искать авто по твоим фильтрам.", reply_markup=main_menu())


@bot.message_handler(func=lambda m: m.text == "➕ Добавить авто")
def add_auto(message):
    bot.send_message(message.chat.id, "Введи марку автомобиля (например, bmw):")
    bot.register_next_step_handler(message, get_brand)


@bot.message_handler(func=lambda m: m.text == "📋 Мои авто")
def my_autos(message):
    chat_id = message.chat.id
    filters = user_filters.get(chat_id, [])
    if not filters:
        bot.send_message(chat_id, "У тебя пока нет добавленных фильтров.", reply_markup=main_menu())
    else:
        text = "📋 Список фильтров:\n\n"
        for i, f in enumerate(filters, 1):
            text += (f"{i}. {f['brand'].upper()} "
                     f"{f['model'] if f['model'] else ''}, "
                     f"двигатель {f['min_engine']}-{f['max_engine']} л, "
                     f"пробег до {f['max_mileage']} тыс., "
                     f"цена {f['min_price']}-{f['max_price']} €, "
                     f"год {f['min_year']}-{f['max_year']}\n")
        bot.send_message(chat_id, text, reply_markup=main_menu())


# ==============================
# Шаги заполнения фильтра
# ==============================
def get_brand(message):
    chat_id = message.chat.id
    brand = message.text.strip().lower()
    new_filter = {"brand": brand}
    user_filters[chat_id].append(new_filter)
    bot.send_message(chat_id, "Хочешь искать по определённой модели? (например tiguan). Если нет — напиши 'нет':")
    bot.register_next_step_handler(message, get_model, new_filter)

def get_model(message, new_filter):
    txt = message.text.strip().lower()
    new_filter["model"] = None if txt == "нет" else txt
    bot.send_message(message.chat.id, "Минимальный объём двигателя (например 1.6, можно оставить пустым):")
    bot.register_next_step_handler(message, get_min_engine, new_filter)

def get_min_engine(message, new_filter):
    txt = message.text.strip()
    new_filter["min_engine"] = float(txt) if txt else None
    bot.send_message(message.chat.id, "Максимальный объём двигателя (например 2.0, можно оставить пустым):")
    bot.register_next_step_handler(message, get_max_engine, new_filter)

def get_max_engine(message, new_filter):
    txt = message.text.strip()
    new_filter["max_engine"] = float(txt) if txt else None
    bot.send_message(message.chat.id, "Максимальный пробег (в тысячах, например 140, можно оставить пустым):")
    bot.register_next_step_handler(message, get_max_mileage, new_filter)

def get_max_mileage(message, new_filter):
    txt = message.text.strip()
    new_filter["max_mileage"] = int(txt) if txt else None
    bot.send_message(message.chat.id, "Минимальная цена (€), можно оставить пустым:")
    bot.register_next_step_handler(message, get_min_price, new_filter)

def get_min_price(message, new_filter):
    txt = message.text.strip()
    new_filter["min_price"] = int(txt) if txt else None
    bot.send_message(message.chat.id, "Максимальная цена (€), можно оставить пустым:")
    bot.register_next_step_handler(message, get_max_price, new_filter)

def get_max_price(message, new_filter):
    txt = message.text.strip()
    new_filter["max_price"] = int(txt) if txt else None
    bot.send_message(message.chat.id, "Мин. год выпуска (например 2005, можно оставить пустым):")
    bot.register_next_step_handler(message, get_min_year, new_filter)

def get_min_year(message, new_filter):
    txt = message.text.strip()
    new_filter["min_year"] = int(txt) if txt else None
    bot.send_message(message.chat.id, "Макс. год выпуска (например 2020, можно оставить пустым):")
    bot.register_next_step_handler(message, get_max_year, new_filter)

def get_max_year(message, new_filter):
    txt = message.text.strip()
    new_filter["max_year"] = int(txt) if txt else None
    bot.send_message(message.chat.id, "Фильтр сохранён ✅", reply_markup=main_menu())
    check_new_ads_for_user(message.chat.id, first_run=True)

# ==============================
# Periodic check (фоновый поток)
# ==============================
def periodic_check():
    while True:
        for chat_id in list(user_filters.keys()):
            try:
                check_new_ads_for_user(chat_id)
            except Exception as e:
                print(f"Ошибка при проверке {chat_id}: {e}")
        time.sleep(CHECK_INTERVAL)

threading.Thread(target=periodic_check, daemon=True).start()

# ==============================
# Run bot
# ==============================
bot.polling(none_stop=True)
