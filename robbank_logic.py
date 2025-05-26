# robbank_logic.py
import asyncio
import random
import html
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Optional, List, Dict, Any, Tuple

from aiogram import Router, Bot, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from pytz import timezone as pytz_timezone

from config import Config
import database
from phrases import (
    ROBBANK_OPERATION_NAMES, ROBBANK_PENDING_PHRASES, ROBBANK_SUCCESS_PHRASES,
    ROBBANK_ARREST_PHRASES, ROBBANK_ALREADY_BLOCKED_PHRASES,
    ROBBANK_ALREADY_PENDING_PHRASES, ROBBANK_COOLDOWN_PHRASES,
    ROBBANK_NOT_ENOUGH_COINS_FOR_PREPARATION_PHRASES, ONEUI_BLOCKED_PHRASES
)
from utils import get_user_mention_html, send_telegram_log
from business_data import BUSINESS_DATA
from achievements_logic import check_and_grant_achievements

import logging

logger = logging.getLogger(__name__)
robbank_router = Router()

# --- Вспомогательные функции для расчета (оставляем без изменений с прошлой версии) ---

def _calculate_success_chance(oneui_version: float, bank_level: int) -> float:
    base_chance = Config.ROBBANK_BASE_SUCCESS_CHANCE
    oneui_bonus = (oneui_version // Config.ROBBANK_ONEUI_X_VERSIONS_FOR_BONUS) * Config.ROBBANK_ONEUI_VERSION_BONUS_PER_X_VERSIONS
    current_chance = base_chance + oneui_bonus
    bank_bonus = bank_level * Config.ROBBANK_BANK_LEVEL_SUCCESS_BONUS_PER_LEVEL
    current_chance += bank_bonus
    if Config.ROBBANK_GUARANTEED_SUCCESS_BANK_LEVEL_MIN <= bank_level <= Config.ROBBANK_GUARANTEED_SUCCESS_BANK_LEVEL_MAX:
        logger.info(f"Robbank: Гарантированный успех из-за уровня банка {bank_level} для пользователя.")
        return 1.0
    return min(current_chance, Config.ROBBANK_MAX_SUCCESS_CHANCE)

def _calculate_reward_multiplier_from_business(businesses: List[Dict[str, Any]]) -> float:
    if not businesses:
        return 1.0
    max_biz_order_idx = 0
    business_keys_ordered = list(BUSINESS_DATA.keys())
    for biz_data in businesses:
        try:
            if biz_data['business_key'] in business_keys_ordered:
                idx = business_keys_ordered.index(biz_data['business_key']) + 1
                if idx > max_biz_order_idx:
                    max_biz_order_idx = idx
            else:
                logger.warning(f"Robbank Calc: Ключ бизнеса '{biz_data.get('business_key')}' не найден в BUSINESS_DATA. Пропуск для расчета бонуса.")
        except ValueError:
            logger.warning(f"Robbank Calc: Ключ бизнеса '{biz_data.get('business_key')}' не найден в business_keys_ordered. Пропуск.")
            continue
        except KeyError:
            logger.warning(f"Robbank Calc: В данных бизнеса отсутствует 'business_key'. Данные: {biz_data}. Пропуск.")
            continue
    if max_biz_order_idx == 0:
        return 1.0
    mult_biz = 1.0
    if 1 <= max_biz_order_idx <= 6:
        min_b_mult = Config.ROBBANK_REWARD_BIZ_TIER_1_6_MIN_BONUS_PERCENT_AS_MULTIPLIER
        max_b_mult = Config.ROBBANK_REWARD_BIZ_TIER_1_6_MAX_BONUS_PERCENT_AS_MULTIPLIER
        if 6 - 1 > 0:
            mult_biz = min_b_mult + (max_biz_order_idx - 1) * ((max_b_mult - min_b_mult) / (6 - 1))
        else:
            mult_biz = min_b_mult
    elif 7 <= max_biz_order_idx <= 14:
        mult_biz = Config.ROBBANK_REWARD_BIZ_TIER_7_14_BONUS_PERCENT_AS_MULTIPLIER
    elif 15 <= max_biz_order_idx <= 18:
        min_b_mult = Config.ROBBANK_REWARD_BIZ_TIER_15_18_MIN_BONUS_PERCENT_AS_MULTIPLIER
        max_b_mult = Config.ROBBANK_REWARD_BIZ_TIER_15_18_MAX_BONUS_PERCENT_AS_MULTIPLIER
        tier_count = Config.ROBBANK_REWARD_BIZ_TIER_15_18_COUNT
        if tier_count > 1: # Избегаем деления на ноль
            mult_biz = min_b_mult + (max_biz_order_idx - 15) * ((max_b_mult - min_b_mult) / (tier_count - 1))
        else: # Если в тире только один бизнес (15-й), то он получает минимальный множитель этого тира
            mult_biz = min_b_mult
    mult_biz = max(1.0, mult_biz) # Множитель не может быть меньше 1.0
    logger.info(f"Robbank: Множитель награды от бизнеса (порядковый номер {max_biz_order_idx}) составил {mult_biz:.2f}")
    return round(mult_biz, 2)

def _calculate_reward(oneui_version: float, bank_level: int, businesses: List[Dict[str, Any]], base_preparation_cost: int) -> int:
    base_reward = Config.ROBBANK_REWARD_BASE_MIN
    if random.random() < Config.ROBBANK_REWARD_MAX_CHANCE:
        base_reward = Config.ROBBANK_REWARD_BASE_MAX
    else:
        if Config.ROBBANK_REWARD_BASE_MAX - 1 >= Config.ROBBANK_REWARD_BASE_MIN:
            base_reward = random.randint(Config.ROBBANK_REWARD_BASE_MIN, Config.ROBBANK_REWARD_BASE_MAX - 1)

    oneui_multiplier = 1.0 + (
        (oneui_version // Config.ROBBANK_REWARD_ONEUI_X_VERSIONS_FOR_MULTIPLIER) *
        Config.ROBBANK_REWARD_ONEUI_MULTIPLIER_PER_X_VERSIONS
    )
    bank_multiplier = 1.0 + (bank_level * Config.ROBBANK_REWARD_BANK_LEVEL_MULTIPLIER_PER_LEVEL)
    business_multiplier = _calculate_reward_multiplier_from_business(businesses)

    final_reward = base_reward * oneui_multiplier * bank_multiplier * business_multiplier
    final_reward = max(final_reward, float(base_preparation_cost))
    logger.info(f"Robbank Reward Calc: Base={base_reward}, PrepCost={base_preparation_cost}, OneUI_Mult={oneui_multiplier:.2f} (v{oneui_version}), Bank_Mult={bank_multiplier:.2f} (lvl{bank_level}), Biz_Mult={business_multiplier:.2f} -> Final={int(final_reward)}")
    return int(final_reward)

# Ключевое изменение: параметр `initial_message_thread_id` добавлен и используется
async def _process_robbank_result(
    user_id: int, 
    chat_id: int, 
    operation_name: str, 
    base_preparation_cost: int, 
    bot_instance: Bot, 
    initial_message_thread_id: Optional[int] # <-- Принимаем ID темы
):
    user_data_for_log = await database.get_user_data_for_update(user_id, chat_id)
    user_mention = get_user_mention_html(user_id, user_data_for_log.get('full_name'), user_data_for_log.get('username'))

    user_robbank_status = await database.get_user_robbank_status(user_id, chat_id)
    if not user_robbank_status or user_robbank_status.get('current_operation_name') != operation_name or user_robbank_status.get('current_operation_start_utc') is None:
        logger.warning(f"Robbank: _process_robbank_result для user {user_id}, chat {chat_id}. Операция '{operation_name}' не найдена или уже обработана.")
        return

    current_oneui_version = await database.get_user_version(user_id, chat_id)
    bank_account_data = await database.get_user_bank(user_id, chat_id)
    bank_level = bank_account_data.get('bank_level', 0) if bank_account_data else 0
    user_businesses_in_chat = await database.get_user_businesses(user_id, chat_id)

    success_chance = _calculate_success_chance(current_oneui_version, bank_level)
    is_success = random.random() < success_chance

    message_to_send = ""
    log_message_parts = [f"💰 Операция '{html.escape(operation_name)}' для {user_mention} (ID: <code>{user_id}</code>) в чате <code>{chat_id}</code> (Тема ID: {initial_message_thread_id if initial_message_thread_id else 'Нет'}):"]
    log_message_parts.append(f"  Шанс успеха: {success_chance*100:.2f}% (OneUI: {current_oneui_version:.1f}, Банк Ур: {bank_level})")

    if is_success:
        reward_amount = _calculate_reward(current_oneui_version, bank_level, user_businesses_in_chat, base_preparation_cost)
        new_balance = await database.update_user_onecoins(user_id, chat_id, reward_amount,
                                           username=user_data_for_log.get('username'),
                                           full_name=user_data_for_log.get('full_name'),
                                           chat_title=user_data_for_log.get('chat_title'))
        message_to_send = random.choice(ROBBANK_SUCCESS_PHRASES).format(amount=f"<b><code>{reward_amount:,}</code></b>")
        log_message_parts.append(f"  <b>РЕЗУЛЬТАТ: УСПЕХ!</b> Награда: <code>{reward_amount:,}</code> OneCoin. Новый баланс: <code>{new_balance:,}</code>")
        
        await database.update_user_robbank_status(
            user_id, chat_id,
            current_operation_name=None,
            current_operation_start_utc=None,
            current_operation_base_reward=None
        )
        await check_and_grant_achievements(
             user_id, chat_id, bot_instance, robbank_success_first_time=True
        )
    else: # Арест
        now_utc = datetime.now(dt_timezone.utc)
        local_tz = pytz_timezone(Config.TIMEZONE)
        
        # Рассчитываем время окончания блокировки на основе новой переменной
        block_until_local = (now_utc.astimezone(local_tz) + timedelta(days=Config.ROBBANK_ONEUI_BLOCK_DURATION_DAYS)).replace(hour=Config.ROBBANK_RESET_HOUR, minute=0, second=0, microsecond=0)
        
        # Если текущее время по местному часовому поясу уже позже часа сброса
        # (например, сейчас 22:00, а сброс в 21:00), то сброс будет на следующий день после этих 'N' дней.
        # Поэтому нужно убедиться, что блокировка будет до 21:00 в конце указанного периода.
        # Если block_until_local уже в прошлом, то надо перенести на следующий день.
        if block_until_local < now_utc.astimezone(local_tz):
            block_until_local += timedelta(days=1)

        block_until_utc = block_until_local.astimezone(dt_timezone.utc)

        streak_info_msg_part = ""
        user_streak_data = await database.get_user_daily_streak(user_id, chat_id)
        if user_streak_data and user_streak_data.get('current_streak', 0) > 0:
            current_s = user_streak_data['current_streak']
            streak_name_for_msg = ""
            for s_goal in Config.DAILY_STREAKS_CONFIG:
                if current_s >= s_goal['target_days']: streak_name_for_msg = s_goal['name']
                else: break
            if streak_name_for_msg:
                 streak_info_msg_part = f"(Текущий стрик: \"<b>{html.escape(streak_name_for_msg)}</b>\" - {current_s} д. если не использовал /oneui сегодня, то используй все ровно, чтобы не потерять стрик свой и после 21:00, ну вообщем используй /oneui, как будто ареста нету, чтобы стрик не потерять свой.)."
            else:
                 streak_info_msg_part = f"(Текущий стрик: {current_s} д. если не использовал /oneui сегодня, то используй все ровно, чтобы не потерять стрик свой и после 21:00, ну вообщем используй /oneui, как будто ареста нету, чтобы стрик не потерять.)"
        else:
            streak_info_msg_part = "(Не забудь использовать /oneui, чтобы не потерять возможный стрик!)"
        
        message_to_send = random.choice(ROBBANK_ARREST_PHRASES).format(
            block_time=block_until_local.strftime('%d.%m %H:%M'),
            streak_info=streak_info_msg_part
        )
        log_message_parts.append(f"  <b>РЕЗУЛЬТАТ: АРЕСТ.</b> /oneui заблокирован до {block_until_utc.isoformat()}.")
        
        await database.update_user_robbank_status(
            user_id, chat_id,
            robbank_oneui_blocked_until_utc=block_until_utc,
            current_operation_name=None, 
            current_operation_start_utc=None,
            current_operation_base_reward=None
        )
        await check_and_grant_achievements(
            user_id, chat_id, bot_instance, robbank_arrest_first_time=True
        )
    
    try:
        logger.info(f"Robbank: Попытка отправить результат в чат {chat_id}, тема ID: {initial_message_thread_id}, текст: {message_to_send[:100]}...")
        await bot_instance.send_message(
            chat_id, 
            f"{user_mention}, {message_to_send}", 
            parse_mode="HTML", 
            message_thread_id=initial_message_thread_id, # <-- Используем переданный ID темы
            disable_web_page_preview=True # Добавил для консистентности
        )
        logger.info(f"Robbank: Сообщение о результате успешно отправлено в чат {chat_id}, тема ID: {initial_message_thread_id}.")
    except Exception as e_send_chat:
        logger.warning(f"Robbank: Не удалось отправить результат операции '{operation_name}' в чат {chat_id} (тема: {initial_message_thread_id}) для user {user_id}: {e_send_chat}. Попытка в ЛС.")
        try:
            await bot_instance.send_message(user_id, f"Результат операции '{html.escape(operation_name)}' в чате ID {chat_id}:\n{message_to_send}", parse_mode="HTML", disable_web_page_preview=True)
        except Exception as e_send_pm:
            logger.error(f"Robbank: Не удалось отправить результат операции '{operation_name}' в ЛС user {user_id}: {e_send_pm}")

    await send_telegram_log(bot_instance, "\n".join(log_message_parts))


@robbank_router.message(Command(*Config.ROBBANK_ALIASES, ignore_case=True))
async def handle_robbank_command(message: Message, bot: Bot): # bot: Bot можно заменить на message.bot далее
    if not message.from_user:
        await message.reply("Не могу определить пользователя.")
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    # Получаем message_thread_id из объекта message
    original_message_thread_id = message.message_thread_id 
    
    user_full_name = message.from_user.full_name
    user_username = message.from_user.username
    user_link = get_user_mention_html(user_id, user_full_name, user_username)
    
    now_utc = datetime.now(dt_timezone.utc)
    local_tz = pytz_timezone(Config.TIMEZONE)

    current_user_chat_lock = await database.get_user_chat_lock(user_id, chat_id)
    async with current_user_chat_lock:
        try:
            robbank_status = await database.get_user_robbank_status(user_id, chat_id)

            if robbank_status and robbank_status.get('current_operation_start_utc'):
                await message.reply(random.choice(ROBBANK_ALREADY_PENDING_PHRASES),
                                    disable_web_page_preview=True) # message.reply() сам использует thread_id
                return

            if robbank_status and robbank_status.get('last_robbank_attempt_utc'):
                last_attempt_utc = robbank_status['last_robbank_attempt_utc']
                current_day_start_local = now_utc.astimezone(local_tz).replace(hour=Config.ROBBANK_RESET_HOUR, minute=0, second=0, microsecond=0)
                if now_utc.astimezone(local_tz) < current_day_start_local:
                    current_day_start_local -= timedelta(days=1)
                cooldown_ends_local = current_day_start_local + timedelta(days=Config.ROBBANK_COOLDOWN_DAYS)
                if last_attempt_utc.astimezone(local_tz) > current_day_start_local:
                    await message.reply(random.choice(ROBBANK_COOLDOWN_PHRASES).format(cooldown_ends_time=cooldown_ends_local.strftime(' %H:%M')),
                                        disable_web_page_preview=True)
                    return
            
            preparation_cost = random.randint(Config.ROBBANK_PREPARATION_COST_MIN, Config.ROBBANK_PREPARATION_COST_MAX)
            current_balance = await database.get_user_onecoins(user_id, chat_id)

            if current_balance < preparation_cost:
                await message.reply(random.choice(ROBBANK_NOT_ENOUGH_COINS_FOR_PREPARATION_PHRASES).format(cost=f"<code>{preparation_cost:,}</code>", current_balance=f"<code>{current_balance:,}</code>"),
                                    parse_mode="HTML",
                                    disable_web_page_preview=True)
                return

            await database.update_user_onecoins(user_id, chat_id, -preparation_cost,
                                               username=user_username, full_name=user_full_name,
                                               chat_title=message.chat.title)
            
            operation_name = random.choice(ROBBANK_OPERATION_NAMES)
            operation_delay_seconds = random.randint(Config.ROBBANK_RESULT_DELAY_MIN_SECONDS, Config.ROBBANK_RESULT_DELAY_MAX_SECONDS)
            
            await database.update_user_robbank_status(
                user_id, chat_id,
                last_robbank_attempt_utc=now_utc,
                current_operation_name=operation_name,
                current_operation_start_utc=now_utc,
                current_operation_base_reward=preparation_cost
            )

            time_left_display_minutes = f"{int(operation_delay_seconds / 60) + 1} мин."
            pending_message_text = random.choice(ROBBANK_PENDING_PHRASES).format(
                base_amount=f"<code>{preparation_cost:,}</code>", 
                time_left_minutes=time_left_display_minutes
            )
            # message.reply() отправит ответ в ту же тему, если original_message_thread_id не None
            await message.reply(f"<b>Операция \"{html.escape(operation_name)}\"</b>\n{user_link}, {pending_message_text}",
                                parse_mode="HTML",
                                disable_web_page_preview=True)
            
            logger.info(f"Robbank: Пользователь {user_id} (чат {chat_id}, тема {original_message_thread_id}) начал операцию '{operation_name}'. Цена: {preparation_cost}, Задержка: {operation_delay_seconds}с.")

            # Передаем original_message_thread_id в отложенную задачу
            asyncio.create_task(
                _delayed_robbank_processing_wrapper(
                    delay_seconds=operation_delay_seconds, 
                    user_id=user_id, 
                    chat_id=chat_id, 
                    operation_name=operation_name, 
                    base_prep_cost=preparation_cost, 
                    bot_instance=message.bot, # Используем message.bot
                    initial_message_thread_id=original_message_thread_id # Передаем ID темы
                )
            )

        except Exception as e:
            logger.error(f"Ошибка в /robbank для user {user_id} в чате {chat_id} (тема {original_message_thread_id}): {e}", exc_info=True)
            await message.reply("Произошла внутренняя ошибка при попытке ограбления. Попробуйте позже.",
                                disable_web_page_preview=True) # message.reply() сам обработает тему
            await send_telegram_log(message.bot, f"🔴 Ошибка в /robbank для {user_link} (тема {original_message_thread_id}): <pre>{html.escape(str(e))}</pre>")


async def _delayed_robbank_processing_wrapper(
    delay_seconds: int, 
    user_id: int, 
    chat_id: int, 
    operation_name: str, 
    base_prep_cost: int, 
    bot_instance: Bot, 
    initial_message_thread_id: Optional[int] # <-- Принимаем ID темы
):
    """Обертка для asyncio.sleep и вызова основной логики с обработкой исключений."""
    try:
        await asyncio.sleep(delay_seconds)
        # Передаем initial_message_thread_id дальше
        await _process_robbank_result(user_id, chat_id, operation_name, base_prep_cost, bot_instance, initial_message_thread_id)
    except Exception as e:
        logger.error(f"Критическая ошибка в отложенной задаче _process_robbank_result для user {user_id}, chat {chat_id}, op '{operation_name}', тема {initial_message_thread_id}: {e}", exc_info=True)
        try:
            await database.update_user_robbank_status(
                user_id, chat_id,
                current_operation_name=None,
                current_operation_start_utc=None,
                current_operation_base_reward=None
            )
            # При ошибке отправляем в ЛС, так как контекст темы мог быть утерян или вызвал ошибку
            await bot_instance.send_message(user_id, f"⚠️ Произошла критическая ошибка во время вашей операции '{html.escape(operation_name)}' в чате {chat_id}. Пожалуйста, попробуйте позже. Операция отменена.", parse_mode="HTML", disable_web_page_preview=True)
            await send_telegram_log(bot_instance, f"🔴 КРИТ. ОШИБКА в отложенной задаче robbank для {user_id} (операция '{html.escape(operation_name)}', чат {chat_id}, тема {initial_message_thread_id} отменена): <pre>{html.escape(str(e))}</pre>")
        except Exception as e_cleanup:
            logger.error(f"Двойная ошибка: не удалось очистить статус robbank для user {user_id} после ошибки в _process_robbank_result: {e_cleanup}", exc_info=True)


def setup_robbank_handlers(dp: Router):
    dp.include_router(robbank_router)
    logger.info("<b>Жирный</b>Robbank command handlers registered.<code>Кликается для копирования</code>")
