# main.py
import os
import random
import asyncio
import html
from datetime import datetime, timedelta, date as DDate, timezone as dt_timezone
from typing import Optional, List, Dict, Any, Tuple

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, Chat, User as AiogramUser # AiogramUser может быть нужен для resolve_target_user
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage # Если используется FSM
from phone_data import PHONE_MODELS as PHONE_MODELS_STANDARD_LIST_FOR_MAIN
from exclusive_phone_data import EXCLUSIVE_PHONE_MODELS as EXCLUSIVE_PHONE_MODELS_LIST_FOR_MAIN
from business_data import BUSINESS_DATA # Добавлено
from business_logic import setup_business_handlers, process_daily_business_income_and_events # Добавлено
from stats_logic import setup_stats_handlers
from achievements_logic import check_and_grant_achievements, setup_achievements_handlers
from commands_data import COMMAND_CATEGORIES
from robbank_logic import setup_robbank_handlers
from dotenv import load_dotenv
from pytz import timezone as pytz_timezone # Убедитесь, что pytz установлен: pip install pytz
import logging
from phrases import ONEUI_BLOCKED_PHRASES
from daily_onecoin_logic import setup_daily_onecoin_handlers

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from black_market_logic import setup_black_market_handlers, refresh_black_market_offers

from config import Config
import database # Импортируем модуль database целиком
# Можно также импортировать конкретные функции, если их много и это улучшает читаемость
from database import (
    init_db,
    get_user_version, update_user_version, check_cooldown,
    get_top_users_in_chat, get_global_top_users, get_user_top_versions, get_user_version_history,
    get_user_family_membership, # Используется в командах семей, которые могут быть здесь
    # FAMILY_CREATION_MIN_VERSION, # Лучше брать из Config напрямую, если это константа
    get_user_onecoins, update_user_onecoins,
    get_top_onecoins_in_chat, get_global_top_onecoins,
    get_setting_timestamp, set_setting_timestamp,
    get_user_bonus_multiplier_status, update_user_bonus_multiplier_status,
    get_user_daily_streak, update_user_daily_streak,
    # НОВЫЕ ИМПОРТЫ ДЛЯ ШЕДУЛЕРА ТЕЛЕФОНОВ
    get_all_operational_phones, get_phones_for_battery_check, update_phone_status_fields,
    get_phones_with_expiring_insurance,
    get_user_chat_lock
)

# Импортируем обработчики из других модулей
try:
    from utils import get_user_mention_html, send_telegram_log
    from item_data import PHONE_CASES, CORE_PHONE_COMPONENT_TYPES, PHONE_COMPONENTS
    from phone_data import PHONE_MODELS as PHONE_MODELS_LIST_MAIN


except ImportError:
    logging.critical("Не удалось импортировать функции из utils.py! Используются заглушки.")
    # Заглушки, если utils.py отсутствует или в нем ошибка
    def get_user_mention_html(user_id: int, full_name: Optional[str], username: Optional[str] = None) -> str:
        display_name = html.escape(full_name or f"User ID {user_id}")
        if username: return f'<a href="https://t.me/{html.escape(username)}">{display_name}</a>'
        return f'<a href="tg://user?id={user_id}">{display_name}</a>'
    async def send_telegram_log(bot_instance: Bot, message_text: str, include_timestamp: bool = True): # type: ignore
        logging.error(f"Функция send_telegram_log не доступна (заглушка). Сообщение: {message_text}")

from item_data import PHONE_CASES, CORE_PHONE_COMPONENT_TYPES
from families_logic import setup_families_handlers
from onecoin_logic import setup_onecoin_handlers
from competition_logic import setup_competition_handlers
from bonus_logic import setup_bonus_handlers
from roulette_logic import setup_roulette_handlers
from market_logic import setup_market_handlers # <<< ИМПОРТ ДЛЯ РЫНКА
from phone_logic import setup_phone_handlers, get_active_user_phone_bonuses 

PHONE_MODELS_MAIN = {phone_info["key"]: phone_info for phone_info in PHONE_MODELS_LIST_MAIN}
load_dotenv()
EXCLUSIVE_PHONE_MODELS_DICT = {p["key"]: p for p in EXCLUSIVE_PHONE_MODELS_LIST_FOR_MAIN}

logging.basicConfig(
    level=logging.INFO, # Общий уровень INFO
    format='%(asctime)s - %(levelname)s - %(name)s - %(filename)s:%(lineno)d - %(message)s'
)
logger = logging.getLogger(__name__)
logging.getLogger('apscheduler').setLevel(logging.DEBUG)

if not Config.BOT_TOKEN:
    logger.critical("BOT_TOKEN environment variable not set.")
    raise ValueError("BOT_TOKEN environment variable not set.")

