# bonus_logic.py
import asyncio
import html
import random
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Optional, List, Dict, Any

from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message
from pytz import timezone as pytz_timezone
import logging
from achievements_logic import check_and_grant_achievements

# Убедитесь, что импорты корректны
from config import Config
import database
from utils import get_user_mention_html, send_telegram_log

bonus_router = Router()
logger = logging.getLogger(__name__)

# === Команды для бонусных множителей ===

@bonus_router.message(Command("bonus", ignore_case=True)) # Оставьте ваши алиасы, если они есть в Config
async def cmd_get_bonus_multiplier(message: Message, bot: Bot):
    if not message.from_user:
        await message.reply("Не удалось определить пользователя.")
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    user_link = get_user_mention_html(user_id, message.from_user.full_name, message.from_user.username)
    current_time_utc = datetime.now(dt_timezone.utc)
    local_tz = pytz_timezone(Config.TIMEZONE)

    reply_text_parts: List[str] = []
    used_extra_attempt_this_time = False
    can_claim_bonus_due_to_extra_attempt = False

    try:
        # 1. Проверка и использование дополнительных попыток (из рулетки или КУПЛЕННЫХ)
        # Поле 'extra_bonus_attempts' в roulette_status теперь общее
        user_roulette_status = await database.get_roulette_status(user_id, chat_id)
        
        available_extra_bonus_attempts = 0
        if user_roulette_status and user_roulette_status.get('extra_bonus_attempts', 0) > 0:
            available_extra_bonus_attempts = user_roulette_status['extra_bonus_attempts']

        if available_extra_bonus_attempts > 0:
            new_extra_attempts_count = available_extra_bonus_attempts - 1
            # Обновляем только extra_bonus_attempts в roulette_status
            await database.update_roulette_status(user_id, chat_id, {'extra_bonus_attempts': new_extra_attempts_count})
            reply_text_parts.append(
                f"🔄 Использована <b>дополнительная попытка /bonus</b> (купленная/от рулетки)! "
                f"Осталось таких попыток: {new_extra_attempts_count}."
            )
            used_extra_attempt_this_time = True
            can_claim_bonus_due_to_extra_attempt = True # Разрешаем получение бонуса, т.к. это доп. попытка
            logger.info(f"User {user_id} in chat {chat_id} used an extra /bonus attempt. Remaining: {new_extra_attempts_count}")
        
        # 2. Проверка стандартного кулдауна, ЕСЛИ дополнительная попытка НЕ была использована
        can_claim_new_bonus_standard = True # По умолчанию можно, если нет инфы о последнем получении
        if not used_extra_attempt_this_time:
            last_global_reset_ts_utc = await database.get_setting_timestamp('last_global_bonus_multiplier_reset')
            if not last_global_reset_ts_utc: # Если настройка не найдена в БД
                logger.warning("'last_global_bonus_multiplier_reset' is not set in DB. User can claim bonus by default.")
                # Устанавливаем фиктивное время в прошлом, чтобы разрешить получение
                last_global_reset_ts_utc = current_time_utc - timedelta(days=(Config.BONUS_MULTIPLIER_COOLDOWN_DAYS * 2))
            
            user_bonus_status = await database.get_user_bonus_multiplier_status(user_id, chat_id)
            if user_bonus_status and user_bonus_status.get('last_claimed_timestamp'):
                # last_claimed_timestamp должно быть aware datetime (UTC) из БД
                last_claimed_ts_aware = user_bonus_status['last_claimed_timestamp']
                if last_claimed_ts_aware >= last_global_reset_ts_utc:
                    can_claim_new_bonus_standard = False # Пользователь уже получал бонус в текущем периоде

        # 3. Если нельзя по стандарту И не использована доп. попытка -> отказ
        if not can_claim_new_bonus_standard and not can_claim_bonus_due_to_extra_attempt:
            # Расчет времени следующего сброса для сообщения пользователю (код из вашего файла)
            last_global_reset_ts_utc_for_msg = await database.get_setting_timestamp('last_global_bonus_multiplier_reset')
            if not last_global_reset_ts_utc_for_msg: # Если вдруг все еще нет
                last_global_reset_ts_utc_for_msg = current_time_utc - timedelta(days=Config.BONUS_MULTIPLIER_COOLDOWN_DAYS * 2)

            effective_next_reset_utc = last_global_reset_ts_utc_for_msg
            # Находим ближайшее будущее время сброса
            while effective_next_reset_utc <= current_time_utc:
                 effective_next_reset_utc += timedelta(days=Config.BONUS_MULTIPLIER_COOLDOWN_DAYS)
            
            # Приводим к часу сброса по местному времени
            effective_next_reset_local = effective_next_reset_utc.astimezone(local_tz)
            reset_today_local_at_hour = effective_next_reset_local.replace(hour=Config.BONUS_MULTIPLIER_RESET_HOUR, minute=2, second=0, microsecond=0)

            next_reset_display_local: datetime
            if effective_next_reset_local.time() > reset_today_local_at_hour.time() and \
               effective_next_reset_local.date() == reset_today_local_at_hour.date(): # Если сброс сегодня, но час уже прошел
                 next_reset_display_local = reset_today_local_at_hour + timedelta(days=Config.BONUS_MULTIPLIER_COOLDOWN_DAYS)
            elif effective_next_reset_local.date() > reset_today_local_at_hour.date(): # Если дата сброса уже в будущем
                 next_reset_display_local = reset_today_local_at_hour.replace(day=effective_next_reset_local.day, month=effective_next_reset_local.month, year=effective_next_reset_local.year)
            else: # Сброс сегодня, и час еще не наступил, или дата сброса совпадает
                 next_reset_display_local = reset_today_local_at_hour
            
            # Убедимся, что next_reset_display_local всегда в будущем относительно current_time_utc
            while next_reset_display_local.astimezone(dt_timezone.utc) <= current_time_utc:
                 next_reset_display_local += timedelta(days=Config.BONUS_MULTIPLIER_COOLDOWN_DAYS)


            await message.reply(
                f"{user_link}, вы уже испытали удачу на бонус-множитель в текущем {Config.BONUS_MULTIPLIER_COOLDOWN_DAYS}-дневном периоде. "
                f"Следующая глобальная возможность будет примерно после {next_reset_display_local.strftime('%Y-%m-%d %H:%M %Z')}.",
                disable_web_page_preview=True
            )
            return
            
        # 4. Логика получения бонус-множителя (если разрешено стандартом ИЛИ использована доп. попытка)
        multipliers = [item[0] for item in Config.BONUS_MULTIPLIER_CHANCES]
        weights = [item[1] for item in Config.BONUS_MULTIPLIER_CHANCES]
        chosen_multiplier = random.choices(multipliers, weights=weights, k=1)[0]

        # Время последнего получения бонуса:
        # Если это НЕ дополнительная попытка, то обновляем last_claimed_timestamp на current_time_utc.
        # Если это ДОПОЛНИТЕЛЬНАЯ попытка, то last_claimed_timestamp НЕ трогаем (оставляем старое или None),
        # чтобы не сбрасывать кулдаун на следующий *бесплатный* бонус.
        # Множитель и флаг is_bonus_consumed (на False) обновляются в любом случае.
        
        timestamp_to_set_for_this_bonus_claim: Optional[datetime] = None
        if not used_extra_attempt_this_time: # Это был стандартный (бесплатный) бонус
            timestamp_to_set_for_this_bonus_claim = current_time_utc
        else: # Это была дополнительная попытка
            # Нужно сохранить существующий last_claimed_timestamp, если он был, чтобы не сбросить период.
            # Если его не было, то и оставляем None.
            existing_bonus_status = await database.get_user_bonus_multiplier_status(user_id, chat_id)
            if existing_bonus_status and existing_bonus_status.get('last_claimed_timestamp'):
                timestamp_to_set_for_this_bonus_claim = existing_bonus_status['last_claimed_timestamp']
            # Если existing_bonus_status is None или там нет last_claimed_timestamp, то timestamp_to_set_for_this_bonus_claim останется None
            # что корректно для функции update_user_bonus_multiplier_status.
        
        await database.update_user_bonus_multiplier_status(
            user_id, chat_id, chosen_multiplier, 
            False, # is_bonus_consumed = False (бонус получен, но еще не применен к /oneui)
            timestamp_to_set_for_this_bonus_claim 
        )

        reply_text_parts.append(f"🎉 {user_link}, вам выпал бонус-множитель: <b>x{chosen_multiplier:.1f}</b>!")
        reply_text_parts.append("Он будет автоматически применен к вашему следующему использованию команды /oneui в этом чате.")

        if chosen_multiplier < 0: reply_text_parts.append("😱 Осторожно, множитель отрицательный!")
        elif chosen_multiplier == 1.0: reply_text_parts.append("😐 Стандартный множитель, эффект от /oneui не изменится.")
        elif chosen_multiplier == 0: reply_text_parts.append("🤷 Множитель x0.0... Эффект от /oneui будет равен нулю.")

        await message.reply("\n".join(reply_text_parts), parse_mode="HTML", disable_web_page_preview=True)

        chat_title_for_log = html.escape(message.chat.title or f"ChatID {chat_id}")
        log_action_type = "получил (с доп. попытки)" if used_extra_attempt_this_time else "получил"
        await send_telegram_log(bot, f"🎁 Пользователь {user_link} {log_action_type} бонус-множитель x{chosen_multiplier:.1f} в чате \"{chat_title_for_log}\"")

        # --- ВЫЗОВ ПРОВЕРКИ ДОСТИЖЕНИЙ ---
        await check_and_grant_achievements(
            user_id,
            chat_id,
            bot,
            bonus_multiplier_value=chosen_multiplier, # Значение полученного множителя
            bonus_extra_attempts_total_count=(new_extra_attempts_count if used_extra_attempt_this_time else None), # Если использовалась доп. попытка, передать их текущее кол-во
            bonus_multiplier_zero_applied=(True if chosen_multiplier == 0 else False), # Для "Эхо Пустоты"
            bonus_multiplier_very_negative=(True if chosen_multiplier <= -1.0 else False) # Для "Проклятие Фортуны"
        )
        # --- КОНЕЦ ВЫЗОВА ПРОВЕРКИ ДОСТИЖЕНИЙ ---


    except Exception as e:
        logger.error(f"Error in /bonus command for {user_link} in chat {chat_id}: {e}", exc_info=True)
        await message.reply("Произошла ошибка при получении бонуса. Попробуйте позже.")
        chat_title_display_exc = html.escape(message.chat.title or f"ID: {chat_id}")
        await send_telegram_log(bot, f"🔴 Ошибка в /bonus\nПользователь: {user_link} (ID: <code>{user_id}</code>)\nЧат: {chat_title_display_exc} (ID: <code>{chat_id}</code>)\nОшибка: <pre>{html.escape(str(e))}</pre>")


