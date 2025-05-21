# roulette_logic.py
import asyncio
import html
import random
from datetime import datetime, timedelta, timezone as dt_timezone, date as DDate
from typing import Optional, Tuple, Dict, Any, List
from pytz import timezone as pytz_timezone # Убедись, что pytz установлен
from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import Message, Chat # Chat добавлен
import asyncpg 
import logging

try:
    from config import Config
except ImportError:
    raise ImportError("Не удалось импортировать Config в roulette_logic.py")

try:
    import database
    # utils теперь должен содержать get_current_price
    from utils import get_user_mention_html, send_telegram_log, get_current_price 
except ImportError:
    raise ImportError("Не удалось импортировать database или utils (с get_current_price) в roulette_logic.py")

try:
    from phone_logic import get_active_user_phone_bonuses
except ImportError:
    logging.warning("ЗАГЛУШКА: phone_logic.py или get_active_user_phone_bonuses не найден. "
                    "Бонус от чехла на OneCoin не будет работать.")
    async def get_active_user_phone_bonuses(user_id: int) -> dict:
        return {}

# >>>>> ИЗМЕНЕНИЕ: Импорт и создание PHONE_MODELS и PHONE_COLORS <<<<<
try:
    from phone_data import PHONE_MODELS as PHONE_MODELS_LIST, PHONE_COLORS
    PHONE_MODELS: Dict[str, Dict[str, Any]] = {
        phone_info["key"]: phone_info for phone_info in PHONE_MODELS_LIST
    }
    if not PHONE_COLORS: # На случай, если PHONE_COLORS пуст
        PHONE_COLORS = ["Черный", "Белый", "Синий", "Красный"] # Минимальный набор по умолчанию
except ImportError:
    logging.critical("Не удалось импортировать PHONE_MODELS_LIST или PHONE_COLORS из phone_data.py!")
    # Создаем заглушки, чтобы бот не упал, но функционал телефонов будет сломан
    PHONE_MODELS = {}
    PHONE_COLORS = ["Черный", "Белый", "Синий", "Красный"]


roulette_router = Router()
logger = logging.getLogger(__name__)

# Блокировки команд
user_roulette_locks: Dict[Tuple[int, int], asyncio.Lock] = {} 
roulette_locks_lock = asyncio.Lock()

async def get_roulette_lock(user_id: int, chat_id: int) -> asyncio.Lock:
    key = (user_id, chat_id)
    async with roulette_locks_lock:
        if key not in user_roulette_locks:
            user_roulette_locks[key] = asyncio.Lock()
        return user_roulette_locks[key]

# >>>>> ИЗМЕНЕНИЕ: Вспомогательная функция parse_memory_string_to_gb <<<<<
# Эту функцию лучше вынести в utils.py, если она используется где-то еще.
# Для простоты пока оставляю здесь.
def parse_memory_string_to_gb(memory_str: str) -> int:
    if not isinstance(memory_str, str):
        logger.warning(f"parse_memory_string_to_gb: получена не строка: {memory_str}")
        return 128 # Дефолтное значение

    memory_str_upper = memory_str.upper().strip()
    num_val = 0
    num_part = ""
    try:
        for char_mem in memory_str_upper:
            if char_mem.isdigit() or char_mem == '.':
                num_part += char_mem
            else:
                if num_part: break
        
        if not num_part:
            logger.warning(f"Не удалось извлечь число из строки памяти: '{memory_str}'. Возвращено 128GB.")
            return 128

        value = float(num_part)
        if 'TB' in memory_str_upper:
            num_val = int(value * 1024)
        elif 'GB' in memory_str_upper:
            num_val = int(value)
        else: 
            num_val = int(value) # Если нет единиц, считаем GB
            
    except ValueError:
        logger.warning(f"ValueError при парсинге памяти '{memory_str}'. Возвращено 128GB.")
        return 128 
    except Exception as e:
        logger.error(f"Общая ошибка при парсинге памяти '{memory_str}': {e}. Возвращено 128GB.")
        return 128
    
    return num_val if num_val > 0 else 128


async def ensure_user_oneui_record_for_roulette(
    user_id: int, chat_id: int, user_tg_username: Optional[str],
    full_name_from_msg: Optional[str], message_chat_obj: Chat, # Изменен тип на Chat
    bot_instance: Bot
):
    # ... (остальная часть функции без изменений, только message_chat_obj теперь Chat)
    chat_title_for_db: Optional[str] = None
    telegram_chat_public_link: Optional[str] = None

    if message_chat_obj.type == "private": # Используем message_chat_obj.type
        chat_title_for_db = f"Личный чат ({user_id})"
    else:
        chat_title_for_db = message_chat_obj.title or f"Чат {chat_id}" # Используем message_chat_obj.title
        if message_chat_obj.username: # Используем message_chat_obj.username
            telegram_chat_public_link = f"https://t.me/{message_chat_obj.username}"
        else:
            try:
                # get_chat уже не нужен, так как message_chat_obj это уже Chat
                if message_chat_obj.title: chat_title_for_db = message_chat_obj.title
                if hasattr(message_chat_obj, 'invite_link') and message_chat_obj.invite_link: # Проверяем наличие invite_link
                     telegram_chat_public_link = message_chat_obj.invite_link
            except Exception as e_chat_info: # Хотя здесь ошибок быть не должно уже
                logger.warning(f"Roulette (ensure_user_oneui): Could not get chat_info for {chat_id} from Chat object: {e_chat_info}")
    try:
        current_version = await database.get_user_version(user_id, chat_id)
        await database.update_user_version(
            user_id, chat_id, new_version=current_version,
            username=user_tg_username, full_name=full_name_from_msg,
            chat_title=chat_title_for_db, telegram_chat_link=telegram_chat_public_link,
            set_last_used_time_utc=None, force_update_last_used=False
        )
        logger.info(f"Roulette: Ensured/updated user_oneui record for user {user_id} in chat {chat_id}.")
    except Exception as e:
        logger.error(f"Roulette: Failed to ensure/update user_oneui record for user {user_id} in chat {chat_id}: {e}", exc_info=True)
        raise

