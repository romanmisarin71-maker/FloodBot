import asyncio
import logging
import os
import threading
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

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = int(os.getenv("OWNER_CHAT_ID", "0"))
if not OWNER_CHAT_ID:
    raise ValueError("OWNER_CHAT_ID не задан")

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
START_TEXT = "Выбери действие на кнопках ниже"

HOUSE_INFO_TEXT = "🏠 Информация о хаусе\n\nДрим текст быстрее"

RULES_MENU_TEXT = (
    "📜 Правила\n\n"
    "Выбери, какие правила хочешь посмотреть:"
)

CHAT_RULES_TEXT = (
    "📜 Правила Чата\n"
    "━━━━━━━━━━━━━━━━━━\n\n"

    "1.1 — Оскорбление\n"
    "Оскорбление какого-либо участника в любой форме (не считая дружеских, "
    "где оба человека понимают, что оскорбления не всерьёз) будут наказаны, "
    "то есть оскорбления личности, родных, друзей, религии, нации, страны, "
    "гендера, языка и т.д. — варн и мут на 1 час\n\n"

    "1.2 — Спам и «лесенки»\n"
    "Спамом считаются 2-4 (и больше) одинаковых соо, стикеров, гиф, гс, "
    "фоток, музыки и т.д. За спам выдаётся 2 варна и мут на 3 часа.\n"
    "Лесенкой считаются больше 5-ти соо (стиков, гифок, гс и т.д.), идущих "
    "друг за другом. Если лесенка будет больше и больше, то кол-во варнов "
    "увеличится. За лесенку варн (может до 3х возрасти).\n\n"

    "1.3 — Шок-контент\n"
    "Любой контент 18+ (порнушка, расчленёнка и т.д.) будет наказуем — "
    "варн и мут на 3 часа. За контент 21+ — бан без возврата.\n\n"

    "1.4 — Нежелательные темы\n"
    "Темы, которые касаются политики, полит. войн, религиозных взглядов, "
    "религии, сексизма, нацизма и т.д., не приветствуются здесь. — 2 варна, "
    "если будете продолжать — кик с хауса.\n\n"

    "1.5 — Использование команд\n"
    "Использование команд «калл», «!рулетка», «кости» и т.д. не разрешено. "
    "Команду «калл» может использовать только владелец Хауса, главы и тех "
    "админ, и оператор. А команды рулетка, кости, дуэль и т.д. запрещены по "
    "причине, что вас может кикнуть из-за них. Если используют эту команду — "
    "вас возвращать не станут, учтите. За использование команды «калл» вы "
    "получите варн, если продолжите — мут и так вплоть до кика с хауса.\n\n"

    "1.6 — Рекламы\n"
    "Рекламирование ботов, тгк, других проектов (флуды, хаусы, ролки и т.д.) "
    "категорически запрещено. Рекламировать что-либо можно только с разрешением "
    "владельца хауса. — за отправку рекламы варн и мут на 20 минут\n\n"

    "1.7 — Лич. данные\n"
    "Сливать личные данные участников хауса запрещено. Если про что-то подобное "
    "узнает администрация, то вы будете моментально кикнуты с хауса. Любой сват, "
    "докс, дианон и прочая хрень не приветствуется в хаусе.\n\n"

    "1.8 — Добавление друзей в хаус\n"
    "Прежде чем звать друзей в хаус, предупредите администрацию заранее, что "
    "ваш друг будет вступать. Если не предупредите — риск принятия может быть "
    "меньше, как у обычного нью.\n\n"

    "1.9 — Удаление соо\n"
    "Администрация вправе удалять соо участников, если это необходимо. Примерные "
    "соо по типу «чито гей, саша гей, а я не гей».\n\n"

    "1.10 — Перечить администрации\n"
    "Перечить делам администрации тоже не разрешено, администрация сама знает, "
    "что и как им нужно делать в хаусе. Также нельзя обжаловать выданное "
    "наказание от администрации. — варн\n\n"

    "1.11 — Игнорирование просьб/указов администрации\n"
    "Любое игнорирование просьб администрации будет серьёзно наказано. "
    "Категорически нельзя ослушиваться их указов и просьб, которые касаются "
    "сервера и чата. — варн, мут на 2 часа (может дойти до бана)\n\n"

    "1.12 — Кик и баны\n"
    "Некоторых участников, которые категорически портят настроение, вайб и "
    "дружелюбную атмосферу, могут кикать без какой-либо причины.\n\n"

    "1.13 — Выход без причин\n"
    "Если человек вышел уже более 2 раз, то его обратно невозможно вернуть, "
    "так как он уже без причины выходил/вылетал в прошлые разы. Но есть "
    "исключение (такие участники могут много раз выходить и заходить по причине "
    "«проверки телефона» и других не менее важных причин).\n\n"

    "1.14 — Ответственность\n"
    "Каждый участник самостоятельно несёт ответственность за свои сообщения "
    "и действия в сообществе.\n\n"

    "1.15 — Упоминание двух грехов\n"
    "Любое упоминание Жрима и Жрито без разрешения самого Дрима и Чито будет "
    "наказано алмазом в задницу."
)

