# daily_onecoin_logic.py
import asyncio
import html
import random
from datetime import datetime, timedelta, timezone as dt_timezone, date as DDate
from typing import Optional, List, Dict

from aiogram import Router, Bot, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from pytz import timezone as pytz_timezone

from config import Config
import database
from utils import get_user_mention_html, send_telegram_log
from onecoin_phrases import ( # Импортируем новые фразы
    ONECOIN_CMD_SUCCESS_LOW_TIER,
    ONECOIN_CMD_SUCCESS_MID_TIER,
    ONECOIN_CMD_SUCCESS_HIGH_TIER,
    ONECOIN_CMD_SUCCESS_JACKPOT,
    ONECOIN_CMD_COOLDOWN,
    ONECOIN_CMD_ERROR
)
from achievements_logic import check_and_grant_achievements # Если будут ачивки

import logging

logger = logging.getLogger(__name__)
daily_onecoin_router = Router() # Создаем новый роутер

# --- Команда Ежедневной Награды OneCoin ---
@daily_onecoin_router.message(Command(*Config.DAILY_ONECOIN_ALIASES, ignore_case=True))
async def cmd_daily_onecoin_claim(message: Message, bot: Bot):
    if not message.from_user:
        await message.reply("Я тебя не знаю, проходимец!", disable_web_page_preview=True)
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    user_full_name = message.from_user.full_name
    user_username = message.from_user.username
    user_link = get_user_mention_html(user_id, user_full_name, user_username)
    
    current_utc_time = datetime.now(dt_timezone.utc)
    local_tz = pytz_timezone(Config.TIMEZONE)
    current_local_time = current_utc_time.astimezone(local_tz)

    # Определяем "эффективный день" для кулдауна
    effective_current_claim_day = current_local_time.date()
    if current_local_time.hour < Config.RESET_HOUR:
        effective_current_claim_day -= timedelta(days=1)

    logger.info(f"CMD_DAILY_ONECOIN: User {user_id} in chat {chat_id}. Effective claim date: {effective_current_claim_day}")

    user_chat_lock = await database.get_user_chat_lock(user_id, chat_id)
    async with user_chat_lock:
        conn = None
        try:
            conn = await database.get_connection()
            async with conn.transaction():
                # 1. Проверка кулдауна
                last_claim_utc = await database.get_user_daily_onecoin_claim_status(user_id, chat_id, conn_ext=conn)
                
                if last_claim_utc:
                    last_claim_local_time = last_claim_utc.astimezone(local_tz)
                    effective_last_claim_day = last_claim_local_time.date()
                    if last_claim_local_time.hour < Config.RESET_HOUR:
                        effective_last_claim_day -= timedelta(days=1)
                    
                    if effective_last_claim_day == effective_current_claim_day:
                        next_reset_time_display_local = current_local_time.replace(hour=Config.RESET_HOUR, minute=0, second=0, microsecond=0)
                        if current_local_time.hour >= Config.RESET_HOUR:
                            next_reset_time_display_local += timedelta(days=1)
                        
                        cooldown_phrase = random.choice(ONECOIN_CMD_COOLDOWN).format(
                            cooldown_ends_time=next_reset_time_display_local.strftime('%H:%M')
                        )
                        await message.reply(f"{user_link}, {cooldown_phrase}", disable_web_page_preview=True, parse_mode="HTML")
                        return
                
                # 2. Определение награды OneCoin
                chosen_tier_config = random.choices(
                    Config.DAILY_ONECOIN_REWARD_TIERS, 
                    weights=[t[1] for t in Config.DAILY_ONECOIN_REWARD_TIERS], 
                    k=1
                )[0]
                (min_c, max_c), _ = chosen_tier_config
                onecoin_reward = random.randint(min_c, max_c)

                # 3. Обновление баланса пользователя
                new_balance = await database.update_user_onecoins(
                    user_id, chat_id, onecoin_reward,
                    username=user_username, full_name=user_full_name,
                    chat_title=(message.chat.title or f"Чат {chat_id}"), 
                    conn_ext=conn
                )

                # 4. Обновление времени использования команды
                await database.update_user_daily_onecoin_claim_time(user_id, chat_id, current_utc_time, conn_ext=conn)

                # 5. Формирование и отправка "дерзкого" сообщения
                reply_phrase_template = ""
                if min_c == 500 and max_c == 500: # Джекпот
                    reply_phrase_template = random.choice(ONECOIN_CMD_SUCCESS_JACKPOT)
                elif 161 <= min_c <= 200: # Высокий тир (кроме джекпота)
                    reply_phrase_template = random.choice(ONECOIN_CMD_SUCCESS_HIGH_TIER)
                elif 51 <= min_c <= 160: # Средний тир
                    reply_phrase_template = random.choice(ONECOIN_CMD_SUCCESS_MID_TIER)
                else: # Низкий тир (30-50)
                    reply_phrase_template = random.choice(ONECOIN_CMD_SUCCESS_LOW_TIER)
                
                # Для отрицательных сумм (если бы они были, сейчас их нет в конфиге DAILY_ONECOIN_REWARD_TIERS)
                # if onecoin_reward < 0:
                #    reply_phrase_template = random.choice(ONECOIN_CMD_SUCCESS_NEGATIVE_PHRASES)
                #    reply_message = reply_phrase_template.format(amount_abs=abs(onecoin_reward))
                # else:

                reply_message = reply_phrase_template.format(amount=onecoin_reward)
                
                full_reply_message = f"{user_link}! {reply_message}\n💰 Твой новый баланс: <b>{new_balance}</b> OneCoin."
                
                await message.reply(full_reply_message, disable_web_page_preview=True, parse_mode="HTML")

                await send_telegram_log(bot, f"🪙 {user_link} использовал /onecoin и получил {onecoin_reward} OneCoin. Баланс: {new_balance}.")
                
                # 6. Вызов достижений (если будут)
                # await check_and_grant_achievements(user_id, chat_id, bot, daily_onecoin_claimed_amount=onecoin_reward)

        except Exception as e:
            logger.error(f"Ошибка в /onecoin для {user_link} в чате {chat_id}: {e}", exc_info=True)
            await message.reply(ONECOIN_CMD_ERROR, disable_web_page_preview=True)
        finally:
            if conn and not conn.is_closed():
                await conn.close()

def setup_daily_onecoin_handlers(dp: Router): # Название функции регистрации
    dp.include_router(daily_onecoin_router)
    logger.info("Обработчики команды /onecoin (ежедневной награды) зарегистрированы.")