@roulette_router.message(Command(*Config.ROULETTE_COMMAND_ALIASES, ignore_case=True))
async def cmd_spin_roulette(message: Message, bot: Bot):
    if not message.from_user:
        await message.reply("Не удалось определить пользователя.")
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    user_tg_username = message.from_user.username
    full_name_from_msg = message.from_user.full_name
    user_link = get_user_mention_html(user_id, full_name_from_msg, user_tg_username)
    current_time_utc = datetime.now(dt_timezone.utc)
    local_tz = pytz_timezone(Config.TIMEZONE) 

    try:
        await ensure_user_oneui_record_for_roulette(
            user_id, chat_id, user_tg_username, full_name_from_msg, message.chat, bot
        )
    except Exception as e_ensure:
        logger.error(f"Roulette: Критическая ошибка ensure_user_oneui_record для {user_id}@{chat_id}: {e_ensure}", exc_info=True)
        await message.reply("Критическая ошибка подготовки к рулетке (R00).")
        await send_telegram_log(bot, f"🔴 R00 (ensure_user_oneui) для {user_link} (<code>{user_id}@{chat_id}</code>): <pre>{html.escape(str(e_ensure))}</pre>")
        return

    roulette_lock = await get_roulette_lock(user_id, chat_id)
    async with roulette_lock:
        try:
            roulette_status_current = await database.get_roulette_status(user_id, chat_id)
            can_spin_now = False
            used_purchased_spin_this_time = False
            
            available_purchased_spins = roulette_status_current.get('extra_roulette_spins', 0) if roulette_status_current else 0

            if available_purchased_spins > 0:
                # Логика использования купленного спина (остается такой же)
                new_purchased_spins_count = available_purchased_spins - 1
                await database.update_roulette_status(user_id, chat_id, {'extra_roulette_spins': new_purchased_spins_count})
                await message.reply(f"🌀 {user_link}, используется <b>купленный спин рулетки</b>! Осталось: {new_purchased_spins_count}.")
                can_spin_now = True
                used_purchased_spin_this_time = True
                logger.info(f"User {user_id}@{chat_id} used purchased roulette spin. Remaining: {new_purchased_spins_count}")
            
            if not can_spin_now: # Проверяем бесплатную попытку
                # >>>>> НАЧАЛО НОВОЙ ЛОГИКИ ПРОВЕРКИ КУЛДАУНА РУЛЕТКИ (как в /bonus) <<<<<
                roulette_global_reset_key = 'last_global_roulette_period_reset'
                last_global_reset_ts_utc = await database.get_setting_timestamp(roulette_global_reset_key)

                if not last_global_reset_ts_utc: 
                    logger.warning(f"'{roulette_global_reset_key}' не установлен в БД. Рулетка доступна по умолчанию для {user_id}@{chat_id}.")
                    last_global_reset_ts_utc = current_time_utc - timedelta(days=(Config.ROULETTE_GLOBAL_COOLDOWN_DAYS * 2))
                
                last_spin_in_chat_ts_utc: Optional[datetime] = None
                if roulette_status_current and roulette_status_current.get('last_roulette_spin_timestamp'):
                    last_spin_in_chat_ts_utc = roulette_status_current['last_roulette_spin_timestamp']
                    # Убедимся, что время aware UTC
                    if last_spin_in_chat_ts_utc.tzinfo is None:
                        last_spin_in_chat_ts_utc = last_spin_in_chat_ts_utc.replace(tzinfo=dt_timezone.utc)
                    else:
                        last_spin_in_chat_ts_utc = last_spin_in_chat_ts_utc.astimezone(dt_timezone.utc)
                
                if last_spin_in_chat_ts_utc and last_spin_in_chat_ts_utc >= last_global_reset_ts_utc:
                    # Пользователь уже крутил в этом чате в текущем глобальном периоде
                    can_spin_now = False
                    
                    # Расчет времени следующего глобального сброса для сообщения
                    effective_next_reset_utc = last_global_reset_ts_utc
                    # Находим ближайшее будущее время сброса, добавляя периоды кулдауна
                    while effective_next_reset_utc <= current_time_utc: # <= чтобы перейти к следующему периоду, если текущий уже начался
                         effective_next_reset_utc += timedelta(days=Config.ROULETTE_GLOBAL_COOLDOWN_DAYS)
                    
                    # Приводим к часу сброса по местному времени
                    # Минуты для сообщения могут немного отличаться от минут задачи планировщика, это не страшно
                    next_reset_display_local = effective_next_reset_utc.astimezone(local_tz).replace(
                        hour=Config.RESET_HOUR, minute=3, second=0, microsecond=0 
                    )
                    # Убедимся, что это время действительно в будущем
                    while next_reset_display_local.astimezone(dt_timezone.utc) <= current_time_utc:
                        next_reset_display_local += timedelta(days=Config.ROULETTE_GLOBAL_COOLDOWN_DAYS) # Переходим к следующему возможному сбросу

                    await message.reply(
                        f"{user_link}, вы уже испытали удачу в этом чате в текущем "
                        f"{Config.ROULETTE_GLOBAL_COOLDOWN_DAYS}-дневном периоде. "
                        f"Следующая глобальная возможность будет примерно после "
                        f"{next_reset_display_local.strftime('%Y-%m-%d %H:%M %Z')}.",
                        disable_web_page_preview=True
                    )
                    return # Выходим, так как крутить нельзя
                else: # Можно крутить бесплатно
                    can_spin_now = True
                # >>>>> КОНЕЦ НОВОЙ ЛОГИКИ ПРОВЕРКИ КУЛДАУНА РУЛЕТКИ <<<<<
            
            if not can_spin_now: 
                 logger.warning(f"Roulette: Logic error (R08), user {user_id}@{chat_id} cannot spin but should.")
                 await message.reply("Ошибка определения возможности спина (R08).")
                 return

            # --- Остальная часть функции cmd_spin_roulette (выбор приза, применение, отправка сообщения) ---
            # остается такой же, как в моем предыдущем полном ответе для roulette_logic.py
            # (начиная с processing_message = await message.reply(...))
            # Важно, что в конце, если это был бесплатный спин, обновляется 
            # 'last_roulette_spin_timestamp' в roulette_status.

            processing_message = await message.reply(f"🎲 {user_link} запускает рулетку удачи... Посмотрим, что выпадет!",
             disable_web_page_preview=True 
            )
            await asyncio.sleep(random.uniform(0.8, 2.0))

            prize_category, prize_value, prize_log_desc_from_determine = await _determine_prize()
            
            response_text_prize = await _apply_prize_and_get_message(
                user_id, chat_id, prize_category, prize_value, 
                user_link, bot,
                current_time_utc,      
                user_tg_username,      
                full_name_from_msg,    
                message.chat           
            )

            final_response_text = f"🎉 Вращение завершено!\n{response_text_prize}"
            try:
                await processing_message.edit_text(final_response_text, parse_mode="HTML", disable_web_page_preview=True)
            except Exception:
                await message.reply(final_response_text, parse_mode="HTML", disable_web_page_preview=True)

            # Обновляем время последнего *бесплатного* спина, если это был он и он был успешным
            if not used_purchased_spin_this_time and \
               "код R05" not in response_text_prize and \
               "код R00" not in response_text_prize: 
                 await database.update_roulette_status(user_id, chat_id, {'last_roulette_spin_timestamp': current_time_utc})
                 logger.info(f"Roulette: FREE spin time updated for user {user_id}@{chat_id}.")
            
            chat_title_for_log_final = html.escape(message.chat.title or f"ChatID {chat_id}")
            spin_type_log = "купленный" if used_purchased_spin_this_time else "бесплатный"
            log_prize_description = prize_log_desc_from_determine if prize_log_desc_from_determine else prize_category
            await send_telegram_log(bot, f"🎰 Рулетка ({spin_type_log} спин) для {user_link} в чате \"{chat_title_for_log_final}\": выпал приз \"{log_prize_description}\".")

        except Exception as e:
            logger.error(f"Ошибка в команде рулетки для {user_link} в чате {chat_id}: {e}", exc_info=True)
            await message.reply("Ой, что-то пошло не так с рулеткой! (R07).")
            await send_telegram_log(bot, f"🔴 Критическая ошибка R07 в рулетке для {user_link} (чат <code>{chat_id}</code>): <pre>{html.escape(str(e))}</pre>")