SERVER_RULES_TEXT = (
    "⚔️ Правила Сервера\n"
    "━━━━━━━━━━━━━━━━━━\n\n"

    "2.1 — Гриферство\n"
    "Запрещено намеренно портить чужие постройки, заставлять их блоками, "
    "разливать лаву/воду рядом с приватной территорией или изменять ландшафт "
    "с целью навредить другим игрокам.\n"
    "Наказание: за первое такое нарушение — кик сервера на 3 дня. Если было "
    "нарушено во второй раз — бан.\n\n"

    "2.2 — Запрещённые моды\n"
    "Запрещено использовать читы, чит-клиенты (X-Ray, Baritone, Meteor и др.), "
    "модификации или скрипты, дающие нечестное преимущество над другими игроками.\n"
    "Наказание: бан.\n\n"

    "2.3 — Запрещённые постройки\n"
    "Запрещено возведение построек, содержащих нацистскую, экстремистскую или "
    "дискриминационную символику.\n"
    "Наказание: варн + кик с сервера на 1 день.\n\n"

    "2.4 — Запрещено строить дюп и лаг-машины\n"
    "Категорически запрещено использование любых багов игры для дюпа "
    "(клонирования) предметов, а также создание редстоун-схем и механизмов, "
    "создающих повышенную нагрузку на сервер (лаг-машин).\n"
    "Наказание: бан.\n\n"

    "2.5 — Воровство ресурсов\n"
    "Запрещено присваивать себе чужие ресурсы, ценности и предметы из сундуков, "
    "печей или воронок, даже если они не были запривачены.\n"
    "Наказание: варн + кик с сервера на 1 день.\n\n"

    "2.6 — Заходить на чужую терру\n"
    "Запрещено находиться на территории/базе без разрешения владельца, если тот "
    "явно просит вас уйти (в чате или табличкой).\n"
    "Наказание: варн.\n\n"

    "2.7 — Регулирование PvP\n"
    "Нападение на других игроков и проведение дуэлей разрешено строго по "
    "обоюдному согласию обеих сторон.\n"
    "Наказание: варн.\n\n"

    "2.8 — Помехи игровому миру и серверу\n"
    "Запрещены любые действия с окружением, которые создают визуальный мусор "
    "или вызывают нагрузку на сервер. По типу: массовое поджигание лесов и "
    "ландшафта, разлитие лавы/воды с большой высоты, взрыв большого количества "
    "ТНТ (динамита) без согласования с администрацией.\n"
    "Наказание: варн и кик с сервера на 3 дня.\n\n"

    "2.9 — Использование уязвимостей и багов\n"
    "Запрещено использовать любые баги игры или сервера для получения "
    "преимущества, захода в чужие закрытые помещения (например, баги с жемчугом "
    "Края, вагонетками, лодками, элитрами) или обхода установленных механик.\n"
    "Наказание: за одно нарушение — варн, за второе — бан."
)

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
BANNED_REPLY = "🚫 Пользователь {name} добавлен в БААААААН"
UNBANNED_REPLY = "✅ Пользователь {name} разбанен"
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
owner_msg_map: Dict[int, Dict] = {}

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

def rules_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Правила чата", callback_data="rules_chat")],
        [InlineKeyboardButton(text="⚔️ Правила сервера", callback_data="rules_server")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")],
    ])

def chat_rules_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ Правила сервера", callback_data="rules_server")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="rules")],
    ])

def server_rules_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Правила чата", callback_data="rules_chat")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="rules")],
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
    await call.message.edit_text(RULES_MENU_TEXT, reply_markup=rules_menu_kb())
    await call.answer()

@router.callback_query(F.data == "rules_chat")
async def cb_rules_chat(call: CallbackQuery):
    await call.message.edit_text(CHAT_RULES_TEXT, reply_markup=chat_rules_kb())
    await call.answer()

@router.callback_query(F.data == "rules_server")
async def cb_rules_server(call: CallbackQuery):
    await call.message.edit_text(SERVER_RULES_TEXT, reply_markup=server_rules_kb())
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

# ============ ОТВЕТ ИЗ ЧАТА ============
@router.message(F.chat.id == OWNER_CHAT_ID, F.from_user.id.in_(ADMIN_IDS), F.reply_to_message)
async def admin_reply(message: Message, bot: Bot):
    entry = owner_msg_map.get(message.reply_to_message.message_id)
    if entry is None:
        return
    target_user_id = entry["user_id"]
    target_name = entry["name"]
    text = (message.text or "").strip()

    if text == "/ban":
        add_to_blacklist(target_user_id)
        await message.reply(BANNED_REPLY.format(name=target_name))
        try:
            await bot.send_message(target_user_id, BANNED_NOTIFY)
        except Exception:
            pass
        return

    if text == "/unban":
        remove_from_blacklist(target_user_id)
        await message.reply(UNBANNED_REPLY.format(name=target_name))
        try:
            await bot.send_message(target_user_id, UNBANNED_NOTIFY)
        except Exception:
            pass
        return

    try:
        await bot.send_message(target_user_id, f"💬 Ответ от администрации:\n\n{message.text}")
        await message.reply("✅ Ответ отправлен.")
    except Exception as e:
        await message.reply(f"⚠️ Не удалось отправить: {e}")

# ============ СООБЩЕНИЯ ПОЛЬЗОВАТЕЛЕЙ ============
def _user_signature(user) -> str:
    username = f"@{user.username}" if user.username else "без юзернейма"
    return f"👤 {user.full_name} | {username} | id: {user.id}"

def _display_name(user) -> str:
    if user.username:
        return f"@{user.username}"
    return user.full_name or f"id{user.id}"

@router.message(F.text | F.caption)
async def handle_user_message(message: Message, bot: Bot):
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
    owner_msg_map[sent.message_id] = {
        "user_id": user_id,
        "name": _display_name(message.from_user),
    }
    if state == "anketa":
        await message.answer(ANKETA_ACCEPTED, reply_markup=main_menu_kb())
    else:
        await message.answer(QUESTION_ACCEPTED, reply_markup=main_menu_kb())

# ============ FLASK ============
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
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.run(main())
