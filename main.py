import asyncio
import logging
import os
import threading
import time
from typing import Dict, Set

from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from dotenv import load_dotenv
from flask import Flask

# ============ КОНФИГ ============
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
# Чат, куда бот шлёт анкеты и вопросы
OWNER_CHAT_ID = -1004371458244
# Список ID админов через запятую, например: "123456789,987654321"
ADMIN_IDS: Set[int] = set()
_raw_admins = os.getenv("ADMIN_IDS", "")
for _x in _raw_admins.split(","):
    _x = _x.strip()
    if _x:
        try:
            ADMIN_IDS.add(int(_x))
        except ValueError:
            pass

PORT = int(os.getenv("PORT", 10000))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан")
if not ADMIN_IDS:
    raise ValueError("ADMIN_IDS не задан (нужен хотя бы один ID)")

# ============ ТЕКСТЫ ============
START_TEXT = "Привет! Я бот для приёма анкет в Хаус\n\nВыбери действие на кнопках ниже"
HOUSE_INFO_TEXT = "🏠 Информация о хаусе\n\nДрим сука когда текст"
RULES_TEXT = "📜 Правила\n\nИ правила нада дрим пиши давай"

ANKETA_TEMPLATE = (
    "Отлично!\nНапишите достойную анкету, шаблон анкеты ниже:\n\n"
    "1. Ваше имя или кличка/псевдоним\n\n2. Ваш часовой пояс: (пример: +2 к мск)\n\n"
    "3. Ваш возраст\n\n4. Ваш пол (Мужской или женский)\n\n"
    "5. Насколько вы будете активны в чатике и на сервере?\n\n6. Конфликтный вы человек?\n\n"
    "7. Состоите в других Хаусах или нет?\n\n8. Есть ли Discord?\n\n"
    "9. Расскажите о себе (чем больше информации — тем больше шансов на принятие)\n\n"
    "10. Ваш юз\n\n➡️ Отправь следующим сообщением заполненную анкету."
)
ANKETA_ACCEPTED = "✅ Вашу анкету рассмотрят! Нужно подождать."
QUESTION_PROMPT = "❓ Напишите свой вопрос, что вы хотите спросить?"
QUESTION_ACCEPTED = "✅ Вопрос задан! На него обязательно вам ответят."
BANNED_REPLY = "🚫 Пользователь {user_id} добавлен в БААААААН"
UNBANNED_REPLY = "✅ Пользователь {user_id} разбанен"
BANNED_NOTIFY = "🚫 Вы были забанены в боте."
UNBANNED_NOTIFY = "✅ Вы были разбанены в боте."

# ============ ЧС (навсегда, до рестарта) ============
_blacklist: Set[int] = set()

def is_banned(user_id: int) -> bool:
    return user_id in _blacklist

def add_to_blacklist(user_id: int):
    _blacklist.add(user_id)

def remove_from_blacklist(user_id: int):
    _blacklist.discard(user_id)

# ============ СОСТОЯНИЯ ============
awaiting: Dict[int, str] = {}
owner_msg_map: Dict[int, int] = {}

# ============ КЛАВИАТУРЫ ============
def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Информация о хаусе", callback_data="info")],
        [InlineKeyboardButton(text="📜 Правила", callback_data="rules")],
        [InlineKeyboardButton(text="📝 Заполнение анкеты", callback_data="anketa")],
        [InlineKeyboardButton(text="❓ Задать вопрос", callback_data="question")],
    ])

def back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")],
    ])

# ============ БОТ ============
router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    if is_banned(message.from_user.id):
        return
    await message.answer(START_TEXT, reply_markup=main_menu_kb())

@router.callback_query(F.data == "back")
async def cb_back(call: CallbackQuery):
    await call.message.edit_text(START_TEXT, reply_markup=main_menu_kb())
    await call.answer()

@router.callback_query(F.data == "info")
async def cb_info(call: CallbackQuery):
    await call.message.edit_text(HOUSE_INFO_TEXT, reply_markup=back_kb())
    await call.answer()