# setup_roulette_handlers остается без изменений
def setup_roulette_handlers(dp_main: Router):
    dp_main.include_router(roulette_router)
    logger.info("Обработчики команд рулетки зарегистрированы.")


# >>>>> ИЗМЕНЕНИЕ: Функция _determine_prize <<<<<
async def _determine_prize() -> Tuple[str, Any, Optional[str]]:
    categories = [item[0] for item in Config.ROULETTE_PRIZE_CATEGORIES_CHANCES]
    weights = [item[1] for item in Config.ROULETTE_PRIZE_CATEGORIES_CHANCES]
    
    if not categories or not weights or sum(weights) <= 0:
        logger.error("ROULETTE (_determine_prize): Ошибка в ROULETTE_PRIZE_CATEGORIES_CHANCES.")
        return "onecoin_reward", 10, "10 OneCoin(ов) (fallback из-за ошибки конфига)"

    chosen_category = random.choices(categories, weights=weights, k=1)[0]

    prize_value: Any = None
    prize_description: Optional[str] = None 

    if chosen_category == "onecoin_reward":
        # ... (твоя существующая логика выбора OneCoin награды, она корректна)
        chosen_range_config = random.choices(Config.ROULETTE_ONECOIN_PRIZES, weights=[item[1] for item in Config.ROULETTE_ONECOIN_PRIZES], k=1)[0]
        (min_coins, max_coins), _ = chosen_range_config
        prize_value = random.randint(min_coins, max_coins)
        prize_description = f"{prize_value} OneCoin(ов)"
    elif chosen_category == "extra_bonus_attempt":
        prize_value = 1
        prize_description = "1 доп. попытка /bonus"
    elif chosen_category == "extra_oneui_attempt":
        prize_value = 1
        prize_description = "1 доп. попытка /oneui"
    elif chosen_category == "bonus_multiplier_boost":
        # ... (твоя существующая логика выбора буста, она корректна)
        chosen_boost_config = random.choices(Config.ROULETTE_BONUS_MULTIPLIER_BOOSTS, weights=[item[1] for item in Config.ROULETTE_BONUS_MULTIPLIER_BOOSTS], k=1)[0]
        boost_factor, _ = chosen_boost_config
        prize_value = boost_factor
        prize_description = f"Усиление x{prize_value:.1f} для /bonus"
    elif chosen_category == "negative_protection_charge":
        prize_value = 1
        prize_description = "1 заряд защиты /oneui"
    
    # +++ ВАЖНО: ДОБАВЛЕН elif ДЛЯ phone_reward +++
    elif chosen_category == "phone_reward":
        prize_value = "PHONE_PLACEHOLDER" # Специальное значение, конкретный телефон выберется позже
        prize_description = "Телефон!" # Это описание пойдет в общий лог рулетки
    
    else: 
        # Этот else теперь для ДЕЙСТВИТЕЛЬНО неизвестных категорий, если такие появятся в конфиге без обработки
        logger.error(f"_determine_prize: Неизвестная категория приза рулетки: {chosen_category}. Выдаю fallback OneCoin.")
        chosen_category = "onecoin_reward" 
        prize_value = 10 
        prize_description = f"{prize_value} OneCoin(ов) (fallback из-за неизвестной категории)"

    return chosen_category, prize_value, prize_description


