from bot_instance import bot
from bot_interaction import main_menu, cancel_button, CANCEL_TEXT
from storage import user_filters, seen_links_per_user
from page_parser import parse_all_pages, filter_ads
import re

def parse_engine_with_dot(text: str) -> float:
    cleaned = text.strip()
    # format 2.0/1.6/0.5 etc - only with dot
    if not re.fullmatch(r"\d\.\d", cleaned):
        raise ValueError
    return float(cleaned)

def parse_int(text):
    cleaned = text.strip()
    if not cleaned.isdigit():
        raise ValueError
    return int(cleaned)

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

def handle_cancel(message):
    if message.text == CANCEL_TEXT:
        bot.send_message(message.chat.id, "Добавление машины отменено", reply_markup=main_menu())
        return True
    return False

def check_new_ads_for_user(chat_id, initial=False):
    seen_links_per_user.setdefault(chat_id, set())
    new_sent = False

    for filters in user_filters.get(chat_id, []):
        ads = parse_all_pages(filters["brand"])
        ads = filter_ads(ads, filters)

        for ad in ads:
            link = ad[-1]
            if link in seen_links_per_user[chat_id]:
                continue
            seen_links_per_user[chat_id].add(link)
            send_to_tg_chat(chat_id, ad)
            new_sent = True

    if not initial and not new_sent:
        bot.send_message(chat_id, "Нет новых объявлений", reply_markup=main_menu())


# =========================
# Bot message handlers
# =========================
@bot.message_handler(commands=["menu"])
def menu_cmd(message):
    bot.send_message(message.chat.id, "Выберите действие:", reply_markup=main_menu())

@bot.message_handler(commands=["add"])
def add_cmd(message):
    add_auto(message)

@bot.message_handler(commands=["myautos"])
def my_autos_cmd(message):
    my_autos(message)

@bot.message_handler(commands=["start"])
def start(message):
    chat_id = message.chat.id
    user_filters[chat_id] = []
    seen_links_per_user[chat_id] = set()
    bot.send_message(chat_id, "Привет! Я буду искать авто по твоим фильтрам.", reply_markup=main_menu())


@bot.message_handler(func=lambda m: m.text == "➕ Добавить авто")
def add_auto(message):
    bot.send_message(message.chat.id, "Введи марку автомобиля (например Volkswagen):", reply_markup=cancel_button())
    bot.register_next_step_handler(message, get_brand)


@bot.message_handler(func=lambda m: m.text == "📋 Мои авто")
def my_autos(message):
    chat_id = message.chat.id
    filters = user_filters.get(chat_id, [])

    if not filters:
        bot.send_message(chat_id, "Фильтров пока нет.", reply_markup=main_menu())
        return

    text = "📋 Твои фильтры:\n\n"
    for i, f in enumerate(filters, 1):
        text += (
            f"{i}. {f['brand'].upper()} {f['model'] or ''}, "
            f"двигатель {f['min_engine']}-{f['max_engine']} л, "
            f"пробег до {f['max_mileage']} тыс. км, "
            f"цена {f['min_price']}-{f['max_price']} €, "
            f"год {f['min_year']}-{f['max_year']}\n"
        )

    bot.send_message(chat_id, text, reply_markup=main_menu())


# =========================
# Get all necessary filters
# =========================

def get_brand(message):
    if handle_cancel(message):
        return
    chat_id = message.chat.id
    new_filter = {"brand": message.text.strip().lower()}
    user_filters.setdefault(chat_id, []).append(new_filter)

    bot.send_message(chat_id, "Модель? (или 'нет')", reply_markup=cancel_button())
    bot.register_next_step_handler(message, get_model, new_filter)


def get_model(message, new_filter):
    if handle_cancel(message):
        return
    txt = message.text.lower()
    new_filter["model"] = None if txt == "нет" else txt
    bot.send_message(message.chat.id, "Минимальный объём двигателя:", reply_markup=cancel_button())
    bot.register_next_step_handler(message, get_min_engine, new_filter)


