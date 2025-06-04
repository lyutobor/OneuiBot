# reminders_logic.py
import asyncio
import html
import logging
import random # Убедимся, что random импортирован
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import List, Optional

from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import Message
from pytz import timezone as pytz_timezone

from config import Config #
import database
from utils import get_user_mention_html
from business_data import BANK_DATA
from phrases import ONEUI_BLOCKED_PHRASES #

from phone_data import PHONE_MODELS as PHONE_MODELS_STANDARD_LIST_REM
from exclusive_phone_data import EXCLUSIVE_PHONE_MODELS as EXCLUSIVE_PHONE_MODELS_LIST_REM
from item_data import PHONE_COMPONENTS as PHONE_COMPONENTS_REM

PHONE_MODELS_REM = {phone_info["key"]: phone_info for phone_info in PHONE_MODELS_STANDARD_LIST_REM}
EXCLUSIVE_PHONE_MODELS_DICT_REM = {phone_info["key"]: phone_info for phone_info in EXCLUSIVE_PHONE_MODELS_LIST_REM}

logger = logging.getLogger(__name__)
reminders_router = Router()

COMMAND_ALIASES = ["напоминания", "reminders", "todo", "ежедневныезадания", "напомни"]

async def get_chat_specific_reminders_for_user(user_id: int, chat_id: int, bot: Bot) -> List[str]:
    reminders_oneui: List[str] = []
    reminders_onecoin: List[str] = []
    reminders_other: List[str] = []

    now_utc = datetime.now(dt_timezone.utc)
    local_tz = pytz_timezone(Config.TIMEZONE) #
    time_format_for_user = "%d.%m %H:%M %Z"

    # 1. Напоминание для /oneui
    oneui_reminder_message: Optional[str] = None
    oneui_check_failed_critically = False # Флаг для критических ошибок
    try:
        on_cooldown_oneui, next_reset_oneui_utc_cooldown = await database.check_cooldown(user_id, chat_id)

        robbank_status_oneui = await database.get_user_robbank_status(user_id, chat_id)
        robbank_blocked_until_utc: Optional[datetime] = None
        if robbank_status_oneui and robbank_status_oneui.get('robbank_oneui_blocked_until_utc'):
            block_time_val = robbank_status_oneui['robbank_oneui_blocked_until_utc']
            if isinstance(block_time_val, datetime):
                robbank_blocked_until_utc = block_time_val.replace(tzinfo=dt_timezone.utc) if block_time_val.tzinfo is None else block_time_val.astimezone(dt_timezone.utc)

        oneui_block_reason_msg_part = ""
        final_block_time_utc: Optional[datetime] = None

        if robbank_blocked_until_utc and robbank_blocked_until_utc > now_utc:
            final_block_time_utc = robbank_blocked_until_utc
            
            selected_block_phrase_template = random.choice(ONEUI_BLOCKED_PHRASES) #
            simplified_block_phrase = selected_block_phrase_template.split("{streak_info}")[0].strip()
            # Используем .get() для безопасности, если вдруг 'block_time' не будет в .format() некоторых фраз
            oneui_block_reason_msg_part = simplified_block_phrase.format(block_time=robbank_blocked_until_utc.astimezone(local_tz).strftime('%d.%m %H:%M'))
            
            oneui_block_reason_msg_part = oneui_block_reason_msg_part.replace("Ваше использование /oneui", "Команда /oneui")
            oneui_block_reason_msg_part = oneui_block_reason_msg_part.replace("Версия не изменилась.", "").strip()
            oneui_block_reason_msg_part = f" ({oneui_block_reason_msg_part})"

        if on_cooldown_oneui and next_reset_oneui_utc_cooldown:
            if final_block_time_utc:
                final_block_time_utc = max(final_block_time_utc, next_reset_oneui_utc_cooldown)
            else:
                final_block_time_utc = next_reset_oneui_utc_cooldown
        
        if final_block_time_utc and final_block_time_utc > now_utc:
            next_availability_local_str = final_block_time_utc.astimezone(local_tz).strftime(time_format_for_user)
            if "заблокирован" in oneui_block_reason_msg_part.lower():
                 oneui_reminder_message = f"❌ /oneui{oneui_block_reason_msg_part}"
            else:
                 oneui_reminder_message = f"❌ /oneui будет доступен после {next_availability_local_str}."
        else:
            oneui_reminder_message = "✅ /oneui доступен для изменения версии."

    except Exception as e:
        logger.error(f"Reminders: КРИТИЧЕСКАЯ ошибка проверки /oneui для user {user_id} chat {chat_id}: {e}", exc_info=True)
        oneui_check_failed_critically = True # Устанавливаем флаг критической ошибки
    
    if oneui_check_failed_critically:
        reminders_oneui.append("⚠️ Не удалось проверить статус /oneui.")
    elif oneui_reminder_message is not None: # Если сообщение было успешно сформировано (даже если это блокировка)
        reminders_oneui.append(oneui_reminder_message)
    else: # Этого не должно происходить, но на всякий случай
        logger.warning(f"Reminders: oneui_reminder_message остался None для user {user_id} chat {chat_id} без критической ошибки.")
        reminders_oneui.append("⚠️ Не удалось определить статус /oneui (неизвестная причина).")


    # 2. Напоминание для /onecoin
    try:
        last_claim_onecoin_utc = await database.get_user_daily_onecoin_claim_status(user_id, chat_id)
        current_local_time_onecoin = now_utc.astimezone(local_tz)
        effective_current_claim_day_onecoin = current_local_time_onecoin.date()
        if current_local_time_onecoin.hour < Config.RESET_HOUR: #
            effective_current_claim_day_onecoin -= timedelta(days=1)

        can_claim_daily_onecoin = True
        if last_claim_onecoin_utc:
            last_claim_onecoin_local_time = last_claim_onecoin_utc.astimezone(local_tz)
            effective_last_claim_day_onecoin = last_claim_onecoin_local_time.date()
            if last_claim_onecoin_local_time.hour < Config.RESET_HOUR: #
                effective_last_claim_day_onecoin -= timedelta(days=1)
            if effective_last_claim_day_onecoin == effective_current_claim_day_onecoin:
                can_claim_daily_onecoin = False

        if can_claim_daily_onecoin:
            reminders_onecoin.append("✅ /onecoin доступен.")
        else:
            next_reset_onecoin_local = current_local_time_onecoin.replace(hour=Config.RESET_HOUR, minute=0, second=0, microsecond=0) #
            if current_local_time_onecoin.hour >= Config.RESET_HOUR: #
                next_reset_onecoin_local += timedelta(days=1)
            reminders_onecoin.append(f"❌ /onecoin будет доступен после {next_reset_onecoin_local.strftime(time_format_for_user)}.")
    except Exception as e:
        logger.error(f"Reminders: Ошибка проверки /onecoin для user {user_id} chat {chat_id}: {e}")
        reminders_onecoin.append("⚠️ Не удалось проверить статус /onecoin.")

    # 3. Напоминание для /bonus
    try:
        can_claim_bonus = True
        last_global_reset_bonus_utc = await database.get_setting_timestamp('last_global_bonus_multiplier_reset')
        if not last_global_reset_bonus_utc:
            last_global_reset_bonus_utc = now_utc - timedelta(days=(Config.BONUS_MULTIPLIER_COOLDOWN_DAYS * 2)) #

        user_bonus_status = await database.get_user_bonus_multiplier_status(user_id, chat_id)
        if user_bonus_status and user_bonus_status.get('last_claimed_timestamp'):
            last_claimed_ts_bonus_aware = user_bonus_status['last_claimed_timestamp']
            if last_claimed_ts_bonus_aware.tzinfo is None:
                last_claimed_ts_bonus_aware = last_claimed_ts_bonus_aware.replace(tzinfo=dt_timezone.utc)
            if last_global_reset_bonus_utc.tzinfo is None:
                last_global_reset_bonus_utc = last_global_reset_bonus_utc.replace(tzinfo=dt_timezone.utc)

            if last_claimed_ts_bonus_aware.astimezone(dt_timezone.utc) >= last_global_reset_bonus_utc.astimezone(dt_timezone.utc):
                can_claim_bonus = False

        user_roulette_status_bonus = await database.get_roulette_status(user_id, chat_id)
        available_extra_bonus_attempts = 0
        if user_roulette_status_bonus and user_roulette_status_bonus.get('extra_bonus_attempts', 0) > 0:
            available_extra_bonus_attempts = user_roulette_status_bonus['extra_bonus_attempts']
            can_claim_bonus = True

        if can_claim_bonus:
            bonus_msg = "✅ /bonus доступен."
            if available_extra_bonus_attempts > 0:
                bonus_msg += f" (Есть {available_extra_bonus_attempts} доп. попыток)"
            reminders_other.append(bonus_msg)
        else:
            effective_next_reset_bonus_utc = last_global_reset_bonus_utc
            while effective_next_reset_bonus_utc.astimezone(dt_timezone.utc) <= now_utc:
                 effective_next_reset_bonus_utc += timedelta(days=Config.BONUS_MULTIPLIER_COOLDOWN_DAYS) #

            next_reset_bonus_local = effective_next_reset_bonus_utc.astimezone(local_tz).replace(
                hour=Config.BONUS_MULTIPLIER_RESET_HOUR, minute=2, second=0, microsecond=0 #
            )
            while next_reset_bonus_local.astimezone(dt_timezone.utc) <= now_utc:
                 next_reset_bonus_local += timedelta(days=Config.BONUS_MULTIPLIER_COOLDOWN_DAYS) #
            reminders_other.append(f"❌ /bonus будет доступен после {next_reset_bonus_local.strftime(time_format_for_user)}.")
    except Exception as e:
        logger.error(f"Reminders: Ошибка проверки /bonus для user {user_id} chat {chat_id}: {e}")
        reminders_other.append("⚠️ Не удалось проверить статус /bonus.")

    # 4. Напоминание для /roulette
    try:
        roulette_can_spin_free = True
        roulette_status_cooldown = await database.get_roulette_status(user_id, chat_id)
        available_extra_roulette_spins = 0
        if roulette_status_cooldown:
            available_extra_roulette_spins = roulette_status_cooldown.get('extra_roulette_spins', 0)

        last_global_reset_roulette_utc = await database.get_setting_timestamp('last_global_roulette_period_reset')
        if not last_global_reset_roulette_utc:
            last_global_reset_roulette_utc = now_utc - timedelta(days=(Config.ROULETTE_GLOBAL_COOLDOWN_DAYS * 5)) #

        last_spin_chat_utc: Optional[datetime] = None
        if roulette_status_cooldown and roulette_status_cooldown.get('last_roulette_spin_timestamp'):
            last_spin_val = roulette_status_cooldown['last_roulette_spin_timestamp']
            if isinstance(last_spin_val, datetime):
                if last_spin_val.tzinfo is None:
                            last_spin_chat_utc = last_spin_val.replace(tzinfo=dt_timezone.utc)
                else:
                            last_spin_chat_utc = last_spin_val.astimezone(dt_timezone.utc)
            else:
                logger.warning(f"Некорректный тип last_roulette_spin_timestamp ({type(last_spin_val)}) для user {user_id}@{chat_id}")


        if last_spin_chat_utc and last_spin_chat_utc >= last_global_reset_roulette_utc.astimezone(dt_timezone.utc):
            roulette_can_spin_free = False

        roulette_reminder_msg = ""
        if roulette_can_spin_free:
            roulette_reminder_msg = "✅ /roulette доступен."
            if available_extra_roulette_spins > 0:
                roulette_reminder_msg += f" (Также есть {available_extra_roulette_spins} купленных)"
            reminders_other.append(roulette_reminder_msg)
        elif available_extra_roulette_spins > 0:
             reminders_other.append(f"✅ /roulette доступен (есть {available_extra_roulette_spins} купленных спинов). Бесплатный будет позже.")
        else:
            effective_next_reset_roulette_utc = last_global_reset_roulette_utc
            while effective_next_reset_roulette_utc.astimezone(dt_timezone.utc) <= now_utc:
                 effective_next_reset_roulette_utc += timedelta(days=Config.ROULETTE_GLOBAL_COOLDOWN_DAYS) #

            next_reset_roulette_local = effective_next_reset_roulette_utc.astimezone(local_tz).replace(
                hour=Config.RESET_HOUR, minute=4, second=0, microsecond=0 #
            )
            while next_reset_roulette_local.astimezone(dt_timezone.utc) <= now_utc:
                next_reset_roulette_local += timedelta(days=Config.ROULETTE_GLOBAL_COOLDOWN_DAYS) #
            reminders_other.append(f"❌ /roulette будет доступен после {next_reset_roulette_local.strftime(time_format_for_user)}.")
    except Exception as e:
        logger.error(f"Reminders: Ошибка проверки /roulette для user {user_id} chat {chat_id}: {e}")
        reminders_other.append("⚠️ Не удалось проверить статус /roulette.")

    # 5. Напоминание про Черный Рынок (/bm)
    try:
        streak_data_bm = await database.get_user_daily_streak(user_id, chat_id)
        current_streak_bm = 0
        if streak_data_bm and streak_data_bm.get('last_streak_check_date'):
            today_local_date_bm = now_utc.astimezone(local_tz).date()
            last_check_date_bm_val = streak_data_bm['last_streak_check_date']
            if isinstance(last_check_date_bm_val, datetime):
                last_check_date_bm_val = last_check_date_bm_val.date()

            if last_check_date_bm_val == today_local_date_bm or last_check_date_bm_val == (today_local_date_bm - timedelta(days=1)):
                current_streak_bm = streak_data_bm.get('current_streak', 0)

        if current_streak_bm >= Config.BLACKMARKET_ACCESS_STREAK_REQUIREMENT: #
            user_bm_offers = await database.get_user_black_market_slots(user_id)
            bm_reset_hour_local = Config.BLACKMARKET_RESET_HOUR #

            current_period_start_bm_local = now_utc.astimezone(local_tz).replace(hour=bm_reset_hour_local, minute=0, second=0, microsecond=0)
            if now_utc.astimezone(local_tz).hour < bm_reset_hour_local:
                current_period_start_bm_local -= timedelta(days=1)
            current_period_start_bm_utc = current_period_start_bm_local.astimezone(dt_timezone.utc)

            bm_slots_are_current = False
            if user_bm_offers:
                first_slot_generated_at_bm = user_bm_offers[0].get('generated_at_utc')
                if first_slot_generated_at_bm and isinstance(first_slot_generated_at_bm, datetime):
                    first_slot_generated_at_bm_aware = first_slot_generated_at_bm.replace(tzinfo=dt_timezone.utc) if first_slot_generated_at_bm.tzinfo is None else first_slot_generated_at_bm.astimezone(dt_timezone.utc)
                    if first_slot_generated_at_bm_aware >= current_period_start_bm_utc:
                        bm_slots_are_current = True

            if bm_slots_are_current:
                reminders_other.append(f"✅ Черный Рынок (/bm) ждет! (Товары уже обновлены)")
            else:
                reminders_other.append(f"✅ Загляни на Черный Рынок (/bm)! Обновится при первом входе после {bm_reset_hour_local:02d}:00 {local_tz.zone}.") # type: ignore
    except Exception as e:
        logger.error(f"Reminders: Ошибка проверки /bm для user {user_id} chat {chat_id}: {e}")
        reminders_other.append("⚠️ Не удалось проверить статус Черного Рынка (/bm).")

    # 6. Напоминание о банке (если есть бизнесы и деньги в банке)
    try:
        user_businesses = await database.get_user_businesses(user_id, chat_id)
        if user_businesses:
            user_bank_data = await database.get_user_bank(user_id, chat_id)
            if user_bank_data and user_bank_data.get('current_balance', 0) > 0:
                bank_balance_rem = user_bank_data.get('current_balance', 0)
                bank_level_rem = user_bank_data.get('bank_level', 0)
                bank_static_info_rem = BANK_DATA.get(bank_level_rem, BANK_DATA.get(0))
                bank_capacity_rem = bank_static_info_rem.get('max_capacity', 0) if bank_static_info_rem else 0

                bank_details_str = ""
                if bank_capacity_rem > 0:
                    bank_fill_percentage = (bank_balance_rem / bank_capacity_rem * 100) if bank_capacity_rem > 0 else 0
                    bank_details_str = f"{bank_fill_percentage:.0f}% (<code>{bank_balance_rem:,}</code> / {bank_capacity_rem:,} OC)"
                else:
                    bank_details_str = f"(<code>{bank_balance_rem:,}</code> OC, вместимость не определена)"

                reminders_other.append(f"💰 В банке {bank_details_str}. \n     └ Вывод: <code>/withdrawbank all</code>")
            elif not user_bank_data or user_bank_data.get('current_balance', 0) == 0 :
                 reminders_other.append(f"🏦 Твой банк (<code>/mybank</code>) пока пуст. Доход с бизнесов зачисляется туда автоматически.")
    except Exception as e:
        logger.error(f"Reminders: Ошибка проверки бизнесов/банка для user {user_id} chat {chat_id}: {e}")
        reminders_other.append("⚠️ Не удалось проверить статус бизнесов и банка.")

    return reminders_oneui + reminders_onecoin + reminders_other