# >>>>> ИЗМЕНЕНИЕ: Сигнатура функции _apply_prize_and_get_message <<<<<
# >>>>> ИЗМЕНЕНИЕ: Сигнатура функции _apply_prize_and_get_message <<<<<
async def _apply_prize_and_get_message(
    user_id: int,
    chat_id: int,
    prize_category: str,
    prize_value: Any,
    user_mention: str,
    bot_instance: Bot,
    current_time_utc_param: datetime,
    user_tg_username_param: Optional[str],
    user_full_name_param: Optional[str],
    message_chat_obj_param: Chat
) -> str:
    message_to_user = ""
    updated_fields_for_roulette_status: Dict[str, Any] = {}
    bonus_amount_from_phone = 0

    # ... (логика определения chat_title_for_fallback_logic) ...
    chat_title_for_fallback_logic: Optional[str]
    if message_chat_obj_param.type == "private":
        chat_title_for_fallback_logic = f"Личный чат ({user_id})"
    else:
        chat_title_for_fallback_logic = message_chat_obj_param.title or f"Чат {chat_id}"
    # ... (остальная часть функции до elif prize_category == "phone_reward") ...

    try:
        user_db_data_for_onecoins_update: Optional[Dict[str, Any]] = None
        user_db_data_for_onecoins_update = await database.get_user_data_for_update(user_id, chat_id)
        if user_db_data_for_onecoins_update is None:
            user_db_data_for_onecoins_update = {}

        current_roulette_status_before_prize = await database.get_roulette_status(user_id, chat_id)
        if current_roulette_status_before_prize is None:
            logger.info(f"Roulette (_apply_prize): No prior roulette_status for user {user_id} chat {chat_id}.")
            current_roulette_status_before_prize = {}

        if prize_category == "onecoin_reward":
            # ... (существующая логика для onecoin_reward) ...
            onecoins_to_add = int(prize_value)
            try:
                phone_bonuses = await get_active_user_phone_bonuses(user_id)
                onecoin_bonus_p = phone_bonuses.get("onecoin_bonus_percent", 0.0)
                if onecoin_bonus_p > 0:
                    bonus_value_calculated = round(int(prize_value) * (onecoin_bonus_p / 100.0))
                    if bonus_value_calculated > 0:
                         onecoins_to_add += bonus_value_calculated
                         bonus_amount_from_phone = bonus_value_calculated
            except Exception as e_onecoin_bonus:
                logger.error(f"OneCoin Reward (Roulette Apply): Error applying phone bonus for user {user_id}: {e_onecoin_bonus}")

            await database.update_user_onecoins(
                user_id, chat_id, onecoins_to_add,
                username=user_db_data_for_onecoins_update.get('username', user_tg_username_param),
                full_name=user_db_data_for_onecoins_update.get('full_name', user_full_name_param),
                chat_title=user_db_data_for_onecoins_update.get('chat_title', chat_title_for_fallback_logic)
            )
            message_to_user = f"💰 {user_mention}, вы выиграли <b>{prize_value} OneCoin(ов)</b>!"
            if bonus_amount_from_phone > 0:
                message_to_user += f" (+{bonus_amount_from_phone} от бонуса чехла ✨)"
            message_to_user += " Они уже на вашем балансе в этом чате."

        elif prize_category == "extra_bonus_attempt":
            # ... (существующая логика) ...
             new_attempts = current_roulette_status_before_prize.get('extra_bonus_attempts', 0) + int(prize_value)
             updated_fields_for_roulette_status['extra_bonus_attempts'] = new_attempts
             message_to_user = (f"🔄 {user_mention}, вы выиграли <b>{prize_value} дополнительную попытку</b> для команды /bonus в этом чате! "
                                f"Теперь у вас {new_attempts} таких попыток. Неиспользованные сгорят в {Config.RESET_HOUR}:00.")
        elif prize_category == "extra_oneui_attempt":
            # ... (существующая логика) ...
             new_attempts = current_roulette_status_before_prize.get('extra_oneui_attempts', 0) + int(prize_value)
             updated_fields_for_roulette_status['extra_oneui_attempts'] = new_attempts
             message_to_user = (f"🔄 {user_mention}, вы выиграли <b>{prize_value} дополнительную попытку</b> использовать команду /oneui сегодня в этом чате! "
                                f"Теперь у вас {new_attempts} таких попыток. Неиспользованные сгорят в {Config.RESET_HOUR}:00.")
        elif prize_category == "bonus_multiplier_boost":
            # ... (существующая логика) ...
             boost_factor = float(prize_value)
             updated_fields_for_roulette_status['pending_bonus_multiplier_boost'] = boost_factor
             message_to_user = (f"✨ {user_mention}, ваш следующий множитель от <code>/bonus</code> (использованного в этом чате) будет <b>дополнительно умножен на x{boost_factor:.1f}</b>! "
                                "Этот бонус применится один раз и затем расходуется.")
        elif prize_category == "negative_protection_charge":
            # ... (существующая логика) ...
             new_charges = current_roulette_status_before_prize.get('negative_change_protection_charges', 0) + int(prize_value)
             updated_fields_for_roulette_status['negative_change_protection_charges'] = new_charges
             message_to_user = (f"🛡️ {user_mention}, вы получили <b>{prize_value} заряд защиты</b> от отрицательного изменения для /oneui в этом чате! "
                                f"Теперь у вас {new_charges} зарядов. Сработает при следующем негативном ролле.")

        # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # +++ ИЗМЕНЕННАЯ ЛОГИКА ДЛЯ ВЫДАЧИ ТЕЛЕФОНА +++
        # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        elif prize_category == "phone_reward":
            logger.info(f"Roulette (_apply_prize): User {user_id} in chat {chat_id} processing 'phone_reward' category.")

            # 1. Выбор серии и модели телефона (оставляем логику выбора телефона как есть)
            # ... (код для выбора selected_phone_info, chosen_color, initial_memory_gb) ...
            series_options = Config.ROULETTE_PHONE_SERIES_CHANCES
            series_keys = [s[0] for s in series_options]
            series_weights = [s[1] for s in series_options]

            selected_series = None
            if series_keys and sum(series_weights) > 0:
                selected_series_list = random.choices(series_keys, weights=series_weights, k=1)
                if selected_series_list:
                     selected_series = selected_series_list[0]

            if not selected_series:
                logger.error(f"ROULETTE (Phone Apply): Не удалось выбрать серию телефона. Выдаем fallback OneCoin.")
                coins_won_fallback = random.randint(40, 60)
                new_balance_fallback = await database.update_user_onecoins(user_id, chat_id, coins_won_fallback, username=user_db_data_for_onecoins_update.get('username', user_tg_username_param), full_name=user_db_data_for_onecoins_update.get('full_name', user_full_name_param), chat_title=user_db_data_for_onecoins_update.get('chat_title', chat_title_for_fallback_logic))
                message_to_user = f"🎁 Ого! Что-то необычное... Вы выиграли <b>{coins_won_fallback} OneCoin(s)</b> в качестве особого приза! Баланс: {new_balance_fallback} OC."
            else:
                phones_in_selected_series = [
                    model_info for model_key, model_info in PHONE_MODELS.items()
                    if model_info.get("series") == selected_series
                ]

                if not phones_in_selected_series:
                    logger.warning(f"ROULETTE (Phone Apply): Нет телефонов для серии {selected_series} в PHONE_MODELS. Компенсация.")
                    coins_compensation_no_phones = random.randint(30, 50)
                    new_balance_comp = await database.update_user_onecoins(user_id, chat_id, coins_compensation_no_phones, username=user_db_data_for_onecoins_update.get('username', user_tg_username_param), full_name=user_db_data_for_onecoins_update.get('full_name', user_full_name_param), chat_title=user_db_data_for_onecoins_update.get('chat_title', chat_title_for_fallback_logic))
                    message_to_user = f"🤔 Редкая удача! Вы почти выиграли телефон, но в этой серии сейчас пусто. Держите утешительные <b>{coins_compensation_no_phones} OneCoin(s)</b>. Баланс: {new_balance_comp} OC."
                else:
                    # Логика взвешенного выбора модели по возрасту/цене (оставляем как есть)
                    weighted_phone_model_list = []
                    current_year = current_time_utc_param.year

                    for phone_info_iter in phones_in_selected_series:
                        price = phone_info_iter.get("price", 1)
                        if price <= 0: price = 1
                        release_year = phone_info_iter.get("release_year")
                        age = 1
                        if release_year and isinstance(release_year, int):
                            age_calc = current_year - release_year + 1
                            age = max(1, age_calc)
                        calculated_weight = (age / price) * 10000
                        calculated_weight = max(1.0, calculated_weight)
                        weighted_phone_model_list.append((phone_info_iter, calculated_weight))

                    phone_objects = [item[0] for item in weighted_phone_model_list]
                    phone_model_weights = [item[1] for item in weighted_phone_model_list]

                    selected_phone_info = None
                    if phone_objects:
                         if not phone_model_weights or sum(phone_model_weights) == 0:
                              logger.warning(f"ROULETTE (Phone Apply): Нулевые веса для {selected_series}. Случайный выбор.")
                              selected_phone_info = random.choice(phone_objects)
                         else:
                              try:
                                  sel_list = random.choices(phone_objects, weights=phone_model_weights, k=1)
                                  if sel_list: selected_phone_info = sel_list[0]
                              except ValueError as e_choices:
                                  logger.error(f"ROULETTE (Phone Apply): Ошибка random.choices для {selected_series}: {e_choices}. Случайный выбор.")
                                  selected_phone_info = random.choice(phone_objects)
                    # Конец логики выбора selected_phone_info

                    if not selected_phone_info:
                        logger.error(f"ROULETTE (Phone Apply): Не удалось выбрать модель для {selected_series}. Компенсация.")
                        coins_comp_no_model = random.randint(35, 55)
                        new_bal_comp_nm = await database.update_user_onecoins(user_id, chat_id, coins_comp_no_model, username=user_db_data_for_onecoins_update.get('username', user_tg_username_param), full_name=user_db_data_for_onecoins_update.get('full_name', user_full_name_param), chat_title=user_db_data_for_onecoins_update.get('chat_title', chat_title_for_fallback_logic))
                        message_to_user = f"🍀 Почти! Вам чуть-чуть не хватило до телефона. В качестве приза - <b>{coins_comp_no_model} OneCoin(s)</b>. Баланс: {new_bal_comp_nm} OC."
                    else:
                        # Телефон выбран! Теперь проверяем лимит и предлагаем выбор или сохраняем как pending
                        won_phone_key = selected_phone_info['key']
                        won_phone_name = selected_phone_info['name']
                        won_phone_base_price = selected_phone_info['price']
                        chosen_color = random.choice(PHONE_COLORS) if PHONE_COLORS else "Черный"
                        memory_str = selected_phone_info.get("memory", "128GB")
                        initial_memory_gb = parse_memory_string_to_gb(memory_str)

                        active_phones_count = await database.count_user_active_phones(user_id)
                        max_phones_allowed = getattr(Config, "MAX_PHONES_PER_USER", 2)

                        # Проверяем, нет ли уже pending приза у пользователя
                        existing_pending_prize = await database.get_pending_phone_prize(user_id)

                        if existing_pending_prize:
                             # Этого не должно случиться благодаря UNIQUE(user_id) в user_pending_phone_prizes,
                             # но на всякий случай:
                             logger.warning(f"Roulette (_apply_prize): User {user_id} won a phone but already has a pending prize (ID: {existing_pending_prize.get('prize_id')}). Providing small compensation.")
                             coins_comp_existing = random.randint(10, 30)
                             new_bal_comp_ex = await database.update_user_onecoins(user_id, chat_id, coins_comp_existing, username=user_db_data_for_onecoins_update.get('username', user_tg_username_param), full_name=user_db_data_for_onecoins_update.get('full_name', user_full_name_param), chat_title=user_db_data_for_onecoins_update.get('chat_title', chat_title_for_fallback_logic))
                             message_to_user = f"🎁 Вы выиграли телефон, но у вас уже есть приз, ожидающий решения! Вместо этого вы получаете <b>{coins_comp_existing} OneCoin(s)</b>."

                        elif active_phones_count >= max_phones_allowed:
                            # >>> Сохраняем как pending prize и предлагаем выбор <<<
                            pending_prize_id = await database.add_pending_phone_prize(
                                user_id=user_id,
                                phone_model_key=won_phone_key,
                                color=chosen_color,
                                initial_memory_gb=initial_memory_gb,
                                prize_won_at_utc=current_time_utc_param,
                                original_roulette_chat_id=chat_id # Сохраняем чат, где произошел выигрыш
                            )

                            if pending_prize_id:
                                # Переводим пользователя в FSM состояние ожидания решения
                                # Используем FSM из phone_logic
                                from phone_logic import PurchaseStates # Импортируем здесь, чтобы избежать циклического импорта

                                fsm_context = message_chat_obj_param # В aiogram 3 context можно получить из message
                                # Если message_chat_obj_param не имеет метода .get_state() и .set_state(),
                                # возможно, придется передавать state напрямую или использовать другой подход.
                                # Предположим, что можно получить state через message: await state.set_state(...)

                                # Если это не работает, то придется передавать объект StateContext
                                # из основного хендлера в apply_prize.
                                # Для простоты сейчас используем message как FSMContext, но это может потребовать доработки.
                                # НАИБОЛЕЕ ВЕРОЯТНЫЙ СПОСОБ: FSMState привязан к user_id И chat_id.
                                # Чтобы состояние сохранялось независимо от чата для pending prize,
                                # можно либо привязывать его к (user_id, user_id) или использовать кастомный storage,
                                # либо просто проверять наличие pending prize в БД при попытке использовать /keepwonphone /sellwonphone.
                                # Давайте пойдем по пути проверки pending prize в БД, это проще, чем FSM cross-chat.
                                # FSM state оставим только для подтверждений покупок/продаж.

                                # Сбрасываем FSM состояние пользователя, если оно было установлено (например, после неудачной покупки)
                                try:
                                     user_fsm_state = fsm_context.from_user(user_id) # Пример получения state
                                     if await user_fsm_state.get_state() is not None:
                                          await user_fsm_state.clear()
                                except Exception as e_clear_state:
                                     logger.warning(f"Roulette (_apply_prize): Не удалось очистить FSM состояние для user {user_id}: {e_clear_state}")


                                message_to_user = (
                                    f"🎉 Вы выиграли телефон <b>{html.escape(won_phone_name)}</b> ({chosen_color}, {initial_memory_gb}GB)!\n"
                                    f"Однако, у вас уже максимальное количество телефонов ({active_phones_count}/{max_phones_allowed}).\n"
                                    f"У вас есть <b>1 час</b> на принятие решения:"
                                    f"\n  1. Взять этот телефон: Для этого продайте один из своих старых командой <code>/keepwonphone ID_старого_телефона</code> (ID ваших телефонов в /myphones)."
                                    f"\n  2. Продать выигранный телефон боту: Используйте команду <code>/sellwonphone</code> (вы получите 80% его рыночной стоимости)."
                                    f"\nЕсли вы не примете решение в течение часа, телефон будет автоматически продан боту за 80% стоимости."
                                )
                                logger.info(f"Roulette (_apply_prize): User {user_id} won {won_phone_key} but maxed. Pending decision (Prize ID: {pending_prize_id}).")
                                # Логируем приз, который ожидает решения
                                log_chat_title = chat_title_for_fallback_logic
                                await send_telegram_log(bot_instance,
                                    f"🎰⏳ <b>ПРИЗ ОЖИДАЕТ РЕШЕНИЯ!</b>\n"
                                    f"Пользователь: {user_mention} ({user_id})\n"
                                    f"Чат: {html.escape(log_chat_title)} ({chat_id})\n"
                                    f"Выиграл телефон: <b>{html.escape(won_phone_name)} ({won_phone_key})</b>, {chosen_color}, {initial_memory_gb}GB.\n"
                                    f"Ожидает решения ({Config.MARKET_PHONE_CONFIRMATION_TIMEOUT_SECONDS // 60} мин)." # Используем тот же таймаут, что и для покупок/продаж
                                )
                            else:
                                # ... (fallback при ошибке добавления в pending) ...
                                logger.error(f"ROULETTE (Phone Apply): Не удалось добавить pending prize для user {user_id}. Fallback.")
                                coins_fall_db = random.randint(70, 150)
                                new_bal_fall_db = await database.update_user_onecoins(user_id, chat_id, coins_fall_db, username=user_db_data_for_onecoins_update.get('username', user_tg_username_param), full_name=user_db_data_for_onecoins_update.get('full_name', user_full_name_param), chat_title=user_db_data_for_onecoins_update.get('chat_title', chat_title_for_fallback_logic))
                                message_to_user = f"✨ Вы почти выиграли телефон, но произошла ошибка при его добавлении в список ожидания! Вместо этого вы получаете <b>{coins_fall_db} OneCoin(s)</b>. Баланс: {new_bal_fall_db} OC."

                        else: # Пользователь может получить телефон, инвентарь не полный
                             # ... (существующая логика добавления телефона в инвентарь и сообщения о джекпоте) ...
                             new_phone_inventory_id = await database.add_phone_to_user_inventory(
                                user_id=user_id,
                                chat_id_acquired_in=chat_id,
                                phone_model_key=won_phone_key,
                                color=chosen_color,
                                purchase_price_onecoins=0,
                                purchase_date_utc=current_time_utc_param,
                                initial_memory_gb=initial_memory_gb,
                                is_contraband=False
                            )
                             if new_phone_inventory_id:
                                message_to_user = (
                                    f"🎉🎉🎉 <b>ДЖЕКПОТ!!!</b> 🎉🎉🎉\n"
                                    f"{user_mention}, вы выиграли совершенно новый телефон: \n"
                                    f"<b>📱 {html.escape(won_phone_name)}</b> ({chosen_color}, {initial_memory_gb}GB)!\n"
                                    f"Он добавлен в ваш инвентарь (/myphones) с ID: <code>{new_phone_inventory_id}</code>."
                                )
                                logger.info(f"Roulette (_apply_prize): User {user_id} received phone {won_phone_key} (ID: {new_phone_inventory_id}).")
                                log_chat_title = chat_title_for_fallback_logic
                                await send_telegram_log(bot_instance,
                                    f"🎰📱 <b>ДЖЕКПОТ РУЛЕТКИ!</b>\n"
                                    f"Пользователь: {user_mention} ({user_id})\n"
                                    f"Чат: {html.escape(log_chat_title)} ({chat_id})\n"
                                    f"Выиграл телефон: <b>{html.escape(won_phone_name)} ({won_phone_key})</b>, {chosen_color}, {initial_memory_gb}GB.\n"
                                    f"ID в инвентаре: {new_phone_inventory_id}"
                                )
                             else:
                                # ... (fallback при ошибке добавления в БД) ...
                                logger.error(f"ROULETTE (Phone Apply): Не удалось добавить {won_phone_key} user {user_id}. Fallback.")
                                coins_fall_db = random.randint(70, 150)
                                new_bal_fall_db = await database.update_user_onecoins(user_id, chat_id, coins_fall_db, username=user_db_data_for_onecoins_update.get('username', user_tg_username_param), full_name=user_db_data_for_onecoins_update.get('full_name', user_full_name_param), chat_title=user_db_data_for_onecoins_update.get('chat_title', chat_title_for_fallback_logic))
                                message_to_user = f"✨ Вы почти выиграли телефон, но произошла ошибка при его добавлении! Вместо этого вы получаете <b>{coins_fall_db} OneCoin(s)</b>. Баланс: {new_bal_fall_db} OC."

        # ... (остальная часть функции _apply_prize_and_get_message) ...
        # Обновляем поля статуса рулетки (кроме last_roulette_spin_timestamp, он обновляется в cmd_spin_roulette)
        if updated_fields_for_roulette_status:
            await database.update_roulette_status(user_id, chat_id, updated_fields_for_roulette_status)
            logger.info(f"Roulette status updated for user {user_id} chat {chat_id} with: {updated_fields_for_roulette_status}")

        return message_to_user

    except asyncpg.exceptions.ForeignKeyViolationError:
        # ... (существующая обработка) ...
        logger.error(f"Не удалось применить приз рулетки для {user_mention} (user {user_id} chat {chat_id}) из-за ForeignKeyViolationError. "
                     f"Вероятно, отсутствует запись в user_oneui. Приз не зачислен.", exc_info=False)
        await send_telegram_log(bot_instance,
                                f"🔴 Ошибка FK при зачислении приза рулетки для {user_mention} (<code>{user_id}@{chat_id}</code>). "
                                f"Приз: {prize_category} ({prize_value}). Запись user_oneui отсутствует?")
        return (f"{user_mention}, не удалось зачислить ваш приз из-за системной ошибки (код R05 - отсутствует основная запись пользователя). "
                "Пожалуйста, используйте команду <code>/oneui</code> один раз в этом чате, чтобы создать запись, "
                "а затем попробуйте рулетку снова. Если проблема повторится, обратитесь к администратору.")
    except Exception as e_apply:
        # ... (существующая обработка) ...
        logger.error(f"Общая ошибка при применении приза рулетки ({prize_category}, {prize_value}) для {user_mention} (user {user_id} chat {chat_id}): {e_apply}", exc_info=True)
        await send_telegram_log(bot_instance,
                                f"🔴 Ошибка General при зачислении приза рулетки для {user_mention} (<code>{user_id}@{chat_id}</code>). "
                                f"Приз: {prize_category} ({prize_value}). Ошибка: <pre>{html.escape(str(e_apply))}</pre>")
        return f"{user_mention}, произошла непредвиденная ошибка при зачислении вашего приза (код R06). Обратитесь к администратору."


