from telebot import types

CANCEL_TEXT = "❌ Отменить добавление"

def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Добавить авто", "📋 Мои авто")
    return kb

def cancel_button():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(CANCEL_TEXT)
    return kb