@router.callback_query(F.data == "rules")
async def cb_rules(call: CallbackQuery):
    await call.message.edit_text(RULES_TEXT, reply_markup=back_kb())
    await call.answer()

@router.callback_query(F.data == "anketa")
async def cb_anketa(call: CallbackQuery):
    if is_banned(call.from_user.id):
        await call.answer()
        return
    awaiting[call.from_user.id] = "anketa"
    await call.message.edit_text(ANKETA_TEMPLATE)
    await call.answer()

@router.callback_query(F.data == "question")
async def cb_question(call: CallbackQuery):
    if is_banned(call.from_user.id):
        await call.answer()
        return
    awaiting[call.from_user.id] = "question"
    await call.message.edit_text(QUESTION_PROMPT)
    await call.answer()

# ============ ОТВЕТ ИЗ ЧАТА (должен быть выше общего хендлера) ============
@router.message(F.chat.id == OWNER_CHAT_ID, F.from_user.id.in_(ADMIN_IDS), F.reply_to_message)
async def admin_reply(message: Message, bot: Bot):
    target_user_id = owner_msg_map.get(message.reply_to_message.message_id)
    if target_user_id is None:
        return
    text = (message.text or "").strip()

    # --- /ban ---
    if text == "/ban":
        add_to_blacklist(target_user_id)
        await message.reply(BANNED_REPLY.format(user_id=target_user_id))
        try:
            await bot.send_message(target_user_id, BANNED_NOTIFY)
        except Exception:
            pass
        return

    # --- /unban ---
    if text == "/unban":
        remove_from_blacklist(target_user_id)
        await message.reply(UNBANNED_REPLY.format(user_id=target_user_id))
        try:
            await bot.send_message(target_user_id, UNBANNED_NOTIFY)
        except Exception:
            pass
        return

    # --- обычный ответ — пересылаем юзеру ---
    try:
        await bot.send_message(target_user_id, f"💬 Ответ от владельца:\n\n{message.text}")
        await message.reply("✅ Ответ отправлен.")
    except Exception as e:
        await message.reply(f"⚠️ Не удалось отправить: {e}")

# ============ СООБЩЕНИЯ ПОЛЬЗОВАТЕЛЕЙ ============
def _user_signature(user) -> str:
    username = f"@{user.username}" if user.username else "без юзернейма"
    return f"👤 {user.full_name} | {username} | id: {user.id}"

@router.message(F.text | F.caption)
async def handle_user_message(message: Message, bot: Bot):
    # Игнорируем сообщения из админ-чата, чтобы они не улетели как анкеты
    if message.chat.id == OWNER_CHAT_ID:
        return

    user_id = message.from_user.id
    if is_banned(user_id):
        return
    state = awaiting.pop(user_id, None)
    if not state:
        return
    header = "📥 НОВАЯ АНКЕТА" if state == "anketa" else "❓ НОВЫЙ ВОПРОС"
    body = message.text or message.caption or ""
    owner_text = f"{header}\n\n{_user_signature(message.from_user)}\n\n———\n\n{body}"
    sent = await bot.send_message(OWNER_CHAT_ID, owner_text)
    owner_msg_map[sent.message_id] = user_id
    if state == "anketa":
        await message.answer(ANKETA_ACCEPTED, reply_markup=main_menu_kb())
    else:
        await message.answer(QUESTION_ACCEPTED, reply_markup=main_menu_kb())

# ============ FLASK ЗАГЛУШКА ============
app = Flask(__name__)

@app.route("/")
@app.route("/health")
def health():
    return "OK", 200

def run_flask():
    app.run(host="0.0.0.0", port=PORT)

# ============ ЗАПУСК ============
async def main():
    logging.basicConfig(level=logging.INFO)
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    # Flask в отдельном потоке
    threading.Thread(target=run_flask, daemon=True).start()
    # Бот в основном
    asyncio.run(main())