@roulette_router.message(Command(*Config.ROULETTE_COMMAND_ALIASES, ignore_case=True))
async def cmd_spin_roulette(message: Message, bot: Bot):
    if not message.from_user:
        await message.reply("Не удалось определить пользователя.")
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    user_tg_username = message.from_user.username
    full_name_from_msg = message.from_user.full_name # Используем это имя
    user_link = get_user_mention_html(user_id, full_name_from_msg, user_tg_username)
    current_time_utc = datetime.now(dt_timezone.utc)

    try:
        # Передаем message.chat вместо message, так как message_chat_obj теперь Chat
        await ensure_user_oneui_record_for_roulette(
            user_id, chat_id, user_tg_username, full_name_from_msg, message.chat, bot 
        )
    except Exception as e_ensure:
        # ... (твоя обработка ошибки, она корректна) ...
        logger.error(f"Roulette: Критическая ошибка во время ensure_user_oneui_record_for_roulette для user {user_id} chat {chat_id}: {e_ensure}", exc_info=True)
        await message.reply("Произошла критическая ошибка подготовки к рулетке (код R00). Попробуйте позже.")
        await send_telegram_log(bot, f"🔴 Критическая ошибка R00 (ensure_user_oneui) для {user_link} (<code>{user_id}@{chat_id}</code>): <pre>{html.escape(str(e_ensure))}</pre>")
        return

    roulette_lock = await get_roulette_lock(user_id, chat_id) # Получаем лок для пользователя и чата
    async with roulette_lock: # Захватываем лок
        try:
            roulette_status_current = await database.get_roulette_status(user_id, chat_id)

            can_spin_now = False
            used_purchased_spin_this_time = False
            time_to_set_for_last_free_spin: Optional[datetime] = current_time_utc

            available_purchased_spins = 0
            if roulette_status_current and roulette_status_current.get('extra_roulette_spins', 0) > 0:
                 available_purchased_spins = roulette_status_current['extra_roulette_spins']

            if available_purchased_spins > 0:
                # ... (твоя логика использования купленного спина, она корректна) ...
                new_purchased_spins_count = available_purchased_spins - 1
                await database.update_roulette_status(user_id, chat_id, {'extra_roulette_spins': new_purchased_spins_count})
                await message.reply(
                    f"🌀 {user_link}, используется <b>купленный спин рулетки</b>! "
                    f"Осталось купленных спинов: {new_purchased_spins_count}."
                )
                can_spin_now = True
                used_purchased_spin_this_time = True
                time_to_set_for_last_free_spin = None # Не обновляем время бесплатного спина
                logger.info(f"User {user_id} in chat {chat_id} used a purchased roulette spin. Remaining: {new_purchased_spins_count}")


            if not can_spin_now: # Если купленный спин не был использован, проверяем обычный кулдаун
                on_cooldown, next_available_utc = await _check_roulette_cooldown(user_id, chat_id, current_time_utc)
                if on_cooldown and next_available_utc:
                    # ... (твоя логика сообщения о кулдауне, она корректна) ...
                    next_available_local = next_available_utc.astimezone(pytz_timezone(Config.TIMEZONE))
                    await message.reply(
                        f"{user_link}, вы сможете снова испытать удачу в рулетке (бесплатно) в этом чате после "
                        f"<b>{next_available_local.strftime('%Y-%m-%d %H:%M')} {Config.TIMEZONE.split('/')[-1]}</b>."
                    )
                    return
                else: # Кулдауна нет
                    can_spin_now = True
            
            if not can_spin_now: # Этого не должно произойти, если логика выше верна
                 logger.warning(f"Roulette: Logic error, user {user_id} chat {chat_id} cannot spin but passed checks.")
                 await message.reply("Не удалось определить возможность вращения рулетки (код R08).")
                 return

            # Отправка сообщения "крутится барабан"
            processing_message = await message.reply(f"🎲 {user_link} запускает рулетку удачи... Посмотрим, что выпадет!")
            await asyncio.sleep(random.uniform(0.8, 2.0)) # Имитация вращения

            # Определение приза
            prize_category, prize_value, prize_log_desc = await _determine_prize()
            
            # >>>>> ИЗМЕНЕНИЕ: Передача новых параметров в _apply_prize_and_get_message <<<<<
            response_text_prize = await _apply_prize_and_get_message(
                user_id, chat_id, prize_category, prize_value, 
                user_link, bot, # bot это bot_instance
                current_time_utc,      # Передаем current_time_utc
                user_tg_username,      # Передаем username
                full_name_from_msg,    # Передаем full_name
                message.chat           # Передаем объект Chat
            )

            final_response_text = f"🎉 Вращение завершено!\n{response_text_prize}"

            try:
                await processing_message.edit_text(final_response_text, parse_mode="HTML", disable_web_page_preview=True)
            except Exception: # Если редактирование не удалось, отправляем новым сообщением
                await message.reply(final_response_text, parse_mode="HTML", disable_web_page_preview=True)

            # Обновляем время последнего *бесплатного* спина, если нужно
            if not used_purchased_spin_this_time and \
               "код R05" not in response_text_prize and \
               "код R00" not in response_text_prize and \
               time_to_set_for_last_free_spin is not None: # Убедимся, что время есть
                 await database.update_roulette_status(user_id, chat_id, {'last_roulette_spin_timestamp': time_to_set_for_last_free_spin})
                 logger.info(f"Roulette: FREE spin time updated for user {user_id} chat {chat_id}.")
            elif used_purchased_spin_this_time:
                 logger.info(f"Roulette: Purchased spin used by {user_id} chat {chat_id}. Free spin cooldown NOT affected.")
            else: # Если была ошибка R05/R00 или time_to_set_for_last_free_spin был None (хотя не должен при бесплатном)
                 logger.warning(f"Roulette: Spin time NOT updated for user {user_id} chat {chat_id} due to prior error or it was a purchased spin and time_to_set was None.")
            
            # Логирование
            chat_title_for_log = html.escape(message.chat.title or f"ChatID {chat_id}")
            spin_type_log = "купленный" if used_purchased_spin_this_time else "бесплатный"
            await send_telegram_log(bot, f"🎰 Рулетка ({spin_type_log} спин) для {user_link} в чате \"{chat_title_for_log}\": выпал приз \"{prize_log_desc}\".")

        except Exception as e:
            # ... (твоя основная обработка ошибок, она корректна) ...
            logger.error(f"Ошибка в команде рулетки для {user_link} в чате {chat_id}: {e}", exc_info=True)
            await message.reply("Ой, что-то пошло не так с рулеткой! Попробуйте чуть позже или свяжитесь с администратором, если проблема повторяется (код R07).")
            await send_telegram_log(bot, f"🔴 Критическая ошибка R07 в рулетке для {user_link} (чат <code>{chat_id}</code>): <pre>{html.escape(str(e))}</pre>")

def setup_roulette_handlers(dp_main: Router): # dp_main или просто dp, как у тебя в main.py
    dp_main.include_router(roulette_router)
    logger.info("Обработчики команд рулетки зарегистрированы.")