@bonus_router.message(Command("my_streak", "mystreak", "streak", ignore_case=True))
async def cmd_my_streak(message: Message, bot: Bot):
    if not message.from_user:
        await message.reply("Не удалось определить пользователя.")
        return

    user_id = message.from_user.id
    chat_id = message.chat.id # <--- ДОБАВЬТЕ ЭТУ СТРОКУ
    user_link = get_user_mention_html(user_id, message.from_user.full_name, message.from_user.username)

    try:
        # Теперь chat_id определен и может быть использован здесь
        streak_data = await database.get_user_daily_streak(user_id, chat_id) 
        current_streak = 0
        if streak_data and streak_data.get('last_streak_check_date'):
            today_local_date = datetime.now(pytz_timezone(Config.TIMEZONE)).date()
            last_check_date = streak_data['last_streak_check_date']

            if last_check_date == today_local_date or last_check_date == (today_local_date - timedelta(days=1)):
                 current_streak = streak_data.get('current_streak', 0)
            # Если last_check_date < (today_local_date - timedelta(days=1)), стрик считается прерванным (current_streak = 0)
            
        response_parts = [f"🔥 {user_link}, ваш текущий стрик: <b>{current_streak}</b> дней."]

        if current_streak > 0:
            next_goal_info = None
            for goal in Config.DAILY_STREAKS_CONFIG:
                if goal['target_days'] > current_streak:
                    next_goal_info = goal
                    break
            if next_goal_info:
                target_days_for_goal = next_goal_info['target_days']
                goal_name = next_goal_info['name']
                progress_show_within = next_goal_info.get('progress_show_within_days', 3) # Ваш дефолт
                if (target_days_for_goal - current_streak) <= progress_show_within:
                    max_bar_length_chars = 10 
                    filled_chars_visual = int(round((current_streak / target_days_for_goal) * max_bar_length_chars)) if target_days_for_goal > 0 else 0
                    empty_chars_visual = max_bar_length_chars - filled_chars_visual
                    progress_bar_str = Config.PROGRESS_BAR_FILLED_CHAR * filled_chars_visual + \
                                       Config.PROGRESS_BAR_EMPTY_CHAR * empty_chars_visual
                    response_parts.append(f"{goal_name}: {current_streak}/{target_days_for_goal} дней [{progress_bar_str}]")
                else: 
                    response_parts.append(f"🎯 Следующая цель: {goal_name} ({target_days_for_goal} дней).")
            elif Config.DAILY_STREAKS_CONFIG and current_streak >= Config.DAILY_STREAKS_CONFIG[-1]['target_days']:
                 response_parts.append(f"👑 Вы {Config.DAILY_STREAKS_CONFIG[-1]['name']}! Ваш легендарный стрик: {current_streak} дней. Новые испытания еще не объявлены!")
        else: 
            response_parts.append("У вас пока нет активного стрика. Начните сегодня с команды /oneui!")

        await message.reply("\n".join(response_parts), parse_mode="HTML", disable_web_page_preview=True)

        # --- ВЫЗОВ ПРОВЕРКИ ДОСТИЖЕНИЙ ---
        # chat_id также используется здесь и теперь будет определен
        await check_and_grant_achievements(
            user_id,
            chat_id, 
            bot,
            current_daily_streak=current_streak 
        )
        # --- КОНЕЦ ВЫЗОВА ПРОВЕРКИ ДОСТИЖЕНИЙ --
        
    except Exception as e:
        logger.error(f"Error in /my_streak for {user_link}: {e}", exc_info=True)
        await message.reply("Произошла ошибка при отображении информации о стрике.")
        await send_telegram_log(bot, f"🔴 Ошибка в /my_streak для {user_link}: <pre>{html.escape(str(e))}</pre>")


def setup_bonus_handlers(dp: Router): # dp здесь должен быть основным диспетчером или роутером, куда включаются другие
    dp.include_router(bonus_router)
    logger.info("Бонусные команды зарегистрированы.")
