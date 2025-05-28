import html
import logging
from typing import Optional, Tuple, List, Dict, Any # Добавлены List, Dict, Any
from datetime import datetime, timedelta, timezone as dt_timezone # Добавлен dt_timezone, timedelta

from aiogram import F, Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from aiogram.utils.markdown import hlink
from pytz import timezone as pytz_timezone

import database
from config import Config
from utils import get_user_mention_html, send_telegram_log, fetch_user_display_data, resolve_target_user
from business_data import BANK_DATA, BUSINESS_DATA, BUSINESS_UPGRADES
from phone_data import PHONE_MODELS as PHONE_MODELS_STANDARD_LIST
from exclusive_phone_data import EXCLUSIVE_PHONE_MODELS as EXCLUSIVE_PHONE_MODELS_LIST
from item_data import PHONE_COMPONENTS, PHONE_CASES

logger = logging.getLogger(__name__)
stats_router = Router()

PHONE_MODELS_STD_DICT_STATS = {p["key"]: p for p in PHONE_MODELS_STANDARD_LIST}
EXCLUSIVE_PHONE_MODELS_DICT_STATS = {p["key"]: p for p in EXCLUSIVE_PHONE_MODELS_LIST}

def _format_time_delta(seconds: float) -> str:
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)
    parts = []
    if int(days) > 0: parts.append(f"{int(days)}д")
    if int(hours) > 0: parts.append(f"{int(hours)}ч")
    if (int(days) == 0 and int(hours) == 0 and int(minutes) >= 0) or int(minutes) > 0:
        parts.append(f"{int(minutes)}м")
    return " ".join(parts) if parts else "меньше минуты"

