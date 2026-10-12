import asyncio
import logging
import os
import threading
import time
from typing import Dict

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
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
PORT = int(os.getenv("PORT", 10000))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан")
if not OWNER_ID:
    raise ValueError("OWNER_ID не задан")

# ============ ТЕКСТЫ ============
START_TEXT = "Привет! Я бот для приёма анкет в Хаус.\n\nВыбери действие на кнопках ниже 👇"
HOUSE_INFO_TEXT = "🏠 Информация о хаусе\n\nЗдесь будет текст про ваш хаус."
RULES_TEXT = "📜 Правила\n\nЗдесь будут правила хауса."

ANKETA_TEMPLATE = (
    "Здравствуйте!\nЯ бот для принятия анкет. Шаблон анкеты ниже:\n\n"
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
BANNED_REPLY = "🚫 Пользователь {user_id} добавлен в чёрный список на 7 дней."

# ============ ЧС ============
WEEK_SECONDS = 7 * 24 * 60 * 60
_blacklist: Dict[int, float] = {}

def _cleanup_blacklist():
    now = time.time()
    for uid in [u for u, ts in _blacklist.items() if now - ts > WEEK_SECONDS]:
        _blacklist.pop(uid, None)

def is_banned(user_id: int) -> bool:
    _cleanup_blacklist()
    return user_id in _blacklist

def add_to_blacklist(user_id: int):
    _blacklist[user_id] = time.time()

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

def _user_signature(user) -> str:
    username = f"@{user.username}" if user.username else "без юзернейма"
    return f"👤 {user.full_name} | {username} | id: {user.id}"

@router.message(F.text | F.caption)
async def handle_user_message(message: Message, bot: Bot):
    user_id = message.from_user.id
    if is_banned(user_id):
        return
    state = awaiting.pop(user_id, None)
    if not state:
        return
    header = "📥 НОВАЯ АНКЕТА" if state == "anketa" else "❓ НОВЫЙ ВОПРОС"
    body = message.text or message.caption or ""
    owner_text = f"{header}\n\n{_user_signature(message.from_user)}\n\n———\n\n{body}"
    sent = await bot.send_message(OWNER_ID, owner_text)
    owner_msg_map[sent.message_id] = user_id
    if state == "anketa":
        await message.answer(ANKETA_ACCEPTED, reply_markup=main_menu_kb())
    else:
        await message.answer(QUESTION_ACCEPTED, reply_markup=main_menu_kb())

@router.message(F.from_user.id == OWNER_ID, F.reply_to_message)
async def owner_reply(message: Message, bot: Bot):
    target_user_id = owner_msg_map.get(message.reply_to_message.message_id)
    if target_user_id is None:
        return
    text = (message.text or "").strip()
    if text == "/ban":
        add_to_blacklist(target_user_id)
        await message.reply(BANNED_REPLY.format(user_id=target_user_id))
        return
    try:
        await bot.send_message(target_user_id, f"💬 Ответ от владельца:\n\n{message.text}")
        await message.reply("✅ Ответ отправлен.")
    except Exception as e:
        await message.reply(f"⚠️ Не удалось отправить: {e}")

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