async def get_global_phone_reminders_for_user(user_id: int, bot: Bot) -> List[str]:
    """
    Собирает ОБЩИЕ напоминания по всем телефонам пользователя (зарядка, страховка).
    """
    global_phone_reminders: List[str] = []
    now_utc = datetime.now(dt_timezone.utc)

    try:
        user_phones = await database.get_user_phones(user_id, active_only=True)
        if not user_phones:
            return []

        for phone in user_phones:
            phone_id_rem = phone.get('phone_inventory_id')
            phone_name_rem = "Телефон"
            phone_model_key_rem = phone.get('phone_model_key')

            if phone_model_key_rem:
                phone_static_info_rem = PHONE_MODELS_REM.get(phone_model_key_rem)
                if phone_static_info_rem:
                    phone_name_rem = phone_static_info_rem.get('name', phone_model_key_rem)
                else:
                    phone_exclusive_info_rem = EXCLUSIVE_PHONE_MODELS_DICT_REM.get(phone_model_key_rem)
                    if phone_exclusive_info_rem:
                        phone_name_rem = phone_exclusive_info_rem.get('name', phone_model_key_rem)
                    else:
                        phone_name_rem = phone_model_key_rem

            battery_dead_after_utc_rem_val = phone.get('battery_dead_after_utc')
            if battery_dead_after_utc_rem_val and isinstance(battery_dead_after_utc_rem_val, datetime):
                battery_dead_after_utc_aware_rem = battery_dead_after_utc_rem_val.replace(tzinfo=dt_timezone.utc) if battery_dead_after_utc_rem_val.tzinfo is None else battery_dead_after_utc_rem_val.astimezone(dt_timezone.utc)
                if now_utc >= battery_dead_after_utc_aware_rem:
                    is_broken_rem = phone.get('is_broken', False)
                    broken_comp_key_rem = phone.get('broken_component_key')
                    is_battery_broken_rem = False
                    if is_broken_rem and broken_comp_key_rem:
                        comp_info_rem = PHONE_COMPONENTS_REM.get(broken_comp_key_rem)
                        if comp_info_rem and comp_info_rem.get('component_type') == 'battery':
                            is_battery_broken_rem = True

                    if not is_battery_broken_rem:
                        global_phone_reminders.append(f"Телефон \"{html.escape(phone_name_rem)}\" (ID: {phone_id_rem})\n     └ разряжен (0%)! (<code>/chargephone {phone_id_rem}</code>)")

            insurance_until_utc_rem_val = phone.get('insurance_active_until')
            if insurance_until_utc_rem_val and isinstance(insurance_until_utc_rem_val, datetime):
                insurance_until_utc_aware_rem = insurance_until_utc_rem_val.replace(tzinfo=dt_timezone.utc) if insurance_until_utc_rem_val.tzinfo is None else insurance_until_utc_rem_val.astimezone(dt_timezone.utc)
                remind_days = getattr(Config, "PHONE_INSURANCE_REMIND_DAYS_BEFORE", 3)
                if now_utc >= insurance_until_utc_aware_rem:
                    global_phone_reminders.append(f"📄 Страховка \"{html.escape(phone_name_rem)}\" (ID: {phone_id_rem}) истекла! (<code>/insurephone {phone_id_rem}</code>)")
                elif (insurance_until_utc_aware_rem - now_utc).days < remind_days :
                    global_phone_reminders.append(f"📄 Страховка \"{html.escape(phone_name_rem)}\" (ID: {phone_id_rem}) скоро истекает! (<code>/insurephone {phone_id_rem}</code>)")
    except Exception as e:
        logger.error(f"Reminders: Ошибка проверки глобальных напоминаний по телефонам для user {user_id}: {e}")
        global_phone_reminders.append("⚠️ Не удалось проверить статус телефонов.")

    return global_phone_reminders