async def _get_formatted_stats(target_user_id: int, target_chat_id: int, bot_instance: Bot, for_self: bool = True) -> str:
    target_full_name, target_username = await fetch_user_display_data(bot_instance, target_user_id)
    target_user_link = get_user_mention_html(target_user_id, target_full_name, target_username)
    local_tz = pytz_timezone(Config.TIMEZONE)
    now_utc = datetime.now(dt_timezone.utc)

    response_lines = [f"📊 <b>Сводка оперативника {target_user_link}</b>"]

    selected_achievement_key = await database.get_user_selected_achievement(target_user_id)
    title_display = "<i>Титул не выбран</i>"
    if selected_achievement_key:
        ach_info = Config.ACHIEVEMENTS_DATA.get(selected_achievement_key)
        if ach_info:
            title_display = f"<i>Титул: {ach_info['icon']} «{ach_info['name']}»</i>"
        else:
            title_display = "<i>Титул: Неизвестный</i>"
    response_lines.append(title_display)

    response_lines.append("\n════⚔️ <b>Боеготовность</b> ⚔️════")

    current_version_chat = await database.get_user_version(target_user_id, target_chat_id)
    max_version_data = await database.get_user_max_version_global_with_chat_info(target_user_id)
    max_v_global_display = "N/A"
    if max_version_data and max_version_data.get('version') is not None:
        max_v_global_display = f"{float(max_version_data['version']):.1f}"
    response_lines.append(f"💻 OneUI (локально): <code>{current_version_chat:.1f}</code> | Макс. Глобально: <code>{max_v_global_display}</code>")

    streak_data = await database.get_user_daily_streak(target_user_id, target_chat_id)
    current_streak_val = 0
    streak_bonus_info = ""
    if streak_data:
        today_local_date = now_utc.astimezone(local_tz).date()
        last_check_date_db = streak_data.get('last_streak_check_date')
        if last_check_date_db and (last_check_date_db == today_local_date or last_check_date_db == (today_local_date - timedelta(days=1))):
            current_streak_val = streak_data.get('current_streak', 0)
    if current_streak_val > 0:
         next_goal_info = next((goal for goal in Config.DAILY_STREAKS_CONFIG if goal['target_days'] > current_streak_val), None)
         if next_goal_info:
             streak_bonus_info = f"(Цель: {next_goal_info['name']} - еще {next_goal_info['target_days'] - current_streak_val} д.)"
         elif Config.DAILY_STREAKS_CONFIG and current_streak_val >= Config.DAILY_STREAKS_CONFIG[-1]['target_days']:
              streak_bonus_info = f"({Config.DAILY_STREAKS_CONFIG[-1]['name']}!)"
    response_lines.append(f"🔥 Стрик Активности: <b>{current_streak_val}</b> д. {streak_bonus_info}")

    onecoins_chat = await database.get_user_onecoins(target_user_id, target_chat_id)
    response_lines.append(f"💰 Боевой Фонд (OneCoin): <code>{onecoins_chat:,}</code>")

    user_bank_data = await database.get_user_bank(target_user_id, target_chat_id)
    bank_level = user_bank_data['bank_level'] if user_bank_data else 0
    bank_balance = user_bank_data['current_balance'] if user_bank_data else 0
    bank_info_static = BANK_DATA.get(bank_level)
    bank_name_display = html.escape(bank_info_static['name']) if bank_info_static else "Копилка"
    bank_max_capacity = bank_info_static['max_capacity'] if bank_info_static else 0
    bank_fill_percentage = (bank_balance / bank_max_capacity * 100) if bank_max_capacity > 0 else 0
    
    def format_large_number(num):
        if num >= 1_000_000_000: return f"{num / 1_000_000_000:.1f}B"
        if num >= 1_000_000: return f"{num / 1_000_000:.1f}M"
        if num >= 1_000: return f"{num / 1_000:.1f}K"
        return str(num)
    response_lines.append(f"🛡️ Защита Банка: \"{bank_name_display}\" (Ур. {bank_level}) - <code>{format_large_number(bank_balance)}</code>/<code>{format_large_number(bank_max_capacity)}</code> OC ({bank_fill_percentage:.0f}%)")

    response_lines.append("\n════🛠️ <b>Арсенал</b> 🛠️════")
    user_active_phones = await database.get_user_phones(target_user_id, active_only=True)
    active_phones_count = len(user_active_phones)
    response_lines.append(f"📱 Телефоны ({active_phones_count}/{Config.MAX_PHONES_PER_USER}):")
    if user_active_phones:
        for idx, phone_db in enumerate(user_active_phones):
            phone_key = phone_db['phone_model_key']
            phone_inventory_id = phone_db['phone_inventory_id']
            is_contraband = phone_db.get('is_contraband', False)
            phone_data_json = phone_db.get('data', {}) or {}

            phone_name_display = f"Неизвестный ({html.escape(phone_key)})"
            phone_static_info_lookup = PHONE_MODELS_STD_DICT_STATS.get(phone_key) or EXCLUSIVE_PHONE_MODELS_DICT_STATS.get(phone_key)
            if phone_static_info_lookup:
                phone_name_display = html.escape(phone_static_info_lookup.get('display_name', phone_static_info_lookup.get('name', phone_key)))
            elif phone_data_json.get('display_name_override'):
                phone_name_display = html.escape(phone_data_json['display_name_override'])

            contraband_icon = "🥷 " if is_contraband else ""
            current_memory_gb = phone_db.get('current_memory_gb')
            if current_memory_gb is None and phone_static_info_lookup:
                memory_str_static = phone_static_info_lookup.get('memory', '0').upper()
                if 'TB' in memory_str_static: current_memory_gb = int(float(memory_str_static.replace('TB', '').strip()) * 1024)
                elif 'GB' in memory_str_static: current_memory_gb = int(float(memory_str_static.replace('GB', '').strip()))
            current_memory_display = f"{current_memory_gb}GB" if isinstance(current_memory_gb, int) else "N/A"
            if isinstance(current_memory_gb, int) and current_memory_gb >= 1024 and current_memory_gb % 1024 == 0:
                 current_memory_display = f"{current_memory_gb // 1024}TB"
            response_lines.append(f"  {idx+1}. {contraband_icon}<b>{phone_name_display}</b> ({current_memory_display}) (ID: <code>{phone_inventory_id}</code>)")

            properties_parts = []
            status_parts = []
            if is_contraband:
                if phone_data_json.get("custom_bonus_description"):
                    properties_parts.append(html.escape(phone_data_json['custom_bonus_description']))
                elif phone_data_json.get("bm_description"):
                    properties_parts.append(html.escape(phone_data_json['bm_description'].split('.')[0]))

            last_charged_utc = phone_db.get('last_charged_utc')
            battery_dead_after_utc = phone_db.get('battery_dead_after_utc')
            battery_break_after_utc = phone_db.get('battery_break_after_utc')
            battery_str = "Заряд N/A"
            if isinstance(last_charged_utc, datetime) and isinstance(battery_dead_after_utc, datetime):
                if last_charged_utc.tzinfo is None: last_charged_utc = last_charged_utc.replace(tzinfo=dt_timezone.utc)
                if battery_dead_after_utc.tzinfo is None: battery_dead_after_utc = battery_dead_after_utc.replace(tzinfo=dt_timezone.utc)
                if now_utc < battery_dead_after_utc:
                    remaining_seconds = (battery_dead_after_utc - now_utc).total_seconds()
                    total_duration = (battery_dead_after_utc - last_charged_utc).total_seconds()
                    percentage = int(remaining_seconds / total_duration * 100) if total_duration > 0 else 100
                    battery_str = f"🔋{percentage}%"
                else:
                    battery_str = "🔋Разряжен"
                    if isinstance(battery_break_after_utc, datetime):
                        if battery_break_after_utc.tzinfo is None: battery_break_after_utc = battery_break_after_utc.replace(tzinfo=dt_timezone.utc)
                        if now_utc >= battery_break_after_utc:
                            battery_str = "‼️АКБ Сломан"
            status_parts.append(battery_str)

            if phone_db.get('is_broken'):
                broken_comp_key = phone_db.get('broken_component_key')
                broken_comp_info = PHONE_COMPONENTS.get(broken_comp_key, {})
                if not (broken_comp_info.get('component_type') == 'battery' and "Сломан" in battery_str):
                    status_parts.append(f"⚠️Сломан: {html.escape(broken_comp_info.get('name', '?'))}")
            
            equipped_case_key = phone_db.get('equipped_case_key')
            if equipped_case_key:
                case_name = PHONE_CASES.get(equipped_case_key, {}).get('name', 'Чехол')
                status_parts.append(f"🛡️{html.escape(case_name.split(' ')[0])}")
            
            insurance_until = phone_db.get('insurance_active_until')
            if isinstance(insurance_until, datetime):
                if insurance_until.tzinfo is None: insurance_until = insurance_until.replace(tzinfo=dt_timezone.utc)
                if now_utc < insurance_until:
                    status_parts.append("📄✅Застрахован")
            
            if properties_parts:
                 response_lines.append(f"    └ <i>Свойства: {'; '.join(properties_parts)}</i>")
            if status_parts:
                 response_lines.append(f"    └ <i>Статус: {', '.join(status_parts)}.</i>")
    else:
        response_lines.append("  <i>Арсенал пуст.</i>")

    response_lines.append("\n════🏭 <b>Производство</b> 🏭════")
    user_businesses_chat = await database.get_user_businesses(target_user_id, target_chat_id)
    businesses_count_chat = len(user_businesses_chat)
    response_lines.append(f"🏢 Бизнес-мощности (в этом секторе): {businesses_count_chat}/{Config.BUSINESS_MAX_PER_USER_PER_CHAT}")
    if user_businesses_chat:
        for biz_db in user_businesses_chat:
            biz_key = biz_db['business_key']
            biz_level = biz_db['current_level']
            staff_hired = biz_db.get('staff_hired_slots', 0)

            biz_name_override = biz_db.get('name_override')
            biz_static_data = BUSINESS_DATA.get(biz_key)
            level_static_data = biz_static_data['levels'].get(biz_level) if biz_static_data else None

            biz_name_display = f"Н/Д ({html.escape(biz_key)})"
            max_staff = 0
            base_income_hr = 0

            if biz_name_override: biz_name_display = html.escape(biz_name_override)
            elif level_static_data: biz_name_display = html.escape(level_static_data.get('display_name', biz_static_data['name']))
            elif biz_static_data: biz_name_display = html.escape(biz_static_data.get('name', biz_key))

            if level_static_data:
                max_staff = level_static_data.get('max_staff_slots', 0)
                base_income_hr = level_static_data.get('base_income_per_hour', 0)
            
            response_lines.append(f"  - \"{biz_name_display}\" (Ур.{biz_level}) | Доход: ~{base_income_hr} OC/ч | Персонал: {staff_hired}/{max_staff}")
    else:
        response_lines.append("  <i>Производственные мощности отсутствуют.</i>")

    response_lines.append("\n════🤝 <b>Альянс</b> 🤝════")
    family_membership = await database.get_user_family_membership(target_user_id)
    if family_membership:
        family_name_ally = html.escape(family_membership.get('family_name', 'Неизвестный клан'))
        role_ally = "👑 Лидер" if family_membership.get('leader_id') == target_user_id else "Боец"
        family_members_ally = await database.get_family_members(family_membership['family_id'])
        member_count_ally = len(family_members_ally)
        response_lines.append(f"👪 Клан: <b>{family_name_ally}</b> | Роль: {role_ally} | Бойцы: {member_count_ally}/{Config.FAMILY_MAX_MEMBERS}")
    else:
        response_lines.append("👪 Состоит: Вне клана")
    
    

    return "\n".join(response_lines)