def get_min_engine(message, new_filter):
    if handle_cancel(message):
        return
    text = message.text.strip()
    if text:
        try:
            new_filter["min_engine"] = parse_engine_with_dot(text)
        except ValueError:
            bot.send_message(message.chat.id, "Введите объём в формате 2.0(цифры и точка)", reply_markup=cancel_button())
            bot.register_next_step_handler(message, get_min_engine, new_filter)
            return
    else:
        new_filter["min_engine"] = None
    bot.send_message(message.chat.id, "Максимальный объём двигателя:", reply_markup=cancel_button())
    bot.register_next_step_handler(message, get_max_engine, new_filter)


def get_max_engine(message, new_filter):
    if handle_cancel(message):
        return
    text = message.text.strip()
    if text:
        try:
            new_filter["max_engine"] = parse_engine_with_dot(text)
        except ValueError:
            bot.send_message(message.chat.id, "Введите объём в формате 2.0 (цифры и точка)", reply_markup=cancel_button())
            bot.register_next_step_handler(message, get_max_engine, new_filter)
            return
    else:
        new_filter["max_engine"] = None
    bot.send_message(message.chat.id, "Максимальный пробег(в тысячах):", reply_markup=cancel_button())
    bot.register_next_step_handler(message, get_max_mileage, new_filter)


def get_max_mileage(message, new_filter):
    if handle_cancel(message):
        return
    text = message.text.strip()
    if text:
        try:
            new_filter["max_mileage"] = parse_int(text)
        except ValueError:
            bot.send_message(message.chat.id, "Пробег - только цифры", reply_markup=cancel_button())
            bot.register_next_step_handler(message, get_max_mileage, new_filter)
            return
    else:
        new_filter["max_mileage"] = None
    bot.send_message(message.chat.id, "Минимальная цена:", reply_markup=cancel_button())
    bot.register_next_step_handler(message, get_min_price, new_filter)


def get_min_price(message, new_filter):
    if handle_cancel(message):
        return
    text = message.text.strip()
    if text:
        try:
            new_filter["min_price"] = parse_int(text)
        except ValueError:
            bot.send_message(message.chat.id, "Цена - только цифры", reply_markup=cancel_button())
            bot.register_next_step_handler(message, get_min_price, new_filter)
            return
    else:
        new_filter["min_price"] = None
    bot.send_message(message.chat.id, "Максимальная цена:", reply_markup=cancel_button())
    bot.register_next_step_handler(message, get_max_price, new_filter)


def get_max_price(message, new_filter):
    if handle_cancel(message):
        return
    text = message.text.strip()
    if text:
        try:
            new_filter["max_price"] = parse_int(text)
        except ValueError:
            bot.send_message(message.chat.id, "Цена - только цифры", reply_markup=cancel_button())
            bot.register_next_step_handler(message, get_max_price, new_filter)
            return
    else:
        new_filter["max_price"] = None
    bot.send_message(message.chat.id, "Минимальный год выпуска:", reply_markup=cancel_button())
    bot.register_next_step_handler(message, get_min_year, new_filter)


def get_min_year(message, new_filter):
    text = message.text.strip()
    if text:
        try:
            new_filter["min_year"] = parse_int(text)
        except ValueError:
            bot.send_message(message.chat.id, "Год - только цифры", reply_markup=cancel_button())
            bot.register_next_step_handler(message, get_min_year, new_filter)
            return
    else:
        new_filter["min_year"] = None
    bot.send_message(message.chat.id, "Максимальный год выпуска:", reply_markup=cancel_button())
    bot.register_next_step_handler(message, get_max_year, new_filter)


def get_max_year(message, new_filter):
    if handle_cancel(message):
        return
    text = message.text.strip()
    if text:
        try:
            new_filter["max_year"] = parse_int(text)
        except ValueError:
            bot.send_message(message.chat.id, "Год - только цифры", reply_markup=cancel_button())
            bot.register_next_step_handler(message, get_max_year, new_filter)
            return
    else:
        new_filter["max_year"] = None
    bot.send_message(message.chat.id, "Фильтр сохранён ✅", reply_markup=main_menu())
    check_new_ads_for_user(message.chat.id, initial=True)