async def get_global_family_reminders_for_user(user_id: int, bot: Bot) -> List[str]:
    """
    Собирает ОБЩЕЕ напоминание по семье/клану пользователя.
    """
    global_family_reminders: List[str] = []
    try:
        family_membership = await database.get_user_family_membership(user_id)
        if family_membership:
            family_name_ally = html.escape(family_membership.get('family_name', 'Неизвестный клан'))

            reminder_text = f"👪 Семья: <b>{family_name_ally}</b>"

            active_comp = await database.get_active_family_competition()
            if active_comp:
                reminder_text += f" 🏆 Идет соревнование"

            global_family_reminders.append(reminder_text)
    except Exception as e:
        logger.error(f"Reminders: Ошибка проверки глобального напоминания по семье для user {user_id}: {e}")
        global_family_reminders.append("⚠️ Не удалось проверить статус клана.")
    return global_family_reminders


@reminders_router.message(Command(*COMMAND_ALIASES, ignore_case=True))
async def cmd_show_reminders(message: Message, bot: Bot):
    if not message.from_user:
        await message.reply("Не могу определить пользователя.", disable_web_page_preview=True)
        return

    user_id = message.from_user.id
    user_link = get_user_mention_html(user_id, message.from_user.full_name, message.from_user.username)

    processing_msg = await message.reply(f"⏳ {user_link}, собираю твои напоминания...", disable_web_page_preview=True)

    all_reminders_text_parts: List[str] = []
    any_reminders_found_globally_or_in_chat = False
    active_chat_ids_for_dm: List[int] = []

    try:
        if message.chat.type == "private":
            active_chat_ids_for_dm = await database.get_all_user_activity_chats(user_id)

            if not active_chat_ids_for_dm:
                all_reminders_text_parts.append(f"📌 {user_link}, у тебя пока нет активностей ни в одном из отслеживаемых чатов.")
            else:
                all_reminders_text_parts.append(f"📌 {user_link}, вот твои напоминания:")

                chat_infos = {}
                for chat_id_db_loop in active_chat_ids_for_dm:
                    try:
                        chat_obj = await bot.get_chat(chat_id_db_loop)
                        chat_infos[chat_id_db_loop] = chat_obj
                    except Exception:
                        chat_infos[chat_id_db_loop] = None

                for chat_id_from_db in active_chat_ids_for_dm:
                    chat_display_name = f"Чат ID: {chat_id_from_db}"
                    chat_info = chat_infos.get(chat_id_from_db)

                    if chat_info:
                        if chat_info.title:
                            chat_display_name = html.escape(chat_info.title)
                        elif chat_info.username:
                            chat_display_name = f"@{chat_info.username}"
                        elif chat_info.type == "private" and chat_id_from_db == user_id:
                             chat_display_name = "Личные сообщения (с этим ботом)"

                    reminders_for_chat = await get_chat_specific_reminders_for_user(user_id, chat_id_from_db, bot)
                    if reminders_for_chat:
                        any_reminders_found_globally_or_in_chat = True
                        all_reminders_text_parts.append(f"\n\n🔔<b>В чате {chat_display_name}:</b>")
                        all_reminders_text_parts.extend([f"  • {reminder}" for reminder in reminders_for_chat])

            global_family_reminders_list = await get_global_family_reminders_for_user(user_id, bot)
            if global_family_reminders_list:
                any_reminders_found_globally_or_in_chat = True
                all_reminders_text_parts.append("\n\n🤝 <b>Альянс:</b>")
                all_reminders_text_parts.extend([f"  • {reminder}" for reminder in global_family_reminders_list])

            global_phone_reminders_list = await get_global_phone_reminders_for_user(user_id, bot)
            if global_phone_reminders_list:
                any_reminders_found_globally_or_in_chat = True
                all_reminders_text_parts.append("\n\n📱 <b>Общие по телефонам:</b>")
                all_reminders_text_parts.extend([f"  • {reminder}" for reminder in global_phone_reminders_list])

            if active_chat_ids_for_dm and not any_reminders_found_globally_or_in_chat :
                 all_reminders_text_parts.append("\nПохоже, на сегодня важных напоминаний нет.")

        else:
            current_chat_id = message.chat.id
            reminders_list_chat_specific = await get_chat_specific_reminders_for_user(user_id, current_chat_id, bot)

            global_family_reminders_list_group = await get_global_family_reminders_for_user(user_id, bot)
            global_phone_reminders_list_group = await get_global_phone_reminders_for_user(user_id, bot)

            if not reminders_list_chat_specific and not global_family_reminders_list_group and not global_phone_reminders_list_group:
                all_reminders_text_parts.append(f"📌 {user_link}, на сегодня важных напоминаний нет. Возможно, все уже сделано или сегодня просто выходной! 🎉")
            else:
                any_reminders_found_globally_or_in_chat = True
                all_reminders_text_parts.append(f"📌 {user_link}, вот твои актуальные напоминания:\n")

                if reminders_list_chat_specific:
                    all_reminders_text_parts.append("🔔 <b>В этом чате:</b>")
                    all_reminders_text_parts.extend([f"  • {reminder}" for reminder in reminders_list_chat_specific])

                if global_family_reminders_list_group:
                    if reminders_list_chat_specific: all_reminders_text_parts.append("")
                    all_reminders_text_parts.append("🤝 <b>Альянс:</b>")
                    all_reminders_text_parts.extend([f"  • {reminder}" for reminder in global_family_reminders_list_group])

                if global_phone_reminders_list_group:
                    if reminders_list_chat_specific or global_family_reminders_list_group: all_reminders_text_parts.append("")
                    all_reminders_text_parts.append("📱 <b>Общие по телефонам:</b>")
                    all_reminders_text_parts.extend([f"  • {reminder}" for reminder in global_phone_reminders_list_group])

            all_reminders_text_parts.append("\n💡 Используй <code>/напомни</code> в личных сообщениях со мной, увидеть напоминания по всем чатам")

        if all_reminders_text_parts:
            if any_reminders_found_globally_or_in_chat:
                 all_reminders_text_parts.append("\n\n<i>Абоба</i>")
            elif message.chat.type == "private" and not any_reminders_found_globally_or_in_chat and active_chat_ids_for_dm:
                 all_reminders_text_parts.append("\n\n<i>Удачи в твоих начинаниях!</i>")

        response_text = "\n".join(all_reminders_text_parts)

        MAX_MESSAGE_LENGTH = 4096
        if len(response_text) > MAX_MESSAGE_LENGTH:
            parts_to_send = []
            current_part = ""
            for line in response_text.split('\n'):
                if len(current_part) + len(line) + 1 > MAX_MESSAGE_LENGTH:
                    if current_part: parts_to_send.append(current_part)
                    current_part = line
                else:
                    if current_part: current_part += "\n" + line
                    else: current_part = line
            if current_part: parts_to_send.append(current_part)

            if processing_msg:
                try: await processing_msg.delete()
                except Exception: pass

            for i, part_msg_text in enumerate(parts_to_send):
                if part_msg_text.strip():
                    if i == 0:
                        await message.reply(part_msg_text, parse_mode="HTML", disable_web_page_preview=True)
                    else:
                        await message.answer(part_msg_text, parse_mode="HTML", disable_web_page_preview=True)
                    await asyncio.sleep(0.2)
        else:
            if processing_msg:
                await processing_msg.edit_text(response_text, parse_mode="HTML", disable_web_page_preview=True)
            else:
                await message.reply(response_text, parse_mode="HTML", disable_web_page_preview=True)

    except Exception as e:
        logger.error(f"Ошибка в /напоминания для {user_link} (чат: {message.chat.id}): {e}", exc_info=True)
        err_msg_fallback = "Произошла ошибка при формировании напоминаний. Попробуйте позже."
        if processing_msg:
            try: await processing_msg.edit_text(err_msg_fallback, disable_web_page_preview=True)
            except: await message.reply(err_msg_fallback, disable_web_page_preview=True)
        else:
            await message.reply(err_msg_fallback, disable_web_page_preview=True)


def setup_reminders_handlers(dp: Router):
    dp.include_router(reminders_router)
    logger.info("Обработчики команды /напоминания зарегистрированы.")