@stats_router.message(Command("стата", "статистика", ignore_case=True))
async def cmd_general_stats_handler(message: Message, command: CommandObject, bot: Bot):
    # 1. Определяем пользователя, вызвавшего команду
    if not message.from_user:
        await message.reply("Не удалось определить пользователя.", disable_web_page_preview=True)
        return

    calling_user_id = message.from_user.id # ID того, кто написал /стата
    current_chat_id = message.chat.id

    # 2. Проверяем, есть ли аргументы у команды или это ответ на сообщение
    has_args = bool(command.args)
    is_reply = bool(message.reply_to_message and message.reply_to_message.from_user and not message.reply_to_message.from_user.is_bot)

    user_to_display_id: Optional[int] = None
    user_to_display_name: Optional[str] = None
    user_to_display_username: Optional[str] = None
    display_for_self = True # По умолчанию, предполагаем, что пользователь смотрит свою стату

    # 3. Логика определения ID пользователя, чью статистику нужно показать
    if has_args or is_reply:
        # Если есть аргументы (например, /стата @username) или это ответ на сообщение,
        # то пытаемся определить целевого пользователя с помощью resolve_target_user
        target_user_data = await resolve_target_user(message, command, bot)
        if target_user_data:
            user_to_display_id, user_to_display_name, user_to_display_username = target_user_data
            display_for_self = (user_to_display_id == calling_user_id)
            # Проверка, не является ли целевой пользователь ботом
            if not display_for_self: # Только если смотрим не свою стату
                try:
                    target_chat_obj = await bot.get_chat(user_to_display_id)
                    if hasattr(target_chat_obj, 'is_bot') and target_chat_obj.is_bot:
                        await message.reply("Нельзя посмотреть статистику бота.", disable_web_page_preview=True)
                        return
                except Exception:
                    pass # Если не удалось проверить, просто продолжаем
        else:
            # Если resolve_target_user не смог определить пользователя (например, юзер не найден)
            if is_reply and not has_args: # Конкретное сообщение об ошибке для ответа на сообщение
                await message.reply("Не удалось определить пользователя по вашему ответу. Возможно, вы ответили на сообщение бота или системное сообщение.", disable_web_page_preview=True)
            # В остальных случаях (неудачный поиск по аргументу) resolve_target_user уже отправил сообщение
            return # Важно: выходим, если не удалось определить цель
    else:
        # Если НЕТ аргументов И это НЕ ответ на сообщение (т.е. просто /стата)
        # Статистика показывается для того, кто вызвал команду
        user_to_display_id = calling_user_id
        user_to_display_name = message.from_user.full_name
        user_to_display_username = message.from_user.username
        display_for_self = True

    # 4. Проверка, что ID пользователя для отображения был определен
    if user_to_display_id is None:
        # Эта проверка сработает, если что-то пошло не так и ID не установился.
        # В случае с /стата без аргументов, user_to_display_id должен быть calling_user_id.
        await message.reply("Не удалось определить пользователя для отображения статистики. (user_to_display_id is None)", disable_web_page_preview=True)
        return

    # 5. Получение и отправка статистики
    try:
        stats_message_content = await _get_formatted_stats(user_to_display_id, current_chat_id, bot, for_self=display_for_self)
        await message.reply(stats_message_content, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Error in /стата (general_stats_handler) for target {user_to_display_id} by {calling_user_id}: {e}", exc_info=True)
        target_user_link_log = get_user_mention_html(user_to_display_id, user_to_display_name, user_to_display_username)
        await message.reply(f"Произошла ошибка при получении статистики для {target_user_link_log}.", parse_mode="HTML", disable_web_page_preview=True)
        calling_user_link_log = get_user_mention_html(calling_user_id, message.from_user.full_name, message.from_user.username)
        await send_telegram_log(bot, f"🔴 Ошибка в /стата (general) для {target_user_link_log} (запросил {calling_user_link_log}): <pre>{html.escape(str(e))}</pre>")


@stats_router.message(Command("стата", "статистика", ignore_case=True))
async def cmd_general_stats_handler(message: Message, command: CommandObject, bot: Bot):
    if not message.from_user:
        await message.reply("Не удалось определить пользователя.", disable_web_page_preview=True)
        return

    calling_user_id = message.from_user.id
    current_chat_id = message.chat.id

    has_args = bool(command.args)
    is_reply = bool(message.reply_to_message and message.reply_to_message.from_user and not message.reply_to_message.from_user.is_bot)

    user_to_display_id: Optional[int] = None
    user_to_display_name: Optional[str] = None
    user_to_display_username: Optional[str] = None
    display_for_self = True

    if has_args or is_reply:
        target_user_data = await resolve_target_user(message, command, bot)
        if target_user_data:
            user_to_display_id, user_to_display_name, user_to_display_username = target_user_data
            display_for_self = (user_to_display_id == calling_user_id)
            if not display_for_self:
                try:
                    target_chat_obj = await bot.get_chat(user_to_display_id)
                    if hasattr(target_chat_obj, 'is_bot') and target_chat_obj.is_bot:
                        await message.reply("Нельзя посмотреть статистику бота.", disable_web_page_preview=True)
                        return
                except Exception: pass
        else:
            if is_reply and not has_args:
                await message.reply("Не удалось определить пользователя по вашему ответу. Возможно, вы ответили на сообщение бота или системное сообщение.", disable_web_page_preview=True)
            return
    else:
        user_to_display_id = calling_user_id
        user_to_display_name = message.from_user.full_name
        user_to_display_username = message.from_user.username
        display_for_self = True

    if user_to_display_id is None:
        await message.reply("Не удалось определить пользователя для отображения статистики.", disable_web_page_preview=True)
        return

    try:
        stats_message_content = await _get_formatted_stats(user_to_display_id, current_chat_id, bot, for_self=display_for_self)
        await message.reply(stats_message_content, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Error in /стата (general_stats_handler) for target {user_to_display_id} by {calling_user_id}: {e}", exc_info=True)
        target_user_link_log = get_user_mention_html(user_to_display_id, user_to_display_name, user_to_display_username)
        await message.reply(f"Произошла ошибка при получении статистики для {target_user_link_log}.", parse_mode="HTML", disable_web_page_preview=True)
        calling_user_link_log = get_user_mention_html(calling_user_id, message.from_user.full_name, message.from_user.username)
        await send_telegram_log(bot, f"🔴 Ошибка в /стата (general) для {target_user_link_log} (запросил {calling_user_link_log}): <pre>{html.escape(str(e))}</pre>")


@stats_router.message(Command("userstats", "статапользователя", ignore_case=True))
async def cmd_user_stats_explicit(message: Message, command: CommandObject, bot: Bot):
    if not message.from_user:
        await message.reply("Не удалось определить, кто вызвал команду.", disable_web_page_preview=True)
        return

    target_user_data = await resolve_target_user(message, command, bot)

    if not target_user_data:
        if not command.args and not message.reply_to_message:
            await message.reply("Укажите пользователя (ID, @username или ответом на сообщение), чью статистику вы хотите посмотреть.", disable_web_page_preview=True)
        return

    target_user_id, target_full_name, target_username = target_user_data
    current_chat_id = message.chat.id

    try:
        target_chat_obj = await bot.get_chat(target_user_id)
        if hasattr(target_chat_obj, 'is_bot') and target_chat_obj.is_bot:
            await message.reply("Нельзя посмотреть статистику бота.", disable_web_page_preview=True)
            return
    except Exception as e_check_bot:
        logger.warning(f"Не удалось проверить, является ли цель {target_user_id} ботом (userstats_explicit): {e_check_bot}")

    try:
        stats_message = await _get_formatted_stats(target_user_id, current_chat_id, bot, for_self=(target_user_id == message.from_user.id))
        await message.reply(stats_message, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Error in /userstats (explicit) for target {target_user_id} by {message.from_user.id}: {e}", exc_info=True)
        target_user_link_for_log = get_user_mention_html(target_user_id, target_full_name, target_username)
        await message.reply(f"Произошла ошибка при получении статистики для {target_user_link_for_log}.", parse_mode="HTML", disable_web_page_preview=True)
        calling_user_link_for_log = get_user_mention_html(message.from_user.id, message.from_user.full_name, message.from_user.username)
        await send_telegram_log(bot, f"🔴 Ошибка в /userstats (explicit) для {target_user_link_for_log} (запросил {calling_user_link_for_log}): <pre>{html.escape(str(e))}</pre>")


def setup_stats_handlers(dp: Router):
    dp.include_router(stats_router)
    logger.info("Обработчики команд статистики зарегистрированы.")