bot = Bot(token=Config.BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
storage = MemoryStorage() # Для FSM
dp = Dispatcher(storage=storage)
scheduler = AsyncIOScheduler(timezone=Config.TIMEZONE if Config.TIMEZONE else "UTC")

# --- Словари для блокировок команд ---
user_command_locks: Dict[Tuple[int, int], asyncio.Lock] = {}
locks_dict_creation_lock = asyncio.Lock()


# --- Конец блокировок ---

# Вероятности для /oneui
try:
    from responses import POSITIVE_RESPONSES, NEGATIVE_RESPONSES, POS_MICRO_CHANGES, NEG_MICRO_CHANGES, ONEUI_COOLDOWN_RESPONSES, ONEUI_STREAK_INFO_DURING_COOLDOWN, ONEUI_STREAK_INFO_DURING_COOLDOWN
except ImportError:
    POSITIVE_RESPONSES = ["Отличные новости! Твоя версия OneUI увеличилась на %.1f!", "Поздравляю, обновление на %.1f установлено!"]
    NEGATIVE_RESPONSES = ["О нет! Произошел откат версии OneUI на %.1f.", "Кажется, что-то пошло не так. Версия уменьшилась на %.1f."]
    ONEUI_STREAK_INFO_DURING_COOLDOWN = ["🔥 Твой текущий стрик: <b>{streak_days}</b> д. (он не сбросится, если вернешься вовремя)."] # <-- Вот эта строка
    #POS_MICRO_CHANGES: List[float] = [0.1, 0.2, 0.3, 0.4, 0.5]
    #NEG_MICRO_CHANGES: List[float] = [-0.1, -0.2, -0.3, -0.4, -0.5]
    logging.warning("Файл responses.py не найден или не содержит нужные константы, используются значения по умолчанию.")


# === ЕЖЕДНЕВНЫЕ ЗАДАЧИ (из вашего предыдущего файла) ===
async def daily_competition_score_update():
    logger.info("Starting daily competition score update job.")
    try:
        active_comp = await database.get_active_family_competition()
        if not active_comp:
            logger.info("No active family competition. Skipping score update.")
            return
        competition_id = active_comp['competition_id']
        today_date_local = datetime.now(pytz_timezone(Config.TIMEZONE)).date()
        logger.info(f"Processing contributions for competition ID {competition_id} for date {today_date_local}")
        all_families = await database.get_all_families_with_active_members()
        if not all_families:
            logger.info("No families with active members found for competition scoring.")
            return
        conn = await database.get_connection()
        try:
            async with conn.transaction():
                for family_data in all_families:
                    family_id = family_data['family_id']
                    family_name = family_data['name']
                    for user_id_member in family_data['member_ids']:
                        max_version = await database.get_user_max_oneui_for_day_in_competition(user_id_member, today_date_local)
                        if max_version is not None and max_version > 0:
                            await database.record_family_daily_contribution(
                                competition_id, family_id, user_id_member, today_date_local, max_version, conn_ext=conn
                            )
                            logger.info(f"User {user_id_member} (Family '{family_name}') contributed {max_version:.1f} for competition {competition_id} on {today_date_local}")
                await database.calculate_and_set_family_competition_total_scores(competition_id, conn_ext=conn)
                logger.info(f"Total scores recalculated for competition ID {competition_id}")
        finally:
            if conn and not conn.is_closed():
                await conn.close()
    except Exception as e:
        logger.error(f"Error in daily_competition_score_update: {e}", exc_info=True)
        await send_telegram_log(bot, f"🔴 Ошибка в ежедневном обновлении очков соревнования:\n<pre>{html.escape(str(e))}</pre>")
    logger.info("Finished daily competition score update job.")

async def start_new_competition_after_delay(admin_id: int, delay_seconds: int):
    await asyncio.sleep(delay_seconds)
    logger.info(f"Попытка запуска нового соревнования после {delay_seconds} секунд ожидания.")
    try:
        active_comp_check = await database.get_active_family_competition()
        if active_comp_check:
            logger.info(f"Новое соревнование не будет запущено автоматически, так как уже есть активное: ID {active_comp_check['competition_id']}")
            return
        new_competition_id = await database.create_family_competition(admin_id, Config.COMPETITION_DURATION_DAYS)
        if new_competition_id:
            logger.info(f"Новое соревнование семей успешно запущено автоматически! ID: {new_competition_id}")
            comp_details_row = None
            conn_temp = await database.get_connection()
            try:
                 comp_details_row_raw = await conn_temp.fetchrow("SELECT * FROM family_competitions WHERE competition_id = $1", new_competition_id)
                 if comp_details_row_raw: comp_details_row = dict(comp_details_row_raw)
            finally:
                 if conn_temp and not conn_temp.is_closed(): await conn_temp.close()

            announcement_text = f"🏆 Запущено новое соревнование семей! ID: <code>{new_competition_id}</code>."
            if comp_details_row and comp_details_row.get('start_ts') and comp_details_row.get('end_ts'):
                start_ts_obj = comp_details_row['start_ts']
                end_ts_obj = comp_details_row['end_ts']
                start_ts_aware = start_ts_obj.replace(tzinfo=dt_timezone.utc) if start_ts_obj.tzinfo is None else start_ts_obj.astimezone(dt_timezone.utc)
                end_ts_aware = end_ts_obj.replace(tzinfo=dt_timezone.utc) if end_ts_obj.tzinfo is None else end_ts_obj.astimezone(dt_timezone.utc)
                start_local = start_ts_aware.astimezone(pytz_timezone(Config.TIMEZONE))
                end_local = end_ts_aware.astimezone(pytz_timezone(Config.TIMEZONE))
                announcement_text += (
                    f"\nНачало: {start_local.strftime('%Y-%m-%d %H:%M:%S %Z')}"
                    f"\nОкончание: {end_local.strftime('%Y-%m-%d %H:%M:%S %Z')}"
                )
            await send_telegram_log(bot, f"🚀 Автоматический запуск соревнования ID: {new_competition_id}. {announcement_text}")
        else:
            logger.error("Не удалось автоматически запустить новое соревнование после завершения предыдущего.")
            await send_telegram_log(bot, "🔴 Не удалось автоматически запустить новое соревнование.")
    except Exception as e:
        logger.error(f"Error in start_new_competition_after_delay: {e}", exc_info=True)
        await send_telegram_log(bot, f"🔴 Ошибка при попытке авто-запуска нового соревнования:\n<pre>{html.escape(str(e))}</pre>")

async def check_and_finalize_competitions():
    logger.info("Checking for competitions to finalize.")
    try:
        pending_competitions = await database.get_competitions_to_finalize()
        if not pending_competitions: return
        logger.info(f"Found {len(pending_competitions)} competitions to finalize.")
        should_schedule_new_competition = False
        for comp_data in pending_competitions:
            competition_id = comp_data['competition_id']
            logger.info(f"Finalizing competition ID {competition_id}...")
            await database.calculate_and_set_family_competition_total_scores(competition_id)
            leaderboard = await database.get_competition_leaderboard(competition_id, limit=1)
            winner_family_id = None
            winner_family_name = "нет"
            if leaderboard and leaderboard[0]['total_score'] > 0:
                winner_entry = leaderboard[0]
                winner_family_id = winner_entry['family_id']
                winner_family_name = html.escape(winner_entry['family_name'])
                logger.info(f"Competition {competition_id} winner is family '{winner_family_name}' (ID: {winner_family_id}) with score {winner_entry['total_score']:.1f}")
                winner_members_data = await database.get_family_members(winner_family_id) if winner_family_id else []
                if winner_members_data:
                    logger.info(f"Awarding {len(winner_members_data)} members of family '{winner_family_name}'.")
                    conn_reward = await database.get_connection()
                    try:
                        async with conn_reward.transaction():
                            for member in winner_members_data:
                                user_id_member = member['user_id']
                                current_user_data = await database.get_user_data_for_update(user_id_member, Config.ADMIN_ID, conn_ext=conn_reward) # Chat_id заглушка
                                final_full_name_for_reward = current_user_data.get('full_name') or member.get('full_name_when_joined') or f"User ID {user_id_member}"
                                final_username_for_reward = current_user_data.get('username') or member.get('username')
                                user_chat_records = await database.get_user_chat_records(user_id_member, conn_ext=conn_reward)
                                reward_chat_id_to_use: Optional[int] = user_id_member
                                if user_chat_records:
                                    user_chat_records.sort(key=lambda x: x.get('last_used', datetime.min.replace(tzinfo=dt_timezone.utc)), reverse=True)
                                    reward_chat_id_to_use = user_chat_records[0]['chat_id']
                                else:
                                     logger.warning(f"User {user_id_member} has no chat records. Awarding to private chat ID {reward_chat_id_to_use}.")

                                current_user_version = await database.get_user_version(user_id_member, reward_chat_id_to_use)
                                new_version = current_user_version + Config.COMPETITION_WINNER_VERSION_BONUS
                                await database.update_user_version(
                                    user_id_member, reward_chat_id_to_use, new_version,
                                    username=final_username_for_reward, full_name=final_full_name_for_reward,
                                    chat_title=f"Награда за соревнование {competition_id}", conn_ext=conn_reward
                                )
                                await database.update_user_onecoins(
                                    user_id_member, reward_chat_id_to_use, Config.COMPETITION_WINNER_ONECOIN_BONUS,
                                    username=final_username_for_reward, full_name=final_full_name_for_reward,
                                    chat_title=f"Награда за соревнование {competition_id}", conn_ext=conn_reward
                                )
                                logger.info(f"Rewarded user {user_id_member} (Family '{winner_family_name}') with {Config.COMPETITION_WINNER_VERSION_BONUS:.1f}V and {Config.COMPETITION_WINNER_ONECOIN_BONUS}C in chat {reward_chat_id_to_use}.")
                    except Exception as e_reward:
                        logger.error(f"Error during reward transaction for comp {competition_id}, family {winner_family_id}: {e_reward}", exc_info=True)
                    finally:
                        if conn_reward and not conn_reward.is_closed(): await conn_reward.close()
                else:
                    logger.warning(f"Competition {competition_id} winner family '{winner_family_name}' (ID: {winner_family_id}) has no members.")
            else:
                logger.info(f"Competition {competition_id} finished with no clear winner.")

            await database.set_competition_winner_and_finish_status(competition_id, winner_family_id)
            await database.mark_competition_rewards_distributed(competition_id)
            comp_end_ts = comp_data.get('end_ts')
            comp_end_local_str = comp_end_ts.astimezone(pytz_timezone(Config.TIMEZONE)).strftime('%Y-%m-%d %H:%M:%S %Z') if comp_end_ts and isinstance(comp_end_ts, datetime) else "неизвестно"
            announcement_message = f"🏁 Соревнование ID <code>{competition_id}</code> завершено {comp_end_local_str}!\n"
            announcement_message += f"🎉 Победила семья <b>{winner_family_name}</b>!" if winner_family_id else "Победитель не определен."
            await send_telegram_log(bot, announcement_message)
            should_schedule_new_competition = True
        if should_schedule_new_competition:
            active_comp_after_finalize = await database.get_active_family_competition()
            if not active_comp_after_finalize:
                logger.info(f"Планируется запуск нового соревнования через {Config.COMPETITION_RESTART_DELAY_SECONDS} сек. ADMIN_ID: {Config.ADMIN_ID}")
                asyncio.create_task(start_new_competition_after_delay(Config.ADMIN_ID, Config.COMPETITION_RESTART_DELAY_SECONDS))
            else:
                logger.info(f"Новое соревнование не будет запланировано, есть активное ID: {active_comp_after_finalize['competition_id']}.")
    except Exception as e_main_check:
        logger.error(f"Critical error in check_and_finalize_competitions: {e_main_check}", exc_info=True)
        await send_telegram_log(bot, f"🔴 Ошибка при завершении соревнований:\n<pre>{html.escape(str(e_main_check))}</pre>")
        
async def scheduled_check_expired_phone_prizes(bot_instance: Bot):
    """
    Периодическая задача для проверки просроченных выигранных телефонов, ожидающих решения.
    Автоматически продает их боту.
    """
    logger.info("SCHEDULER: Запуск проверки просроченных выигранных телефонов...")
    expiry_time_td = timedelta(seconds=getattr(Config, "MARKET_PHONE_CONFIRMATION_TIMEOUT_SECONDS", 60)) # Тот же таймаут

    conn = None
    try:
        conn = await database.get_connection() # Получаем соединение для транзакции
        expired_prizes = await database.get_expired_pending_phone_prizes(expiry_time_td, conn_ext=conn)

        if not expired_prizes:
            logger.info("SCHEDULER (Expired Prizes): Нет просроченных призов для обработки.")
            return

        logger.info(f"SCHEDULER (Expired Prizes): Найдено {len(expired_prizes)} просроченных призов.")

        async with conn.transaction(): # Оборачиваем обработку всех просроченных призов в одну транзакцию
            for prize_data in expired_prizes:
                user_id = prize_data['user_id']
                logger.info(f"SCHEDULER (Expired Prizes): Обработка просроченного приза для user {user_id}.")
                # Вызываем функцию автоматической продажи внутри транзакции
                try:
                    await _auto_sell_expired_prize(user_id, bot_instance, conn_ext=conn)
                except Exception as e_auto_sell:
                    logger.error(f"SCHEDULER (Expired Prizes): Ошибка при автопродаже приза для user {user_id}: {e_auto_sell}", exc_info=True)
                    # Логируем ошибку, но продолжаем обработку других призов в рамках той же транзакции


        logger.info(f"SCHEDULER (Expired Prizes): Завершено обработка просроченных призов.")

    except Exception as e_main_scheduler:
        logger.error(f"SCHEDULER (Expired Prizes): Критическая ошибка в задаче проверки просроченных призов: {e_main_scheduler}", exc_info=True)
        await send_telegram_log(bot_instance, f"🔴 SCHEDULER: Критическая ошибка в проверке просроченных призов:\n<pre>{html.escape(str(e_main_scheduler))}</pre>")
    finally:
        if conn and not conn.is_closed():
            await conn.close()        
        

async def global_roulette_period_reset_task():
    """Сбрасывает глобальный период доступности рулетки."""
    current_time_utc = datetime.now(dt_timezone.utc)
    setting_key_roulette_reset = 'last_global_roulette_period_reset' # Ключ для system_settings

    await database.set_setting_timestamp(setting_key_roulette_reset, current_time_utc)

    local_tz = pytz_timezone(Config.TIMEZONE)
    current_time_local_str = current_time_utc.astimezone(local_tz).strftime('%Y-%m-%d %H:%M:%S %Z')
    logger.info(f"Global roulette usage period reset at {current_time_local_str}.")
    # Используем первый алиас из конфига для команды рулетки в логе
    roulette_cmd_alias = Config.ROULETTE_COMMAND_ALIASES[0] if Config.ROULETTE_COMMAND_ALIASES else 'roulette'
    await send_telegram_log(bot,
        f"🔄 Период для бесплатного использования команды "
        f"<code>/{roulette_cmd_alias}</code> "
        f"глобально обновлен ({current_time_local_str})."
    )

async def global_bonus_multiplier_reset_task():
    current_time_utc = datetime.now(dt_timezone.utc)
    local_tz = pytz_timezone(Config.TIMEZONE)
    await database.set_setting_timestamp('last_global_bonus_multiplier_reset', current_time_utc)
    current_time_local_str = current_time_utc.astimezone(local_tz).strftime('%Y-%m-%d %H:%M:%S %Z')
    logger.info(f"Global bonus multiplier claim period reset at {current_time_local_str}.")
    await send_telegram_log(bot, f"🔄 Период для /bonus обновлен для всех ({current_time_local_str}).")

async def daily_reset_roulette_attempts():
    logger.info("Запуск ежедневного сброса доп. попыток от рулетки (для /bonus, /oneui).")
    conn = None
    try:
        conn = await database.get_connection()
        result = await conn.execute(
            "UPDATE roulette_status SET extra_bonus_attempts = 0, extra_oneui_attempts = 0 "
            "WHERE extra_bonus_attempts > 0 OR extra_oneui_attempts > 0"
        )
        if result and "UPDATE 0" not in result.upper():
            logger.info(f"Ежедневный сброс доп. попыток рулетки (для /bonus, /oneui) выполнен. Затронуто: {result}")
            await send_telegram_log(bot, "🔄 Ежедневный сброс доп. попыток от рулетки (/bonus, /oneui) выполнен.")
        else:
            logger.info("Ежедневный сброс доп. попыток рулетки: не найдено попыток для сброса.")
    except Exception as e:
        logger.error(f"Ошибка в daily_reset_roulette_attempts: {e}", exc_info=True)
        await send_telegram_log(bot, f"🔴 Ошибка при сбросе доп. попыток рулетки: <pre>{html.escape(str(e))}</pre>")
    finally:
        if conn and not conn.is_closed(): await conn.close()
    logger.debug("Завершение задачи сброса доп. попыток от рулетки.")
# === Конец ежедневных задач ===

async def scheduled_check_phone_breakdowns(bot_instance: Bot): # Замени Bot на актуальный тип твоего бота
    """
    Еженедельная проверка на случайные поломки телефонов с учетом
    контрабанды, кастомных факторов и неуязвимости компонентов.
    """
    logger.info("SCHEDULER: Запуск еженедельной проверки поломок телефонов.")
    try:
        # Получаем все телефоны, которые не проданы и не сломаны (is_sold=False, is_broken=False)
        operational_phones = await database.get_all_operational_phones() 
        if not operational_phones:
            logger.info("SCHEDULER (Breakdowns): Нет операционных телефонов для проверки.")
            return

        phones_broken_count = 0
        for phone_data in operational_phones:
            phone_id = phone_data['phone_inventory_id']
            user_id_owner = phone_data['user_id']
            phone_model_key = phone_data.get('phone_model_key')
            
            # --- ПОЛУЧАЕМ ФЛАГ КОНТРАБАНДЫ И ДОПОЛНИТЕЛЬНЫЕ ДАННЫЕ ---
            is_contraband_phone = phone_data.get('is_contraband', False)
            # phone_custom_data это JSONB поле из таблицы user_phones, может содержать различные кастомные атрибуты
            phone_custom_data = phone_data.get('data', {}) 
            # --- КОНЕЦ ПОЛУЧЕНИЯ ФЛАГА И ДАННЫХ ---

            if not phone_model_key:
                logger.warning(f"SCHEDULER (Breakdowns): У телефона ID {phone_id} отсутствует phone_model_key. Пропуск.")
                continue

            # --- ПОЛУЧЕНИЕ СТАТИЧЕСКОЙ ИНФОРМАЦИИ О МОДЕЛИ ТЕЛЕФОНА ---
            phone_static_info = PHONE_MODELS_MAIN.get(phone_model_key)
            # Если телефон не найден в основном словаре, ищем в словаре эксклюзивных моделей
            if not phone_static_info and phone_model_key in EXCLUSIVE_PHONE_MODELS_DICT:
                phone_static_info = EXCLUSIVE_PHONE_MODELS_DICT.get(phone_model_key)

            # Определяем имя телефона для сообщений и логов
            phone_name_for_msg = phone_static_info.get('name', f"Телефон (ключ: {phone_model_key})") if phone_static_info else f"Телефон (ключ: {phone_model_key})"
            # --- КОНЕЦ ПОЛУЧЕНИЯ СТАТИЧЕСКОЙ ИНФОРМАЦИИ ---

            # --- РАСЧЕТ ШАНСА ПОЛОМКИ ---
            # 1. Базовый шанс (случайное значение в заданном диапазоне)
            base_break_chance = random.randint(5, 20) # Например, от 5% до 20%
            original_base_chance_for_log = base_break_chance # Сохраняем для логирования

            # 2. Модификаторы шанса (контрабанда, кастомные факторы)
            final_chance_multiplier = 1.0 # Начальный множитель
            log_breakdown_factors = [] # Список для логирования примененных факторов

            # а) Учет контрабанды
            if is_contraband_phone:
                # CONTRABAND_BREAK_CHANCE_MULTIPLIER должен быть определен в Config, например, 1.5 для увеличения шанса на 50%
                contraband_mult = getattr(Config, "CONTRABAND_BREAK_CHANCE_MULTIPLIER", 1.5) 
                final_chance_multiplier *= contraband_mult
                log_breakdown_factors.append(f"контрабанда x{contraband_mult:.1f}")

            # б) Учет "increased_break_chance_factor" из кастомных данных телефона (например, для краденых или особых эксклюзивов)
            # Этот фактор УВЕЛИЧИВАЕТ шанс поломки.
            if phone_custom_data and isinstance(phone_custom_data.get("increased_break_chance_factor"), (int, float)):
                custom_mult = float(phone_custom_data["increased_break_chance_factor"])
                if custom_mult > 0: # Применяем, только если множитель положительный (обычно > 1.0 для увеличения)
                    final_chance_multiplier *= custom_mult
                    log_breakdown_factors.append(f"особый x{custom_mult:.1f}")
            
            # в) Учет "intrinsic_wear_resistance_factor" из кастомных данных (например, для прочных эксклюзивов)
            # Этот фактор ИЗМЕНЯЕТ (обычно уменьшает, если < 1.0) итоговый шанс.
            if phone_custom_data and isinstance(phone_custom_data.get("intrinsic_wear_resistance_factor"), (int, float)):
                resistance_mult = float(phone_custom_data["intrinsic_wear_resistance_factor"])
                if resistance_mult > 0: # Множитель должен быть положительным
                                        # Если resistance_mult < 1.0, шанс УМЕНЬШИТСЯ (телефон прочнее)
                                        # Если resistance_mult > 1.0, шанс УВЕЛИЧИТСЯ (телефон хрупче по этому параметру)
                    final_chance_multiplier *= resistance_mult 
                    log_breakdown_factors.append(f"сопротивление x{resistance_mult:.2f}")
            
            # Применяем рассчитанный общий множитель к базовому шансу
            if final_chance_multiplier != 1.0:
                base_break_chance = int(round(base_break_chance * final_chance_multiplier))
                logger.debug(f"Phone ID {phone_id} (model: {phone_model_key}). BaseBreak: {original_base_chance_for_log}% -> ModifiedBase: {base_break_chance}% (Factors: {', '.join(log_breakdown_factors)})")
            
            # 3. Уменьшение шанса поломки за счет чехла
            break_reduction_percent = 0 # Процент, на который чехол уменьшает шанс поломки
            equipped_case_key = phone_data.get('equipped_case_key')
            if equipped_case_key and equipped_case_key in PHONE_CASES:
                break_reduction_percent = PHONE_CASES[equipped_case_key].get('break_chance_reduction_percent', 0)

            # Итоговый шанс поломки после всех модификаций и чехла
            # Важно: base_break_chance здесь уже может быть модифицирован множителями
            final_break_chance = base_break_chance - break_reduction_percent
            
            # Шанс не может быть отрицательным
            if final_break_chance < 0: 
                final_break_chance = 0
            
            # Минимальный активный шанс поломки (если шанс вообще есть, он не должен быть слишком мал)
            min_active_break_chance = 1 # Например, если шанс поломки > 0, он не может быть меньше 1%
            if final_break_chance > 0 and final_break_chance < min_active_break_chance:
                final_break_chance = min_active_break_chance

            logger.debug(f"Phone ID {phone_id}: FinalBreakChance={final_break_chance}% (InitialBase: {original_base_chance_for_log}%, MultipliedBase: {base_break_chance}%, CaseReduction: {break_reduction_percent}%)")
            # --- КОНЕЦ РАСЧЕТА ШАНСА ПОЛОМКИ ---

            # --- ПРОВЕРКА НА ПОЛОМКУ И ОБРАБОТКА ---
            # "Бросаем кубик": если случайное число от 1 до 100 меньше или равно итоговому шансу, телефон ломается
            if final_break_chance > 0 and random.randint(1, 100) <= final_break_chance:
                
                # а) Проверка на неуязвимость компонентов для эксклюзивов
                # Если у телефона в data есть флаг "components_are_indestructible_standard_wear": true,
                # то стандартная поломка компонента не происходит.
                if phone_custom_data and phone_custom_data.get("components_are_indestructible_standard_wear") is True:
                    logger.info(f"Phone ID {phone_id} (модель: {phone_model_key}) имеет неуязвимые компоненты от стандартного износа. Пропуск стандартной поломки.")
                    continue # Переходим к следующему телефону

                # б) Определение компонента для поломки
                if not CORE_PHONE_COMPONENT_TYPES:
                    logger.error("SCHEDULER (Breakdowns): CORE_PHONE_COMPONENT_TYPES пуст. Невозможно определить компонент для поломки.")
                    continue

                # Определяем серию компонентов, которые будут ломаться (A, S, Z или дефолтная A для других)
                phone_series_for_component = "A" # Дефолтная серия
                if phone_static_info and phone_static_info.get('series') in ['A', 'S', 'Z']:
                    phone_series_for_component = phone_static_info.get('series')
                elif phone_static_info and phone_static_info.get('series') not in ['A', 'S', 'Z']:
                    # Для эксклюзивных серий (X, L и т.д.) пока используем компоненты A-серии.
                    # В будущем можно будет это кастомизировать.
                    logger.warning(f"SCHEDULER (Breakdowns): Эксклюзивный телефон {phone_model_key} (серия: {phone_static_info.get('series')}) использует компоненты A-серии для поломки по умолчанию.")
                
                # Формируем список возможных ключей компонентов для поломки
                possible_broken_component_keys = [
                    f"{comp_type.upper()}_{phone_series_for_component}" for comp_type in CORE_PHONE_COMPONENT_TYPES
                ]
                chosen_component_key_to_break = random.choice(possible_broken_component_keys)

                if chosen_component_key_to_break not in PHONE_COMPONENTS:
                    logger.error(f"SCHEDULER (Breakdowns): Сгенерированный ключ компонента '{chosen_component_key_to_break}' не найден в PHONE_COMPONENTS. Поломка не записана для телефона ID {phone_id}.")
                    continue

                # в) Обновление статуса телефона в базе данных
                update_success = await database.update_phone_status_fields(
                    phone_id,
                    {'is_broken': True, 'broken_component_key': chosen_component_key_to_break}
                )
                
                # г) Уведомление пользователя
                if update_success:
                    phones_broken_count += 1
                    logger.info(f"SCHEDULER (Breakdowns): Телефон ID {phone_id} (владелец: {user_id_owner}, модель: {phone_name_for_msg}) сломался! Компонент: {chosen_component_key_to_break}")
                    try:
                        # Получаем информацию о пользователе для более персонализированного сообщения
                        user_info_for_log = await database.get_user_data_for_update(user_id_owner, phone_data.get('chat_id_acquired_in', user_id_owner))
                        owner_full_name = user_info_for_log.get('full_name') if user_info_for_log else f"Владелец ID {user_id_owner}"
                        # owner_username = user_info_for_log.get('username') if user_info_for_log else None
                        # user_mention_owner = get_user_mention_html(user_id_owner, owner_full_name, owner_username) # Если нужно будет тегать
                        
                        broken_comp_name_msg = PHONE_COMPONENTS[chosen_component_key_to_break].get('name', chosen_component_key_to_break)
                        
                        # Формируем сообщение о поломке
                        breakdown_message = (
                            f"🔧 Ой! Ваш телефон \"<b>{html.escape(phone_name_for_msg)}</b>\" (ID: {phone_id}) сломался! "
                            f"Поврежденный компонент: <b>{html.escape(broken_comp_name_msg)}</b>.\n"
                        )
                        # Добавляем информацию о контрабанде, если применимо
                        if is_contraband_phone:
                            breakdown_message += "<i>(🥷 Контрабандный товар, повышенный риск поломки!)</i>\n"
                        
                        # Добавляем информацию об особой хрупкости, если есть фактор и он не связан с контрабандой (чтобы не дублировать смысл)
                        if phone_custom_data and isinstance(phone_custom_data.get("increased_break_chance_factor"), (int, float)):
                            custom_factor_val = phone_custom_data["increased_break_chance_factor"]
                            # Сообщение об "особенно хрупком" добавляем, если есть фактор > 1 и телефон НЕ контрабандный
                            if custom_factor_val > 1.0 and not is_contraband_phone: 
                                breakdown_message += "<i>(Этот телефон оказался особенно хрупким!)</i>\n"
                            # Если телефон и контрабандный, и имеет этот фактор, сообщение о контрабанде уже есть.
                            # Можно добавить еще одно, например "Особо рискованная контрабанда!", но пока пропущено (pass в исходной идее)
                            # elif custom_factor_val > 1.0 and is_contraband_phone:
                            #     pass 

                        breakdown_message += "Вы можете починить его с помощью команды /repairphone."

                        await bot_instance.send_message(user_id_owner, breakdown_message, parse_mode="HTML")
                    except Exception as e_notify:
                        logger.warning(f"SCHEDULER (Breakdowns): Не удалось уведомить пользователя {user_id_owner} о поломке телефона ID {phone_id}: {e_notify}")
                else:
                    logger.error(f"SCHEDULER (Breakdowns): Не удалось обновить статус поломки для телефона ID {phone_id} в БД.")
            # --- КОНЕЦ ПРОВЕРКИ НА ПОЛОМКУ И ОБРАБОТКИ ---

        logger.info(f"SCHEDULER: Еженедельная проверка поломок завершена. Сломано телефонов: {phones_broken_count}.")
        if phones_broken_count > 0:
            await send_telegram_log(bot_instance, f"⚙️ Еженедельная 'раздача поломок': {phones_broken_count} телефонов сломалось.")

    except Exception as e:
        logger.error(f"SCHEDULER (Breakdowns): Критическая ошибка: {e}", exc_info=True)
        await send_telegram_log(bot_instance, f"🔴 SCHEDULER: Критическая ошибка в еженедельной проверке поломок телефонов:\n<pre>{html.escape(str(e))}</pre>")

async def scheduled_check_phone_battery_status(bot_instance: Bot):
    """
    Ежедневная проверка состояния аккумуляторов телефонов.
    """
    logger.info("SCHEDULER: Запуск ежедневной проверки состояния аккумуляторов.")
    try:
        phones_to_check = await database.get_phones_for_battery_check()
        if not phones_to_check:
            logger.info("SCHEDULER (Battery): Нет телефонов для проверки аккумуляторов.")
            return

        batteries_broken_count = 0
        now_utc = datetime.now(dt_timezone.utc)

        for phone_data in phones_to_check:
            phone_id = phone_data['phone_inventory_id']
            user_id_owner = phone_data['user_id']
            battery_break_after_utc_val = phone_data.get('battery_break_after_utc')
            phone_model_key = phone_data.get('phone_model_key')

            if not battery_break_after_utc_val or not phone_model_key:
                logger.warning(f"SCHEDULER (Battery): Пропуск телефона ID {phone_id} из-за отсутствия battery_break_after_utc или phone_model_key.")
                continue

            phone_static_info = PHONE_MODELS_MAIN.get(phone_model_key) # Используем PHONE_MODELS_MAIN
            phone_name_for_msg = phone_static_info.get('name', f"Телефон (ключ: {phone_model_key})") if phone_static_info else f"Телефон (ключ: {phone_model_key})"

            battery_break_after_utc_dt: Optional[datetime] = None
            if isinstance(battery_break_after_utc_val, str):
                try: battery_break_after_utc_dt = datetime.fromisoformat(battery_break_after_utc_val)
                except ValueError: pass
            elif isinstance(battery_break_after_utc_val, datetime):
                battery_break_after_utc_dt = battery_break_after_utc_val

            if not battery_break_after_utc_dt:
                 logger.warning(f"SCHEDULER (Battery): Некорректный формат battery_break_after_utc для телефона ID {phone_id}. Пропуск.")
                 continue

            if battery_break_after_utc_dt.tzinfo is None:
                battery_break_after_utc_dt = battery_break_after_utc_dt.replace(tzinfo=dt_timezone.utc)
            else:
                battery_break_after_utc_dt = battery_break_after_utc_dt.astimezone(dt_timezone.utc)

            if now_utc >= battery_break_after_utc_dt:
                phone_series = phone_static_info.get('series', 'A') if phone_static_info else 'A'
                if phone_series not in ['A', 'S', 'Z']: phone_series = 'A'

                battery_component_key_to_break = f"BATTERY_{phone_series}"

                if battery_component_key_to_break not in PHONE_COMPONENTS: # PHONE_COMPONENTS импортирован из item_data
                    logger.error(f"SCHEDULER (Battery): Ключ батареи '{battery_component_key_to_break}' не найден в PHONE_COMPONENTS для телефона ID {phone_id}. Поломка не записана.")
                    continue

                update_success = await database.update_phone_status_fields(
                    phone_id,
                    {'is_broken': True, 'broken_component_key': battery_component_key_to_break}
                )
                if update_success:
                    batteries_broken_count += 1
                    logger.info(f"SCHEDULER (Battery): Аккумулятор телефона ID {phone_id} (владелец: {user_id_owner}, модель: {phone_name_for_msg}) окончательно сломался (компонент: {battery_component_key_to_break}).")
                    try:
                        user_info_for_log_batt = await database.get_user_data_for_update(user_id_owner, phone_data.get('chat_id_acquired_in', user_id_owner))
                        owner_full_name_batt = user_info_for_log_batt.get('full_name') if user_info_for_log_batt else f"Владелец ID {user_id_owner}"
                        owner_username_batt = user_info_for_log_batt.get('username') if user_info_for_log_batt else None
                        user_mention_owner = get_user_mention_html(user_id_owner, owner_full_name_batt, owner_username_batt)
                        broken_comp_name_msg = PHONE_COMPONENTS[battery_component_key_to_break].get('name', battery_component_key_to_break)
                        await bot_instance.send_message(
                            user_id_owner,
                            f"🔋‼️ Ваш телефон \"<b>{html.escape(phone_name_for_msg)}</b>\" (ID: {phone_id}) не был заряжен вовремя, "
                            f"и его аккумулятор (<b>{html.escape(broken_comp_name_msg)}</b>) окончательно вышел из строя!\n"
                            f"Теперь его нужно чинить (/repairphone).",
                            parse_mode="HTML"
                        )
                    except Exception as e_notify_battery:
                        logger.warning(f"SCHEDULER (Battery): Не удалось уведомить пользователя {user_id_owner} о поломке аккумулятора телефона ID {phone_id}: {e_notify_battery}")
                else:
                    logger.error(f"SCHEDULER (Battery): Не удалось обновить статус поломки аккумулятора для телефона ID {phone_id} в БД.")

        logger.info(f"SCHEDULER: Ежедневная проверка аккумуляторов завершена. Сломано аккумуляторов: {batteries_broken_count}.")
        if batteries_broken_count > 0:
            await send_telegram_log(bot_instance, f"🔋 Ежедневная проверка батарей: {batteries_broken_count} аккумуляторов сломалось из-за отсутствия зарядки.")

    except Exception as e:
        logger.error(f"SCHEDULER (Battery): Критическая ошибка: {e}", exc_info=True)
        await send_telegram_log(bot_instance, f"🔴 SCHEDULER: Критическая ошибка в ежедневной проверке аккумуляторов:\n<pre>{html.escape(str(e))}</pre>")

async def scheduled_remind_insurance_expiry(bot_instance: Bot):
    """
    Ежедневная задача для напоминания об истечении страховки.
    """
    logger.info("SCHEDULER: Запуск проверки истекающих страховок.")
    days_to_remind_before = getattr(Config, "PHONE_INSURANCE_REMIND_DAYS_BEFORE", 3)

    try:
        expiring_phones = await database.get_phones_with_expiring_insurance(days_before_expiry=days_to_remind_before)

        if not expiring_phones:
            logger.info("SCHEDULER (Insurance): Нет телефонов с истекающей страховкой для напоминания.")
            return

        reminders_sent_count = 0
        now_utc_aware = datetime.now(dt_timezone.utc)

        for phone_data in expiring_phones:
            phone_id = phone_data['phone_inventory_id']
            user_id_owner = phone_data['user_id']
            insurance_until_utc_val = phone_data.get('insurance_active_until')
            phone_model_key = phone_data.get('phone_model_key')

            if not insurance_until_utc_val or not phone_model_key:
                logger.warning(f"SCHEDULER (Insurance): Пропуск телефона ID {phone_id} (владелец {user_id_owner}) из-за отсутствия insurance_active_until или phone_model_key.")
                continue

            phone_static_info = PHONE_MODELS_MAIN.get(phone_model_key) # Используем PHONE_MODELS_MAIN
            phone_name_for_msg = phone_static_info.get('name', f"Телефон (ключ: {phone_model_key})") if phone_static_info else f"Телефон (ключ: {phone_model_key})"

            insurance_until_utc_dt: Optional[datetime] = None
            if isinstance(insurance_until_utc_val, str):
                try: insurance_until_utc_dt = datetime.fromisoformat(insurance_until_utc_val)
                except ValueError: pass
            elif isinstance(insurance_until_utc_val, datetime):
                insurance_until_utc_dt = insurance_until_utc_val

            if not insurance_until_utc_dt:
                 logger.warning(f"SCHEDULER (Insurance): Некорректный формат insurance_active_until для телефона ID {phone_id}. Пропуск.")
                 continue

            if insurance_until_utc_dt.tzinfo is None:
                insurance_until_utc_dt = insurance_until_utc_dt.replace(tzinfo=dt_timezone.utc)
            else:
                insurance_until_utc_dt = insurance_until_utc_dt.astimezone(dt_timezone.utc)

            expiry_date_local_str = insurance_until_utc_dt.astimezone(pytz_timezone(Config.TIMEZONE)).strftime('%Y-%m-%d')
            reminder_message_text = ""

            if insurance_until_utc_dt < now_utc_aware:
                reminder_message_text = (
                    f"🔔 Внимание! Страховка для вашего телефона \"<b>{html.escape(phone_name_for_msg)}</b>\" "
                    f"(ID: {phone_id}) истекла {expiry_date_local_str}.\n"
                    f"Чтобы снова застраховать его, используйте команду /insurephone."
                )
            else:
                time_left_to_expiry = insurance_until_utc_dt - now_utc_aware
                days_left = time_left_to_expiry.days

                days_str = "дней" # По умолчанию
                if days_left == 0: days_str = "сегодня"
                elif days_left == 1: days_str = "день"
                elif days_left % 10 == 1 and days_left % 100 != 11: days_str = "день" # 1, 21, 31...
                elif 2 <= days_left % 10 <= 4 and (days_left % 100 < 10 or days_left % 100 >= 20): days_str = "дня" # 2-4, 22-24...
                else: days_str = "дней" # 0, 5-20, 25-30...

                reminder_message_text = (
                    f"🔔 Напоминание! Страховка для вашего телефона \"<b>{html.escape(phone_name_for_msg)}</b>\" "
                    f"(ID: {phone_id}) истекает {expiry_date_local_str} (примерно через {days_left} {days_str}).\n"
                    f"Вы можете продлить ее с помощью команды /insurephone."
                )

            try:
                await bot_instance.send_message(user_id_owner, reminder_message_text, parse_mode="HTML")
                reminders_sent_count += 1
                logger.info(f"SCHEDULER (Insurance): Отправлено напоминание пользователю {user_id_owner} для телефона ID {phone_id}.")
            except Exception as e_notify_ins:
                logger.warning(f"SCHEDULER (Insurance): Не удалось отправить напоминание пользователю {user_id_owner} для телефона ID {phone_id}: {e_notify_ins}")

        logger.info(f"SCHEDULER (Insurance): Проверка истекающих страховок завершена. Отправлено напоминаний: {reminders_sent_count}.")
        if reminders_sent_count > 0:
             await send_telegram_log(bot_instance, f"📄 Проверка страховок: {reminders_sent_count} напоминаний об истечении отправлено.")

    except Exception as e:
        logger.error(f"SCHEDULER (Insurance): Критическая ошибка: {e}", exc_info=True)
        await send_telegram_log(bot_instance, f"🔴 SCHEDULER: Критическая ошибка в проверке истекающих страховок:\n<pre>{html.escape(str(e))}</pre>")

async def scheduled_apply_inflation(bot_instance: Bot):
    """
    Периодическая задача для применения инфляции к ценам в магазинах.
    Увеличивает множитель инфляции в базе данных.
    """
    logger.info("SCHEDULER: Запуск планового применения инфляции...")
    conn = None # Объявляем conn здесь, чтобы он был доступен в finally
    try:
        conn = await database.get_connection() # Получаем новое соединение
        current_multiplier = await database.get_setting_float(
            Config.INFLATION_SETTING_KEY,
            Config.DEFAULT_INFLATION_MULTIPLIER, # Значение по умолчанию, если в БД нет
            conn_ext=conn # Передаем соединение
        )

        if current_multiplier is None: # Если даже дефолт не сработал (например, ошибка БД при чтении)
            # Это не должно происходить, если init_db отработал корректно
            # и get_setting_float возвращает default_value при отсутствии ключа.
            # Эта проверка скорее на случай, если get_setting_float вернул None из-за ошибки БД.
            logger.error("SCHEDULER (Inflation): Не удалось получить текущий множитель инфляции из БД. Инфляция не применена.")
            if conn and not conn.is_closed(): await conn.close()
            return

        new_multiplier = current_multiplier + Config.INFLATION_INCREASE_RATE
        # Округляем, чтобы избежать накопления ошибок с float и для консистентности
        new_multiplier = round(new_multiplier, 4) # Округление до 4 знаков после запятой

        await database.set_setting_float(Config.INFLATION_SETTING_KEY, new_multiplier, conn_ext=conn)

        logger.info(f"SCHEDULER (Inflation): Инфляция применена. Старый множитель: {current_multiplier:.4f}, новый множитель: {new_multiplier:.4f}")

        # Формируем сообщение для лога в Telegram
        # Используем .2f для отображения пользователю (2 знака после запятой)
        # Используем .0f для отображения процента инфляции как целого числа
        await send_telegram_log(
            bot_instance,
            f"📈 Внимание! Произошла плановая инфляция в магазинах!\n"
            f"Текущий модификатор цен обновлен и теперь составляет: <b>x{new_multiplier:.2f}</b> "
            f"(предыдущий: x{current_multiplier:.2f}, увеличение на {Config.INFLATION_INCREASE_RATE*100:.0f}%)."
        )

    except Exception as e:
        logger.error(f"SCHEDULER (Inflation): Критическая ошибка при применении инфляции: {e}", exc_info=True)
        await send_telegram_log(bot_instance, f"🔴 SCHEDULER: Критическая ошибка при применении инфляции:\n<pre>{html.escape(str(e))}</pre>")
    finally:
        if conn and not conn.is_closed(): # Закрываем соединение, если оно было открыто
            await conn.close()

# === КОНЕЦ НОВЫХ ФУНКЦИЙ ДЛЯ ШЕДУЛЕРА ===

async def on_startup(dispatcher: Dispatcher):
    logger.info("Starting bot startup sequence...")
    await init_db()
    logger.info("Database initialized.")

    # Инициализация для бонуса (это у тебя уже есть, оставляем)
    bonus_reset_key = 'last_global_bonus_multiplier_reset'
    if not await database.get_setting_timestamp(bonus_reset_key):
        logger.info(f"Setting initial '{bonus_reset_key}'.")
        try:
            local_tz_startup = pytz_timezone(Config.TIMEZONE)
            initial_reset_time_local_bonus = datetime.now(local_tz_startup).replace(
                hour=Config.BONUS_MULTIPLIER_RESET_HOUR, minute=2, second=0, microsecond=0
            )
            # Отнимаем количество дней большее, чем кулдаун, для гарантии доступности при первом запуске
            initial_reset_time_local_bonus -= timedelta(days=Config.BONUS_MULTIPLIER_COOLDOWN_DAYS + 1)
            await database.set_setting_timestamp(bonus_reset_key, initial_reset_time_local_bonus.astimezone(dt_timezone.utc))
            logger.info(f"Initial '{bonus_reset_key}' set to: {initial_reset_time_local_bonus.isoformat()} {Config.TIMEZONE}")
        except Exception as e_init_reset_bonus: # Изменил имя переменной для избежания конфликта
            logger.error(f"Failed to set initial '{bonus_reset_key}': {e_init_reset_bonus}", exc_info=True)

    # >>>>> ДОБАВИТЬ: Инициализация времени сброса периода рулетки <<<<<
    roulette_reset_key = 'last_global_roulette_period_reset'
    if not await database.get_setting_timestamp(roulette_reset_key):
        logger.info(f"Setting initial '{roulette_reset_key}' as it was not found in DB.")
        try:
            # Устанавливаем время давно в прошлом, чтобы первый сброс по расписанию произошел корректно
            # и рулетка была доступна сразу
            initial_roulette_reset_time_local = datetime.now(pytz_timezone(Config.TIMEZONE)).replace(
                 hour=Config.RESET_HOUR, minute=4, second=0, microsecond=0 # Используем общие RESET_HOUR и минуты 4
            )
            initial_roulette_reset_time_local -= timedelta(days=(Config.ROULETTE_GLOBAL_COOLDOWN_DAYS * 2 + 1)) # Отнимаем больше дней

            await database.set_setting_timestamp(roulette_reset_key, initial_roulette_reset_time_local.astimezone(dt_timezone.utc))
            logger.info(f"Initial '{roulette_reset_key}' set to: {initial_roulette_reset_time_local.isoformat()} {Config.TIMEZONE}")
        except Exception as e_init_roulette_reset:
            logger.error(f"Failed to set initial '{roulette_reset_key}': {e_init_roulette_reset}", exc_info=True)
    # >>>>> КОНЕЦ ИНИЦИАЛИЗАЦИИ <<<<<

    logger.info("Registering handlers...")
    setup_families_handlers(dispatcher)
    setup_onecoin_handlers(dispatcher)
    setup_competition_handlers(dispatcher)
    setup_bonus_handlers(dispatcher)
    setup_roulette_handlers(dispatcher)
    setup_market_handlers(dispatcher) # <<< РЕГИСТРАЦИЯ РЫНКА
    setup_phone_handlers(dispatcher)
    setup_business_handlers(dispatcher) # Добавлено
    setup_black_market_handlers(dispatcher) # Регистрируем хендлеры Черного Рынка
    logger.info("Registering stats_logic handlers...") # Добавь это
    setup_stats_handlers(dispatcher) # И это
    setup_achievements_handlers(dispatcher)
    setup_robbank_handlers(dispatcher)
    setup_daily_onecoin_handlers(dispatcher)
    logger.info("Achievements command handlers registered.")
    logger.info("Stats command handlers registered.") # И это
    logger.info("Black Market command handlers registered.")
    logger.info("All command handlers registered.")

    try:
        if Config.TIMEZONE and pytz_timezone(Config.TIMEZONE):
            
            # vvv НОВАЯ ЗАДАЧА ДЛЯ ЧЕРНОГО РЫНКА vvv
            # Обновление ассортимента Черного Рынка
            bm_reset_hour = getattr(Config, "BLACKMARKET_RESET_HOUR", 21)
            scheduler.add_job(
                refresh_black_market_offers, # <--- И ЭТУ ТОЖЕ ПРОВЕРЬ
                CronTrigger(hour=bm_reset_hour, minute=random.randint(0, 5), timezone=Config.TIMEZONE), 
                args=[bot], 
                id='refresh_black_market_job',
                replace_existing=True,
                misfire_grace_time=600
            )
            logger.info(f"Black Market refresh job scheduled for {bm_reset_hour:02d}:xx {Config.TIMEZONE}")

            # Опционально: первый запуск обновления ЧР при старте бота, чтобы он не был пустым
            # Это полезно, если бот перезапускается, а до планового обновления еще далеко.
            
            logger.info("Initial Black Market refresh task created.")
            
            # Ежедневное начисление дохода с бизнесов и обработка событий
            business_income_hour = Config.BUSINESS_DAILY_INCOME_COLLECTION_HOUR # 21:00 по умолчанию
            # Можно поставить на несколько минут позже, чтобы не конфликтовать с другими задачами в 21:00:
            business_income_minute = 10 
            scheduler.add_job(
                process_daily_business_income_and_events,
                CronTrigger(hour=business_income_hour, minute=business_income_minute, timezone=Config.TIMEZONE),
                args=[bot],
                id='daily_business_income_and_events_job',
                replace_existing=True,
                misfire_grace_time=600 # Допускаем задержку до 10 минут
            )
            logger.info(f"Daily business income and events job scheduled for {business_income_hour:02d}:{business_income_minute:02d} {Config.TIMEZONE}")
            
            # --- Существующие задачи планировщика (оставляем их) ---
            scheduler.add_job(daily_competition_score_update, CronTrigger(hour=Config.RESET_HOUR, minute=5, timezone=Config.TIMEZONE), id='daily_competition_score_update_job', replace_existing=True, misfire_grace_time=300)
            scheduler.add_job(check_and_finalize_competitions, 'interval', seconds=Config.COMPETITION_END_CHECK_INTERVAL_SECONDS, id='check_finalize_competitions_job', replace_existing=True, misfire_grace_time=600)
            scheduler.add_job(global_bonus_multiplier_reset_task, CronTrigger(hour=Config.BONUS_MULTIPLIER_RESET_HOUR, minute=2, timezone=Config.TIMEZONE), id='global_bonus_reset_job', replace_existing=True, misfire_grace_time=120)
            scheduler.add_job(daily_reset_roulette_attempts, CronTrigger(hour=Config.RESET_HOUR, minute=1, timezone=Config.TIMEZONE), id='daily_reset_roulette_extras_job', replace_existing=True, misfire_grace_time=120)
            scheduler.add_job(scheduled_check_phone_breakdowns, CronTrigger(day_of_week='sun', hour=3, minute=0, timezone=Config.TIMEZONE),
                               args=[bot], id='weekly_phone_breakdowns_job', replace_existing=True, misfire_grace_time=1800)

            battery_check_hour = Config.RESET_HOUR
            battery_check_minute = 3
            scheduler.add_job(scheduled_check_phone_battery_status, CronTrigger(hour=battery_check_hour, minute=battery_check_minute, timezone=Config.TIMEZONE),
                               args=[bot], id='daily_phone_battery_check_job', replace_existing=True, misfire_grace_time=300)

            insurance_remind_hour = getattr(Config, "PHONE_INSURANCE_REMIND_HOUR", 10)
            insurance_remind_minute = getattr(Config, "PHONE_INSURANCE_REMIND_MINUTE", 0)
            scheduler.add_job(scheduled_remind_insurance_expiry, CronTrigger(hour=insurance_remind_hour, minute=insurance_remind_minute, timezone=Config.TIMEZONE),
                              args=[bot], id='daily_insurance_expiry_reminder_job', replace_existing=True, misfire_grace_time=600)

            inflation_hour = getattr(Config, "INFLATION_HOUR", 1)
            inflation_minute = getattr(Config, "INFLATION_MINUTE", 15)
            scheduler.add_job(
                scheduled_apply_inflation,
                CronTrigger(day=1, month=f"*/{Config.INFLATION_PERIOD_MONTHS}", hour=inflation_hour, minute=inflation_minute, timezone=Config.TIMEZONE),
                args=[bot], id='quarterly_inflation_job', replace_existing=True, misfire_grace_time=3600
            )
            logger.info(f"Задача инфляции запланирована на 1 число каждого {Config.INFLATION_PERIOD_MONTHS}-го месяца в {inflation_hour:02d}:{inflation_minute:02d} {Config.TIMEZONE}")

            trigger_day_roulette = '*' if Config.ROULETTE_GLOBAL_COOLDOWN_DAYS == 1 else f"*/{Config.ROULETTE_GLOBAL_COOLDOWN_DAYS}"
            scheduler.add_job(
                global_roulette_period_reset_task,
                CronTrigger(
                    day=trigger_day_roulette,
                    hour=Config.RESET_HOUR,
                    minute=4, 
                    timezone=Config.TIMEZONE
                ),
                id='global_roulette_period_reset_job',
                replace_existing=True,
                misfire_grace_time=300 
            )
            logger.info(f"Задача сброса глобального периода рулетки запланирована на день '{trigger_day_roulette}' в {Config.RESET_HOUR:02d}:04 {Config.TIMEZONE}")
            
            check_interval_seconds = 300 # 5 минут
            scheduler.add_job(
                scheduled_check_expired_phone_prizes,
                'interval',
                seconds=check_interval_seconds,
                args=[bot], 
                id='check_expired_phone_prizes_job',
                replace_existing=True,
                misfire_grace_time=120 
            )
            logger.info(f"Задача проверки просроченных призов запланирована на выполнение каждые {check_interval_seconds} секунд.")
            # === КОНЕЦ НОВОЙ ЗАДАЧИ === # Это был комментарий в твоем коде, я его оставляю

        # ДОБАВЛЕНО: Блок except для обработки ошибок планировщика
        else: # Этот else относится к `if Config.TIMEZONE and pytz_timezone(Config.TIMEZONE):`
            logger.warning("TIMEZONE не настроен или некорректен. Задачи планировщика не будут запущены.")
            
    except Exception as e: # Ловим любые ошибки, которые могли произойти в try-блоке
        logger.error(f"Ошибка при настройке задач планировщика: {e}", exc_info=True)
        # Тут можно добавить await send_telegram_log(bot, f"🔴 Ошибка настройки планировщика: {e}") если нужно
    # Теперь функция on_startup корректно завершена

async def on_shutdown(dispatcher: Dispatcher):
    logger.info("Starting bot shutdown sequence...")
    if scheduler.running:
        scheduler.shutdown(wait=True)
        logger.info("Планировщик остановлен.")
    logger.info("Bot shutdown sequence completed (on_shutdown).")
    await send_telegram_log(bot, "⛔️ <b>Бот остановлен.</b>")

dp.startup.register(on_startup)
dp.shutdown.register(on_shutdown)

# Если их нет, функция будет использовать значения по умолчанию (0.1 и -0.1)
POS_MICRO_CHANGES = [0.1, 0.2, 0.3, 0.4]
NEG_MICRO_CHANGES = [-0.1, -0.2, -0.3, -0.4]

def get_oneui_version_change() -> float:
    rand_category = random.random() # Случайное число для выбора категории (позитив, негатив, ноль)

    # Шаг 1: Выбираем общую категорию (позитив, негатив, ноль)
    # По вашему запросу: 68% - позитив, 30% - негатив, 2% - ноль
    if rand_category < 0.68: # 68% шанс на положительное изменение
        # Эта часть кода будет работать, если rand_category меньше 0.68
        # Теперь генерируем случайное число ДЛЯ ПОЛОЖИТЕЛЬНЫХ ИЗМЕНЕНИЙ
        rand_pos_value = random.random()

        # Распределение внутри положительных изменений
        # Очень часто 0.5-1.5 (больше 60% положительных изменений)
        if rand_pos_value < 0.65: # 65% из 68% общего шанса на позитив (то есть 0.65 * 0.68 = ~44% от всех вызовов)
            return round(random.uniform(0.5, 1.5), 1)
        # Часто 0.5-3.5 (следующие 20%)
        elif rand_pos_value < 0.85: # (20% из 68%)
            return round(random.uniform(0.5, 3.5), 1)
        # Редко 2.5-7.5 (следующие 10%)
        elif rand_pos_value < 0.95: # (10% из 68%)
            return round(random.uniform(2.5, 7.5), 1)
        # Очень редко 5.0-7.0 (следующие 4%)
        elif rand_pos_value < 0.99: # (4% из 68%)
            return round(random.uniform(5.0, 7.0), 1)
        # Супер редко 7.0-13.0 (последние 1%)
        else: # (1% из 68%)
            return round(random.uniform(7.0, 15.0), 1)

    elif rand_category < 0.98: # Следующие 30% шанса на отрицательное изменение (от 0.68 до 0.98)
        # Эта часть кода будет работать, если rand_category от 0.68 до 0.98
        # Теперь генерируем случайное число ДЛЯ ОТРИЦАТЕЛЬНЫХ ИЗМЕНЕНИЙ
        rand_neg_value = random.random()

        # Распределение внутри отрицательных изменений
        # Чаще -0.5 до -1.5 (45% отрицательных изменений)
        if rand_neg_value < 0.45: # 45% из 30% общего шанса на негатив (то есть 0.45 * 0.30 = ~13.5% от всех вызовов)
            return round(random.uniform(-1.5, -0.5), 1)
        # Реже -0.5 до -3.5 (25% отрицательных изменений)
        elif rand_neg_value < 0.70: # (25% из 30%)
            return round(random.uniform(-3.5, -0.5), 1)
        # Еще реже -2.5 до -7.5 (20% отрицательных изменений)
        elif rand_neg_value < 0.90: # (20% из 30%)
            return round(random.uniform(-7.5, -2.5), 1)
        # Супер редко -5.0 до -7.0 (8% отрицательных изменений)
        elif rand_neg_value < 0.98: # (8% из 30%)
            return round(random.uniform(-7.0, -5.0), 1)
        # Мега редко -7.0 до -13.0 (последние 2% отрицательных изменений)
        else: # (2% из 30%)
            return round(random.uniform(-13.0, -7.0), 1)

    else: # Оставшиеся 2% шанса на нулевое изменение (от 0.98 до 1.0)
        return 0.0

# === /oneui КОМАНДА (с учетом купленных/бонусных попыток) ===
@dp.message(Command(
    "oneui", "ванюай", "уанюай", "обнова", "версия", "обновить", "прошивка",
    "one_ui", "get_version", "my_oneui", "моя_версия_oneui", "ванюи", "оней",
    ignore_case=True
))
async def oneui_command(message: Message):
    if not message.from_user: await message.reply("Не могу определить пользователя."); return

    user_id = message.from_user.id
    user_tg_username = message.from_user.username
    full_name = message.from_user.full_name
    chat_id_current_message = message.chat.id
    user_link = get_user_mention_html(user_id, full_name, user_tg_username)
    original_message_thread_id = message.message_thread_id

    current_utc_time_for_command = datetime.now(dt_timezone.utc)
    local_tz = pytz_timezone(Config.TIMEZONE)
    current_local_date_for_streak = current_utc_time_for_command.astimezone(local_tz).date()

    chat_title_for_db: Optional[str] = None
    telegram_chat_public_link: Optional[str] = None
    if message.chat.type == "private":
        chat_title_for_db = f"Личный чат ({user_id})"
    else:
        chat_title_for_db = message.chat.title or f"Чат {chat_id_current_message}"
        if message.chat.username:
            telegram_chat_public_link = f"https://t.me/{message.chat.username}"
        # ... (твой код для получения invite_link, если нужен)

    current_user_chat_lock = await database.get_user_chat_lock(user_id, chat_id_current_message)
    async with current_user_chat_lock:
        logger.info(f"/oneui from user {user_id} in chat {chat_id_current_message} (thread: {original_message_thread_id}) - START")
        response_message_parts: List[str] = []
        
        streak_bonus_version_change: float = 0.0
        streak_bonus_onecoin_change: int = 0
        
        # Аргументы для database.update_user_version относительно last_used
        set_last_used_time_arg: Optional[datetime] = None 
        force_update_last_used_arg: bool = False

        # --- НАЧАЛО НОВОГО БЛОКА: ОБРАБОТКА ЕЖЕДНЕВНОГО СТРИКА (ВСЕГДА ВЫПОЛНЯЕТСЯ) ---
        new_calculated_streak = 0
        user_streak_data = await database.get_user_daily_streak(user_id)
        current_streak_in_db = user_streak_data.get('current_streak', 0) if user_streak_data else 0
        last_streak_check_date_in_db = user_streak_data.get('last_streak_check_date') if user_streak_data else None
        streak_updated_this_session = False

        if last_streak_check_date_in_db == current_local_date_for_streak:
            logger.info(f"Streak for user {user_id} already processed today ({current_local_date_for_streak}). Current DB streak: {current_streak_in_db}")
            new_calculated_streak = current_streak_in_db
        elif last_streak_check_date_in_db is None or last_streak_check_date_in_db < (current_local_date_for_streak - timedelta(days=1)):
            if current_streak_in_db > 0:
                comp_v, comp_c = 0.0, 0
                for tier in sorted(Config.PROGRESSIVE_STREAK_BREAK_COMPENSATION, key=lambda x: x['min_streak_days_before_break'], reverse=True):
                    if current_streak_in_db >= tier['min_streak_days_before_break']: comp_v, comp_c = tier['version_bonus'], tier['onecoin_bonus']; break
                if comp_v == 0.0 and comp_c == 0 and current_streak_in_db > 0: comp_v, comp_c = Config.DEFAULT_STREAK_BREAK_COMPENSATION_VERSION, Config.DEFAULT_STREAK_BREAK_COMPENSATION_ONECOIN
                if comp_v > 0 or comp_c > 0:
                    response_message_parts.append(f"⚠️ Серия из {current_streak_in_db} дней прервана! Компенсация: <b>+{comp_v:.1f}</b>V, <b>+{comp_c}</b>C.")
                    streak_bonus_version_change += comp_v; streak_bonus_onecoin_change += comp_c
                    logger.info(f"User {user_id} streak broken ({current_streak_in_db} days). Compensation: +{comp_v:.1f}V, +{comp_c}C.")
            new_calculated_streak = 1; streak_updated_this_session = True
            logger.info(f"User {user_id} streak reset/started. New calculated streak: 1 on {current_local_date_for_streak}")
        elif last_streak_check_date_in_db == (current_local_date_for_streak - timedelta(days=1)):
            new_calculated_streak = current_streak_in_db + 1; streak_updated_this_session = True
            logger.info(f"User {user_id} continued streak. Old DB: {current_streak_in_db}, New calculated: {new_calculated_streak} on {current_local_date_for_streak}")
        
        if streak_updated_this_session:
            await database.update_user_daily_streak(user_id, new_calculated_streak, current_local_date_for_streak, current_utc_time_for_command)
            if new_calculated_streak > 0:
                for goal in Config.DAILY_STREAKS_CONFIG:
                    if new_calculated_streak == goal['target_days']:
                        vs, oc = goal.get('version_reward',0.0), goal.get('onecoin_reward',0)
                        if vs > 0 or oc > 0:
                            response_message_parts.append(f"🎉 Стрик \"<b>{html.escape(goal['name'])}</b>\" ({new_calculated_streak} д.)! Награда: <b>+{vs:.1f}</b>V, <b>+{oc}</b>C.")
                            streak_bonus_version_change += vs; streak_bonus_onecoin_change += oc
                            logger.info(f"User {user_id} achieved streak '{goal['name']}': +{vs:.1f}V, +{oc}C")
                        await check_and_grant_achievements(
                            user_id, chat_id_current_message, message.bot,
                            message_thread_id=original_message_thread_id,
                            current_daily_streak=new_calculated_streak # Используем current_daily_streak
                        )
                        break
        
        # Отображение стрика (актуальное значение new_calculated_streak)
        if new_calculated_streak > 0:
            response_message_parts.append(f"🔥 Текущий стрик: <b>{new_calculated_streak}</b> д.")

            next_goal_streak = next((g for g in Config.DAILY_STREAKS_CONFIG if g['target_days'] > new_calculated_streak), None)
            current_achieved_goal = next((g for g in Config.DAILY_STREAKS_CONFIG if g['target_days'] == new_calculated_streak), None)

            if (next_goal_streak and (next_goal_streak['target_days'] - new_calculated_streak) <= next_goal_streak.get('progress_show_within_days', 7)) or current_achieved_goal:
                target_for_pb = next_goal_streak
                name_for_pb = ""
                fill_char = Config.PROGRESS_BAR_FILLED_CHAR

                if current_achieved_goal:
                    target_for_pb = current_achieved_goal
                    name_for_pb = html.escape(current_achieved_goal['name']) + " (Завершено)"
                    fill_char = Config.PROGRESS_BAR_FULL_STREAK_CHAR
                elif next_goal_streak:
                    name_for_pb = html.escape(next_goal_streak['name'])

                if target_for_pb:
                    pb_streak_fill_count = round(new_calculated_streak / target_for_pb['target_days'] * 10)
                    if pb_streak_fill_count > 10:
                        pb_streak_fill_count = 10
                    if current_achieved_goal and new_calculated_streak == current_achieved_goal['target_days']:
                        pb_streak_fill_count = 10

                    pb_streak = fill_char * pb_streak_fill_count + Config.PROGRESS_BAR_EMPTY_CHAR * (10 - pb_streak_fill_count)
                    response_message_parts.append(f"<b>{name_for_pb}</b>: {new_calculated_streak}/{target_for_pb['target_days']}\n{pb_streak}")
            elif Config.DAILY_STREAKS_CONFIG and new_calculated_streak >= Config.DAILY_STREAKS_CONFIG[-1]['target_days']:
                response_message_parts.append(f"👑 Вы <b>{html.escape(Config.DAILY_STREAKS_CONFIG[-1]['name'])}</b>! Легендарный стрик: {new_calculated_streak} д.!")
        # --- КОНЕЦ НОВОГО БЛОКА: ОБРАБОТКА ЕЖЕДНЕВНОГО СТРИКА ---

        try:
            # --- 1. ПРОВЕРКА БЛОКИРОВКИ ОТ ОГРАБЛЕНИЯ ---
            robbank_status_for_oneui = await database.get_user_robbank_status(user_id, chat_id_current_message)
            if robbank_status_for_oneui and robbank_status_for_oneui.get('robbank_oneui_blocked_until_utc'):
                blocked_until_utc = robbank_status_for_oneui['robbank_oneui_blocked_until_utc']
                if current_utc_time_for_command < blocked_until_utc:
                    blocked_until_local_str = blocked_until_utc.astimezone(local_tz).strftime('%d.%m.%Y %H:%M:%S %Z')
                    
                    # Сообщение о блокировке будет включать уже обновленную информацию о стрике
                    block_msg = random.choice(ONEUI_BLOCKED_PHRASES).format(
                        block_time=blocked_until_local_str,
                        streak_info="" # Удаляем эту часть, так как инфо о стрике уже в `response_message_parts`
                    )
                    
                    # Отправляем сообщение о блокировке, добавляя к нему общие части сообщения
                    final_blocked_response_parts = [f"{user_link}, {block_msg}"]
                    if new_calculated_streak > 0: # Добавляем информацию о стрике
                        final_blocked_response_parts.append(f"Ваш стрик: <b>{new_calculated_streak}</b> дней.")
                        # Добавляем пояснение, что арест не сбрасывает стрик, но надо продолжить использовать /oneui
                        final_blocked_response_parts.append("(Блокировка не сбрасывает стрик, если вы продолжите использовать /oneui каждый день).")

                    await message.reply("\n".join(final_blocked_response_parts), parse_mode="HTML", disable_web_page_preview=True)
                    logger.info(f"/oneui user {user_id} in chat {chat_id_current_message} - BLOCKED BY ROBBANK until {blocked_until_utc.isoformat()}. Streak PROCESSED.")
                    return 
            
            # --- 2. ПРОВЕРКА И ИСПОЛЬЗОВАНИЕ ДОПОЛНИТЕЛЬНОЙ ПОПЫТКИ ---
            used_extra_attempt_this_time: bool = False
            roulette_status_current = await database.get_roulette_status(user_id, chat_id_current_message)
            available_extra_oneui_attempts = roulette_status_current.get('extra_oneui_attempts', 0) if roulette_status_current else 0

            if available_extra_oneui_attempts > 0:
                new_extra_attempts_count = available_extra_oneui_attempts - 1
                await database.update_roulette_status(user_id, chat_id_current_message, {'extra_oneui_attempts': new_extra_attempts_count})
                response_message_parts.append(f"🌀 Использована <b>доп. попытка /oneui</b>! Осталось: {new_extra_attempts_count}.")
                used_extra_attempt_this_time = True
                force_update_last_used_arg = False # Доп. попытка не должна обновлять last_used для основного кулдауна
                set_last_used_time_arg = None
                logger.info(f"User {user_id} in chat {chat_id_current_message} used extra /oneui attempt. Remaining: {new_extra_attempts_count}")

            is_free_regular_attempt_available = False
            if not used_extra_attempt_this_time:
                on_cooldown_status, next_reset_time_utc = await database.check_cooldown(user_id, chat_id_current_message)
                if on_cooldown_status and next_reset_time_utc:
                    # Пользователь на обычном кулдауне
                    next_reset_local = next_reset_time_utc.astimezone(local_tz)
                    chosen_cooldown_template = random.choice(ONEUI_COOLDOWN_RESPONSES)
                    cooldown_message = chosen_cooldown_template.format(time=next_reset_local.strftime('%H:%M'), zone=local_tz.zone)
                    
                    # Сначала добавляем сообщение о кулдауне
                    response_message_parts.append(cooldown_message) #

                    # Формируем итоговое сообщение, просто соединяя части
                    final_cooldown_response = f"{user_link}, " + "".join(response_message_parts) #

                    await message.reply(final_cooldown_response, parse_mode="HTML", disable_web_page_preview=True) #
                    logger.info(f"/oneui user {user_id} in chat {chat_id_current_message} - ON REGULAR COOLDOWN.") #
                    return
                else:
                    # Кулдауна нет, это доступная бесплатная попытка
                    is_free_regular_attempt_available = True
                    force_update_last_used_arg = True # Обновляем last_used для кулдауна
                    set_last_used_time_arg = current_utc_time_for_command
            

            # --- ОСНОВНАЯ ЛОГИКА ИЗМЕНЕНИЯ OneUI ---
            current_db_version = await database.get_user_version(user_id, chat_id_current_message)
            base_oneui_change = get_oneui_version_change()
            actual_base_change_for_next_steps = base_oneui_change
            version_change_from_bonus_multiplier_applied = 0.0
            phone_case_bonus_applied_value = 0.0

            if base_oneui_change < 0 and roulette_status_current and roulette_status_current.get('negative_change_protection_charges', 0) > 0:
                new_charges = roulette_status_current['negative_change_protection_charges'] - 1
                await database.update_roulette_status(user_id, chat_id_current_message, {'negative_change_protection_charges': new_charges})
                original_negative_change = base_oneui_change
                actual_base_change_for_next_steps = abs(base_oneui_change) 
                response_message_parts.append(f"🛡️ Сработал <b>заряд защиты</b>! Изменение <code>{original_negative_change:.1f}</code> стало <code>+{actual_base_change_for_next_steps:.1f}</code>! Зарядов: {new_charges}.")
            
            effective_oneui_change_from_roll_and_protection = actual_base_change_for_next_steps
            
            user_bonus_mult_status = await database.get_user_bonus_multiplier_status(user_id, chat_id_current_message)
            if user_bonus_mult_status and user_bonus_mult_status.get('current_bonus_multiplier') is not None and not user_bonus_mult_status.get('is_bonus_consumed', True):
                bonus_multiplier_value = float(user_bonus_mult_status['current_bonus_multiplier'])
                pending_boost_from_roulette = roulette_status_current.get('pending_bonus_multiplier_boost') if roulette_status_current else None
                if pending_boost_from_roulette is not None:
                    bonus_multiplier_value *= float(pending_boost_from_roulette)
                    await database.update_roulette_status(user_id, chat_id_current_message, {'pending_bonus_multiplier_boost': None})
                    response_message_parts.append(f"🎲 Применен <b>буст x{float(pending_boost_from_roulette):.1f}</b> от рулетки к бонусу!")
                
                change_if_multiplier_applied = effective_oneui_change_from_roll_and_protection * bonus_multiplier_value
                version_change_from_bonus_multiplier_applied = change_if_multiplier_applied - effective_oneui_change_from_roll_and_protection
                effective_oneui_change_from_roll_and_protection = change_if_multiplier_applied
                response_message_parts.append(f"✨ Применен бонус-множитель <b>x{bonus_multiplier_value:.2f}</b>! (<code>{actual_base_change_for_next_steps:.1f}</code> -> <code>{effective_oneui_change_from_roll_and_protection:.1f}</code>)")
                await database.update_user_bonus_multiplier_status(user_id, chat_id_current_message, user_bonus_mult_status['current_bonus_multiplier'], True, user_bonus_mult_status.get('last_claimed_timestamp'))

            total_version_change_before_phone_bonus = effective_oneui_change_from_roll_and_protection + streak_bonus_version_change
            
            try:
                phone_bonuses = await get_active_user_phone_bonuses(user_id)
                oneui_bonus_percent_from_case = phone_bonuses.get("oneui_version_bonus_percent", 0.0)
                if oneui_bonus_percent_from_case != 0:
                    bonus_value_from_case = total_version_change_before_phone_bonus * (oneui_bonus_percent_from_case / 100.0)
                    phone_case_bonus_applied_value = bonus_value_from_case
                    final_oneui_change_to_apply = total_version_change_before_phone_bonus + bonus_value_from_case
                    response_message_parts.append(f"📱 Бонус от чехла <b>{'+' if oneui_bonus_percent_from_case > 0 else ''}{oneui_bonus_percent_from_case:.0f}%</b> применен!")
                else:
                    final_oneui_change_to_apply = total_version_change_before_phone_bonus
            except Exception as e_phone_bonus_main:
                logger.error(f"OneUI: Error applying phone case bonus for user {user_id}: {e_phone_bonus_main}", exc_info=True)
                final_oneui_change_to_apply = total_version_change_before_phone_bonus
            
            new_version_final_raw = current_db_version + final_oneui_change_to_apply
            new_version_final_rounded = round(new_version_final_raw, 1)
            
            main_roll_response_part = f"📉 Обнова не вышла." if base_oneui_change == 0.0 else \
                                     random.choice(POSITIVE_RESPONSES).replace("%.1f", f"<b>{base_oneui_change:.1f}</b>") if base_oneui_change > 0.0 else \
                                     random.choice(NEGATIVE_RESPONSES).replace("%.1f", f"<b>{abs(base_oneui_change):.1f}</b>")
            response_message_parts.insert(0, main_roll_response_part)
            response_message_parts.append(f"\n<b>Итоговая версия OneUI: <code>{new_version_final_rounded:.1f}</code>.</b>")

            await database.update_user_version(
                user_id, chat_id_current_message, new_version_final_rounded,
                user_tg_username, full_name, chat_title_for_db, telegram_chat_public_link,
                set_last_used_time_utc=set_last_used_time_arg, # None для доп. попытки, current_utc_time_for_command для бесплатной
                force_update_last_used=force_update_last_used_arg # False для доп. попытки, True для бесплатной
            )

            if streak_bonus_onecoin_change != 0:
                await database.update_user_onecoins(
                    user_id, chat_id_current_message, streak_bonus_onecoin_change,
                    user_tg_username, full_name, chat_title_for_db
                )
            
            await check_and_grant_achievements(
                user_id, chat_id_current_message, message.bot,
                message_thread_id=original_message_thread_id,
                current_oneui_version=new_version_final_rounded
            )

            logger.info(f"Version for {user_id} in {chat_id_current_message} updated: {current_db_version:.1f} -> {new_version_final_rounded:.1f}. "
                        f"Details: BaseRoll={base_oneui_change:.1f}, ProtEffect={actual_base_change_for_next_steps-base_oneui_change:.1f}, "
                        f"BonusMultEffect={version_change_from_bonus_multiplier_applied:.2f}, "
                        f"StreakVersion={streak_bonus_version_change:.1f}, StreakCoin={streak_bonus_onecoin_change}, "
                        f"PhoneCaseBonus={phone_case_bonus_applied_value:.2f}, "
                        f"TotalAppliedChange={final_oneui_change_to_apply:.2f}")
            
            await message.reply("\n".join(response_message_parts), parse_mode="HTML", disable_web_page_preview=True)
            logger.info(f"/oneui user {user_id} in chat {chat_id_current_message} (thread: {original_message_thread_id}) - SUCCESS")

        except Exception as e:
            logger.error(f"Error in /oneui for user {user_id} in chat {chat_id_current_message} (thread: {original_message_thread_id}): {e}", exc_info=True)
            await message.reply("Внутренняя ошибка при обработке /oneui. Попробуйте позже.", disable_web_page_preview=True)
            await send_telegram_log(message.bot, f"🔴 <b>Ошибка /oneui</b>\nUser: {user_link} ({user_id})\nChat: {html.escape(chat_title_for_db or str(chat_id_current_message))} ({chat_id_current_message}, thread: {original_message_thread_id})\nErr: <pre>{html.escape(str(e))}</pre>")
        finally:
            logger.info(f"/oneui user {user_id} in chat {chat_id_current_message} (thread: {original_message_thread_id}) - END")

# === Вспомогательные функции для команд (из вашего файла) ===
# fetch_user_display_data и resolve_target_user
async def fetch_user_display_data(bot_instance: Bot, user_id_to_fetch: int) -> Tuple[str, Optional[str]]:
    full_name, username = None, None; conn = None
    try:
        conn = await database.get_connection()
        udb = await conn.fetchrow("SELECT full_name, username FROM user_oneui WHERE user_id = $1 ORDER BY last_used DESC NULLS LAST LIMIT 1", user_id_to_fetch)
        if udb: full_name, username = udb.get('full_name'), udb.get('username')
    except Exception as e: logger.warning(f"DB fetch error for user {user_id_to_fetch}: {e}")
    finally:
        if conn and not conn.is_closed(): await conn.close()
    if not full_name:
        try:
            ci = await bot_instance.get_chat(user_id_to_fetch)
            fn_api = getattr(ci, 'full_name', None) or getattr(ci, 'first_name', None)
            if fn_api: full_name = fn_api
            if not username: username = getattr(ci, 'username', None)
        except Exception as e: logger.warning(f"API get_chat error for user {user_id_to_fetch}: {e}")
    return full_name or f"User ID {user_id_to_fetch}", username

async def resolve_target_user(msg: Message, cmd: CommandObject, bot_inst: Bot) -> Optional[Tuple[int, str, Optional[str]]]:
    uid, fn, un = None, None, None
    if msg.reply_to_message and msg.reply_to_message.from_user and not msg.reply_to_message.from_user.is_bot:
        repl_user = msg.reply_to_message.from_user
        uid, fn, un = repl_user.id, repl_user.full_name, repl_user.username
    elif cmd.args:
        arg = cmd.args.strip()
        if arg.startswith('@'):
            uname_find = arg[1:].lower(); conn = None
            try:
                conn = await database.get_connection()
                urow = await conn.fetchrow("SELECT user_id, full_name, username FROM user_oneui WHERE lower(username) = $1 ORDER BY last_used DESC NULLS LAST LIMIT 1", uname_find)
                if urow: uid, fn, un = urow['user_id'], urow.get('full_name'), urow.get('username')
                else: await msg.reply(f"Не найден юзер @{html.escape(arg[1:])}. Попробуйте ID/ответ."); return None
            except Exception as e: logger.error(f"DB error searching @{html.escape(arg[1:])}: {e}", exc_info=True); await msg.reply(f"Ошибка поиска @{html.escape(arg[1:])}."); return None
            finally:
                if conn and not conn.is_closed(): await conn.close()
        else:
            try: uid = int(arg)
            except ValueError: await msg.reply("Неверный формат. ID, @username или ответ."); return None
    else: return None # Ни ответа, ни аргументов
    if uid:
        f_fn, f_un = await fetch_user_display_data(bot_inst, uid)
        final_fn = f_fn if f_fn and f_fn != f"User ID {uid}" else fn
        if not final_fn: final_fn = f_fn
        return uid, final_fn, f_un if f_un else un
    return None
# === Конец вспомогательных функций ===

# === КОМАНДЫ (с добавленными алиасами и обновленным /help) ===
@dp.message(Command("start", "старт", "начало", ignore_case=True))
async def cmd_start(message: Message, bot: Bot):
    user_id = message.from_user.id if message.from_user else 0
    user_full_name = message.from_user.full_name if message.from_user else "Неизвестный пользователь"
    user_username = message.from_user.username if message.from_user else ""
    user_link = html.escape(user_full_name) # Для HTML-форматирования, имя пользователя в сообщении

    response_text = f"""
🌟 <b>Привет, {user_link}! Добро пожаловать!</b> 🌟

🚀 Забудь о посредственности. Здесь ты — архитектор своей цифровой судьбы! Твой путь к вершинам начинается СЕЙЧАС.

🌍 Здесь ты сможешь:

📱 <b>Оптимизировать OneUI:</b> Повышай версию своей уникальной оболочки OneUI и обгоняй других!
➖➖➖➖➖➖➖➖➖➖➖
💎 <b>Зарабатывать OneCoin:</b> Твоя главная валюта для развития.
➖➖➖➖➖➖➖➖➖➖➖
🏢 <b>Развивать бизнес:</b> Открой свою сеть предприятий и получай стабильный доход.
➖➖➖➖➖➖➖➖➖➖➖
🤝 <b>Создавать семьи:</b> Объединяйся с друзьями и доминируй в рейтингах!
➖➖➖➖➖➖➖➖➖➖➖
📱 <b>Модернизировать телефон:</b> Покупай новые модели, улучшай компоненты и оптимизируй OneUI.
➖➖➖➖➖➖➖➖➖➖➖
🎲 <b>Рисковать и выигрывать:</b> Испытай удачу в рулетке и на загадочном Черном рынке.
➖➖➖➖➖➖➖➖➖➖➖
🏆 <b>Соревноваться:</b> Покажи всем, кто здесь настоящий магнат OneCoin/OneUi! 


💡 <b>ТВОИ ПЕРВЫЕ ШАГИ К ВЕЛИЧИЮ (для максимального эффекта!):</b> 💡
Чтобы начать свое восхождение, рекомендуем действовать по плану:
1️⃣Сначала используй команду /roll, чтобы испытать удачу в рулетке. Ты можешь выиграть мощные бонусы!
2️⃣Затем примени команду /bonus, чтобы получить множитель к следующему обновлению OneUI (Но, это не точно).
3️⃣И только потом активируй свой OneUI с помощью команды /oneui


🚧🚧🚧 <b>Предупреждаю</b> Бот находится на стадии <b>бета-тестирования</b>.
Это значит, что ты можешь столкнуться с ошибками, или некоторые функции могут быть еще не доработаны ну или вообще не быть доработаные :). Но, я буду пытаться фиксить!

📩Все замечания, предложения по улучшению, где-то текст кривой, пиши:👉 @lyuto_bor

📌(Советую боту выдать префикс, без прав можно)

ℹ️Чтобы узнать обо всех командах, набери /help.ℹ️
"""
    try:
        await message.reply(response_text, parse_mode="HTML", disable_web_page_preview=True)
        logger.info(f"User {user_id} ({user_link}) received enhanced start message.")
    except Exception as e:
        logger.error(f"Error sending enhanced start message to user {user_id}: {e}", exc_info=True)
        await send_telegram_log(bot, f"🔴 Ошибка отправки /start сообщения пользователю {user_link} ({user_id}): <pre>{html.escape(str(e))}</pre>")

@dp.message(Command(
    "help", "помощь", "хелп", "справка", "команды", "commands", "cmds", "manual", "гайд", "инфо", "info",
    ignore_case=True
))
async def cmd_help(message: Message, command: CommandObject):
    # command: CommandObject - это специальный объект Aiogram,
    # который содержит информацию о команде, включая аргументы.
    # Например, если пользователь написал "/help семья", то "семья" будет в command.args

    # Получаем user_id и user_link для логирования или обращения
    user_id = message.from_user.id if message.from_user else 0
    user_link = html.escape(message.from_user.full_name) if message.from_user else "Неизвестный пользователь"

    if command.args: # Проверяем, есть ли аргументы после /help (например, "/help семья")
        category_key = command.args.lower() # Переводим аргумент в нижний регистр для сравнения

        if category_key in COMMAND_CATEGORIES:
            category_data = COMMAND_CATEGORIES[category_key]
            response_parts = [
                f"<b>📚 {html.escape(category_data['title'])}</b>",
                f"{html.escape(category_data['description'])}",
                "" # Пустая строка для отступа
            ]
            for cmd, desc in category_data['commands'].items():
                response_parts.append(f"<code>{html.escape(cmd)}</code> - {html.escape(desc)}")
            
            await message.reply("\n".join(response_parts), parse_mode="HTML", disable_web_page_preview=True)
            logger.info(f"User {user_link} ({user_id}) requested help for category: '{category_key}'") # Логируем запрос
        else:
            # Если категория не найдена
            available_categories = ", ".join([f"<code>{k}</code>" for k in COMMAND_CATEGORIES.keys() if k != "основные"]) # Исключаем "основные" из списка для help-сообщения
            await message.reply(
                f"Категория команд '<code>{html.escape(category_key)}</code>' не найдена. "
                f"Доступные категории: {available_categories}.\n"
                f"Используйте <code>/help</code> без аргументов для общего списка категорий.",
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            logger.warning(f"User {user_link} ({user_id}) requested unknown help category: '{category_key}'") # Логируем неизвестную категорию
    else:
        # Если аргументов нет (просто /help)
        response_parts = [
            "<b>📚 Доступные категории команд:</b>",
            "Для получения подробной информации о командах в категории, используйте:",
            "/help &lt;название_категории&gt;",
            "" # Пустая строка для отступа
        ]

        # Добавляем список категорий (кроме "основных", так как они будут показаны отдельно)
        for key, data in COMMAND_CATEGORIES.items():
            if key == "основные":
                continue # Пропускаем "основные", чтобы они не дублировались в списке категорий
            
            response_parts.append(f"• <b>{html.escape(data['title'])}</b> (<code>/help {html.escape(key)}</code>) - {html.escape(data['description'])}")
        
        # Добавляем основные команды в конце, чтобы они всегда были видны в общем /help
        response_parts.append("\n<b>✨ Основные команды:</b>")
        for cmd, desc in COMMAND_CATEGORIES["основные"]["commands"].items():
            response_parts.append(f"{html.escape(cmd)} - {html.escape(desc)}")

        await message.reply("\n".join(response_parts), parse_mode="HTML", disable_web_page_preview=True)
        logger.info(f"User {user_link} ({user_id}) requested general help.") # Логируем общий запрос хелпа



@dp.message(Command(
    "my_history", "моя_история", "history", "история", "мои_изменения", "myhistory",
    "logupdates", "log_updates", "myupdates", "моиобновления", "мойлогверсий", "логмоихверсий",
    ignore_case=True
))
async def my_history_command(message: Message, bot: Bot):
    if not message.from_user: await message.reply("Не удалось определить пользователя."); return
    user_id, chat_id = message.from_user.id, message.chat.id
    full_name, username = await fetch_user_display_data(bot, user_id)
    user_link = get_user_mention_html(user_id, full_name, username)
    try:
        history_records = await database.get_user_version_history(user_id, chat_id=chat_id, limit=15)
        if not history_records: return await message.reply(f"{user_link}, у вас пока нет истории версий OneUI в этом чате. Используйте <code>/oneui</code>!", disable_web_page_preview=True)

        response_lines = [f"<b>📜 Ваша история версий OneUI в этом чате (последние {len(history_records)}):</b>"]
        local_tz = pytz_timezone(Config.TIMEZONE)

        # Обрабатываем записи, чтобы показать разницу.
        # history_records уже отсортированы DESCENDING (от новой к старой)
        # и содержат 'version_diff' рассчитанный относительно предыдущей записи в БД
        # или 0.0 для первой записи.

        for i, record in enumerate(history_records):
            version_text = f"V. <b>{record['version']:.1f}</b>"
            diff_text = ""
            # Если это первая запись в списке (самая новая), или diff 0.0, или diff еще не посчитан
            # ИЛИ если это первая запись, которую мы показываем после ЛИМИТА
            # (то есть, мы не знаем ее реальную предыдущую)
            if i == len(history_records) - 1: # Это самая старая запись в отображаемом списке
                diff_text = "" # Для самой старой записи в отображаемом списке не показываем разницу
            elif record.get('version_diff') is not None:
                diff_value = float(record['version_diff'])
                if diff_value > 0:
                    diff_text = f" (<span class='tg-spoiler'>+{diff_value:.1f}</span>)"
                elif diff_value < 0:
                    diff_text = f" (<span class='tg-spoiler'>{diff_value:.1f}</span>)"
                else:
                    diff_text = " (<span class='tg-spoiler'>без изменений</span>)"

            response_lines.append(
                f"  <code>{len(history_records) - i:2}.</code> {version_text}{diff_text} {record['changed_at'].astimezone(local_tz).strftime('%d.%m  %H:%M')}"
            )
        await message.reply("\n".join(response_lines), parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Error in /my_history for {user_link} in chat {chat_id}: {e}", exc_info=True)
        await message.reply("Произошла ошибка при получении вашей истории версий.", disable_web_page_preview=True)
        await send_telegram_log(bot, f"🔴 Ошибка в /my_history для {user_link}: <pre>{html.escape(str(e))}</pre>")


@dp.message(Command(
    "user_history", "история_пользователя", "историяюзера", "юзеристория",
    "log_user", "userlog", "checkuserhistory", "чужаяистория", "егоистория",
    ignore_case=True
))
async def user_history_command(message: Message, command: CommandObject, bot: Bot):
    calling_user = message.from_user
    if not calling_user: return await message.reply("Не удалось определить, кто вызвал команду.", disable_web_page_preview=True)
    target_user_data = await resolve_target_user(message, command, bot)
    if not target_user_data:
        if not command.args and not message.reply_to_message:
            await message.reply("Укажите цель (ID/@user/ответ) для <code>/user_history</code> или используйте <code>/my_history</code> для своей.", disable_web_page_preview=True)
        return
    target_user_id, target_full_name, target_username = target_user_data
    target_user_link = get_user_mention_html(target_user_id, target_full_name, target_username)
    current_chat_id = message.chat.id
    try:
        history_records = await database.get_user_version_history(target_user_id, chat_id=current_chat_id, limit=15)
        if not history_records: return await message.reply(f"У пользователя {target_user_link} нет истории версий OneUI в этом чате.", disable_web_page_preview=True)

        response_lines = [f"<b>📜 История версий OneUI {target_user_link} в этом чате (последние {len(history_records)}):</b>"]
        local_tz = pytz_timezone(Config.TIMEZONE)

        for i, record in enumerate(history_records):
            version_text = f"V. <b>{record['version']:.1f}</b>"
            diff_text = ""
            if i == len(history_records) - 1:
                diff_text = ""
            elif record.get('version_diff') is not None:
                diff_value = float(record['version_diff'])
                if diff_value > 0:
                    diff_text = f" (<span class='tg-spoiler'>+{diff_value:.1f}</span>)"
                elif diff_value < 0:
                    diff_text = f" (<span class='tg-spoiler'>{diff_value:.1f}</span>)"
                else:
                    diff_text = " (<span class='tg-spoiler'>без изменений</span>)"

            response_lines.append(
                f"  <code>{len(history_records) - i:2}.</code> {version_text}{diff_text} {record['changed_at'].astimezone(local_tz).strftime('%d.%m  %H:%M')}"
            )
        await message.reply("\n".join(response_lines), parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Error in /user_history for target {target_user_id} by {calling_user.id}: {e}", exc_info=True)
        await message.reply(f"Ошибка при получении истории для {target_user_link}.", disable_web_page_preview=True)
        await send_telegram_log(bot, f"🔴 Ошибка в /user_history для {target_user_link} (запросил {get_user_mention_html(calling_user.id, calling_user.full_name, calling_user.username)}): <pre>{html.escape(str(e))}</pre>")


@dp.message(Command(
    "top_chat", "топ_чата", "топчата", "топвэтомчате", "топ",
    "chat_top", "chattop", "leaderschat", "лидерычата", "рейтингчата",
    ignore_case=True
))
async def top_chat_command(message: Message, bot: Bot):
    chat_id = message.chat.id
    chat_title_display = html.escape(message.chat.title or f"этом чате (ID: {chat_id})")
    try:
        top_users = await database.get_top_users_in_chat(chat_id, limit=10)
        if not top_users: return await message.reply(f"В {chat_title_display} пока нет данных для топа OneUI.")
        response_lines = [f"<b>🏆 Топ-10 OneUI в {chat_title_display}:</b>"]
        for i, user_data in enumerate(top_users):
            full_name_top, username_top = await fetch_user_display_data(bot, user_data['user_id'])
            user_link_text = get_user_mention_html(user_data['user_id'], full_name_top, username_top)
            response_lines.append(f"{i + 1}. {user_link_text} - <code>{user_data['version']:.1f}</code>")
        await message.reply("\n".join(response_lines), parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Error in /top_chat for chat {chat_id}: {e}", exc_info=True)
        await message.reply("Ошибка отображения топа чата.")
        await send_telegram_log(bot, f"🔴 Ошибка в /top_chat (чат ID <code>{chat_id}</code>): <pre>{html.escape(str(e))}</pre>")


@dp.message(Command(
    "top_global", "глобальный_топ", "топвсех", "мировойтоп", "топглобал",
    "globaltop", "worldtop", "leadersglobal", "всеобщийтоп",
    ignore_case=True
))
async def top_global_command(message: Message, bot: Bot):
    try:
        top_users = await database.get_global_top_users(limit=10)
        if not top_users: return await message.reply("Глобальный топ OneUI пока пуст.")
        response_lines = ["<b>🌍 Глобальный топ-10 OneUI:</b>"]
        for i, user_data in enumerate(top_users):
            full_name_top, username_top = await fetch_user_display_data(bot, user_data['user_id'])
            user_link_text = get_user_mention_html(user_data['user_id'], full_name_top, username_top)
            chat_display_info = ""
            if user_data.get('chat_title'):
                 chat_title_esc = html.escape(user_data['chat_title'])
                 if user_data.get('chat_id') == user_data['user_id'] or user_data['chat_title'] == f"Личный чат ({user_data['user_id']})": chat_display_info = " (ЛС)"
                 elif user_data.get('telegram_chat_link'): chat_display_info = f" (из <a href=\"{user_data['telegram_chat_link']}\">{chat_title_esc}</a>)"
                 else: chat_display_info = f" (в '{chat_title_esc}')"
            response_lines.append(f"{i + 1}. {user_link_text} - <code>{user_data['version']:.1f}</code>{chat_display_info}")
        await message.reply("\n".join(response_lines), parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Error in /top_global: {e}", exc_info=True)
        await message.reply("Ошибка отображения глобального топа.")
        await send_telegram_log(bot, f"🔴 Ошибка в /top_global: <pre>{html.escape(str(e))}</pre>")


@dp.message(Command(
    "my_top_versions", "мои_лучшие_версии", "мойтопверсий", "топмоихверсий",
    "mytopversions", "mybestversions", "лучшиеверсиименя", "мойтоп",
    ignore_case=True
))
async def my_top_versions_command(message: Message, bot: Bot):
    if not message.from_user: await message.reply("Не удалось определить пользователя."); return
    user_id = message.from_user.id
    full_name, username = await fetch_user_display_data(bot, user_id)
    user_link = get_user_mention_html(user_id, full_name, username)
    try:
        top_versions = await database.get_user_top_versions(user_id, limit=10)
        if not top_versions: return await message.reply(f"{user_link}, у вас пока нет записей версий OneUI.")
        response_lines = [f"<b>🌟 Ваши лучшие версии OneUI по чатам (макс. {len(top_versions)}):</b>"]
        for i, record in enumerate(top_versions):
            chat_display_info = ""
            if record.get('chat_title'):
                 chat_title_esc = html.escape(record['chat_title'])
                 if record.get('chat_id') == user_id or record['chat_title'] == f"Личный чат ({user_id})": chat_display_info = " (ЛС)"
                 elif record.get('telegram_chat_link'): chat_display_info = f" (из <a href=\"{record['telegram_chat_link']}\">{chat_title_esc}</a>)"
                 else: chat_display_info = f" (в '{chat_title_esc}')"
            response_lines.append(f"  <code>{i+1:2}.</code> Версия <b>{record['version']:.1f}</b>{chat_display_info}")
        await message.reply("\n".join(response_lines), parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Error in /my_top_versions for {user_link}: {e}", exc_info=True)
        await message.reply("Ошибка отображения ваших топ версий.")
        await send_telegram_log(bot, f"🔴 Ошибка в /my_top_versions для {user_link}: <pre>{html.escape(str(e))}</pre>")


@dp.message(Command(
    "user_top_versions", "топ_версий_пользователя", "еготопверсий", "топверсийюзера", "utv",
    "usertopversions", "checkusertopversions", "чужойтоп", "еготоп",
    ignore_case=True
))
async def user_top_versions_command(message: Message, command: CommandObject, bot: Bot):
    calling_user = message.from_user
    if not calling_user: return await message.reply("Не удалось определить, кто вызвал команду.")
    target_user_data = await resolve_target_user(message, command, bot)
    if not target_user_data:
        if not command.args and not message.reply_to_message:
            await message.reply("Укажите цель (ID/@user/ответ) для <code>/user_top_versions</code> или используйте <code>/my_top_versions</code>.")
        return
    target_user_id, target_full_name, target_username = target_user_data
    target_user_link = get_user_mention_html(target_user_id, target_full_name, target_username)
    try:
        top_versions = await database.get_user_top_versions(target_user_id, limit=10)
        if not top_versions: return await message.reply(f"У пользователя {target_user_link} нет записей версий OneUI.")
        response_lines = [f"<b>🌟 Лучшие версии OneUI {target_user_link} по чатам (макс. {len(top_versions)}):</b>"]
        for i, record in enumerate(top_versions):
            chat_display_info = ""
            if record.get('chat_title'):
                 chat_title_esc = html.escape(record['chat_title'])
                 if record.get('chat_id') == target_user_id or record['chat_title'] == f"Личный чат ({target_user_id})": chat_display_info = " (ЛС)"
                 elif record.get('telegram_chat_link'): chat_display_info = f" (из <a href=\"{record['telegram_chat_link']}\">{chat_title_esc}</a>)"
                 else: chat_display_info = f" (в '{chat_title_esc}')"
            response_lines.append(f"  <code>{i+1:2}.</code> Версия <b>{record['version']:.1f}</b>{chat_display_info}")
        await message.reply("\n".join(response_lines), parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Error in /user_top_versions for target {target_user_id} by {calling_user.id}: {e}", exc_info=True)
        await message.reply(f"Ошибка отображения топ версий для {target_user_link}.")
        await send_telegram_log(bot, f"🔴 Ошибка в /user_top_versions для {target_user_link} (запросил {get_user_mention_html(calling_user.id, calling_user.full_name, calling_user.username)}): <pre>{html.escape(str(e))}</pre>")

# === Конец других команд ===

if __name__ == '__main__':
    async def main_runner():
        try:
            logger.info("Запуск бота...")
            await dp.start_polling(bot)
        except (KeyboardInterrupt, SystemExit):
            logger.info("Бот остановлен вручную (KeyboardInterrupt/SystemExit).")
        except Exception as e_run:
            logger.critical(f"Критическая ошибка при запуске/работе бота: {e_run}", exc_info=True)
        finally:
            logger.info("Начало процедуры остановки...")
            if scheduler.running:
                scheduler.shutdown(wait=False)
                logger.info("Планировщик остановлен.")
            if bot: # Убедимся, что объект бота существует
                try:
                    logger.info("Попытка закрыть сессию бота (из main_runner.finally)...")
                    await bot.close()
                    # Метод close() обычно идемпотентен, т.е. его можно безопасно вызывать, даже если сессия уже закрыта.
                    logger.info("Сессия бота успешно закрыта или уже была закрыта (из main_runner.finally).")
                except Exception as e_bot_close:
                    logger.error(f"Ошибка при вызове bot.close() в main_runner.finally: {e_bot_close}", exc_info=True)
            logger.info("Бот и ресурсы корректно остановлены (из main_runner).")

    asyncio.run(main_runner())
