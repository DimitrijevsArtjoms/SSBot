import threading
import time

from bot_instance import bot
from storage import user_filters
from handlers import check_new_ads_for_user
from config import CHECK_INTERVAL
from telebot.types import BotCommand

def setup_commands():
    bot.set_my_commands([
        BotCommand("menu", "Показать меню"),
        BotCommand("add", "➕ Добавить авто"),
        BotCommand("myautos", "📋 Мои авто"),
    ])

def periodic_check():
    first_pass = True
    while True:
        for chat_id in list(user_filters.keys()):
            try:
                check_new_ads_for_user(chat_id, initial=first_pass)
            except Exception as e:
                print(f"Ошибка проверки {chat_id}: {e}")
        first_pass = False
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    setup_commands()
    threading.Thread(target=periodic_check, daemon=True).start()
    bot.polling(none_stop=True)
