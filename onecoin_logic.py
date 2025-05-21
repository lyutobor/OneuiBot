# onecoin_logic.py
import html
from aiogram import Router, Bot, F # Bot добавлен для send_telegram_log
from aiogram.filters import Command
from aiogram.types import Message
# hlink УДАЛЕН, используется get_user_mention_html
from typing import Optional
from achievements_logic import check_and_grant_achievements 

import database
from utils import get_user_mention_html, send_telegram_log # Импорт из utils
# Config не используется напрямую, но может понадобиться для send_telegram_log, если bot передается без Config
# from config import Config # <-- Если бы Config нужен был здесь

onecoin_router = Router()

# Локальная функция get_user_mention_link_from_db УДАЛЕНА
# Вместо нее используется get_user_mention_html из utils.py

@onecoin_router.message(Command("myonecoins", "balance", "мойбаланс", "моиonecoins", ignore_case=True))
async def my_onecoins_command(message: Message, bot: Bot): # bot добавлен для send_telegram_log
    if not message.from_user:
        await message.reply("Не могу определить пользователя.")
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    user_link = get_user_mention_html(user_id, message.from_user.full_name, message.from_user.username)

    try:
        balance = await database.get_user_onecoins(user_id, chat_id)
        await message.reply(f"{user_link}, ваш баланс в этом чате: <b>{balance}</b> OneCoin(s).",
                             disable_web_page_preview=True) #Превью убрать 
        # --- ВЫЗОВ ПРОВЕРКИ ДОСТИЖЕНИЙ ---
        await check_and_grant_achievements(
            user_id,
            chat_id,
            bot,
            current_onecoin_balance=balance # Передаем текущий баланс OneCoin
        )
        
    except Exception as e:
        await message.reply("Произошла ошибка при проверке баланса OneCoin.")
        await send_telegram_log(bot, f"🔴 Ошибка в /myonecoins для {user_link} в чате {chat_id}: <pre>{html.escape(str(e))}</pre>")


@onecoin_router.message(Command("toponecoins_chat", "топмонетчата", "топванкоиновчат", ignore_case=True))
async def top_onecoins_chat_command(message: Message, bot: Bot): # bot добавлен
    chat_id = message.chat.id
    chat_title_header = html.escape(message.chat.title or f"этом чате ({chat_id})")

    try:
        top_users_coins = await database.get_top_onecoins_in_chat(chat_id, limit=10)

        if not top_users_coins:
            return await message.reply(f"В чате {chat_title_header} пока нет данных о OneCoin балансах для топа.")

        response_lines = [f"<b>🏆 Топ пользователей по OneCoin в {chat_title_header}:</b>"]
        for i, user_data in enumerate(top_users_coins):
            user_link_text = get_user_mention_html(user_data['user_id'], user_data['full_name'], user_data.get('username'))
            response_lines.append(f"{i + 1}. {user_link_text} - <code>{user_data['onecoins']}</code> OneCoin(s)")
        await message.reply("\n".join(response_lines), disable_web_page_preview=True)
    except Exception as e:
        await message.reply("Произошла ошибка при отображении топа OneCoin в чате.")
        await send_telegram_log(bot, f"🔴 Ошибка в /toponecoins_chat (чат ID {chat_id}): <pre>{html.escape(str(e))}</pre>")


@onecoin_router.message(Command("toponecoins_global", "глобальныйтопмонет", "топванкоиновглобал", ignore_case=True))
async def top_onecoins_global_command(message: Message, bot: Bot): # bot добавлен
    try:
        top_global_coins_users = await database.get_global_top_onecoins(limit=10)

        if not top_global_coins_users:
            return await message.reply("В глобальном топе OneCoin пока нет данных.")

        response_lines = ["<b>🌍 Глобальный Топ пользователей по OneCoin:</b>"]
        for i, user_data in enumerate(top_global_coins_users):
            user_link_text = get_user_mention_html(user_data['user_id'], user_data['full_name'], user_data.get('username'))
            chat_display_info = ""
            chat_title_record = user_data.get('chat_title')
            telegram_chat_link_record = user_data.get('telegram_chat_link')
            user_id_record = user_data.get('user_id')
            chat_id_record = user_data.get('chat_id')

            if chat_title_record:
                chat_title_escaped = html.escape(chat_title_record)
                is_private_chat_indicator = f"Личный чат ({user_id_record})"
                if chat_id_record == user_id_record or chat_title_record == is_private_chat_indicator :
                     chat_display_info = " (в Личном чате)"
                elif telegram_chat_link_record:
                    chat_display_info = f" (из <a href=\"{telegram_chat_link_record}\">{chat_title_escaped}</a>)"
                else:
                    chat_display_info = f" (в чате {chat_title_escaped})"
            response_lines.append(f"{i + 1}. {user_link_text} - <code>{user_data['onecoins']}</code> OneCoin(s){chat_display_info}")
        await message.reply("\n".join(response_lines), disable_web_page_preview=True)
    except Exception as e:
        await message.reply("Произошла ошибка при отображении глобального топа OneCoin.")
        await send_telegram_log(bot, f"🔴 Ошибка в /toponecoins_global: <pre>{html.escape(str(e))}</pre>")


def setup_onecoin_handlers(dp):
    dp.include_router(onecoin_router)
    print("Обработчики команд OneCoin зарегистрированы.")