# utils.py
import logging
import asyncpg
import html
from datetime import datetime
from typing import Optional, List, Tuple, Any # Убедись, что Tuple есть

# Импорты из твоего проекта
import database # type: ignore
from config import Config # type: ignore

# Импорты Aiogram
from aiogram import Bot
from aiogram.types import Message
from aiogram.filters import CommandObject # Используем правильный импорт для CommandObject
# Если CommandObject не найден в aiogram.filters, попробуй:
# from aiogram.filters.command import CommandObject

from aiogram.utils.markdown import hlink
from pytz import timezone as pytz_timezone

# Логгер для этого модуля
logger_utils = logging.getLogger(__name__)

def get_user_mention_html(user_id: int, full_name: Optional[str], username: Optional[str] = None) -> str:
    """
    Создает HTML-ссылку для упоминания пользователя.
    """
    display_name = html.escape(full_name or f"User ID {user_id}")
    if username:
        return f'<a href="https://t.me/{html.escape(username)}">{display_name}</a>'
    else:
        # Используем hlink из aiogram.utils.markdown, который уже импортирован
        return hlink(display_name, f"tg://user?id={user_id}")

async def send_telegram_log(bot_instance: Bot, message_text: str, include_timestamp: bool = True):
    """
    Отправляет лог-сообщение в Telegram заданным получателям из Config.
    """
    target_ids: List[int] = []
    if Config.LOG_TELEGRAM_USER_ID is not None:
        target_ids.append(Config.LOG_TELEGRAM_USER_ID)
    if Config.LOG_TELEGRAM_CHAT_ID is not None:
        if Config.LOG_TELEGRAM_CHAT_ID not in target_ids:
            target_ids.append(Config.LOG_TELEGRAM_CHAT_ID)

    if not target_ids:
        logger_utils.info("Получатели логов в Telegram не настроены.")
        return

    full_message = message_text
    if include_timestamp:
        try:
            app_tz = pytz_timezone(Config.TIMEZONE)
            now_local = datetime.now(app_tz)
            timestamp_str = now_local.strftime('%Y-%m-%d %H:%M:%S')
            full_message = f"🕰️ <b>{timestamp_str}</b>\n{message_text}"
        except Exception as e_tz:
            logger_utils.error(f"Ошибка форматирования времени для лога Telegram: {e_tz}")
            full_message = f"🕰️ [Ошибка времени]\n{message_text}"

    for chat_id_to_send in target_ids:
        try:
            message_params = {
                "chat_id": chat_id_to_send,
                "text": full_message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            if Config.LOG_TELEGRAM_CHAT_ID is not None and \
               chat_id_to_send == Config.LOG_TELEGRAM_CHAT_ID and \
               Config.LOG_TELEGRAM_TOPIC_ID is not None:
                message_params["message_thread_id"] = Config.LOG_TELEGRAM_TOPIC_ID
                await bot_instance.send_message(**message_params)
                logger_utils.info(f"Лог отправлен в чат {chat_id_to_send} в тему {Config.LOG_TELEGRAM_TOPIC_ID}")
            else:
                await bot_instance.send_message(**message_params)
                if chat_id_to_send == Config.LOG_TELEGRAM_CHAT_ID:
                    logger_utils.info(f"Лог отправлен в чат {chat_id_to_send} (без указания темы).")
                else:
                    logger_utils.info(f"Лог отправлен пользователю {chat_id_to_send}.")
        except Exception as e:
            logger_utils.error(f"Не удалось отправить лог-сообщение в Telegram для ID {chat_id_to_send}: {e}")

async def get_current_price(base_price: int, conn_ext: Optional[asyncpg.Connection] = None) -> int:
    """
    Рассчитывает текущую цену товара с учетом инфляции.
    """
    conn_was_none = False
    active_conn = conn_ext
    if active_conn is None:
        active_conn = await database.get_connection()
        conn_was_none = True
    
    try:
        inflation_multiplier = await database.get_setting_float(
            Config.INFLATION_SETTING_KEY, 
            Config.DEFAULT_INFLATION_MULTIPLIER,
            conn_ext=active_conn
        )
        if inflation_multiplier is None: 
            inflation_multiplier = Config.DEFAULT_INFLATION_MULTIPLIER 
            logger_utils.error(f"PriceCalc: Не удалось получить множитель инфляции, используется дефолтный: {inflation_multiplier}")
        
        if inflation_multiplier < 0: 
            logger_utils.warning(f"PriceCalc: Множитель инфляции ({inflation_multiplier}) отрицательный. Используется 0.")
            inflation_multiplier = 0.0

        current_price_float = base_price * inflation_multiplier
        current_price_int = int(round(current_price_float))
        
        logger_utils.debug(f"PriceCalc: Base: {base_price}, Multiplier: {inflation_multiplier:.4f}, Calculated: {current_price_float:.2f} -> Rounded: {current_price_int}")
        return max(0, current_price_int)
    except Exception as e:
        logger_utils.error(f"PriceCalc: Ошибка при расчете цены с инфляцией для базовой цены {base_price}: {e}", exc_info=True)
        return base_price 
    finally:
        if conn_was_none and active_conn and not active_conn.is_closed():
            await active_conn.close()

async def fetch_user_display_data(bot_instance: Bot, user_id_to_fetch: int) -> Tuple[str, Optional[str]]:
    """
    Получает отображаемое имя и username пользователя.
    Сначала пытается извлечь из БД user_oneui, затем через API бота.
    """
    full_name: Optional[str] = None
    username: Optional[str] = None
    conn = None
    try:
        conn = await database.get_connection()
        udb = await conn.fetchrow("SELECT full_name, username FROM user_oneui WHERE user_id = $1 ORDER BY last_used DESC NULLS LAST LIMIT 1", user_id_to_fetch)
        if udb:
            full_name = udb.get('full_name')
            username = udb.get('username')
    except Exception as e:
        logger_utils.warning(f"DB fetch error for user {user_id_to_fetch} in fetch_user_display_data: {e}")
    finally:
        if conn and not conn.is_closed():
            await conn.close()
    
    if not full_name: 
        try:
            ci = await bot_instance.get_chat(user_id_to_fetch)
            fn_api = getattr(ci, 'full_name', None) or getattr(ci, 'first_name', None)
            if fn_api:
                full_name = fn_api
            if not username: 
                username = getattr(ci, 'username', None)
        except Exception as e:
            logger_utils.warning(f"API get_chat error for user {user_id_to_fetch} in fetch_user_display_data: {e}")
            
    return full_name or f"User ID {user_id_to_fetch}", username

async def resolve_target_user(msg: Message, cmd: CommandObject, bot_inst: Bot) -> Optional[Tuple[int, str, Optional[str]]]:
    """
    Определяет целевого пользователя из сообщения (ответ, ID, @username).
    Возвращает кортеж (user_id, full_name, username) или None.
    """
    uid: Optional[int] = None
    fn_from_source: Optional[str] = None 
    un_from_source: Optional[str] = None

    if msg.reply_to_message and msg.reply_to_message.from_user and not msg.reply_to_message.from_user.is_bot:
        repl_user = msg.reply_to_message.from_user
        uid, fn_from_source, un_from_source = repl_user.id, repl_user.full_name, repl_user.username
    elif cmd.args:
        arg = cmd.args.strip()
        if arg.startswith('@'):
            uname_find = arg[1:].lower()
            conn = None
            try:
                conn = await database.get_connection()
                urow = await conn.fetchrow("SELECT user_id, full_name, username FROM user_oneui WHERE lower(username) = $1 ORDER BY last_used DESC NULLS LAST LIMIT 1", uname_find)
                if urow:
                    uid, fn_from_source, un_from_source = urow['user_id'], urow.get('full_name'), urow.get('username')
                else:
                    await msg.reply(f"Пользователь @{html.escape(arg[1:])} не найден в базе данных бота. Попробуйте указать ID или ответить на сообщение.", disable_web_page_preview=True)
                    return None
            except Exception as e:
                logger_utils.error(f"DB error searching @{html.escape(arg[1:])} in resolve_target_user: {e}", exc_info=True)
                await msg.reply(f"Произошла ошибка при поиске пользователя @{html.escape(arg[1:])}. Попробуйте позже.", disable_web_page_preview=True)
                return None
            finally:
                if conn and not conn.is_closed():
                    await conn.close()
        else:
            try:
                uid = int(arg)
            except ValueError:
                await msg.reply("Неверный формат аргумента. Укажите ID пользователя, @username или ответьте на сообщение.", disable_web_page_preview=True)
                return None
    else: 
        return None

    if uid:
        final_fn, final_un = await fetch_user_display_data(bot_inst, uid)
        if final_fn == f"User ID {uid}" and fn_from_source:
            final_fn = fn_from_source
        if not final_un and un_from_source:
            final_un = un_from_source
        return uid, final_fn, final_un
    return None