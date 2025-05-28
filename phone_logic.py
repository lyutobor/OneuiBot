# phone_logic.py
import asyncio
from pytz import timezone as pytz_timezone
import html
import random # <--- ДОБАВЛЕНО
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Optional, List, Dict, Any, Tuple

from aiogram import Router, Bot, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from utils import get_current_price
import asyncpg
from achievements_logic import check_and_grant_achievements 

# Импорты из ваших файлов проекта
from config import Config
import database
from utils import get_user_mention_html, send_telegram_log
# !!! ИМПОРТИРУЕМ КАК СПИСОК С ДРУГИМ ИМЕНЕМ !!!
from phone_data import PHONE_MODELS as PHONE_MODELS_LIST, PHONE_COLORS
from item_data import PHONE_COMPONENTS, PHONE_CASES, CORE_PHONE_COMPONENT_TYPES, MAX_PHONE_MEMORY_GB

import logging

class PurchaseStates(StatesGroup):
    awaiting_confirmation = State()

logger = logging.getLogger(__name__)
phone_router = Router()

CONFIRMATION_TIMEOUT_SECONDS_ITEM = getattr(Config, "MARKET_PURCHASE_CONFIRMATION_TIMEOUT_SECONDS", 60) # Таймаут для предметов
CONFIRMATION_TIMEOUT_SECONDS_PHONE = getattr(Config, "MARKET_PHONE_CONFIRMATION_TIMEOUT_SECONDS", 60) # Таймаут для подтверждения покупки/продажи телефона (и ремонта)

# !!! ПРЕОБРАЗУЕМ СПИСОК ТЕЛЕФОНОВ В СЛОВАРЬ ДЛЯ БЫСТРОГО ПОИСКА ПО КЛЮЧУ !!!
# Теперь PHONE_MODELS будет словарем: {"ключ_модели": {информация о модели}, ...}
PHONE_MODELS = {phone_info["key"]: phone_info for phone_info in PHONE_MODELS_LIST}

# =============================================================================
REPAIRPHONE_COMMAND_ALIASES = ["repairphone", "починитьтелефон", "ремонттелефона"]
# АЛИАСЫ КОМАНД
# =============================================================================

# Добавляем алиасы для новой команды продажи предметов
SELLITEM_COMMAND_ALIASES = ["sellitem", "продатьпредмет"]
# Алиас для продажи чехла (хотя функционал sellitem его заменит, оставим для совместимости или специфики)
SELLCASE_COMMAND_ALIASES = ["sellcase", "продатьчехол"]


# =============================================================================
# ХЕЛПЕРЫ / Вспомогательные функции
# =============================================================================

def calculate_phone_sell_price(
    phone_db_data: Dict[str, Any],
    phone_static_data: Dict[str, Any]
) -> Tuple[int, Optional[str]]:
    """
    Рассчитывает цену продажи телефона с учетом износа, состояния и надетого чехла.
    Возвращает (цена_продажи_телефона, описание_состояния_для_продажи).
    Цена продажи чехла рассчитывается отдельно.
    """
    if not phone_static_data or not phone_db_data:
        return 0, "Ошибка данных телефона"

    original_price = phone_static_data.get('price', 0)
    purchase_date = phone_db_data.get('purchase_date_utc')
    is_broken = phone_db_data.get('is_broken', False)
    broken_component_key = phone_db_data.get('broken_component_key')

    if not purchase_date:
        return int(original_price * 0.1), "Неизвестна дата покупки (старый телефон)" # Очень низкая цена

    # Убедимся, что purchase_date имеет корректный тип datetime и Aware
    if isinstance(purchase_date, str):
        try:
            purchase_date = datetime.fromisoformat(purchase_date)
            if purchase_date.tzinfo is None:
                 purchase_date = purchase_date.replace(tzinfo=dt_timezone.utc)
        except ValueError:
            logger.error(f"calculate_phone_sell_price: Некорректный формат purchase_date (str): {purchase_date}")
            return int(original_price * 0.05), "Ошибка даты покупки (формат)"

    if not isinstance(purchase_date, datetime): # Если все еще не datetime
        logger.error(f"calculate_phone_sell_price: purchase_date не является datetime: {type(purchase_date)}")
        return int(original_price * 0.05), "Ошибка типа даты покупки"

    # Если purchase_date был naive, делаем его aware
    if purchase_date.tzinfo is None:
        purchase_date = purchase_date.replace(tzinfo=dt_timezone.utc)


    now_utc = datetime.now(dt_timezone.utc)
    age_days = (now_utc - purchase_date).days

    # 1. Расчет идеальной текущей стоимости с учетом временного износа
    current_value = float(original_price)

    # -10% сразу (но так как мы продаем то, за что заплатили original_price, этот износ как бы уже есть)
    # Мы будем считать износ от original_price

    # Неделя = 7 дней, Месяц = 30 дней, 3 Месяца = 90 дней
    # Последовательное применение процентов
    if age_days >= 90: # 3 месяца
        current_value *= (1 - 0.10) # Изначальный "износ нового"
        current_value *= (1 - 0.05) # За первую неделю
        current_value *= (1 - 0.15) # За первый месяц (сверх недели)
        current_value *= (1 - 0.23) # За три месяца (сверх месяца)
    elif age_days >= 30: # 1 месяц
        current_value *= (1 - 0.10)
        current_value *= (1 - 0.05)
        current_value *= (1 - 0.15)
    elif age_days >= 7: # 1 неделя
        current_value *= (1 - 0.10)
        current_value *= (1 - 0.05)
    elif age_days >= 0: # Меньше недели, но уже куплен
        current_value *= (1 - 0.10) # -10% сразу после покупки

    # Минимальная цена (например, 10% от оригинала)
    min_price = original_price * 0.10
    if current_value < min_price:
        current_value = min_price

    ideal_current_value = int(round(current_value))
    sell_price = ideal_current_value
    description = "Исправен"

    # 2. Учет поломки
    if is_broken and broken_component_key:
        component_cost = PHONE_COMPONENTS.get(broken_component_key, {}).get('price', 0)
        sell_price = int(round(ideal_current_value * 0.40)) - component_cost # 40% от идеальной минус стоимость детали

        broken_component_name = PHONE_COMPONENTS.get(broken_component_key, {}).get('name', broken_component_key)
        description = f"Сломан ({html.escape(broken_component_name)})"

        if sell_price < 1:
            sell_price = 1
    elif is_broken: # Сломан, но неизвестно что (маловероятно при нашей логике)
        sell_price = int(round(ideal_current_value * 0.15)) # Очень низкая цена
        description = "Сломан (неизвестно что)"
        if sell_price < 1: sell_price = 1

    return sell_price, description

# =============================================================================
# =============================================================================
# Команды для магазина
# =============================================================================

@phone_router.message(Command("phoneshop", "телефонмагазин", "купитьтелефон", ignore_case=True))
async def cmd_phoneshop(message: Message, command: CommandObject, bot: Bot):
    if not message.from_user:
        return await message.reply("Не удалось определить пользователя.")

    user_link = get_user_mention_html(message.from_user.id, message.from_user.full_name, message.from_user.username)

    # Здесь мы все еще хотим работать с телефонами, сгруппированными по сериям,
    # поэтому лучше использовать оригинальный список или итерироваться по значениям словаря
    # Сгруппируем телефоны из словаря по сериям:
    phones_by_series: Dict[str, List[Dict[str, Any]]] = {"S": [], "A": [], "Z": [], "NOTE": [], "OTHER": []}
    # !!! ИТЕРИРУЕМ ПО ЗНАЧЕНИЯМ СЛОВАРЯ !!!
    for phone_info in PHONE_MODELS.values():
        series = phone_info.get("series", "Other").upper()
        if series in phones_by_series:
            phones_by_series[series].append(phone_info)
        else:
            phones_by_series["OTHER"].append(phone_info)

    # Используем order, определенный выше
    phones_by_series_global_order = ["S", "A", "Z", "NOTE", "OTHER"]

    args = command.args
    requested_series_key: Optional[str] = None

    if args:
        requested_series_key = args.strip().upper()
        # Проверяем наличие серии в наших сгруппированных данных
        if requested_series_key not in phones_by_series_global_order or requested_series_key not in phones_by_series:
             await message.reply(
                 f"{user_link}, такой серии телефонов нет или в ней пока нет товаров. Используйте S, A, Z, Note.\n"
                 f"Пример: /phoneshop S\n"
                 f"Или просто /phoneshop, чтобы увидеть доступные серии."
             )
             return
        if not phones_by_series.get(requested_series_key): # Дополнительная проверка на пустую серию
             await message.reply(f"{user_link}, в серии '{requested_series_key}' пока нет телефонов.")
             return


    response_parts = []

    series_display_name_map = {
        "S": "💎 Флагманы Galaxy S", "A": "📱 Доступные Galaxy A",
        "Z": "🧬 Гибкие Galaxy Z", "NOTE": "🖋 Производительные Galaxy Note",
        "OTHER": "⚙️ Другие модели"
    }

    if not requested_series_key:
        response_parts.append(f"📱 <b>Магазин Телефонов</b>\n{user_link}, выберите серию для просмотра:\n")
        available_series_display = []
        # !!! ИТЕРИРУЕМ ПО ЗАРАНЕЕ ОПРЕДЕЛЕННОМУ ПОРЯДКУ И ПРОВЕРЯЕМ НАЛИЧИЕ В phones_by_series !!!
        for series_key_iter in phones_by_series_global_order:
            if phones_by_series.get(series_key_iter): # Проверяем, есть ли в этой серии телефоны
                display_name = series_display_name_map.get(series_key_iter, f"Линейка {series_key_iter}")
                available_series_display.append(f"  {display_name}: /phoneshop {series_key_iter}")

        if not available_series_display:
            response_parts.append("На данный момент телефонов в продаже нет.")
        else:
            response_parts.extend(available_series_display)
        response_parts.append(f"\nДоступные цвета для покупки: {', '.join(PHONE_COLORS)}.")
        response_parts.append("Для покупки используйте: /buyphone КЛЮЧ_ТЕЛЕФОНА Цвет")
        response_parts.append("Пример: /buyphone galaxy_s24_128gb Черный")

    else:
        series_phones_to_show = phones_by_series.get(requested_series_key, []) # Берем из сгруппированного списка
        series_title = series_display_name_map.get(requested_series_key, f"Линейка {requested_series_key}")
        response_parts.append(f"📱 <b>{series_title}</b>\n{user_link}, вот доступные модели:\n")

        if not series_phones_to_show:
            response_parts.append(f"Телефонов серии '{requested_series_key}' пока нет в продаже (внутренняя ошибка группировки).") # Этого не должно быть после проверки выше
        else:
            series_phones_to_show.sort(key=lambda x: (x.get("release_year", 0), x.get("price", 0)))
            phone_lines_for_series = []
            for phone_info in series_phones_to_show:
                base_price = phone_info['price']
                    # Получаем актуальную цену с учетом инфляции
                    # Предполагается, что get_current_price сама управляет соединением с БД,
                    # либо вы открываете соединение в начале cmd_phoneshop и передаете conn_ext.
                    # Для простоты, пусть get_current_price сама управляет.
                display_price = await get_current_price(base_price)
                    # TODO: Учесть здесь активные скидки при расчете display_price

                    # Компактный вывод в одну строку: Имя (Память, Год) - Цена OC (Ключ: КЛЮЧ_ТЕЛЕФОНА)
                phone_line = (
                    f"• <b>{html.escape(phone_info['name'])}</b> "
                    f"({phone_info['memory']}, {phone_info.get('release_year', 'N/A')}) "
                    f"- {display_price} OC (<code>{phone_info['key']}</code>)"
                )
                phone_lines_for_series.append(phone_line)

            response_parts.append("\n".join(phone_lines_for_series)) # Объединяем строки телефонов
            response_parts.append(f"\nДоступные цвета: {', '.join(PHONE_COLORS)}.")
            response_parts.append("Для покупки используйте: /buyphone КЛЮЧ_ТЕЛЕФОНА Цвет")
            response_parts.append("Пример: /buyphone galaxy_s23_ultra_256gb Белый")


    full_response = "\n".join(response_parts)

    MAX_MESSAGE_LENGTH = 4096
    if len(full_response) > MAX_MESSAGE_LENGTH:
        temp_parts = []
        current_part = ""
        for line in full_response.split('\n'):
            if len(current_part) + len(line) + 1 > MAX_MESSAGE_LENGTH:
                temp_parts.append(current_part)
                current_part = line
            else:
                if current_part:
                    current_part += "\n" + line
                else:
                    current_part = line
        if current_part:
            temp_parts.append(current_part)

        for part_msg in temp_parts:
            await message.answer(part_msg, parse_mode="HTML", disable_web_page_preview=True)
            await asyncio.sleep(0.2)
    else:
        await message.answer(full_response, parse_mode="HTML", disable_web_page_preview=True)

@phone_router.message(Command("itemshop", "магазинпредметов", "предметы", "детали", "чехлы", ignore_case=True))
async def cmd_itemshop(message: Message, command: CommandObject, bot: Bot):
    if not message.from_user:
        return await message.reply("Не удалось определить пользователя.")

    user_link = get_user_mention_html(message.from_user.id, message.from_user.full_name, message.from_user.username)

    args = command.args.split() if command.args else []
    category: Optional[str] = None
    sub_category: Optional[str] = None

    if len(args) > 0:
        category = args[0].lower()
    if len(args) > 1:
        sub_category = args[1].upper()

    response_parts = [f"🛠️ <b>Магазин Предметов и Аксессуаров</b>\n{user_link}\n"]

    # --- Основное меню /itemshop ---
    if not category:
        response_parts.append("Выберите категорию для просмотра:")
        response_parts.append("  🔩 Компоненты: /itemshop components")
        response_parts.append("  💾 Модули памяти: /itemshop memory")
        response_parts.append("  🛡️ Чехлы: /itemshop cases")
        response_parts.append("\nДля покупки используйте: /buyitem КЛЮЧ_ПРЕДМЕТА [количество]")

    # --- Категория: Компоненты ---
    elif category == "components":
        if not sub_category: # /itemshop components -> показать серии
            response_parts.append("<b>🔩 Компоненты для телефонов</b>\nВыберите серию:")
            response_parts.append("  - Компоненты A-серии: /itemshop components A")
            response_parts.append("  - Компоненты S-серии: /itemshop components S")
            response_parts.append("  - Компоненты Z-серии: /itemshop components Z")
        elif sub_category in ["A", "S", "Z"]: # /itemshop components <серия>
            response_parts.append(f"<b>🔩 Компоненты для {sub_category}-серии:</b>")
            component_lines = []
            # Итерируем по компонентам и фильтруем по серии
            sorted_components = sorted(
                [(key, info) for key, info in PHONE_COMPONENTS.items() if info.get("series") == sub_category and info.get("component_type") != "memory_module"], # Исключаем модули памяти
                key=lambda x: x[1]["name"]
            )
            if not sorted_components:
                response_parts.append(f"  Компонентов для {sub_category}-серии пока нет.")
            else:
                for key, comp_info in sorted_components:
                    name = html.escape(comp_info.get("name", key))
                    #price = comp_info.get("price", "N/A")
                    base_price = comp_info.get("price", 0) # Получаем базовую цену как число
                    actual_price = await get_current_price(base_price) # Вызываем нашу новую функцию
                    component_lines.append(f"  • {name} - {actual_price} OC (Ключ: <code>{key}</code>)")
                response_parts.extend(component_lines)
            response_parts.append("\n  Для покупки: /buyitem КЛЮЧ_КОМПОНЕНТА [количество]")
        else:
            response_parts.append(f"Неверная серия для компонентов: {html.escape(sub_category)}. Доступны: A, S, Z.")

    # --- Категория: Модули памяти ---
    elif category == "memory":
        response_parts.append("<b>💾 Модули памяти:</b>")
        memory_lines = []
        # Итерируем по компонентам и ищем модули памяти
        sorted_memory_modules = sorted(
             [(key, info) for key, info in PHONE_COMPONENTS.items() if info.get("component_type") == "memory_module"],
             key=lambda x: x[1].get("capacity_gb", 0) # Сортируем по объему памяти
        )

        if not sorted_memory_modules:
            response_parts.append("  Модулей памяти пока нет.")
        else:
            for key, comp_info in sorted_memory_modules:
                name = html.escape(comp_info.get("name", key))
                base_price = comp_info.get("price", 0) # Базовая цена
                actual_price = await get_current_price(base_price) # <--- ИЗМЕН
                capacity_gb = comp_info.get("memory_gb") # Исправлено: memory_gb
                capacity_display = f" ({capacity_gb}GB)" if capacity_gb else ""
                memory_lines.append(f"  • {name}{capacity_display} - {actual_price} OC (Ключ: <code>{key}</code>)") # <--- ИЗМЕНЕНИ
            response_parts.extend(memory_lines)
        response_parts.append("\n  Для покупки: /buyitem КЛЮЧ_МОДУЛЯ [количество]")

    # --- Категория: Чехлы ---
    elif category == "cases":
        if not sub_category: # /itemshop cases -> показать серии
            response_parts.append("<b>🛡️ Чехлы для телефонов</b>\nВыберите серию:")
            response_parts.append("  - Чехлы A-серии: /itemshop cases A")
            response_parts.append("  - Чехлы S-серии: /itemshop cases S")
            response_parts.append("  - Чехлы Z-серии: /itemshop cases Z")
        elif sub_category in ["A", "S", "Z"]: # /itemshop cases <серия>
            response_parts.append(f"<b>🛡️ Чехлы для {sub_category}-серии:</b>")
            case_lines = []

            # Собираем и сортируем чехлы для текущей серии по цене
            temp_case_list_for_sorting = []
            # Итерируем по чехлам и фильтруем по серии
            for key, case_info in PHONE_CASES.items():
                if case_info.get("series") == sub_category:
                    temp_case_list_for_sorting.append((key, case_info))

            temp_case_list_for_sorting.sort(key=lambda x: x[1].get("price", 0))

            if not temp_case_list_for_sorting:
                 response_parts.append(f"  Чехлов для {sub_category}-серии пока нет.")
            else:
                for key, case_info in temp_case_list_for_sorting:
                    name = html.escape(case_info.get("name", key))
                    base_price = case_info.get("price", 0) # Базовая цена
                    actual_price = await get_current_price(base_price) # <--- ИЗМЕНЕНИЕ
                    protection = case_info.get("break_chance_reduction_percent", 0)

                    bonuses_text_parts = []
                    if case_info.get("battery_days_increase"): bonuses_text_parts.append(f"+{case_info['battery_days_increase']}д. заряда")
                    if case_info.get("oneui_version_bonus_percent"): bonuses_text_parts.append(f"+{case_info['oneui_version_bonus_percent']}% к OneUI")
                    if case_info.get("onecoin_bonus_percent"): bonuses_text_parts.append(f"+{case_info['onecoin_bonus_percent']}% к OneCoin")
                    if case_info.get("market_discount_percent"): bonuses_text_parts.append(f"-{case_info['market_discount_percent']}% на рынке")
                    if case_info.get("bonus_roulette_luck_percent"): bonuses_text_parts.append(f"+{case_info['bonus_roulette_luck_percent']}% удачи в рулетке")

                    bonus_str_suffix = ""
                    if bonuses_text_parts:
                        bonus_str_suffix = f"; {', '.join(bonuses_text_parts)}"

                    case_lines.append(f"  • {name} - {actual_price} OC (Защита: {protection}%{bonus_str_suffix}) (Ключ: <code>{key}</code>)")
                response_parts.extend(case_lines)
            response_parts.append("\n  Для покупки чехла: /buyitem КЛЮЧ_ЧЕХЛА")
        else:
            response_parts.append(f"Неверная серия для чехлов: {html.escape(sub_category)}. Доступны: A, S, Z.")
    else:
        # Если категория не распознана, показываем основное меню
        response_parts = [f"🛠️ <b>Магазин Предметов и Аксессуаров</b>\n{user_link}\n"]
        response_parts.append("Неверная категория. Выберите из списка:")
        response_parts.append("  🔩 Компоненты: /itemshop components")
        response_parts.append("  💾 Модули памяти: /itemshop memory")
        response_parts.append("  🛡️ Чехлы: /itemshop cases")

    # Отправка сообщения (с разбивкой, если длинное)
    full_response = "\n".join(response_parts)

    MAX_MESSAGE_LENGTH = 4096
    if len(full_response) > MAX_MESSAGE_LENGTH:
        # ... (логика разбивки сообщения, как в cmd_phoneshop) ...
        temp_parts = []
        current_part = ""
        for line in full_response.split('\n'):
            if len(current_part) + len(line) + 1 > MAX_MESSAGE_LENGTH:
                temp_parts.append(current_part)
                current_part = line
            else:
                if current_part: current_part += "\n" + line
                else: current_part = line
        if current_part: temp_parts.append(current_part)

        for part_msg in temp_parts:
            await message.answer(part_msg, parse_mode="HTML", disable_web_page_preview=True)
            await asyncio.sleep(0.2)
    else:
        await message.answer(full_response, parse_mode="HTML", disable_web_page_preview=True)


        


@phone_router.message(Command("buyphone", "купитьсмартфон", ignore_case=True))
async def cmd_buyphone_start(message: Message, command: CommandObject, state: FSMContext, bot: Bot):
    if not message.from_user:
        return await message.reply("Не удалось определить пользователя.")

    user_id = message.from_user.id
    chat_id = message.chat.id
    user_link = get_user_mention_html(user_id, message.from_user.full_name, message.from_user.username)

    args = command.args
    if not args:
        await message.reply(
            f"{user_link}, укажите ключ модели телефона и цвет.\n"
            f"Пример: /buyphone galaxy_s24_128gb Черный\n"
            f"Посмотреть доступные телефоны: /phoneshop"
        )
        return

    args_list = args.split(maxsplit=1)
    phone_model_key_arg = args_list[0].lower()
    chosen_color_arg = args_list[1].strip().capitalize() if len(args_list) > 1 else None

    if not chosen_color_arg:
        await message.reply(
            f"{user_link}, вы не указали цвет телефона.\n"
            f"Пример: /buyphone {phone_model_key_arg} Черный\n"
            f"Доступные цвета: {', '.join(PHONE_COLORS)}"
        )
        return

    valid_colors_lower = [color.lower() for color in PHONE_COLORS]
    if chosen_color_arg.lower() not in valid_colors_lower:
        await message.reply(
            f"{user_link}, цвет '{html.escape(chosen_color_arg)}' недоступен.\n"
            f"Доступные цвета: {', '.join(PHONE_COLORS)}"
        )
        return
    chosen_color_canonical = PHONE_COLORS[valid_colors_lower.index(chosen_color_arg.lower())]

    # !!! ИСПОЛЬЗУЕМ СЛОВАРЬ ДЛЯ ПОИСКА !!!
    phone_to_buy_info: Optional[Dict[str, Any]] = PHONE_MODELS.get(phone_model_key_arg)

    if not phone_to_buy_info:
        await message.reply(f"{user_link}, телефон с ключом '<code>{html.escape(phone_model_key_arg)}</code>' не найден в магазине.")
        return

    item_name_display = html.escape(phone_to_buy_info['name'])
    base_item_price = phone_to_buy_info['price'] # <--- БАЗОВАЯ ЦЕНА

    conn_buy_phone = None 
    try:
        conn_buy_phone = await database.get_connection()
        
        # Получаем актуальную цену с учетом инфляции
        actual_item_price = await get_current_price(base_item_price, conn_ext=conn_buy_phone) # <--- НОВОЕ: РАСЧЕТ ЦЕНЫ

        active_phones_count = await database.count_user_active_phones(user_id, conn_ext=conn_buy_phone)
        max_phones = getattr(Config, "MAX_PHONES_PER_USER", 2)
        if active_phones_count >= max_phones:
            await message.reply(
                f"{user_link}, у тебя уже максимальное количество телефонов ({active_phones_count}/{max_phones}).",
                disable_web_page_preview=True
            )
            if conn_buy_phone and not conn_buy_phone.is_closed(): await conn_buy_phone.close()
            return
        
        current_balance = await database.get_user_onecoins(user_id, chat_id, conn_ext=conn_buy_phone)
        if current_balance < actual_item_price: # <--- ИСПОЛЬЗУЕМ АКТУАЛЬНУЮ ЦЕНУ
            await message.reply(
                f"{user_link}, у вас недостаточно средств для покупки <b>{item_name_display}</b>.\n"
                f"Нужно: {actual_item_price} OC, у вас: {current_balance} OC."
            )
            if conn_buy_phone and not conn_buy_phone.is_closed(): await conn_buy_phone.close()
            return

        memory_str = phone_to_buy_info.get('memory', '0').upper()
        initial_memory_val = 0
        if 'TB' in memory_str:
            try: initial_memory_val = int(float(memory_str.replace('TB', '').strip()) * 1024)
            except ValueError: initial_memory_val = 1024
        elif 'GB' in memory_str:
            try: initial_memory_val = int(float(memory_str.replace('GB', '').strip()))
            except ValueError: initial_memory_val = 0
        else: initial_memory_val = 0

        await state.set_state(PurchaseStates.awaiting_confirmation)
        await state.update_data(
            phone_key=phone_to_buy_info['key'],
            phone_name=phone_to_buy_info['name'],
            phone_price=actual_item_price, # <--- НОВОЕ: СОХРАНЯЕМ АКТУАЛЬНУЮ ЦЕНУ
            phone_color=chosen_color_canonical,
            initial_memory_gb=initial_memory_val,
            is_contraband=False, 
            confirmation_initiated_at=datetime.now(dt_timezone.utc).isoformat(),
            original_chat_id=chat_id,
            original_user_id=user_id,
            action_type="buy_phone"
        )

        await message.reply(
            f"{user_link}, вы уверены, что хотите купить:\n"
            f"<b>{item_name_display}</b> ({chosen_color_canonical})\n"
            f"Цена: {actual_item_price} OneCoin(s)?\n" # <--- ИСПОЛЬЗУЕМ АКТУАЛЬНУЮ ЦЕНУ
            f"Ваш баланс: {current_balance} OneCoin(s).\n\n"
            f"Ответьте 'Да' или 'Нет' в течение {CONFIRMATION_TIMEOUT_SECONDS_PHONE} секунд.",
            disable_web_page_preview=True
        )
             

    except Exception as e_buy_start:
        logger.error(f"BuyPhone: Ошибка на старте покупки для user {user_id}, item {phone_model_key_arg}: {e_buy_start}", exc_info=True)
        await message.reply("Произошла ошибка при начале покупки. Попробуйте позже.")
        await send_telegram_log(bot, f"🔴 Ошибка в /buyphone (старт) для {user_link}, товар {phone_model_key_arg}: <pre>{html.escape(str(e_buy_start))}</pre>")
    finally:
        if conn_buy_phone and not conn_buy_phone.is_closed():
            await conn_buy_phone.close()

# --- КОМАНДА ПРОДАЖИ ТЕЛЕФОНА ---
@phone_router.message(Command("sellphone", "продатьтелефон", ignore_case=True))
async def cmd_sellphone_start(message: Message, command: CommandObject, state: FSMContext, bot: Bot):
    if not message.from_user:
        return await message.reply("Не удалось определить пользователя.")

    user_id = message.from_user.id
    chat_id = message.chat.id
    user_link = get_user_mention_html(user_id, message.from_user.full_name, message.from_user.username)

    args_str = command.args
    if not args_str:
        await message.reply(
            f"{user_link}, укажите ID телефона, который хотите продать.\n"
            f"Пример: /sellphone 123\n"
            f"ID ваших телефонов: /myphones"
        )
        return

    try:
        phone_inventory_id_arg = int(args_str.strip())
    except ValueError:
        await message.reply("ID телефона должен быть числом.")
        return

    phone_db_data = await database.get_phone_by_inventory_id(phone_inventory_id_arg)
    if not phone_db_data or phone_db_data['user_id'] != user_id:
        await message.reply(f"Телефон с ID <code>{phone_inventory_id_arg}</code> не найден в вашем инвентаре.")
        return
    if phone_db_data['is_sold']:
        await message.reply(f"Телефон ID <code>{phone_inventory_id_arg}</code> уже был продан ранее.")
        return

    phone_model_key = phone_db_data['phone_model_key']
    phone_static_data = PHONE_MODELS.get(phone_model_key) # Используем словарь
    if not phone_static_data:
        await message.reply(f"Ошибка: не найдены данные для модели телефона ID <code>{phone_inventory_id_arg}</code>.")
        return

    phone_sell_price, phone_condition_desc = calculate_phone_sell_price(phone_db_data, phone_static_data)

    equipped_case_key = phone_db_data.get('equipped_case_key')
    case_sell_price = 0
    case_name_for_msg = ""

    if equipped_case_key:
        case_static_info = PHONE_CASES.get(equipped_case_key)
        if case_static_info:
            case_original_price = case_static_info.get('price', 0)
            # Используем Config.CASE_SELL_PERCENTAGE для чехла
            case_sell_percentage = getattr(Config, "CASE_SELL_PERCENTAGE", 0.20)
            case_sell_price = int(round(case_original_price * case_sell_percentage))
            # Используем общую минимальную цену продажи
            min_sell_price = getattr(Config, "MIN_SELL_PRICE_IF_ORIGINAL_GT_ZERO", 1)
            if case_sell_price < min_sell_price and case_original_price > 0 : case_sell_price = min_sell_price
            case_name_for_msg = html.escape(case_static_info['name'])
        else: # Чехол есть, но нет в PHONE_CASES - странно, но продаем за 0
            case_sell_price = 0
            case_name_for_msg = f"неизвестный чехол (<code>{html.escape(equipped_case_key)}</code>)"


    total_sell_amount = phone_sell_price + case_sell_price

    await state.set_state(PurchaseStates.awaiting_confirmation) # Используем тот же FSM
    await state.update_data(
        action_type="sell_phone",
        phone_inventory_id=phone_inventory_id_arg,
        phone_name=phone_static_data['name'],
        total_sell_amount=total_sell_amount,
        phone_sell_price_calculated=phone_sell_price, # Для лога
        case_sell_price_calculated=case_sell_price,   # Для лога
        equipped_case_key_at_sell=equipped_case_key,  # Для лога
        confirmation_initiated_at=datetime.now(dt_timezone.utc).isoformat(),
        original_chat_id=chat_id,
        original_user_id=user_id
    )

    confirmation_message = [
        f"{user_link}, вы уверены, что хотите продать:",
        f"  <b>{html.escape(phone_static_data['name'])}</b> (ID: {phone_inventory_id_arg})",
        f"  Состояние: {phone_condition_desc}",
        f"  Цена продажи телефона: {phone_sell_price} OC"
    ]
    if equipped_case_key:
        confirmation_message.append(f"  Надетый чехол \"{case_name_for_msg}\" также будет продан за: {case_sell_price} OC")

    confirmation_message.append(f"<b>Итого к получению: {total_sell_amount} OC</b>")
    confirmation_message.append(f"\nОтветьте 'Да' или 'Нет' в течение {CONFIRMATION_TIMEOUT_SECONDS_PHONE} секунд.") # Используем тот же таймаут

    await message.reply("\n".join(confirmation_message), parse_mode="HTML")


# --- КОМАНДА ПРОДАЖИ ПРЕДМЕТА (НОВЫЙ БЛОК) ---
@phone_router.message(Command(*SELLITEM_COMMAND_ALIASES, ignore_case=True))
async def cmd_sellitem_start(message: Message, command: CommandObject, state: FSMContext, bot: Bot):
    if not message.from_user:
        return await message.reply("Не удалось определить пользователя.")

    user_id = message.from_user.id
    chat_id = message.chat.id # OneCoin зачисляются на баланс текущего чата
    user_link = get_user_mention_html(user_id, message.from_user.full_name, message.from_user.username)

    args_str = command.args
    if not args_str:
        await message.reply(
            f"{user_link}, укажите ID предмета из вашего инвентаря и, опционально, количество для продажи.\n"
            f"Пример: /sellitem 789 2 (продать 2 шт. предмета с ID 789)\n"
            f"Пример: /sellitem 789 (продать 1 шт. предмета с ID 789)\n"
            f"ID ваших предметов: /myitems",
            parse_mode="HTML"
        )
        return

    args_list = args_str.split()
    try:
        user_item_id_to_sell = int(args_list[0])
        quantity_to_sell_arg = 1
        if len(args_list) > 1:
            quantity_to_sell_arg = int(args_list[1])
        if quantity_to_sell_arg <= 0:
            await message.reply("Количество для продажи должно быть больше нуля.")
            return
    except ValueError:
        await message.reply("ID предмета и количество должны быть числами.")
        return

    conn = None
    try:
        conn = await database.get_connection() # Открываем соединение здесь
        # Получаем информацию о предмете из инвентаря пользователя по его user_item_id
        # Важно: get_user_item_by_id по user_item_id уникален, но для стакаемых предметов в одной строке может быть quantity > 1
        item_db_data = await database.get_user_item_by_id(user_item_id_to_sell, user_id=user_id, conn_ext=conn)

        if not item_db_data:
            await message.reply(f"Предмет с ID <code>{user_item_id_to_sell}</code> не найден в вашем инвентаре.", parse_mode="HTML")
            # Закрываем соединение только если оно было открыто и не будет использовано дальше
            if conn and not conn.is_closed(): await conn.close()
            return

        item_key = item_db_data['item_key']
        item_type = item_db_data['item_type'] # 'component', 'memory_module', 'case'
        current_quantity_in_db = item_db_data['quantity'] # Актуальное количество в БД для этой user_item записи

        item_static_info: Optional[Dict[str, Any]] = None
        sell_percentage = 0.0

        # Определяем статические данные и процент продажи в зависимости от типа
        if item_type == 'component':
            item_static_info = PHONE_COMPONENTS.get(item_key)
            sell_percentage = getattr(Config, "COMPONENT_SELL_PERCENTAGE", 0.20) # Используем getattr с дефолтом на всякий случай
        elif item_type == 'memory_module':
            item_static_info = PHONE_COMPONENTS.get(item_key) # Модули памяти тоже в PHONE_COMPONENTS
            sell_percentage = getattr(Config, "MEMORY_MODULE_SELL_PERCENTAGE", 0.20)
        elif item_type == 'case':
            # Для чехлов quantity_to_sell_arg всегда должен быть 1, т.к. каждый чехол в БД - отдельная запись
            if quantity_to_sell_arg > 1:
                 await message.reply(f"Чехлы продаются поштучно по их ID. Укажите ID одного чехла для продажи.")
                 if conn and not conn.is_closed(): await conn.close()
                 return
            quantity_to_sell_arg = 1 # Убеждаемся, что для чехла количество = 1

            item_static_info = PHONE_CASES.get(item_key)
            sell_percentage = getattr(Config, "CASE_SELL_PERCENTAGE", 0.20)

        else:
            await message.reply(f"Неизвестный тип предмета: {item_type}. Продажа невозможна.")
            if conn and not conn.is_closed(): await conn.close()
            return

        if not item_static_info:
            await message.reply(f"Ошибка: не найдены статические данные для предмета <code>{html.escape(item_key)}</code> (ID: {user_item_id_to_sell}). Продать невозможно.", parse_mode="HTML")
            if conn and not conn.is_closed(): await conn.close()
            return

        # Проверка количества для стакаемых предметов (для чехлов current_quantity_in_db всегда 1)
        if quantity_to_sell_arg > current_quantity_in_db:
            await message.reply(f"У вас только {current_quantity_in_db} шт. предмета \"{html.escape(item_static_info.get('name', item_key))}\" (ID: {user_item_id_to_sell}), нельзя продать {quantity_to_sell_arg}.", parse_mode="HTML")
            if conn and not conn.is_closed(): await conn.close()
            return

        item_name_display = html.escape(item_static_info.get('name', item_key)) # Используем .get с дефолтом
        original_price_per_unit = item_static_info.get('price', 0)

        sell_price_per_unit = int(round(original_price_per_unit * sell_percentage))

        # Применяем минимальную цену продажи, если оригинальная цена > 0
        min_sell_price = getattr(Config, "MIN_SELL_PRICE_IF_ORIGINAL_GT_ZERO", 1)
        if original_price_per_unit > 0 and sell_price_per_unit < min_sell_price:
            sell_price_per_unit = min_sell_price
        elif original_price_per_unit == 0: # Если предмет бесплатный
            sell_price_per_unit = 0

        total_sell_value = sell_price_per_unit * quantity_to_sell_arg

        # Начинаем транзакцию для подтверждения, если все проверки пройдены
        # (Здесь только подготовка FSM, транзакция будет в хендлере подтверждения)
        await state.set_state(PurchaseStates.awaiting_confirmation)
        await state.update_data(
            action_type="sell_item", # Новый тип действия
            user_item_id_to_sell=user_item_id_to_sell, # ID конкретной записи в user_items
            item_key=item_key,
            item_type=item_type,
            item_name=item_name_display,
            quantity_to_sell=quantity_to_sell_arg,
            total_sell_value=total_sell_value,
            sell_price_per_unit=sell_price_per_unit, # для лога
            original_price_per_unit=original_price_per_unit, # для лога
            confirmation_initiated_at=datetime.now(dt_timezone.utc).isoformat(),
            original_chat_id=chat_id,
            original_user_id=user_id
        )

        quantity_text = f"{quantity_to_sell_arg} шт. " if quantity_to_sell_arg > 1 else ""
        confirmation_message = (
            f"{user_link}, вы уверены, что хотите продать:\n"
            f"  <b>{quantity_text}{item_name_display}</b> (ID инвентаря: {user_item_id_to_sell})\n"
            f"  Цена продажи: {total_sell_value} OneCoin(s) (по {sell_price_per_unit} OC за шт.)?\n\n"
            f"Ответьте 'Да' или 'Нет' в течение {CONFIRMATION_TIMEOUT_SECONDS_ITEM} секунд." # Используем таймаут предметов
        )
        await message.reply(confirmation_message, parse_mode="HTML")

    except ValueError: # Это уже было выше, но дублируем для args_list[1] если он не число
        await message.reply("Количество для продажи должно быть числом.")
    except Exception as e_sellitem_start:
        logger.error(f"SellItem: Ошибка на старте продажи для user {user_id}, item_id {args_list[0] if args_list else 'N/A'}: {e_sellitem_start}", exc_info=True)
        await message.reply("Произошла ошибка при подготовке к продаже предмета.")
        await send_telegram_log(bot, f"🔴 Ошибка в /sellitem (старт) для {user_link}, предмет ID {args_list[0] if args_list else 'N/A'}: <pre>{html.escape(str(e_sellitem_start))}</pre>")
    finally:
        # Закрываем соединение здесь, так как в try/except/else блоках мы могли выйти раньше,
        # и если state был установлен, транзакция начнется в другом хендлере.
        # Если же произошла ошибка до установки state, соединение нужно закрыть.
        if conn and not conn.is_closed():
             await conn.close()


# --- ОБЩИЕ ОБРАБОТЧИКИ FSM ДЛЯ ПОКУПОК И ПРОДАЖ ---
@phone_router.message(PurchaseStates.awaiting_confirmation, F.text.lower() == "да")
async def cmd_purchase_confirm_yes(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    current_chat_id = message.chat.id

    user_data_from_state = await state.get_data()
    state_user_id = user_data_from_state.get('original_user_id')
    original_chat_id_of_action = user_data_from_state.get('original_chat_id')
    action_type = user_data_from_state.get('action_type')

    if state_user_id != user_id or original_chat_id_of_action != current_chat_id:
        # logger.warning(f"PurchaseConfirm YES: User ID {user_id} from chat {current_chat_id} attempted to confirm state for user {state_user_id} in chat {original_chat_id_of_action}.")
        return # Игнорируем подтверждение от другого пользователя или в другом чате

    user_link = get_user_mention_html(user_id, message.from_user.full_name, message.from_user.username)
    confirmation_initiated_at_iso = user_data_from_state.get('confirmation_initiated_at')

    timeout_seconds = CONFIRMATION_TIMEOUT_SECONDS_PHONE # По умолчанию для телефона (покупка/продажа)
    if action_type in ["buy_item", "sell_item", "repair_phone", "craft_phone"]: # Обновлено: Таймаут для предметов/действий, добавлен craft_phone
        timeout_seconds = CONFIRMATION_TIMEOUT_SECONDS_ITEM

    item_name_for_msg = "действие"
    if action_type == "buy_phone":
        item_name_for_msg = user_data_from_state.get('phone_name', 'покупку телефона')
    elif action_type == "sell_phone":
        item_name_for_msg = user_data_from_state.get('phone_name', 'продажу телефона')
    elif action_type == "buy_item":
        item_name_for_msg = user_data_from_state.get('item_name', 'покупку предмета')
    elif action_type == "sell_item": # Обновлено
        item_name_for_msg = user_data_from_state.get('item_name', 'продажу предмета')
    elif action_type == "repair_phone": 
         item_name_for_msg = user_data_from_state.get('phone_name', 'ремонт телефона')
    elif action_type == "craft_phone": # <--- ДОБАВЛЕНО для сообщения об истечении таймаута
         phone_series_to_craft_msg = user_data_from_state.get('phone_series_to_craft', 'неизвестной')
         item_name_for_msg = f'сборку телефона {phone_series_to_craft_msg}-серии'


    if confirmation_initiated_at_iso:
        try:
            confirmation_initiated_at = datetime.fromisoformat(confirmation_initiated_at_iso)
            if (datetime.now(dt_timezone.utc) - confirmation_initiated_at) > timedelta(seconds=timeout_seconds):
                await message.reply(f"Время на подтверждение \"<b>{html.escape(item_name_for_msg)}</b>\" истекло.", parse_mode="HTML")
                await state.clear()
                return
        except ValueError:
            await message.reply("Ошибка в формате времени подтверждения. Начните действие заново.")
            await state.clear()
            return
    else:
        await message.reply("Ошибка состояния подтверждения (нет времени). Пожалуйста, начните действие заново.")
        await state.clear()
        return

    conn = None
    try:
        conn = await database.get_connection()
        async with conn.transaction(): # Оборачиваем все действия с БД в транзакцию
            current_balance_before_op = await database.get_user_onecoins(user_id, original_chat_id_of_action) # Баланс из чата действия
            user_db_data_for_log = await database.get_user_data_for_update(user_id, original_chat_id_of_action, conn_ext=conn)

            if action_type == "buy_phone":
                phone_key = user_data_from_state.get('phone_key')
                phone_name = user_data_from_state.get('phone_name')
                phone_price = user_data_from_state.get('phone_price')
                phone_color = user_data_from_state.get('phone_color')
                initial_memory = user_data_from_state.get('initial_memory_gb')
                is_contraband_phone = user_data_from_state.get('is_contraband', False)

                if not all([phone_key, phone_name, isinstance(phone_price, int), phone_color, isinstance(initial_memory, int)]):
                    await message.reply("Ошибка данных покупки телефона. Начните сначала.")
                    await state.clear() # Очищаем состояние при ошибке
                    return # Транзакция откатится

                active_phones_count = await database.count_user_active_phones(user_id, conn_ext=conn) # Используем транзакцию
                max_phones = getattr(Config, "MAX_PHONES_PER_USER", 2)
                if active_phones_count >= max_phones:
                    await message.reply(
                        f"{user_link}, у вас уже максимальное количество телефонов ({active_phones_count}/{max_phones}). Покупка отменена.",
                        parse_mode="HTML",
                        disable_web_page_preview=True # <-- ДОБАВЬТЕ ЭТУ СТРОКУ
                    )
                    await state.clear()
                    return

                if current_balance_before_op < phone_price:
                    await message.reply(
                        f"{user_link}, недостаточно средств (<code>{current_balance_before_op}</code> OC) "
                        f"для \"<b>{html.escape(phone_name)}</b>\" (нужно <code>{phone_price}</code> OC).",
                        parse_mode="HTML"
                    )
                    await state.clear()
                    return

                # Списываем средства
                await database.update_user_onecoins(
                    user_id, original_chat_id_of_action, -phone_price,
                    username=user_db_data_for_log.get('username'), full_name=user_db_data_for_log.get('full_name'),
                    chat_title=user_db_data_for_log.get('chat_title'), conn_ext=conn
                )

                purchase_time = datetime.now(dt_timezone.utc)
                new_phone_inventory_id = await database.add_phone_to_user_inventory(
                    user_id, original_chat_id_of_action, phone_key, phone_color,
                    phone_price, purchase_time, initial_memory, is_contraband_phone, conn_ext=conn
                )

                if not new_phone_inventory_id:
                    raise Exception(f"Не удалось добавить телефон {phone_key} в инвентарь user {user_id}.")
                    
                    

                new_balance_after_purchase = current_balance_before_op - phone_price
                await message.reply(
                    f"✅ Поздравляем, {user_link}!\n"
                    f"Вы успешно купили <b>{html.escape(phone_name)}</b> ({phone_color}) за {phone_price} OneCoin(s).\n"
                    f"ID в инвентаре: <code>{new_phone_inventory_id}</code>\n"
                    f"Ваш новый баланс в этом чате: {new_balance_after_purchase} OneCoin(s).",
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
                await send_telegram_log(bot,
                    f"📱 Телефон куплен: {user_link} купил <b>{html.escape(phone_name)}</b> ({phone_color}, ключ: {phone_key}) "
                    f"за {phone_price} OC. ID: {new_phone_inventory_id}. Баланс: {new_balance_after_purchase} OC."
                )
                
                
                
                    # --- КОНЕЦ ВЫЗОВА ПРОВЕРКИ ДОСТИЖЕНИЙ ---

            elif action_type == "sell_phone":
                phone_inv_id_to_sell = user_data_from_state.get('phone_inventory_id')
                phone_name_to_sell = user_data_from_state.get('phone_name')
                total_sell_amount = user_data_from_state.get('total_sell_amount')
                # Данные для лога
                phone_sell_price_calc = user_data_from_state.get('phone_sell_price_calculated')
                case_sell_price_calc = user_data_from_state.get('case_sell_price_calculated')
                equipped_case_key_at_sell = user_data_from_state.get('equipped_case_key_at_sell')

                if not all([isinstance(phone_inv_id_to_sell, int), phone_name_to_sell, isinstance(total_sell_amount, int)]):
                    await message.reply("Ошибка данных продажи телефона. Начните сначала.")
                    await state.clear()
                    return

                # Проверяем, что телефон все еще принадлежит пользователю и не продан
                phone_to_sell_check = await database.get_phone_by_inventory_id(phone_inv_id_to_sell, conn_ext=conn)
                if not phone_to_sell_check or phone_to_sell_check['user_id'] != user_id:
                    await message.reply(f"Телефон ID {phone_inv_id_to_sell} больше не принадлежит вам. Продажа отменена.")
                    await state.clear()
                    return
                # Исправлено: Проверяем поле is_sold в полученных данных phone_to_sell_check, а не phone_db_data
                if phone_to_sell_check.get('is_sold', False): # Используем .get с дефолтом
                    await message.reply(f"Телефон ID <code>{phone_inv_id_to_sell}</code> уже был продан. Продажа отменена.", parse_mode="HTML")
                    await state.clear()
                    return

                # Обновляем статус телефона на "продан" и снимаем чехол (он продается вместе с телефоном, данные о нем уже есть)
                mark_sold_success = await database.update_phone_as_sold(
                    phone_inventory_id=phone_inv_id_to_sell,
                    sold_date_utc=datetime.now(dt_timezone.utc),
                    # total_sell_amount включает цену телефона и, возможно, чехла.
                    # Поле sold_price_onecoins в БД должно хранить именно эту общую сумму, за которую "ушла" запись телефона.
                    sold_price_onecoins=total_sell_amount,
                    conn_ext=conn
                )
                if not mark_sold_success:
                    # Эта ошибка более специфична и важна
                    raise Exception(f"Не удалось пометить телефон ID {phone_inv_id_to_sell} как проданный в БД (update_phone_as_sold вернул False).")

                # 2. Снимаем чехол с телефона в БД (даже если он "продан" вместе с ним, на телефоне его быть не должно)
                # Проверяем, был ли чехол на телефоне до продажи (используем phone_to_sell_check, который был получен ранее в этой же функции)
                if phone_to_sell_check and phone_to_sell_check.get('equipped_case_key'):
                    remove_case_fields = {'equipped_case_key': None}
                    remove_case_success = await database.update_phone_status_fields(
                        phone_inv_id_to_sell, remove_case_fields, conn_ext=conn
                    )
                    if not remove_case_success:
                        # Это не должно блокировать основную логику продажи, но стоит залогировать
                        logger.warning(f"SellPhone: Не удалось обновить equipped_case_key=None "
                                       f"для проданного телефона ID {phone_inv_id_to_sell} в БД. "
                                       f"Возможно, UPDATE вернул '0 строк обновлено', если чехол уже был None.")

                # Начисляем средства пользователю (этот блок у вас уже должен быть похожим)
                await database.update_user_onecoins(
                    user_id, original_chat_id_of_action, total_sell_amount,
                    username=user_db_data_for_log.get('username'), full_name=user_db_data_for_log.get('full_name'),
                    chat_title=user_db_data_for_log.get('chat_title'), conn_ext=conn
                )
                new_balance_after_sell = current_balance_before_op + total_sell_amount

                # Сообщение пользователю (этот блок у вас уже должен быть похожим)
                await message.reply(
                    f"✅ {user_link}, вы успешно продали <b>{html.escape(phone_name_to_sell)}</b> (ID: {phone_inv_id_to_sell})!\n"
                    f"Получено: {total_sell_amount} OneCoin(s).\n"
                    f"Ваш новый баланс в этом чате: {new_balance_after_sell} OneCoin(s).",
                    parse_mode="HTML"
                )

                # Логирование (этот блок у вас уже должен быть похожим, убедитесь, что он использует корректные переменные)
                case_log_str = ""
                if equipped_case_key_at_sell: # equipped_case_key_at_sell должен быть из user_data_from_state
                    case_name_log = PHONE_CASES.get(equipped_case_key_at_sell, {}).get('name', equipped_case_key_at_sell)
                    case_log_str = f" (включая чехол \"{html.escape(case_name_log)}\" за {case_sell_price_calc} OC)" # case_sell_price_calc из state

                await send_telegram_log(bot,
                    f"💸 Телефон продан: {user_link} продал <b>{html.escape(phone_name_to_sell)}</b> (ID: {phone_inv_id_to_sell}) "
                    f"за {total_sell_amount} OC{case_log_str}. "
                    # phone_sell_price_calc из state
                    f"Цена самого телефона (расчетная): {phone_sell_price_calc} OC. Баланс: {new_balance_after_sell} OC."
                )
                

            elif action_type == "insure_phone":
                phone_inv_id_to_insure = user_data_from_state.get('phone_inventory_id')
                phone_name_insured = user_data_from_state.get('phone_name') 
                insurance_cost_state = user_data_from_state.get('insurance_cost')
                current_insurance_until_iso_state = user_data_from_state.get('current_insurance_until_iso')
                # НОВЫЕ ПОЛЯ ИЗ STATE
                insurance_duration_days_state = user_data_from_state.get('insurance_duration_days', 30) # Дефолт 30 дней
                duration_display_text_state = user_data_from_state.get('duration_display_text', '1 месяц')
                is_early_renewal_log = user_data_from_state.get('is_early_renewal_for_log', False)


                if not all([isinstance(phone_inv_id_to_insure, int), phone_name_insured, isinstance(insurance_cost_state, int)]):
                    await message.reply("Ошибка данных для оформления страховки. Начните сначала.")
                    return 

                # ... (существующие повторные проверки телефона и баланса - ОСТАВЛЯЕМ ИХ) ...
                # ... (списание средств - ОСТАВЛЯЕМ) ...

                # Расчет новой даты окончания страховки
                now_utc = datetime.now(dt_timezone.utc)
                start_date_for_new_insurance = now_utc
                
                current_insurance_until_dt = None
                if current_insurance_until_iso_state:
                    try:
                        current_insurance_until_dt = datetime.fromisoformat(current_insurance_until_iso_state)
                        if current_insurance_until_dt.tzinfo is None:
                           current_insurance_until_dt = current_insurance_until_dt.replace(tzinfo=dt_timezone.utc)
                        else:
                           current_insurance_until_dt = current_insurance_until_dt.astimezone(dt_timezone.utc)
                    except ValueError: # Ошибка парсинга
                        current_insurance_until_dt = None

                if current_insurance_until_dt and current_insurance_until_dt > now_utc:
                    start_date_for_new_insurance = current_insurance_until_dt
                
                # ИСПОЛЬЗУЕМ insurance_duration_days_state
                new_insurance_until_utc = start_date_for_new_insurance + timedelta(days=insurance_duration_days_state) 
                
                update_success = await database.update_phone_status_fields(
                    phone_inv_id_to_insure, 
                    {'insurance_active_until': new_insurance_until_utc}, 
                    conn_ext=conn
                )
                if not update_success:
                    raise Exception(f"Не удалось обновить дату страховки для телефона ID {phone_inv_id_to_insure}.")

                new_balance_after_op = current_balance_before_op - insurance_cost_state
                new_insurance_until_display_confirm = new_insurance_until_utc.astimezone(pytz_timezone(Config.TIMEZONE)).strftime('%Y-%m-%d %H:%M %Z')

                success_message_parts = [
                    f"✅ {user_link}, страховка для телефона \"<b>{phone_name_insured}</b>\" (ID: {phone_inv_id_to_insure}) "
                    f"успешно оформлена/продлена на <b>{duration_display_text_state}</b> до {new_insurance_until_display_confirm}!"
                ]
                if duration_display_text_state == "1 месяц" and is_early_renewal_log:
                    base_1m_cost_msg = getattr(Config, "PHONE_INSURANCE_COST", 50)
                    success_message_parts.append(f"(<i>Цена со скидкой {insurance_cost_state} OC, обычная цена {base_1m_cost_msg} OC</i>)")
                
                success_message_parts.extend([
                    f"Списано: {insurance_cost_state} OneCoin(s).",
                    f"Ваш новый баланс в этом чате: {new_balance_after_op} OneCoin(s)."
                ])
                await message.reply("\n".join(success_message_parts), parse_mode="HTML")
                
                log_renewal_type_str = ""
                if duration_display_text_state == "1 месяц" and is_early_renewal_log:
                    log_renewal_type_str = " (раннее продление со скидкой)"

                await send_telegram_log(bot,
                    f"🛡️ Страховка оформлена{log_renewal_type_str}: {user_link} для телефона \"{phone_name_insured}\" "
                    f"(ID: {phone_inv_id_to_insure}) на {duration_display_text_state} до {new_insurance_until_display_confirm}. "
                    f"Цена: {insurance_cost_state} OC. Баланс: {new_balance_after_op} OC."
                )
                



            # --- НАЧАЛО НОВОГО БЛОКА ДЛЯ ПРОДАЖИ ПРЕДМЕТА (sell_item) ---
            elif action_type == "sell_item":
                user_item_id_sold = user_data_from_state.get('user_item_id_to_sell')
                item_key_sold = user_data_from_state.get('item_key')
                item_type_sold = user_data_from_state.get('item_type')
                item_name_sold = user_data_from_state.get('item_name') # Уже экранировано при записи в state
                quantity_sold = user_data_from_state.get('quantity_to_sell')
                total_value_received = user_data_from_state.get('total_sell_value')
                sell_price_unit = user_data_from_state.get('sell_price_per_unit') # для лога
                original_price_unit = user_data_from_state.get('original_price_per_unit') # для лога

                if not all([isinstance(user_item_id_sold, int), item_key_sold, item_type_sold, item_name_sold,
                             isinstance(quantity_sold, int) and quantity_sold > 0,
                             isinstance(total_value_received, int)]):
                    # Если данные некорректны, сообщение об ошибке уже может быть в логе,
                    # но на всякий случай сообщаем пользователю.
                    await message.reply("Ошибка данных продажи предмета. Начните сначала.")
                    # Транзакция откатится автоматически при выходе из async with с исключением
                    return # Важно выйти, если данные некорректны

                # Проверяем, существует ли еще предмет и достаточно ли количества
                # (на случай, если между запросом и подтверждением что-то изменилось)
                # Эта проверка использует conn из внешнего try/finally блока функции cmd_purchase_confirm_yes
                item_check_db = await database.get_user_item_by_id(user_item_id_sold, user_id=user_id, conn_ext=conn)
                if not item_check_db:
                    await message.reply(f"Предмет ID {user_item_id_sold} больше не найден в вашем инвентаре. Продажа отменена.")
                    return
                # NOTE: Для стакаемых предметов item_check_db['quantity'] может быть больше 1.
                # Для чехлов item_check_db['quantity'] всегда 1 в этой реализации.
                if item_check_db['quantity'] < quantity_sold:
                    await message.reply(f"У вас осталось только {item_check_db['quantity']} шт. предмета \"{html.escape(item_name_sold)}\" (ID: {user_item_id_sold}). Нельзя продать {quantity_sold}. Продажа отменена.", parse_mode="HTML")
                    return

                # Удаляем/уменьшаем количество предмета в инвентаре
                # Логика удаления в database.remove_item_from_user_inventory обрабатывает
                # стакаемые предметы (quantity_to_remove) и уникальные (user_item_id_to_remove).
                # Передаем user_item_id_sold только для уникальных (чехлов).
                # quantity_to_remove для стакаемых берем из quantity_sold. Для чехла удаляем 1 шт. запись по ID.
                id_for_removal_param = user_item_id_sold if item_type_sold == 'case' else None
                quantity_for_removal = quantity_sold # Количество для списания из стакаемой записи, если это не чехол
                # Если это чехол, quantity_sold из state будет 1, а логика remove_item_from_user_inventory
                # при наличии user_item_id_to_remove удалит именно эту запись.

                remove_success = await database.remove_item_from_user_inventory(
                    user_id, item_key_sold, item_type_sold,
                    quantity_to_remove=quantity_for_removal, # Передаем количество для стакаемых
                    user_item_id_to_remove=id_for_removal_param, # Передаем user_item_id_sold только если это чехол
                    conn_ext=conn
                )

                if not remove_success:
                    # Эта ошибка более специфична и важна
                    raise Exception(f"Не удалось удалить/уменьшить предмет ID {user_item_id_sold} (ключ: {item_key_sold}, тип: {item_type_sold}, кол-во: {quantity_sold}) из инвентаря.")

                # Начисляем OneCoins
                # user_db_data_for_log уже получены в начале cmd_purchase_confirm_yes
                await database.update_user_onecoins(
                    user_id, original_chat_id_of_action, total_value_received,
                    username=user_db_data_for_log.get('username'),
                    full_name=user_db_data_for_log.get('full_name'),
                    chat_title=user_db_data_for_log.get('chat_title'),
                    conn_ext=conn
                )
                new_balance_after_sell = current_balance_before_op + total_value_received

                quantity_text_msg = f"{quantity_sold} шт. " if quantity_sold > 1 else ""
                await message.reply(
                    f"✅ {user_link}, вы успешно продали {quantity_text_msg}<b>{item_name_sold}</b> (ID инвентаря: {user_item_id_sold})!\n"
                    f"Получено: {total_value_received} OneCoin(s).\n"
                    f"Ваш новый баланс в этом чате: {new_balance_after_sell} OneCoin(s).",
                    parse_mode="HTML"
                )

                await send_telegram_log(bot,
                    f"♻️ Предмет продан: {user_link} продал {quantity_text_msg}<b>{item_name_sold}</b> "
                    f"(ID инв: {user_item_id_sold}, ключ: {item_key_sold}, тип: {item_type_sold}) "
                    f"за {total_value_received} OC (по {sell_price_unit} OC/шт, ориг. цена {original_price_unit} OC/шт). "
                    f"Баланс: {new_balance_after_sell} OC."
                )
            # --- КОНЕЦ НОВОГО БЛОКА sell_item ---


            elif action_type == "buy_item":
                item_key = user_data_from_state.get('item_key')
                item_name = user_data_from_state.get('item_name') # Уже экранировано при записи в state
                item_type = user_data_from_state.get('item_type')
                item_price_total = user_data_from_state.get('item_price_total')
                quantity_to_buy = user_data_from_state.get('quantity_to_buy')

                if not all([item_key, item_name, item_type, isinstance(item_price_total, int), isinstance(quantity_to_buy, int)]):
                    await message.reply("Ошибка данных покупки предмета. Начните сначала.")
                    await state.clear()
                    return

                if current_balance_before_op < item_price_total:
                    await message.reply(
                        f"{user_link}, недостаточно средств (<code>{current_balance_before_op}</code> OC) "
                        f"для покупки {quantity_to_buy} шт. \"<b>{item_name}</b>\" (нужно <code>{item_price_total}</code> OC).",
                        parse_mode="HTML"
                    )
                    await state.clear()
                    return

                # Списываем средства
                await database.update_user_onecoins(
                    user_id, original_chat_id_of_action, -item_price_total,
                    username=user_db_data_for_log.get('username'), full_name=user_db_data_for_log.get('full_name'),
                    chat_title=user_db_data_for_log.get('chat_title'), conn_ext=conn
                )

                add_success = await database.add_item_to_user_inventory(
                    user_id, item_key, item_type, quantity_to_buy, conn_ext=conn
                )

                if not add_success:
                    raise Exception(f"Не удалось добавить предмет {item_key} (x{quantity_to_buy}) в инвентарь user {user_id}.")

                new_balance_after_purchase = current_balance_before_op - item_price_total
                item_quantity_str = f"{quantity_to_buy} шт. " if quantity_to_buy > 1 and item_type != 'case' else ""
                await message.reply(
                    f"✅ Поздравляем, {user_link}!\n"
                    f"Вы успешно купили {item_quantity_str}<b>{item_name}</b> за {item_price_total} OneCoin(s).\n"
                    f"Ваш новый баланс в этом чате: {new_balance_after_purchase} OneCoin(s).",
                    parse_mode="HTML"
                )
                await send_telegram_log(bot,
                    f"🛍️ Предмет куплен: {user_link} купил {item_quantity_str}<b>{item_name}</b> (ключ: {item_key}) "
                    f"за {item_price_total} OC. Баланс: {new_balance_after_purchase} OC."
                )
            elif action_type == "repair_phone": # <--- СУЩЕСТВУЮЩИЙ БЛОК
                 phone_inv_id_to_repair = user_data_from_state.get('phone_inventory_id')
                 phone_name_to_repair = user_data_from_state.get('phone_name') # Уже экранировано при записи в state
                 broken_component_key_repair = user_data_from_state.get('broken_component_key')
                 broken_component_name_repair = user_data_from_state.get('broken_component_name') # Уже экранировано при записи в state
                 repair_work_cost_calc = user_data_from_state.get('repair_work_cost')

                 if not all([isinstance(phone_inv_id_to_repair, int), phone_name_to_repair, broken_component_key_repair, broken_component_name_repair, isinstance(repair_work_cost_calc, int)]):
                     await message.reply("Ошибка данных ремонта телефона. Начните сначала.")
                     await state.clear()
                     return

                 # Проверяем, что телефон все еще сломан этим компонентом
                 phone_to_repair_check = await database.get_phone_by_inventory_id(phone_inv_id_to_repair, conn_ext=conn)
                 if not phone_to_repair_check or phone_to_repair_check['user_id'] != user_id or \
                    not phone_to_repair_check.get('is_broken') or phone_to_repair_check.get('broken_component_key') != broken_component_key_repair:
                     await message.reply(f"Телефон ID {phone_inv_id_to_repair} больше не требует ремонта или поломка изменилась. Ремонт отменен.")
                     await state.clear()
                     return

                 # Проверяем наличие детали в инвентаре (еще раз, на всякий случай)
                 broken_comp_info = PHONE_COMPONENTS.get(broken_component_key_repair)
                 if not broken_comp_info:
                     await message.reply(f"Ошибка: данные для компонента {html.escape(broken_component_key_repair)} не найдены. Ремонт отменен.", parse_mode="HTML")
                     await state.clear()
                     return
                     
                 # --- vvv НОВЫЙ КОД: ПРОВЕРКА КОМПОНЕНТА НА БРАК ---
                 item_for_repair_data_db = None
                 if component_user_item_id_for_repair: # Если у нас есть ID конкретного экземпляра компонента
                     item_for_repair_data_db = await database.get_user_item_by_id(component_user_item_id_for_repair, user_id, conn_ext=conn)
                 
                 if item_for_repair_data_db:
                     item_custom_data = await database.get_item_custom_data(item_for_repair_data_db['user_item_id'], conn_ext=conn) or {} # Используем новую функцию
                     is_contraband_component = item_custom_data.get("is_bm_contraband", False)
                     is_defective_component = item_custom_data.get("is_defective", False)

                     if is_contraband_component and is_defective_component:
                         # Удаляем бракованный компонент
                         await database.remove_item_from_user_inventory(
                             user_id, broken_component_key_repair, 
                             broken_comp_info.get("component_type", "component"), 
                             quantity_to_remove=1, # Удаляем 1 шт.
                             user_item_id_to_remove=item_for_repair_data_db['user_item_id'], # Указываем ID конкретного бракованного
                             conn_ext=conn
                         )
                         await message.reply(
                             f"🥷 Ой-ой! Компонент \"<b>{broken_component_name_repair_esc}</b>\" с Чёрного Рынка оказался бракованным и рассыпался в пыль! "
                             f"Ремонт не выполнен. Попробуйте найти другую деталь.", parse_mode="HTML"
                         )
                         await send_telegram_log(bot, f"🚫 Брак ЧР: {user_link} пытался починить \"{broken_component_name_repair_esc}\" бракованной деталью с ЧР. Деталь удалена.")
                         return # Выходим, транзакция откатится для списания денег за работу, если оно было до
                 elif component_user_item_id_for_repair: # Если ID был, но предмет не найден
                     await message.reply(f"Ошибка: выбранная деталь \"{broken_component_name_repair_esc}\" не найдена в вашем инвентаре. Ремонт отменен.", parse_mode="HTML")
                     return
                 # Если component_user_item_id_for_repair не был передан или предмет не найден,
                 # то старая логика проверки количества user_has_comp_count сработает ниже.
                 # Но для корректной проверки брака нужен ID конкретного экземпляра.
                 # --- ^^^ КОНЕЦ НОВОГО КОДА ^^^    

                 user_has_comp_count = await database.get_user_specific_item_count(user_id, broken_component_key_repair, broken_comp_info.get("component_type", "component"), conn_ext=conn)
                 if user_has_comp_count < 1:
                      await message.reply(f"У вас больше нет необходимой детали \"{broken_component_name_repair}\" для ремонта.", parse_mode="HTML")
                      await state.clear()
                      return

                 if current_balance_before_op < repair_work_cost_calc:
                      await message.reply(f"Недостаточно средств ({current_balance_before_op} OC) для оплаты работы мастера ({repair_work_cost_calc} OC). Ремонт отменен.")
                      await state.clear()
                      return

                 # Списываем средства за работу
                 await database.update_user_onecoins(
                     user_id, original_chat_id_of_action, -repair_work_cost_calc,
                     username=user_db_data_for_log.get('username'), full_name=user_db_data_for_log.get('full_name'),
                     chat_title=user_db_data_for_log.get('chat_title'), conn_ext=conn
                 )

                 # Списываем деталь
                 remove_comp_success = await database.remove_item_from_user_inventory(
                     user_id, broken_component_key_repair, broken_comp_info.get("component_type", "component"), 1, conn_ext=conn
                 )
                 if not remove_comp_success:
                      raise Exception(f"Не удалось списать компонент {broken_component_key_repair} у user {user_id} при ремонте телефона {phone_inv_id_to_repair}.")

                 # Обновляем статус телефона - он больше не сломан
                 update_phone_success = await database.update_phone_status_fields(
                     phone_inv_id_to_repair, {'is_broken': False, 'broken_component_key': None}, conn_ext=conn
                 )
                 if not update_phone_success:
                      raise Exception(f"Не удалось обновить статус телефона ID {phone_inv_id_to_repair} после ремонта в БД.")

                 new_balance_after_repair = current_balance_before_op - repair_work_cost_calc

                 await message.reply(
                     f"✅ {user_link}, вы успешно починили \"<b>{broken_component_name_repair}</b>\" "
                     f"на телефоне \"<b>{html.escape(phone_name_to_repair)}</b>\" (ID: {phone_inv_id_to_repair})!\n"
                     f"Списано {repair_work_cost_calc} OC за работу и 1 шт. \"<b>{broken_component_name_repair}</b>\" из инвентаря.\n" # Добавлено HTML escape и жирный шрифт
                     f"Ваш новый баланс в этом чате: {new_balance_after_repair} OneCoin(s).",
                     parse_mode="HTML"
                 )
                 await send_telegram_log(bot,
                     f"🔧 Телефон починен: {user_link} починил \"{broken_component_name_repair}\" "
                     f"на телефоне \"{html.escape(phone_name_to_repair)}\" (ID: {phone_inv_id_to_repair}) "
                     f"за {repair_work_cost_calc} OC и 1 деталь. Баланс: {new_balance_after_repair} OC."
                 )
                 
                 # --- ВЫЗОВ ПРОВЕРКИ ДОСТИЖЕНИЙ ---
                 
                 # --- КОНЕЦ ВЫЗОВА ПРОВЕРКИ ДОСТИЖЕНИЙ ---
                 
                 
            # --- БЛОК ДЛЯ СБОРКИ ТЕЛЕФОНА (craft_phone) ---
            elif action_type == "craft_phone":
                phone_series_to_craft = user_data_from_state.get('phone_series_to_craft')
                components_to_use_keys = user_data_from_state.get('components_to_use_keys')

                if not phone_series_to_craft or not components_to_use_keys or not isinstance(components_to_use_keys, list) or len(components_to_use_keys) != 5:
                    await message.reply("Ошибка данных для сборки телефона. Пожалуйста, начните сначала с /craftphone.")
                    logger.error(f"CraftPhone Confirm: Некорректные данные в state для user {user_id}: series='{phone_series_to_craft}', components='{components_to_use_keys}'")
                    return # Транзакция откатится

                # Повторная проверка лимита телефонов
                active_phones_count_craft = await database.count_user_active_phones(user_id, conn_ext=conn)
                max_phones_craft = getattr(Config, "MAX_PHONES_PER_USER", 2)
                if active_phones_count_craft >= max_phones_craft:
                    await message.reply(
                        f"{user_link}, у вас уже максимальное количество телефонов ({active_phones_count_craft}/{max_phones_craft}). "
                        f"Сборка отменена.",
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )
                    return

                # Повторная проверка наличия компонентов
                missing_components_for_craft_names: List[str] = []
                for comp_key in components_to_use_keys: 
                    comp_static_info = PHONE_COMPONENTS.get(comp_key)
                    if not comp_static_info: 
                        logger.error(f"CraftPhone Confirm: Статическая инфо для компонента {comp_key} не найдена для user {user_id}")
                        missing_components_for_craft_names.append(f"данные для {comp_key} (ошибка)")
                        continue

                    # ИСПРАВЛЕНИЕ: Всегда берем 'component_type' из статических данных.
                    # Поскольку в item_data.py для всех компонентов телефона теперь 'component', 
                    # comp_type_for_check будет 'component'.
                    comp_type_for_check = comp_static_info.get("component_type") 

                    # Если вдруг в item_data.py для какого-то компонента забыли указать component_type
                    if not comp_type_for_check:
                        logger.error(f"CraftPhone Confirm: 'component_type' не найден для {comp_key} в PHONE_COMPONENTS. Используется 'component' по умолчанию.")
                        comp_type_for_check = "component" # Безопасное значение по умолчанию

                    logger.info(f"[CRAFT_CHECK] User: {user_id}, Checking component: Key='{comp_key}', TypeForCheck='{comp_type_for_check}'")

                    has_comp_count = await database.get_user_specific_item_count(
                        user_id, comp_key, comp_type_for_check, conn_ext=conn
                    )

                    logger.info(f"[CRAFT_CHECK_RESULT] User: {user_id}, Component: Key='{comp_key}', TypeForCheck='{comp_type_for_check}', FoundCount={has_comp_count}")

                    if has_comp_count < 1:
                        missing_components_for_craft_names.append(comp_static_info.get('name', comp_key))
                
                if missing_components_for_craft_names:
                    missing_list_str = "\n - ".join(missing_components_for_craft_names)
                    await message.reply(
                        f"{user_link}, во время подтверждения выяснилось, что у вас не хватает:\n"
                        f" - {missing_list_str}\n"
                        f"Сборка отменена. Пожалуйста, проверьте инвентарь (/myitems) и попробуйте снова.",
                        parse_mode="HTML"
                    )
                    return

                # Логика выбора модели телефона для крафта
                # Фильтруем PHONE_MODELS (словарь) по серии
                craftable_phones_in_series = [
                    model_info for model_key, model_info in PHONE_MODELS.items()
                    if model_info.get("series") == phone_series_to_craft
                ]

                if not craftable_phones_in_series:
                    await message.reply(f"К сожалению, в данный момент нет доступных для сборки моделей {phone_series_to_craft}-серии (внутренняя ошибка). Попробуйте позже.")
                    logger.error(f"CraftPhone Confirm: Нет моделей для крафта в серии {phone_series_to_craft} для user {user_id}")
                    return
                
                crafted_phone_model_static = random.choice(craftable_phones_in_series)
                crafted_phone_key = crafted_phone_model_static['key']
                crafted_phone_name_display = html.escape(crafted_phone_model_static['name'])

                # Списываем компоненты
                for comp_key_to_remove in components_to_use_keys:
                    comp_static_info_remove = PHONE_COMPONENTS.get(comp_key_to_remove)
                    if not comp_static_info_remove: # Маловероятно после предыдущих проверок
                        raise Exception(f"Ошибка конфигурации: компонент {comp_key_to_remove} не найден при списании для крафта.")

                    # Определяем тип компонента для функции remove_item_from_user_inventory
                    # Это важно, т.к. для чехлов и компонентов/модулей логика удаления разная.
                    # Но здесь мы ТОЧНО знаем, что это компоненты телефона (не чехлы).
                    item_type_for_removal = comp_static_info_remove.get("component_type", "component")
                    # Если component_type не указан явно или он "component", пытаемся уточнить из ключа
                    

                    remove_success = await database.remove_item_from_user_inventory(
                        user_id, comp_key_to_remove, item_type_for_removal, 
                        quantity_to_remove=1, conn_ext=conn
                    )
                    if not remove_success:
                        raise Exception(f"Не удалось списать компонент {comp_key_to_remove} для крафта у user {user_id}")

                # Выбор цвета и определение начальной памяти
                crafted_phone_color = random.choice(PHONE_COLORS)
                
                memory_str_crafted = crafted_phone_model_static.get('memory', '0').upper()
                initial_memory_crafted_gb = 0
                if 'TB' in memory_str_crafted:
                    try: initial_memory_crafted_gb = int(float(memory_str_crafted.replace('TB', '').strip()) * 1024)
                    except ValueError: initial_memory_crafted_gb = 1024 # Default for TB if parse fails
                elif 'GB' in memory_str_crafted:
                    try: initial_memory_crafted_gb = int(float(memory_str_crafted.replace('GB', '').strip()))
                    except ValueError: initial_memory_crafted_gb = 0 # Default for GB if parse fails
                
                # Добавляем новый телефон в инвентарь
                purchase_time_craft = datetime.now(dt_timezone.utc)
                # Цена покупки для скрафченного телефона = 0
                # (или можно сделать суммой стоимостей деталей, но по ТЗ 0)
                purchase_price_for_crafted = 0 

                new_crafted_phone_inventory_id = await database.add_phone_to_user_inventory(
                    user_id,
                    original_chat_id_of_action, # Чат, где была инициирована команда
                    crafted_phone_key,
                    crafted_phone_color,
                    purchase_price_for_crafted, # Цена 0
                    purchase_time_craft,
                    initial_memory_crafted_gb,
                    is_contraband=False, # По умолчанию не контрабанда
                    conn_ext=conn
                )

                if not new_crafted_phone_inventory_id:
                    raise Exception(f"Не удалось добавить скрафченный телефон {crafted_phone_key} в инвентарь user {user_id}")

                await message.reply(
                    f"🎉 Поздравляем, {user_link}!\n"
                    f"Вы успешно собрали новый телефон: <b>{crafted_phone_name_display}</b> ({crafted_phone_color})!\n"
                    f"ID в инвентаре: <code>{new_crafted_phone_inventory_id}</code>\n"
                    f"Проверьте его в /myphones.",
                    parse_mode="HTML"
                )

                # Формируем список названий использованных компонентов для лога
                used_component_names_log = []
                for comp_key_log in components_to_use_keys:
                    comp_info_log = PHONE_COMPONENTS.get(comp_key_log)
                    used_component_names_log.append(comp_info_log.get('name', comp_key_log) if comp_info_log else comp_key_log)
                
                await send_telegram_log(bot,
                    f"🛠️ Телефон собран: {user_link} собрал <b>{crafted_phone_name_display}</b> ({crafted_phone_color}, ключ: {crafted_phone_key}) "
                    f"{phone_series_to_craft}-серии. ID: {new_crafted_phone_inventory_id}.\n"
                    f"Использованы компоненты: {', '.join(map(html.escape, used_component_names_log))}."
                )
            else:
                logger.warning(f"PurchaseConfirm YES: Неизвестный action_type '{action_type}' в состоянии для user {user_id}.")
                await message.reply("Неизвестное действие для подтверждения.")

    except Exception as e_confirm:
        logger.error(f"PurchaseConfirm YES: Ошибка при подтверждении ({action_type}) для user {user_id}: {e_confirm}", exc_info=True)
        err_msg_item_name = "действие"
        if action_type == "buy_phone": err_msg_item_name = user_data_from_state.get('phone_name', 'покупку телефона')
        elif action_type == "sell_phone": err_msg_item_name = user_data_from_state.get('phone_name', 'продажу телефона')
        elif action_type == "buy_item": err_msg_item_name = user_data_from_state.get('item_name', 'покупку предмета')
        elif action_type == "sell_item": err_msg_item_name = user_data_from_state.get('item_name', 'продажу предмета') 
        elif action_type == "repair_phone": err_msg_item_name = user_data_from_state.get('phone_name', 'ремонт телефона') 
        elif action_type == "craft_phone": # <--- ДОБАВЛЕНО для сообщения об ошибке
            phone_series_to_craft_err_msg = user_data_from_state.get('phone_series_to_craft', 'неизвестной')
            err_msg_item_name = f'сборку телефона {phone_series_to_craft_err_msg}-серии'


        await message.reply(f"Произошла серьезная ошибка при совершении \"<b>{html.escape(err_msg_item_name)}</b>\". "
                            "Изменения должны были быть отменены. Если это не так, обратитесь к администратору.",
                            parse_mode="HTML")
        # --- ВЫЗОВ ПРОВЕРКИ ДОСТИЖЕНИЙ ---
        
                # --- КОНЕЦ ВЫЗОВА ПРОВЕРКИ ДОСТИЖЕНИЙ ---                          
                            
    finally:
        if conn and not conn.is_closed():
            await conn.close()
        await state.clear()
        
        
@phone_router.message(Command("insurephone", "застраховатьтелефон", ignore_case=True))
async def cmd_insurephone_start(message: Message, command: CommandObject, state: FSMContext, bot: Bot):
    if not message.from_user:
        return await message.reply("Не удалось определить пользователя.")

    user_id = message.from_user.id
    chat_id = message.chat.id
    user_link = get_user_mention_html(user_id, message.from_user.full_name, message.from_user.username)

    args_list = command.args.split() if command.args else []
    phone_inventory_id_arg: Optional[int] = None
    duration_choice_arg: Optional[str] = None # '1m' или '6m'

    if not args_list:
        await message.reply(
            f"{user_link}, укажите ID телефона и срок страхования (<code>1m</code> или <code>6m</code>).\n"
            f"Примеры:\n"
            f"  <code>/insurephone 123 1m</code> (на 1 месяц)\n"
            f"  <code>/insurephone 123 6m</code> (на 6 месяцев)\n"
            f"ID ваших телефонов: /myphones",
            parse_mode="HTML"
        )
        return

    if len(args_list) < 1: # Должен быть хотя бы ID
        # Сообщение об ошибке уже было выше, но на всякий случай
        await message.reply("Пожалуйста, укажите ID телефона.")
        return
        
    try:
        phone_inventory_id_arg = int(args_list[0])
    except ValueError:
        await message.reply("ID телефона должен быть числом.")
        return

    if len(args_list) > 1:
        duration_choice_arg = args_list[1].lower()
        if duration_choice_arg not in ["1m", "6m"]:
            await message.reply(f"Неверный срок страхования. Укажите <code>1m</code> (1 месяц) или <code>6m</code> (6 месяцев).")
            return
    else: # Если срок не указан, по умолчанию предлагаем 1 месяц
        duration_choice_arg = "1m"


    conn = None
    try:
        conn = await database.get_connection()
        phone_db_data = await database.get_phone_by_inventory_id(phone_inventory_id_arg, conn_ext=conn)

        # ... (существующие проверки телефона: не найден, продан, сломан - ОСТАВЛЯЕМ ИХ) ...
        if not phone_db_data or phone_db_data['user_id'] != user_id: # Проверка принадлежности
            await message.reply(f"Телефон с ID <code>{phone_inventory_id_arg}</code> не найден в вашем инвентаре.", parse_mode="HTML")
            if conn and not conn.is_closed(): await conn.close() # Закрываем, если выходим
            return
        if phone_db_data.get('is_sold', False):
            await message.reply(f"Телефон ID <code>{phone_inventory_id_arg}</code> уже продан.", parse_mode="HTML")
            if conn and not conn.is_closed(): await conn.close()
            return
        if phone_db_data.get('is_broken'):
            await message.reply(f"Телефон ID <code>{phone_inventory_id_arg}</code> сломан. Сначала почините его, чтобы оформить страховку.", parse_mode="HTML")
            if conn and not conn.is_closed(): await conn.close()
            return


        phone_model_key = phone_db_data['phone_model_key']
        phone_static_data = PHONE_MODELS.get(phone_model_key)
        if not phone_static_data:
            await message.reply(f"Ошибка: не найдены данные для модели телефона ID <code>{phone_inventory_id_arg}</code>.", parse_mode="HTML")
            if conn and not conn.is_closed(): await conn.close()
            return
        
        phone_name_display = html.escape(phone_static_data.get('name', phone_model_key))
        now_utc = datetime.now(dt_timezone.utc)
        current_insurance_until = phone_db_data.get('insurance_active_until')
        current_insurance_until_iso = None
        current_insurance_until_display = "нет"

        insurance_duration_days: int
        actual_insurance_cost: int
        duration_display_text: str

        if duration_choice_arg == "6m":
            insurance_duration_days = getattr(Config, "PHONE_INSURANCE_DURATION_6_MONTHS_DAYS", 180)
            actual_insurance_cost = getattr(Config, "PHONE_INSURANCE_COST_6_MONTHS", 270)
            duration_display_text = "6 месяцев"
            # Здесь можно добавить логику скидки на раннее продление для 6м, если хотите
        else: # По умолчанию 1m
            insurance_duration_days = 30 
            base_insurance_cost = getattr(Config, "PHONE_INSURANCE_COST", 50)
            early_renewal_days = getattr(Config, "PHONE_INSURANCE_EARLY_RENEWAL_DAYS", 5)
            early_renewal_cost = getattr(Config, "PHONE_INSURANCE_EARLY_RENEWAL_COST", 40)
            actual_insurance_cost = base_insurance_cost
            duration_display_text = "1 месяц"
            is_early_renewal = False # Этот флаг теперь специфичен для 1m

            if current_insurance_until:
                # ... (Ваша существующая логика парсинга current_insurance_until и приведения к aware datetime) ...
                if isinstance(current_insurance_until, str):
                    try: current_insurance_until = datetime.fromisoformat(current_insurance_until)
                    except ValueError: current_insurance_until = None
                if isinstance(current_insurance_until, datetime):
                    if current_insurance_until.tzinfo is None: current_insurance_until = current_insurance_until.replace(tzinfo=dt_timezone.utc)
                    else: current_insurance_until = current_insurance_until.astimezone(dt_timezone.utc)
                    
                    current_insurance_until_iso = current_insurance_until.isoformat()
                    current_insurance_until_display = current_insurance_until.astimezone(pytz_timezone(Config.TIMEZONE)).strftime('%Y-%m-%d %H:%M %Z')
                
                    # Проверка на слишком раннее продление (оставляем ее общей)
                    # (можно решить, применимо ли это к 6-месячной страховке так же)
                    if current_insurance_until > (now_utc + timedelta(days=max(7, early_renewal_days + 2))):
                        await message.reply(
                            f"{user_link}, телефон \"<b>{phone_name_display}</b>\" уже застрахован до {current_insurance_until_display}.\n"
                            f"Продлить страховку можно будет позже.", parse_mode="HTML")
                        if conn and not conn.is_closed(): await conn.close()
                        return
                    
                    # Логика скидки для 1-месячного продления
                    if duration_choice_arg == "1m": # Скидка только для 1m
                        time_until_expiry = current_insurance_until - now_utc
                        if now_utc < current_insurance_until and time_until_expiry <= timedelta(days=early_renewal_days): # Используем <=
                            actual_insurance_cost = early_renewal_cost
                            is_early_renewal = True
                            logger.info(f"InsurePhone: User {user_id} phone {phone_inventory_id_arg} eligible for 1m early renewal. Cost: {actual_insurance_cost} OC.")
        
        current_balance = await database.get_user_onecoins(user_id, chat_id)
        if current_balance < actual_insurance_cost:
            await message.reply(
                f"{user_link}, у вас недостаточно средств ({actual_insurance_cost} OC) для страховки на {duration_display_text}. Ваш баланс: {current_balance} OC.",
                parse_mode="HTML")
            if conn and not conn.is_closed(): await conn.close()
            return

        start_date_for_new_insurance = now_utc
        if current_insurance_until and current_insurance_until > now_utc:
            start_date_for_new_insurance = current_insurance_until
        
        new_insurance_until_calc = start_date_for_new_insurance + timedelta(days=insurance_duration_days)
        new_insurance_until_display = new_insurance_until_calc.astimezone(pytz_timezone(Config.TIMEZONE)).strftime('%Y-%m-%d %H:%M %Z')

        await state.set_state(PurchaseStates.awaiting_confirmation)
        state_data_to_set = {
            "action_type": "insure_phone",
            "phone_inventory_id": phone_inventory_id_arg,
            "phone_name": phone_name_display,
            "insurance_cost": actual_insurance_cost,
            "insurance_duration_days": insurance_duration_days, # НОВОЕ ПОЛЕ
            "duration_display_text": duration_display_text, # НОВОЕ ПОЛЕ
            "current_insurance_until_iso": current_insurance_until_iso,
            "confirmation_initiated_at": datetime.now(dt_timezone.utc).isoformat(),
            "original_chat_id": chat_id,
            "original_user_id": user_id
        }
        if duration_choice_arg == "1m" and is_early_renewal: # Флаг is_early_renewal только для 1м
            state_data_to_set["is_early_renewal_for_log"] = True
        
        await state.update_data(**state_data_to_set)

        confirmation_message_parts = [
            f"{user_link}, вы хотите оформить/продлить страховку на телефон",
            f"\"<b>{phone_name_display}</b>\" (ID: {phone_inventory_id_arg}) на <b>{duration_display_text}</b> за {actual_insurance_cost} OC?",
        ]
        if duration_choice_arg == "1m" and is_early_renewal:
             base_1m_cost = getattr(Config, "PHONE_INSURANCE_COST", 50)
             confirmation_message_parts.append(f"(<i>Цена со скидкой за раннее продление! Обычная цена на 1 месяц: {base_1m_cost} OC</i>)")
        
        confirmation_message_parts.extend([
            f"Текущая страховка активна до: {current_insurance_until_display}.",
            f"Новая страховка будет действовать до: {new_insurance_until_display}.",
            "(Страховка дает 80% скидку на стоимость <b>работы</b> при ремонте).",
            f"Ответьте 'Да' или 'Нет' в течение {CONFIRMATION_TIMEOUT_SECONDS_PHONE} секунд."
        ])
        await message.reply("\n".join(confirmation_message_parts), parse_mode="HTML")
        
        # --- ВЫЗОВ ПРОВЕРКИ ДОСТИЖЕНИЙ ---
        
                # --- КОНЕЦ ВЫЗОВА ПРОВЕРКИ ДОСТИЖЕНИЙ ---

    except Exception as e_insure_start:
        logger.error(f"InsurePhone: Ошибка на старте для user {user_id}, phone_id {phone_inventory_id_arg}, duration {duration_choice_arg}: {e_insure_start}", exc_info=True)
        await message.reply("Произошла ошибка при начале оформления страховки.")
        await send_telegram_log(bot, f"🔴 Ошибка в /insurephone (старт) для {user_link}, телефон ID {phone_inventory_id_arg}, срок {duration_choice_arg}: <pre>{html.escape(str(e_insure_start))}</pre>")
    finally:
        if conn and not conn.is_closed():
            await conn.close()        
        


@phone_router.message(PurchaseStates.awaiting_confirmation, F.text.lower() == "нет")
async def cmd_purchase_confirm_no(message: Message, state: FSMContext):
    user_data_from_state = await state.get_data()
    state_user_id = user_data_from_state.get('original_user_id')
    action_type = user_data_from_state.get('action_type')

    if state_user_id != message.from_user.id:
        return

    item_name_display = "действие" # Общее слово
    if action_type == "buy_phone":
        item_name_display = f"покупку \"<b>{html.escape(user_data_from_state.get('phone_name', 'телефона'))}</b>\""
    elif action_type == "sell_phone":
        item_name_display = f"продажу \"<b>{html.escape(user_data_from_state.get('phone_name', 'телефона'))}</b>\""
    elif action_type == "buy_item":
        item_name_display = f"покупку \"<b>{html.escape(user_data_from_state.get('item_name', 'предмета'))}</b>\""
    elif action_type == "sell_item": 
         item_name_display = f"продажу \"<b>{html.escape(user_data_from_state.get('item_name', 'предмета'))}</b>\""
    elif action_type == "repair_phone": 
         item_name_display = f"ремонт \"<b>{html.escape(user_data_from_state.get('phone_name', 'телефона'))}</b>\""
    elif action_type == "craft_phone": # <--- ДОБАВЛЕНО для сообщения об отмене
         phone_series_to_craft_no_msg = user_data_from_state.get('phone_series_to_craft', 'неизвестной')
         item_name_display = f'сборку телефона {phone_series_to_craft_no_msg}-серии'


    await message.reply(f"{item_name_display.capitalize()} отменена.", parse_mode="HTML")
    await state.clear()

@phone_router.message(PurchaseStates.awaiting_confirmation)
async def cmd_purchase_invalid_confirmation(message: Message, state: FSMContext):
    user_data_from_state = await state.get_data()
    state_user_id = user_data_from_state.get('original_user_id')

    if state_user_id != message.from_user.id:
        return

    confirmation_initiated_at_iso = user_data_from_state.get('confirmation_initiated_at')
    action_type = user_data_from_state.get('action_type')
    item_name_display = "действие"
    timeout_seconds = CONFIRMATION_TIMEOUT_SECONDS_PHONE # По умолчанию

    if action_type == "buy_phone":
        item_name_display = f"покупку \"<b>{html.escape(user_data_from_state.get('phone_name', 'телефона'))}</b>\""
    elif action_type == "sell_phone":
        item_name_display = f"продажу \"<b>{html.escape(user_data_from_state.get('phone_name', 'телефона'))}</b>\""
        # timeout_seconds остается CONFIRMATION_TIMEOUT_SECONDS_PHONE
    elif action_type == "buy_item":
        item_name_display = f"покупку \"<b>{html.escape(user_data_from_state.get('item_name', 'предмета'))}</b>\""
        timeout_seconds = CONFIRMATION_TIMEOUT_SECONDS_ITEM
    elif action_type == "sell_item": 
         item_name_display = f"продажу \"<b>{html.escape(user_data_from_state.get('item_name', 'предмета'))}</b>\""
         timeout_seconds = CONFIRMATION_TIMEOUT_SECONDS_ITEM
    elif action_type == "repair_phone": 
         item_name_display = f"ремонт \"<b>{html.escape(user_data_from_state.get('phone_name', 'телефона'))}</b>\""
         timeout_seconds = CONFIRMATION_TIMEOUT_SECONDS_ITEM # Используем таймаут для предметов/действий
    elif action_type == "craft_phone": # <--- ДОБАВЛЕНО для сообщения о неверном подтверждении / таймауте
         phone_series_to_craft_invalid_msg = user_data_from_state.get('phone_series_to_craft', 'неизвестной')
         item_name_display = f'сборку телефона {phone_series_to_craft_invalid_msg}-серии'
         timeout_seconds = CONFIRMATION_TIMEOUT_SECONDS_ITEM


    if confirmation_initiated_at_iso:
        try:
            confirmation_initiated_at = datetime.fromisoformat(confirmation_initiated_at_iso)
            if (datetime.now(dt_timezone.utc) - confirmation_initiated_at) > timedelta(seconds=timeout_seconds):
                await state.clear()
                await message.reply(f"Время на подтверждение {item_name_display} истекло. Попробуйте снова.", parse_mode="HTML")
                return
        except ValueError:
            await state.clear()
            await message.reply("Ошибка состояния подтверждения. Пожалуйста, начните действие заново.")
            return

    await message.reply("Пожалуйста, ответьте 'Да' или 'Нет'.")

# =============================================================================
# ПРОЧИЕ КОМАНДЫ С ТЕЛЕФОНАМИ И ПРЕДМЕТАМИ
# =============================================================================

@phone_router.message(Command("buyitem", "купитьпредмет", ignore_case=True))
async def cmd_buyitem_start(message: Message, command: CommandObject, state: FSMContext, bot: Bot):
    if not message.from_user:
        return await message.reply("Не удалось определить пользователя.")

    user_id = message.from_user.id
    chat_id = message.chat.id
    user_link = get_user_mention_html(user_id, message.from_user.full_name, message.from_user.username)

    args_str = command.args
    if not args_str:
        await message.reply(
            f"{user_link}, укажите ключ предмета и, если нужно, количество.\n"
            f"Пример покупки детали: /buyitem SCREEN_S 2\n"
            f"Пример покупки чехла: /buyitem CASE_S_TITAN_GUARD\n"
            f"Посмотреть доступные предметы: /itemshop",
            parse_mode="HTML"
        )
        return

    args_list = args_str.split()
    item_key_arg = args_list[0].upper()
    quantity_arg_str = args_list[1] if len(args_list) > 1 else "1"

    try:
        quantity_to_buy = int(quantity_arg_str)
        if quantity_to_buy <= 0:
            await message.reply(f"{user_link}, количество должно быть больше нуля.", parse_mode="HTML")
            return
    except ValueError:
        await message.reply(f"{user_link}, указано неверное количество. Введите число.", parse_mode="HTML")
        return

    item_info: Optional[Dict[str, Any]] = None
    item_type: Optional[str] = None

    if item_key_arg in PHONE_COMPONENTS:
        item_info = PHONE_COMPONENTS[item_key_arg]
        item_type = item_info.get("component_type")
        if not item_type:
            # Пробуем определить тип по ключу, если нет в данных компонента
             if item_key_arg.startswith("MEMORY_MODULE_"): item_type = "memory_module"
             else: item_type = "component"
    elif item_key_arg in PHONE_CASES:
        item_info = PHONE_CASES[item_key_arg]
        item_type = "case"
        # Чехлы всегда по 1 штуке
        if quantity_to_buy > 1:
            await message.reply(f"{user_link}, чехлы можно покупать только по одной штуке за раз.", parse_mode="HTML")
            return
        quantity_to_buy = 1 # Для чехлов количество всегда 1 независимо от ввода

    if not item_info or not item_type:
        await message.reply(f"{user_link}, предмет с ключом '<code>{html.escape(item_key_arg)}</code>' не найден в магазине.", parse_mode="HTML")
        return

    item_name_display = html.escape(item_info.get('name', item_key_arg))
    base_item_price_per_unit = item_info.get('price', 0) # <--- БАЗОВАЯ ЦЕНА ЗА ШТ.
    
    conn_buy_item = None
    try:
        conn_buy_item = await database.get_connection()

        # Получаем актуальную цену за единицу с учетом инфляции
        actual_item_price_per_unit = await get_current_price(base_item_price_per_unit, conn_ext=conn_buy_item) # <--- НОВОЕ
        
        total_actual_price = actual_item_price_per_unit * quantity_to_buy # <--- НОВОЕ: Общая актуальная цена

        current_balance = await database.get_user_onecoins(user_id, chat_id, conn_ext=conn_buy_item)
        if current_balance < total_actual_price: # <--- ИСПОЛЬЗУЕМ АКТУАЛЬНУЮ ЦЕНУ
            await message.reply(
                f"{user_link}, у вас недостаточно средств для покупки {quantity_to_buy} шт. \"<b>{item_name_display}</b>\".\n"
                f"Нужно: {total_actual_price} OC, у вас: {current_balance} OC.",
                parse_mode="HTML"
            )
            if conn_buy_item and not conn_buy_item.is_closed(): await conn_buy_item.close()
            return

        await state.set_state(PurchaseStates.awaiting_confirmation) 
        await state.update_data(
            action_type="buy_item", 
            item_key=item_key_arg,
            item_name=item_info.get('name', item_key_arg), 
            item_type=item_type,
            item_price_total=total_actual_price, # <--- НОВОЕ: Сохраняем актуальную общую цену
            quantity_to_buy=quantity_to_buy,
            confirmation_initiated_at=datetime.now(dt_timezone.utc).isoformat(),
            original_chat_id=chat_id,
            original_user_id=user_id
        )

        quantity_text = f"{quantity_to_buy} шт. " if quantity_to_buy > 1 and item_type != 'case' else ""
        confirmation_message = (
            f"{user_link}, вы уверены, что хотите купить:\n"
            f"<b>{quantity_text}{item_name_display}</b>\n"
            f"Общая цена: {total_actual_price} OneCoin(s)" # <--- ИСПОЛЬЗУЕМ АКТУАЛЬНУЮ ЦЕНУ
        )
        timeout_for_item = CONFIRMATION_TIMEOUT_SECONDS_ITEM 
        confirmation_message += (
            f"?\nВаш баланс: {current_balance} OneCoin(s).\n\n"
            f"Ответьте 'Да' или 'Нет' в течение {timeout_for_item} секунд."
        )
        await message.reply(confirmation_message, parse_mode="HTML")

    except Exception as e_buy_item_start:
        logger.error(f"BuyItem: Ошибка на старте покупки для user {user_id}, item {item_key_arg}: {e_buy_item_start}", exc_info=True)
        await message.reply("Произошла ошибка при начале покупки предмета.")
        await send_telegram_log(bot, f"🔴 Ошибка в /buyitem (старт) для {user_link}, товар {item_key_arg}: <pre>{html.escape(str(e_buy_item_start))}</pre>")
    finally:
        if conn_buy_item and not conn_buy_item.is_closed():
            await conn_buy_item.close()




@phone_router.message(Command("myphones", "моителефоны", ignore_case=True))
async def cmd_myphones(message: Message, bot: Bot): # bot остается, если используется для fetch_user_display_data
    if not message.from_user:
        return await message.reply("Не удалось определить пользователя.")

    user_id = message.from_user.id
    user_link = get_user_mention_html(user_id, message.from_user.full_name, message.from_user.username)

    try:
        user_phones = await database.get_user_phones(user_id, active_only=True)

        if not user_phones:
            await message.reply(f"{user_link}, у вас пока нет телефонов. Вы можете купить их в /phoneshop или испытать удачу на /blackmarket.", parse_mode="HTML")
            return

        response_parts = [f"📱 <b>Ваши телефоны ({len(user_phones)}/{getattr(Config, 'MAX_PHONES_PER_USER', 2)}):</b>"]
        now_utc = datetime.now(dt_timezone.utc)

        # Вспомогательная функция для корректной обработки datetime (у тебя она уже есть, просто убедись)
        def ensure_aware_datetime(dt_val: Any) -> Optional[datetime]:
            # ... (твоя реализация ensure_aware_datetime)
            if isinstance(dt_val, str):
                try: dt_val = datetime.fromisoformat(dt_val)
                except ValueError: return None
            if isinstance(dt_val, datetime):
                if dt_val.tzinfo is None: return dt_val.replace(tzinfo=dt_timezone.utc)
                return dt_val.astimezone(dt_timezone.utc)
            return None


        for idx, phone_db_info in enumerate(user_phones):
            phone_model_key = phone_db_info.get('phone_model_key')
            
            # --- Получаем статические данные (учитывая стандартные и эксклюзивные) ---
            phone_info_static = PHONE_MODELS.get(phone_model_key) # PHONE_MODELS это PHONE_MODELS_STD_DICT из phone_logic
            # Нужно импортировать EXCLUSIVE_PHONE_MODELS_DICT из black_market_logic или определить его здесь
            # Предположим, что EXCLUSIVE_PHONE_MODELS_DICT доступен (например, импортирован в начале phone_logic.py)
            # from black_market_logic import EXCLUSIVE_PHONE_MODELS_DICT # <--- Потенциальный импорт, если он нужен здесь
            # Или лучше передавать его, или реимпортировать из exclusive_phone_data.py
            # Для простоты, предположим, что если не нашли в PHONE_MODELS, то это может быть эксклюзив,
            # и его имя будет просто phone_model_key если EXCLUSIVE_PHONE_MODELS_DICT недоступен здесь напрямую.
            # Но лучше иметь доступ к EXCLUSIVE_PHONE_MODELS_DICT для отображения display_name.
            # Допустим, он импортирован как в black_market_logic.py:
            # from exclusive_phone_data import EXCLUSIVE_PHONE_MODELS
            # EXCLUSIVE_PHONE_MODELS_DICT_MYPHONES = {ex_phone["key"]: ex_phone for ex_phone in EXCLUSIVE_PHONE_MODELS}
            # phone_info_exclusive = EXCLUSIVE_PHONE_MODELS_DICT_MYPHONES.get(phone_model_key)
            # phone_info_to_use = phone_info_exclusive or phone_info_static
            
            # Упрощенный вариант: если это эксклюзив, его имя может быть в phone_db_info['data']
            phone_custom_data_for_name = phone_db_info.get('data', {}) or {}
            
            if phone_info_static: # Обычный телефон Samsung
                phone_name_display = html.escape(phone_info_static.get('name', 'Неизвестная модель'))
            elif phone_custom_data_for_name.get('display_name_override'): # Эксклюзив с ЧР
                 phone_name_display = html.escape(phone_custom_data_for_name.get('display_name_override'))
            elif phone_custom_data_for_name.get('name'): # Если вдруг в data есть 'name' от эксклюзива
                 phone_name_display = html.escape(phone_custom_data_for_name.get('name'))
            else: # Если это эксклюзив без display_name_override в data, ищем в EXCLUSIVE_PHONE_MODELS_DICT
                 # Предполагаем, что EXCLUSIVE_PHONE_MODELS_DICT импортирован в phone_logic.py
                 # from exclusive_phone_data import EXCLUSIVE_PHONE_MODELS
                 # TEMP_EXCLUSIVE_DICT = {p["key"]: p for p in EXCLUSIVE_PHONE_MODELS} # Определить в начале файла
                 # phone_info_excl_temp = TEMP_EXCLUSIVE_DICT.get(phone_model_key)
                 # if phone_info_excl_temp:
                 #     phone_name_display = html.escape(phone_info_excl_temp.get('name', phone_model_key))
                 # else:
                 #     phone_name_display = f"Особый телефон (<code>{html.escape(str(phone_model_key))}</code>)"
                 # Пока упростим:
                 phone_name_display = f"Особый телефон (<code>{html.escape(str(phone_model_key))}</code>)"


            phone_color = html.escape(phone_db_info.get('color', 'N/A'))
            phone_inventory_id = phone_db_info.get('phone_inventory_id', 'N/A')
            
            # vvv ИЗМЕНЕНИЯ ДЛЯ ОТОБРАЖЕНИЯ КОНТРАБАНДЫ И ДЕФЕКТОВ vvv
            is_contraband = phone_db_info.get('is_contraband', False)
            phone_specific_data = phone_db_info.get('data', {}) or {} # Это JSONB поле `data`
            
            contraband_prefix = "🥷 " if is_contraband else ""
            # ^^^ КОНЕЦ ИЗМЕНЕНИЙ ^^^

            current_memory_gb = phone_db_info.get('current_memory_gb')
            # ... (твоя логика определения current_memory_gb и current_memory_display - ОСТАВЛЯЕМ ЕЕ) ...
            if current_memory_gb is None:
                memory_str_static = (phone_info_static or {}).get('memory', '0').upper()
                if 'TB' in memory_str_static:
                    try: current_memory_gb = int(float(memory_str_static.replace('TB', '').strip()) * 1024)
                    except ValueError: current_memory_gb = 1024
                elif 'GB' in memory_str_static:
                    try: current_memory_gb = int(float(memory_str_static.replace('GB', '').strip()))
                    except ValueError: current_memory_gb = 0
                else: current_memory_gb = 0 # Если формат памяти неизвестен
            
            current_memory_display = f"{current_memory_gb}GB" if isinstance(current_memory_gb, int) else html.escape(str(current_memory_gb))
            if isinstance(current_memory_gb, int) and current_memory_gb >= 1024 and current_memory_gb % 1024 == 0:
                 current_memory_display = f"{current_memory_gb // 1024}TB"
            
            # --- ФОРМИРОВАНИЕ СТРОКИ ТЕЛЕФОНА ---
            phone_line_parts = [f"\n<b>{idx+1}. {contraband_prefix}{phone_name_display}</b> ({phone_color}, {current_memory_display})"]
            phone_line_parts.append(f"   ID в инвентаре: <code>{phone_inventory_id}</code>")

            # --- Особенности из user_phones.data ---
            phone_features_display = []
            if phone_specific_data.get("cosmetic_defect"):
                phone_features_display.append(f"<i>Дефект: {html.escape(phone_specific_data['cosmetic_defect'])}</i>")
            
            # Попытка получить bm_description или custom_bonus_description из custom_data эксклюзива, если они там есть
            # custom_data с ЧР записывается в user_phones.data
            exclusive_bm_desc = phone_specific_data.get("bm_description")
            exclusive_bonus_desc = phone_specific_data.get("custom_bonus_description")

            if exclusive_bm_desc and is_contraband : # Показываем bm_description только если это контрабанда (подразумевая эксклюзив ЧР)
                 phone_features_display.append(f"<i>{html.escape(exclusive_bm_desc)}</i>")
            if exclusive_bonus_desc and is_contraband:
                 phone_features_display.append(f"<i>Особое свойство: {html.escape(exclusive_bonus_desc)}</i>")
            
            if phone_features_display:
                phone_line_parts.append("   ✨ " + " ".join(phone_features_display))
            # --- Конец особенностей ---

            # ... (твоя существующая логика для заряда, возраста, поломки, чехла, страховки - ОСТАВЛЯЕМ ЕЕ) ...
            # Просто убедись, что она добавляет строки в phone_line_parts или собирает их в phone_line
            # Пример (нужно будет адаптировать к твоей структуре):
            # phone_line_parts.append(f"   {battery_status_str}")
            # phone_line_parts.append(f"   ⏳ {age_display_str}")
            # if is_broken_db and ...: phone_line_parts.append(f"   ⚠️ Сломан: ...")
            # ... и так далее для чехла и страховки ...
            # В твоем коде это уже делается через phone_line += ... , это тоже нормально.
            # Главное, чтобы новые строки с особенностями были добавлены.
            
            # Я скопирую твою логику отображения статусов и вставлю ее сюда, добавив новые строки
            # --- Расчет и отображение заряда ---
            battery_status_str = "Заряд: N/A"
            last_charged_utc = ensure_aware_datetime(phone_db_info.get('last_charged_utc'))
            battery_dead_after_utc = ensure_aware_datetime(phone_db_info.get('battery_dead_after_utc'))
            # battery_break_after_utc нам здесь не так важен для отображения заряда, но нужен для is_broken
            is_broken_db = phone_db_info.get('is_broken', False)
            broken_component_key_db = phone_db_info.get('broken_component_key')
            broken_battery_component_keys = [k for k, v in PHONE_COMPONENTS.items() if v.get("component_type") == "battery"]

            if is_broken_db and broken_component_key_db in broken_battery_component_keys:
                broken_comp_name = PHONE_COMPONENTS.get(broken_component_key_db, {}).get('name', 'Аккумулятор')
                battery_status_str = f"🔋❌ {html.escape(broken_comp_name)} сломан!"
            # ... (остальная твоя логика заряда из cmd_myphones, строки ~510-545) ...
            # Я ее немного сокращу для примера, тебе нужно будет вставить свою полную логику
            elif last_charged_utc and battery_dead_after_utc:
                 total_duration_seconds = (battery_dead_after_utc - last_charged_utc).total_seconds()
                 if total_duration_seconds > 0:
                    remaining_seconds_until_dead = (battery_dead_after_utc - now_utc).total_seconds()
                    percentage = max(0, min(100, round((remaining_seconds_until_dead / total_duration_seconds) * 100)))
                    if percentage == 0:
                        battery_status_str = f"🔋 {int(percentage)}% (Разряжен!)"
                        # Проверка на окончательную поломку
                        battery_break_after_utc_dt = ensure_aware_datetime(phone_db_info.get('battery_break_after_utc'))
                        if battery_break_after_utc_dt and now_utc >= battery_break_after_utc_dt:
                             battery_status_str = "🔋‼️ Аккумулятор окончательно сломан!"
                    else:
                        # ... (твой код для отображения оставшегося времени) ...
                        time_left_work = battery_dead_after_utc - now_utc
                        # ... (форматирование time_left_work_str)
                        days_work, rem_s_work = divmod(time_left_work.total_seconds(), 86400); hours_work, rem_s_work = divmod(rem_s_work, 3600); minutes_work, _ = divmod(rem_s_work, 60)
                        parts_work = []
                        if int(days_work) > 0: parts_work.append(f"{int(days_work)}д")
                        if int(hours_work) > 0: parts_work.append(f"{int(hours_work)}ч")
                        if (int(days_work) == 0 and int(hours_work) == 0 and int(minutes_work) >= 0) or int(minutes_work) > 0: parts_work.append(f"{int(minutes_work)}м")
                        time_left_work_str = " ".join(parts_work) if parts_work else "меньше минуты"
                        battery_status_str = f"🔋 {int(percentage)}% (осталось ~{time_left_work_str})"
                 else: # total_duration_seconds <= 0
                     battery_status_str = "🔋 ?% (ошибка данных батареи)"
            
            phone_line_parts.append(f"   {battery_status_str}")
            
            # --- Возраст, Поломка (не батарея), Чехол, Страховка ---
            # (Твоя существующая логика отображения этих полей, добавляй их в phone_line_parts)
            purchase_date_aware = ensure_aware_datetime(phone_db_info.get('purchase_date_utc'))
            age_display_str = "неизвестно когда"
            if purchase_date_aware:
                # ... (твой код для age_display_str) ...
                age_delta = now_utc - purchase_date_aware; days_passed = age_delta.days
                if days_passed == 0: age_display_str = "Взял сегодня" # Упрощено
                elif days_passed == 1: age_display_str = "Взял вчера"
                else: age_display_str = f"Взял {days_passed} дн. назад" # Упрощено
            phone_line_parts.append(f"   ⏳ {age_display_str}")

            if is_broken_db and broken_component_key_db and broken_component_key_db not in broken_battery_component_keys:
                broken_comp_name_other = PHONE_COMPONENTS.get(broken_component_key_db, {}).get('name', 'Компонент')
                phone_line_parts.append(f"   ⚠️ Сломан: {html.escape(broken_comp_name_other)}!")

            equipped_case_key_phone = phone_db_info.get('equipped_case_key')
            if equipped_case_key_phone:
                # ... (твой код для отображения чехла) ...
                 case_name_display = html.escape(PHONE_CASES.get(equipped_case_key_phone, {}).get('name', equipped_case_key_phone))
                 phone_line_parts.append(f"   🛡️ Чехол: {case_name_display}")
            else:
                phone_line_parts.append("   🛡️ Чехол: отсутствует")
            
            insurance_active_until = ensure_aware_datetime(phone_db_info.get('insurance_active_until'))
            insurance_status_str_display = "📄 Страховка: отсутствует"
            if insurance_active_until:
                # ... (твой код для отображения страховки) ...
                if now_utc < insurance_active_until: insurance_status_str_display = f"📄✅ Страховка активна (до ~{(insurance_active_until - now_utc).days} д.)" # Упрощено
                else: insurance_status_str_display = "📄❌ Страховка истекла"
            phone_line_parts.append(f"   {insurance_status_str_display}")

            phone_line = "\n".join(phone_line_parts) # Объединяем части в одну строку
            response_parts.append(phone_line) # ОДНО добавление строки телефона в список
        
        response_parts.append("\n--------------------")
        response_parts.append("🔧 Для просмотра всех команд управления телефоном используйте: <code>/help телефон</code>")
        

    except Exception as e:
        logger.error(f"MyPhones: Ошибка для user {user_id}: {e}", exc_info=True)
        await message.reply("Произошла ошибка при отображении ваших телефонов.")
        return 

    full_response = "\n".join(response_parts)

    MAX_MESSAGE_LENGTH = 4096
    if len(full_response) > MAX_MESSAGE_LENGTH:
        temp_parts = []
        current_part = ""
        for line in full_response.split('\n'):
            if len(current_part) + len(line) + 1 > MAX_MESSAGE_LENGTH: # +1 для символа новой строки
                if current_part: # Добавляем, только если не пусто
                    temp_parts.append(current_part)
                current_part = line
            else:
                if current_part: current_part += "\n" + line
                else: current_part = line
        if current_part: 
            temp_parts.append(current_part)

        for part_msg in temp_parts:
            if part_msg.strip(): # Отправляем только непустые части
                await message.answer(part_msg, parse_mode="HTML", disable_web_page_preview=True)
                await asyncio.sleep(0.2) # Небольшая задержка между сообщениями
    else:
        if full_response.strip(): # Отправляем, только если не пусто
            await message.answer(full_response, parse_mode="HTML", disable_web_page_preview=True)

@phone_router.message(Command("myitems", "моипредметы", "инвентарьпредметов", ignore_case=True))
async def cmd_myitems(message: Message, bot: Bot):
    if not message.from_user:
        return await message.reply("Не удалось определить пользователя.")

    user_id = message.from_user.id
    user_link = get_user_mention_html(user_id, message.from_user.full_name, message.from_user.username)

    try:
        user_all_items_db = await database.get_user_items(user_id)

        if not user_all_items_db:
            await message.reply(f"{user_link}, ваш инвентарь предметов пуст. Вы можете купить их в /itemshop.", parse_mode="HTML")
            return

        response_parts = [f"📦 <b>Ваш инвентарь предметов:</b>\n{user_link}\n"]

        components_lines = []
        memory_modules_lines = []
        cases_lines = []

        for item_db in user_all_items_db:
            item_key = item_db['item_key']
            item_type = item_db['item_type']
            quantity = item_db['quantity']
            user_item_id = item_db['user_item_id'] # ID конкретного экземпляра в инвентаре

            item_info_static: Optional[Dict[str, Any]] = None
            # !!! ИСПОЛЬЗУЕМ СЛОВАРИ PHONE_COMPONENTS И PHONE_CASES ДЛЯ ПОИСКА !!!
            if item_key in PHONE_COMPONENTS:
                item_info_static = PHONE_COMPONENTS[item_key]
            elif item_key in PHONE_CASES:
                item_info_static = PHONE_CASES[item_key]

            if not item_info_static:
                logger.warning(f"MyItems: Не найдены статические данные для предмета с ключом {item_key} (тип: {item_type}) у user {user_id}")
                item_display_name = f"Неизвестный предмет (<code>{html.escape(item_key)}</code>)"
                # Для неизвестных предметов или чехлов, количество не показываем, только ID
                item_line = f"  • {item_display_name} (ID: <code>{user_item_id}</code>)" if item_type == 'case' else f"  • {item_display_name} - {quantity} шт. (ID: <code>{user_item_id}</code>)"
            else:
                item_display_name = html.escape(item_info_static.get('name', item_key)) # Используем .get
                if item_type == 'case':
                    # Для чехлов показываем бонусы
                    protection = item_info_static.get("break_chance_reduction_percent", 0)
                    bonuses_text_parts = []
                    if item_info_static.get("battery_days_increase"): bonuses_text_parts.append(f"+{item_info_static['battery_days_increase']}д. заряда")
                    if item_info_static.get("oneui_version_bonus_percent"): bonuses_text_parts.append(f"+{item_info_static['oneui_version_bonus_percent']}% к OneUI")
                    if item_info_static.get("onecoin_bonus_percent"): bonuses_text_parts.append(f"+{item_info_static['onecoin_bonus_percent']}% к OneCoin")
                    if item_info_static.get("market_discount_percent"): bonuses_text_parts.append(f"-{item_info_static['market_discount_percent']}% на рынке")
                    if item_info_static.get("bonus_roulette_luck_percent"): bonuses_text_parts.append(f"+{item_info_static['bonus_roulette_luck_percent']}% удачи в рулетке")

                    bonus_str_suffix = ""
                    if bonuses_text_parts:
                        bonus_str_suffix = f"; {', '.join(bonuses_text_parts)}"
                    item_line = f"  • {item_display_name} (Защита: {protection}%{bonus_str_suffix}) (ID: <code>{user_item_id}</code>)"
                else: # Компоненты и модули памяти (для них есть quantity)
                    item_line = f"  • {item_display_name} - {quantity} шт. (Ключ: <code>{item_key}</code>) (ID: <code>{user_item_id}</code>)."

            if item_type == 'component':
                components_lines.append(item_line)
            elif item_type == 'memory_module':
                memory_modules_lines.append(item_line)
            elif item_type == 'case':
                cases_lines.append(item_line)

        if components_lines:
            response_parts.append("\n<b>🔩 Компоненты:</b>")
            # Сортировка компонентов по имени
            sorted_components_lines = sorted(components_lines)
            response_parts.extend(sorted_components_lines)

        if memory_modules_lines:
            response_parts.append("\n<b>💾 Модули памяти:</b>")
             # Сортировка модулей памяти по имени
            sorted_memory_lines = sorted(memory_modules_lines)
            response_parts.extend(sorted_memory_lines)

        if cases_lines:
            response_parts.append("\n<b>🛡️ Чехлы:</b>")
            cases_lines.sort() # Сортируем чехлы по их строковому представлению (включая имя)
            response_parts.extend(cases_lines)

        response_parts.append("\n--------------------")
        response_parts.append("ID чехла нужен для команды /equipcase.")
        response_parts.append("Ключ модуля памяти нужен для /upgradememory (модуль 'memory_module_50gb').")
        response_parts.append("ID предмета нужен для команды /sellitem.") # Обновлено: Подсказка для продажи любого предмета
        response_parts.append("Используйте /sellitem ID_предмета [количество] для продажи.") # Добавлена подсказка по формату команды

    except Exception as e:
        logger.error(f"MyItems: Ошибка для user {user_id}: {e}", exc_info=True)
        await message.reply("Произошла ошибка при отображении вашего инвентаря предметов.")
        return

    full_response = "\n".join(response_parts)

    MAX_MESSAGE_LENGTH = 4096
    if len(full_response) > MAX_MESSAGE_LENGTH:
        # ... (та же логика разбивки, что и в /phoneshop, /itemshop) ...
        temp_parts = []
        current_part = ""
        for line in full_response.split('\n'):
            if len(current_part) + len(line) + 1 > MAX_MESSAGE_LENGTH:
                temp_parts.append(current_part)
                current_part = line
            else:
                if current_part: current_part += "\n" + line
                else: current_part = line
        if current_part: temp_parts.append(current_part)

        for part_msg in temp_parts:
            await message.answer(part_msg, parse_mode="HTML", disable_web_page_preview=True)
            await asyncio.sleep(0.2)
    else:
        await message.answer(full_response, parse_mode="HTML", disable_web_page_preview=True)

@phone_router.message(Command("equipcase", "надетьчехол", ignore_case=True))
async def cmd_equip_case(message: Message, command: CommandObject, bot: Bot):
    if not message.from_user:
        return await message.reply("Не удалось определить пользователя.")

    user_id = message.from_user.id
    user_link = get_user_mention_html(user_id, message.from_user.full_name, message.from_user.username)

    args_str = command.args
    if not args_str:
        await message.reply(
            f"{user_link}, укажите ID телефона и ID чехла из вашего инвентаря.\n"
            f"Пример: /equipcase ID_телефона ID_чехла_в_инвентаре\n"
            f"ID телефонов: /myphones\n"
            f"ID чехлов: /myitems (смотрите ID конкретного экземпляра)",
            parse_mode="HTML", disable_web_page_preview=True
        )
        return

    args_list = args_str.split()
    if len(args_list) != 2:
        await message.reply("Нужно указать два ID: сначала ID телефона, потом ID чехла. Пример: /equipcase 123 45")
        return

    try:
        phone_inventory_id_arg = int(args_list[0])
        user_item_id_of_case_arg = int(args_list[1])
    except ValueError:
        await message.reply("ID телефона и ID чехла должны быть числами.")
        return

    conn = None
    try:
        conn = await database.get_connection()
        async with conn.transaction(): # Оборачиваем все действия с БД в транзакцию
            # 1. Получаем телефон пользователя
            phone_db_data = await database.get_phone_by_inventory_id(phone_inventory_id_arg, conn_ext=conn)
            if not phone_db_data or phone_db_data['user_id'] != user_id:
                await message.reply(f"Телефон с ID <code>{phone_inventory_id_arg}</code> не найден в вашем инвентаре.", parse_mode="HTML")
                return
            if phone_db_data.get('is_sold', False):
                await message.reply(f"Телефон ID <code>{phone_inventory_id_arg}</code> уже продан.", parse_mode="HTML")
                return
            if phone_db_data.get('is_broken'):
                broken_comp_key = phone_db_data.get('broken_component_key')
                broken_comp_name = "какой-то компонент"
                if broken_comp_key and broken_comp_key in PHONE_COMPONENTS:
                    broken_comp_name = PHONE_COMPONENTS[broken_comp_key].get('name', broken_comp_key)
                await message.reply(f"Телефон ID <code>{phone_inventory_id_arg}</code> сломан ({html.escape(broken_comp_name)}). Сначала почините его, чтобы сменить чехол.", parse_mode="HTML")
                return

            phone_model_key = phone_db_data['phone_model_key']
            # !!! ИСПОЛЬЗУЕМ СЛОВАРЬ ДЛЯ ПОИСКА !!!
            phone_static_info = PHONE_MODELS.get(phone_model_key)
            if not phone_static_info:
                await message.reply(f"Ошибка: не найдены данные для модели телефона ID <code>{phone_inventory_id_arg}</code>.", parse_mode="HTML")
                return
            phone_series = phone_static_info.get('series')

            # 2. Получаем чехол из инвентаря пользователя
            case_to_equip_db = await database.get_user_item_by_id(user_item_id_of_case_arg, user_id=user_id, conn_ext=conn)
            if not case_to_equip_db:
                await message.reply(f"Чехол с ID <code>{user_item_id_of_case_arg}</code> не найден в вашем инвентаре.", parse_mode="HTML")
                return
            if case_to_equip_db['item_type'] != 'case':
                await message.reply(f"Предмет с ID <code>{user_item_id_of_case_arg}</code> не является чехлом.", parse_mode="HTML")
                return
            # Проверка, что чехол не надет на другой телефон (для уникальных предметов)
            # В данном случае, в `database.py` для `user_items` чехол может быть привязан к телефону через `equipped_phone_id`
            # Если чехол уже надет на какой-либо телефон, его `equipped_phone_id` будет не `None`.
            if case_to_equip_db.get('equipped_phone_id') is not None:
                await message.reply(f"Чехол ID <code>{user_item_id_of_case_arg}</code> уже надет на другой телефон (ID: {case_to_equip_db['equipped_phone_id']}). Сначала снимите его.", parse_mode="HTML")
                return


            new_case_key = case_to_equip_db['item_key']
            new_case_static_info = PHONE_CASES.get(new_case_key)
            if not new_case_static_info:
                await message.reply(f"Ошибка: не найдены данные для чехла <code>{html.escape(new_case_key)}</code>.", parse_mode="HTML")
                return

            # 3. Проверка совместимости серий (проверяем, что обе серии существуют)
            new_case_series = new_case_static_info.get('series')
            if phone_series is None or new_case_series is None or new_case_series != phone_series:
                phone_series_display = phone_series if phone_series else "неизвестная"
                new_case_series_display = new_case_series if new_case_series else "неизвестная"
                await message.reply(
                    f"Несовместимость! Чехол \"{html.escape(new_case_static_info.get('name', new_case_key))}\" ({new_case_series_display}-серия) "
                    f"не подходит для телефона \"<b>{html.escape(phone_static_info.get('name', phone_model_key))}</b>\" ({phone_series_display}-серия).",
                    parse_mode="HTML"
                )
                return

            fields_to_update_for_phone: Dict[str, Any] = {}
            old_case_key_on_phone = phone_db_data.get('equipped_case_key')

            # Если был старый чехол, снимаем его с телефона и обновляем его статус в инвентаре
            if old_case_key_on_phone:
                # Находим конкретный экземпляр старого чехла, который был на этом телефоне
                old_case_item_on_phone = await database.get_user_item_by_equipped_phone_id(user_id, phone_inventory_id_arg, old_case_key_on_phone, conn_ext=conn)
                if old_case_item_on_phone:
                    update_old_case_item_success = await database.update_user_item_fields(
                        old_case_item_on_phone['user_item_id'], user_id, {'equipped_phone_id': None}, conn_ext=conn
                    )
                    if not update_old_case_item_success:
                        logger.critical(f"CRITICAL: Failed to unequip old case item ID {old_case_item_on_phone['user_item_id']} from phone {phone_inventory_id_arg} for user {user_id}!")
                else:
                    logger.warning(f"EquipCase: Old equipped case item '{old_case_key_on_phone}' not found in user_items for phone {phone_inventory_id_arg} of user {user_id} when unequipping.")


            # Надеваем новый чехол на телефон
            fields_to_update_for_phone['equipped_case_key'] = new_case_key
            # Обновляем `equipped_phone_id` поля для нового предмета чехла в `user_items`
            update_new_case_item_success = await database.update_user_item_fields(
                user_item_id_of_case_arg, user_id, {'equipped_phone_id': phone_inventory_id_arg}, conn_ext=conn
            )
            if not update_new_case_item_success:
                logger.critical(f"CRITICAL: Failed to update equipped_phone_id for new case item ID {user_item_id_of_case_arg} for user {user_id}!")
                raise Exception(f"Failed to update equipped_phone_id for new case item ID {user_item_id_of_case_arg} for user {user_id}.")


            # Пересчет времени работы батареи (если она была заряжена)
            last_charged_utc_val = phone_db_data.get('last_charged_utc')
            if last_charged_utc_val and isinstance(last_charged_utc_val, datetime):
                last_charged_aware = last_charged_utc_val.replace(tzinfo=dt_timezone.utc) if last_charged_utc_val.tzinfo is None else last_charged_utc_val.astimezone(dt_timezone.utc)
                new_case_battery_bonus_days = new_case_static_info.get('battery_days_increase', 0)
                base_phone_battery_days = getattr(Config, "PHONE_BASE_BATTERY_DAYS", 2)

                new_total_battery_life_days = base_phone_battery_days + new_case_battery_bonus_days

                new_battery_dead_after = last_charged_aware + timedelta(days=new_total_battery_life_days)
                new_battery_break_after = new_battery_dead_after + timedelta(days=getattr(Config, "PHONE_CHARGE_WINDOW_DAYS", 2))

                fields_to_update_for_phone['battery_dead_after_utc'] = new_battery_dead_after
                fields_to_update_for_phone['battery_break_after_utc'] = new_battery_break_after
                logger.info(f"Phone {phone_inventory_id_arg} battery times updated. New dead: {new_battery_dead_after}, break: {new_battery_break_after}")
            elif last_charged_utc_val is not None:
                logger.warning(f"EquipCase: last_charged_utc для phone {phone_inventory_id_arg} не является datetime ({type(last_charged_utc_val)}). Батарея не пересчитана.")


            # Обновляем телефон в БД (надеваем чехол, обновляем батарею)
            update_phone_success = await database.update_phone_status_fields(
                phone_inventory_id_arg, fields_to_update_for_phone, conn_ext=conn
            )
            if not update_phone_success:
                raise Exception(f"Не удалось обновить данные телефона {phone_inventory_id_arg} при надевании чехла.")

            await message.reply(
                f"{user_link}, вы успешно надели чехол \"<b>{html.escape(new_case_static_info.get('name', new_case_key))}\</b>\" "
                f"на телефон \"<b>{html.escape(phone_static_info.get('name', phone_model_key))}\</b>\" (ID: {phone_inventory_id_arg}).",
                parse_mode="HTML"
            )
            if old_case_key_on_phone:
                old_case_name_display = html.escape(PHONE_CASES.get(old_case_key_on_phone, {}).get('name', old_case_key_on_phone))
                await message.answer(f"Старый чехол \"{old_case_name_display}\" возвращен в ваш инвентарь (/myitems).", parse_mode="HTML")


            await send_telegram_log(bot,
                f"🛡️ Чехол надет: {user_link} надел \"{html.escape(new_case_static_info.get('name', new_case_key))}\" (item_id: {user_item_id_of_case_arg}) "
                f"на телефон \"{html.escape(phone_static_info.get('name', phone_model_key))}\" (phone_id: {phone_inventory_id_arg})."
            )

    except Exception as e_equip:
        logger.error(f"EquipCase: Ошибка для user {user_id}, phone_id {phone_inventory_id_arg}, case_item_id {user_item_id_of_case_arg}: {e_equip}", exc_info=True)
        await message.reply("Произошла ошибка при попытке надеть чехол. Изменения отменены.")
    finally:
        if conn and not conn.is_closed():
            await conn.close()


@phone_router.message(Command("removecase", "снятьчехол", ignore_case=True))
async def cmd_remove_case(message: Message, command: CommandObject, bot: Bot):
    if not message.from_user:
        return await message.reply("Не удалось определить пользователя.")

    user_id = message.from_user.id
    user_link = get_user_mention_html(user_id, message.from_user.full_name, message.from_user.username)

    args_str = command.args
    if not args_str:
        await message.reply(
            f"{user_link}, укажите ID телефона, с которого нужно снять чехол.\n"
            f"Пример: /removecase 123\n"
            f"ID телефонов: /myphones",
            parse_mode="HTML"
        )
        return

    try:
        phone_inventory_id_arg = int(args_str.strip())
    except ValueError:
        await message.reply("ID телефона должен быть числом.")
        return

    conn = None
    try:
        conn = await database.get_connection()
        async with conn.transaction(): # Оборачиваем все действия с БД в транзакцию
            # 1. Получаем телефон пользователя
            phone_db_data = await database.get_phone_by_inventory_id(phone_inventory_id_arg, conn_ext=conn)
            if not phone_db_data or phone_db_data['user_id'] != user_id:
                await message.reply(f"Телефон с ID <code>{phone_inventory_id_arg}</code> не найден в вашем инвентаре.", parse_mode="HTML")
                return
            if phone_db_data.get('is_sold', False):
                await message.reply(f"Телефон ID <code>{phone_inventory_id_arg}</code> уже продан.", parse_mode="HTML")
                return
            if phone_db_data.get('is_broken'):
                broken_comp_key = phone_db_data.get('broken_component_key')
                broken_comp_name = "какой-то компонент"
                if broken_comp_key and broken_comp_key in PHONE_COMPONENTS:
                    broken_comp_name = PHONE_COMPONENTS[broken_comp_key].get('name', broken_comp_key)
                await message.reply(f"Телефон ID <code>{phone_inventory_id_arg}</code> сломан ({html.escape(broken_comp_name)}). Сначала почините его.", parse_mode="HTML")
                return


            old_case_key_on_phone = phone_db_data.get('equipped_case_key')
            if not old_case_key_on_phone:
                await message.reply(f"На телефоне ID <code>{phone_inventory_id_arg}</code> нет надетого чехла.", parse_mode="HTML")
                return

            # Получаем статические данные чехла (из словаря PHONE_CASES)
            old_case_static_info = PHONE_CASES.get(old_case_key_on_phone)
            removed_case_name_display = html.escape(old_case_static_info.get('name', old_case_key_on_phone)) if old_case_static_info else f"чехол (ключ: {html.escape(old_case_key_on_phone)})"

            # Находим запись чехла в инвентаре по item_key и equipped_phone_id и обновляем его статус
            # Добавлена новая функция `get_user_item_by_equipped_phone_id`
            case_item_db_data_to_update = await database.get_user_item_by_equipped_phone_id(user_id, phone_inventory_id_arg, old_case_key_on_phone, conn_ext=conn)
            if case_item_db_data_to_update:
                update_case_item_success = await database.update_user_item_fields(
                    case_item_db_data_to_update['user_item_id'], user_id, {'equipped_phone_id': None}, conn_ext=conn
                )
                if not update_case_item_success:
                    logger.critical(f"КРИТИЧНО: Не удалось сбросить equipped_phone_id=NULL для чехла ID {case_item_db_data_to_update['user_item_id']} у user {user_id}!")
                    pass # Продолжаем, но логируем проблему
                else:
                    logger.info(f"User {user_id} case item ID {case_item_db_data_to_update['user_item_id']} (key: {old_case_key_on_phone}) equipped_phone_id set to NULL.")
            else:
                # Если запись чехла не найдена по equipped_phone_id, возможно, это ошибка логики или старые данные.
                # Логируем и, возможно, добавляем новый экземпляр для восстановления предмета.
                logger.warning(f"RemoveCase: Не найдена запись чехла с key={old_case_key_on_phone} и equipped_phone_id={phone_inventory_id_arg} у user {user_id} при снятии. Добавляем новый экземпляр.")
                add_old_case_back = await database.add_item_to_user_inventory(
                    user_id, old_case_key_on_phone, 'case', 1, conn_ext=conn
                )
                if not add_old_case_back:
                    logger.critical(f"КРИТИЧНО: Не удалось вернуть снятый чехол {old_case_key_on_phone} в инвентарь user {user_id} с телефона {phone_inventory_id_arg}!")
                    raise Exception(f"Внутренняя ошибка: Не удалось вернуть чехол в инвентарь. Обратитесь к администратору.")
                else:
                    logger.info(f"User {user_id} new case {old_case_key_on_phone} added to inventory (removed from phone {phone_inventory_id_arg}).")


            fields_to_update_for_phone: Dict[str, Any] = {'equipped_case_key': None}

            # Пересчет времени работы батареи на базовое (без бонуса чехла)
            last_charged_utc_val = phone_db_data.get('last_charged_utc')
            if last_charged_utc_val and isinstance(last_charged_utc_val, datetime):
                last_charged_aware = last_charged_utc_val.replace(tzinfo=dt_timezone.utc) if last_charged_utc_val.tzinfo is None else last_charged_utc_val.astimezone(dt_timezone.utc)
                base_phone_battery_days = getattr(Config, "PHONE_BASE_BATTERY_DAYS", 2)
                charge_window_days = getattr(Config, "PHONE_CHARGE_WINDOW_DAYS", 2)

                time_since_last_charge = now_utc.astimezone(dt_timezone.utc) - last_charged_aware.astimezone(dt_timezone.utc)

                base_total_battery_life_td = timedelta(days=base_phone_battery_days)

                base_battery_dead_time = last_charged_aware + base_total_battery_life_td

                if now_utc.astimezone(dt_timezone.utc) < base_battery_dead_time.astimezone(dt_timezone.utc):
                    new_battery_dead_after = base_battery_dead_time
                else:
                    new_battery_dead_after = now_utc.astimezone(dt_timezone.utc)
                    old_battery_dead_after_utc = phone_db_data.get('battery_dead_after_utc')
                    old_battery_break_after_utc = phone_db_data.get('battery_break_after_utc')

                    if old_battery_dead_after_utc and old_battery_break_after_utc:
                        old_charge_window = old_battery_break_after_utc.astimezone(dt_timezone.utc) - old_battery_dead_after_utc.astimezone(dt_timezone.utc)
                        new_battery_break_after = new_battery_dead_after + old_charge_window
                    else:
                        new_battery_break_after = new_battery_dead_after + timedelta(days=charge_window_days)

                    fields_to_update_for_phone['battery_break_after_utc'] = new_battery_break_after


                fields_to_update_for_phone['battery_dead_after_utc'] = new_battery_dead_after
                logger.info(f"Phone {phone_inventory_id_arg} battery times recalculated after case removal. New dead: {new_battery_dead_after}")
            elif last_charged_utc_val is not None:
                logger.warning(f"RemoveCase: last_charged_utc для phone {phone_inventory_id_arg} не является datetime ({type(last_charged_utc_val)}). Батарея не пересчитана.")


            # Обновляем телефон в БД (снимаем чехол, обновляем батарею)
            update_phone_success = await database.update_phone_status_fields(
                phone_inventory_id_arg, fields_to_update_for_phone, conn_ext=conn
            )
            if not update_phone_success:
                raise Exception(f"Не удалось обновить данные телефона {phone_inventory_id_arg} при снятии чехла.")

            # !!! ИСПОЛЬЗУЕМ СЛОВАРЬ PHONE_MODELS ДЛЯ ПОИСКА ИМЕНИ ТЕЛЕФОНА !!!
            phone_model_key_on_phone = phone_db_data['phone_model_key']
            phone_static_info_model = PHONE_MODELS.get(phone_model_key_on_phone)
            phone_name_static = phone_static_info_model.get('name', phone_model_key_on_phone) if phone_static_info_model else phone_model_key_on_phone


            await message.reply(
                f"{user_link}, вы успешно сняли чехол \"<b>{removed_case_name_display}</b>\" "
                f"с телефона \"<b>{html.escape(phone_name_static)}</b>\" (ID: <code>{phone_inventory_id_arg}</code>).",
                parse_mode="HTML"
            )
            await message.answer("Чехол возвращен в ваш инвентарь (/myitems).", parse_mode="HTML")


            await send_telegram_log(bot,
                f"🛡️ Чехол снят: {user_link} снял \"{removed_case_name_display}\" "
                f"с телефона \"{html.escape(phone_name_static)}\" (phone_id: {phone_inventory_id_arg}). Чехол возвращен в инвентарь."
            )

    except Exception as e_remove:
            logger.error(f"RemoveCase: Ошибка для user {user_id}, phone_id {phone_inventory_id_arg}: {e_remove}", exc_info=True)
            await message.reply("Произошла ошибка при попытке снять чехол. Изменения отменены.")
    finally:
        if conn and not conn.is_closed():
            await conn.close()


@phone_router.message(Command("chargephone", "зарядитьтелефон", ignore_case=True))
async def cmd_charge_phone(message: Message, command: CommandObject, bot: Bot):
    if not message.from_user:
        return await message.reply("Не удалось определить пользователя.")

    user_id = message.from_user.id
    chat_id = message.chat.id # OneCoin списываются с баланса текущего чата
    user_link = get_user_mention_html(user_id, message.from_user.full_name, message.from_user.username)

    args_str = command.args
    if not args_str:
        await message.reply(
            f"{user_link}, укажите ID телефона, который нужно зарядить.\n"
            f"Пример: /chargephone 123\n"
            f"ID телефонов: /myphones",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        return

    try:
        phone_inventory_id_arg = int(args_str.strip())
    except ValueError:
        await message.reply("ID телефона должен быть числом.")
        return

    charge_cost = getattr(Config, "PHONE_CHARGE_COST", 20)
    base_battery_days = getattr(Config, "PHONE_BASE_BATTERY_DAYS", 2)
    charge_window_days = getattr(Config, "PHONE_CHARGE_WINDOW_DAYS", 2)

    conn = None
    try:
        conn = await database.get_connection()
        async with conn.transaction():
            phone_db_data = await database.get_phone_by_inventory_id(phone_inventory_id_arg, conn_ext=conn)
            if not phone_db_data or phone_db_data['user_id'] != user_id:
                await message.reply(
                    f"Телефон с ID <code>{phone_inventory_id_arg}</code> не найден в вашем инвентаре.", 
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
                return
            if phone_db_data.get('is_sold', False):
                await message.reply(
                    f"Телефон ID <code>{phone_inventory_id_arg}</code> уже продан.", 
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
                return

            # --- НАЧАЛО БЛОКА ПРОВЕРКИ СОСТОЯНИЯ АККУМУЛЯТОРА ---
            now_utc = datetime.now(dt_timezone.utc)

            # 1. Проверка на явную поломку аккумулятора (is_broken и broken_component_key)
            is_explicitly_broken_battery = False
            broken_component_key_from_db = phone_db_data.get('broken_component_key')
            if phone_db_data.get('is_broken') and \
               broken_component_key_from_db and \
               PHONE_COMPONENTS.get(broken_component_key_from_db, {}).get('component_type') == "battery":
                is_explicitly_broken_battery = True

            # 2. Проверка на окончательную поломку по времени (battery_break_after_utc)
            is_permanently_dead_battery_by_time = False
            battery_break_after_utc_val = phone_db_data.get('battery_break_after_utc')
            battery_break_after_utc_dt = None

            if isinstance(battery_break_after_utc_val, str):
                try:
                    battery_break_after_utc_dt = datetime.fromisoformat(battery_break_after_utc_val)
                except ValueError:
                    logger.warning(f"ChargePhone: Некорректный формат battery_break_after_utc (str): {battery_break_after_utc_val} для phone_id {phone_inventory_id_arg}")
            elif isinstance(battery_break_after_utc_val, datetime):
                battery_break_after_utc_dt = battery_break_after_utc_val
            
            if battery_break_after_utc_dt:
                if battery_break_after_utc_dt.tzinfo is None: # Делаем aware, если naive
                    battery_break_after_utc_dt = battery_break_after_utc_dt.replace(tzinfo=dt_timezone.utc)
                else: # Приводим к UTC, если уже aware, но в другом поясе
                    battery_break_after_utc_dt = battery_break_after_utc_dt.astimezone(dt_timezone.utc)
                
                if now_utc >= battery_break_after_utc_dt:
                    is_permanently_dead_battery_by_time = True

            # Принимаем решение и ОБНОВЛЯЕМ СТАТУС В БД, если нужно
            if is_explicitly_broken_battery:
                await message.reply(
                    f"Аккумулятор телефона ID <code>{phone_inventory_id_arg}</code> сломан (отмечен как поврежденный)! Его нужно сначала починить.", 
                    parse_mode="HTML", 
                    disable_web_page_preview=True
                )
                return
            elif is_permanently_dead_battery_by_time:
                # Аккумулятор "умер по времени". Попробуем обновить статус телефона в БД.
                if not is_explicitly_broken_battery: # Только если он еще не помечен как "батарея сломана"
                    determined_battery_key_to_set = None
                    phone_model_key = phone_db_data.get('phone_model_key')
                    phone_static_data = PHONE_MODELS.get(phone_model_key)

                    if phone_static_data:
                        phone_series = phone_static_data.get('series')
                        if phone_series:
                            potential_battery_key = f"BATTERY_{phone_series.upper()}"
                            if potential_battery_key in PHONE_COMPONENTS and \
                               PHONE_COMPONENTS[potential_battery_key].get('component_type') == 'battery':
                                determined_battery_key_to_set = potential_battery_key
                            else:
                                for comp_key_iter, comp_info_iter in PHONE_COMPONENTS.items():
                                    if comp_info_iter.get("component_type") == "battery" and \
                                       comp_info_iter.get("series") == phone_series:
                                        determined_battery_key_to_set = comp_key_iter
                                        break
                            
                            if determined_battery_key_to_set:
                                try:
                                    logger.info(f"ChargePhone: Phone ID {phone_inventory_id_arg} battery timed out. Auto-setting is_broken=True, broken_component_key='{determined_battery_key_to_set}'.")
                                    await database.update_phone_status_fields(
                                        phone_inventory_id_arg,
                                        {'is_broken': True, 'broken_component_key': determined_battery_key_to_set},
                                        conn_ext=conn
                                    )
                                    phone_db_data['is_broken'] = True # Обновляем локальную копию для консистентности
                                    phone_db_data['broken_component_key'] = determined_battery_key_to_set
                                except Exception as e_update_status:
                                    logger.error(f"ChargePhone: Failed to auto-update status for timed-out battery on phone ID {phone_inventory_id_arg}: {e_update_status}")
                            else:
                                logger.warning(f"ChargePhone: Battery for phone ID {phone_inventory_id_arg} (Series {phone_series}) timed out, but could not determine a specific battery component key to set as broken.")
                        else:
                            logger.warning(f"ChargePhone: Battery for phone ID {phone_inventory_id_arg} timed out, but phone series not found in static data.")
                    else:
                        logger.warning(f"ChargePhone: Battery for phone ID {phone_inventory_id_arg} timed out, but phone static data not found.")
                
                # Сообщение пользователю
                await message.reply(
                    f"Аккумулятор телефона ID <code>{phone_inventory_id_arg}</code> окончательно вышел из строя (не был заряжен вовремя)! Зарядка невозможна. Теперь он помечен как сломанный, и его нужно чинить (/repairphone).", 
                    parse_mode="HTML", 
                    disable_web_page_preview=True
                )
                return
            # --- КОНЕЦ БЛОКА ПРОВЕРКИ СОСТОЯНИЯ АККУМУЛЯТОРА ---

            # Проверка, не заряжен ли уже телефон (если время до разрядки еще не наступило)
            battery_dead_after_utc_val = phone_db_data.get('battery_dead_after_utc')
            battery_dead_after_utc_dt_check = None # Используем новое имя переменной для этой проверки

            if isinstance(battery_dead_after_utc_val, str):
                 try: battery_dead_after_utc_dt_check = datetime.fromisoformat(battery_dead_after_utc_val)
                 except ValueError: battery_dead_after_utc_dt_check = None
            elif isinstance(battery_dead_after_utc_val, datetime):
                battery_dead_after_utc_dt_check = battery_dead_after_utc_val
            
            if battery_dead_after_utc_dt_check:
                if battery_dead_after_utc_dt_check.tzinfo is None:
                     battery_dead_after_utc_dt_check = battery_dead_after_utc_dt_check.replace(tzinfo=dt_timezone.utc)
                else:
                    battery_dead_after_utc_dt_check = battery_dead_after_utc_dt_check.astimezone(dt_timezone.utc)

                if now_utc < battery_dead_after_utc_dt_check: # Сравниваем с now_utc определенным ранее
                    time_left = battery_dead_after_utc_dt_check - now_utc
                    d, r = divmod(time_left.total_seconds(), 86400); h, r = divmod(r, 3600); m, _ = divmod(r, 60)
                    time_left_str = f"{int(d)}д {int(h)}ч {int(m)}м" if d > 0 else (f"{int(h)}ч {int(m)}м" if h > 0 else f"{int(m)}м")
                    await message.reply(
                        f"Телефон ID <code>{phone_inventory_id_arg}</code> еще заряжен. Хватит на ~{time_left_str}.", 
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )
                    return

            # Проверка баланса для зарядки
            current_balance = await database.get_user_onecoins(user_id, chat_id, conn_ext=conn)
            if current_balance < charge_cost:
                await message.reply(
                    f"{user_link}, у вас недостаточно средств для зарядки телефона.\n"
                    f"Нужно: {charge_cost} OC, у вас: {current_balance} OC.",
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
                return

            # Списываем OneCoin
            user_db_data_for_log = await database.get_user_data_for_update(user_id, chat_id, conn_ext=conn)
            await database.update_user_onecoins(
                user_id, chat_id, -charge_cost,
                username=user_db_data_for_log.get('username'),
                full_name=user_db_data_for_log.get('full_name'),
                chat_title=user_db_data_for_log.get('chat_title'),
                conn_ext=conn
            )

            # Обновляем время зарядки и время работы
            fields_to_update: Dict[str, Any] = {}
            new_last_charged_utc = now_utc # Используем already defined and timezone-aware now_utc
            fields_to_update['last_charged_utc'] = new_last_charged_utc

            equipped_case_key = phone_db_data.get('equipped_case_key')
            case_battery_bonus_days = 0
            if equipped_case_key and equipped_case_key in PHONE_CASES: # Используем прямой доступ к PHONE_CASES
                case_battery_bonus_days = PHONE_CASES[equipped_case_key].get('battery_days_increase', 0)

            total_battery_life_days = base_battery_days + case_battery_bonus_days

            fields_to_update['battery_dead_after_utc'] = new_last_charged_utc + timedelta(days=total_battery_life_days)
            fields_to_update['battery_break_after_utc'] = fields_to_update['battery_dead_after_utc'] + timedelta(days=charge_window_days)
            
            # Если телефон был "окончательно сломан по времени", то он НЕ был is_broken=True с компонентом батареи.
            # Теперь, после "зарядки" (которая по факту замена/починка батареи в данном контексте),
            # мы должны также сбросить флаги is_broken и broken_component_key, если они были установлены нашей логикой выше.
            # Однако, если телефон заряжается, предполагается, что он НЕ сломан.
            # Логика выше уже не даст зарядить сломанный телефон.
            # Если мы дошли сюда, значит, телефон НЕ был сломан (или его поломка не батарея).
            # Поэтому, если он был "timed out" и мы его "зарядили" (по сути, это как бы новая батарея),
            # то is_broken и broken_component_key (если они были установлены для timed-out батареи) должны быть сброшены.
            # В данном случае, мы просто устанавливаем новые времена жизни батареи.
            # Если ранее мы установили is_broken=True и broken_component_key для timed-out батареи,
            # то эта логика зарядки не должна была бы выполниться из-за return выше.
            # Этот комментарий немного сбивает с толку, так как если is_permanently_dead_battery_by_time было true,
            # мы бы вышли из функции. Значит, если мы здесь, телефон не был is_permanently_dead_battery_by_time.
            # Значит, просто заряжаем.
            # Поля is_broken и broken_component_key сбрасываются при УСПЕШНОМ РЕМОНТЕ. Зарядка их не трогает.

            update_success = await database.update_phone_status_fields(
                phone_inventory_id_arg, fields_to_update, conn_ext=conn
            )

            if not update_success:
                # Эта ошибка более специфична и важна
                raise Exception(f"Не удалось обновить статус зарядки для телефона ID {phone_inventory_id_arg} (update_phone_status_fields вернул False/None).")


            phone_name_static = PHONE_MODELS.get(phone_db_data.get('phone_model_key'), {}).get('name', phone_db_data.get('phone_model_key', 'N/A'))
            new_balance = current_balance - charge_cost

            time_left_dead = fields_to_update['battery_dead_after_utc'] - now_utc
            d, r = divmod(time_left_dead.total_seconds(), 86400); h, r = divmod(r, 3600); m, _ = divmod(r, 60)
            time_left_str = f"{int(d)}д {int(h)}ч {int(m)}м" if d > 0 else (f"{int(h)}ч {int(m)}м" if h > 0 else f"{int(m)}м")

            await message.reply(
                f"{user_link}, телефон \"<b>{html.escape(phone_name_static)}</b>\" (ID: {phone_inventory_id_arg}) успешно заряжен за {charge_cost} OC!\n"
                f"Теперь его хватит на ~{time_left_str}.\n"
                f"Ваш новый баланс в этом чате: {new_balance} OC.",
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            await send_telegram_log(bot,
                f"🔋 Телефон заряжен: {user_link} зарядил \"{html.escape(phone_name_static)}\" (ID: {phone_inventory_id_arg}) "
                f"за {charge_cost} OC. Хватит на ~{time_left_str}. Баланс: {new_balance} OC."
            )
            
            # --- Вызов проверки достижений (если он есть в оригинале) ---
            # await check_and_grant_achievements(bot, message, user_id, "charge_phone", conn_ext=conn)


    except Exception as e_charge:
        logger.error(f"ChargePhone: Ошибка для user {user_id}, phone_id {phone_inventory_id_arg}: {e_charge}", exc_info=True)
        await message.reply(
            "Произошла ошибка при попытке зарядить телефон.",
            disable_web_page_preview=True
        )
    finally:
        if conn and not conn.is_closed():
            await conn.close()


@phone_router.message(Command("upgradememory", "улучшитьпамять", "апгрейдпамяти", ignore_case=True))
async def cmd_upgrade_memory(message: Message, command: CommandObject, bot: Bot):
    if not message.from_user:
        return await message.reply("Не удалось определить пользователя.")

    user_id = message.from_user.id
    chat_id = message.chat.id # OneCoin списываются с баланса текущего чата
    user_link = get_user_mention_html(user_id, message.from_user.full_name, message.from_user.username)

    args_str = command.args
    if not args_str:
        await message.reply(
            f"{user_link}, укажите ID телефона, память которого вы хотите улучшить.\n"
            f"Пример: /upgradememory 123\n"
            f"ID телефонов: /myphones",
            parse_mode="HTML"
        )
        return

    try:
        phone_inventory_id_arg = int(args_str.strip())
    except ValueError:
        await message.reply("ID телефона должен быть числом.")
        return

    upgrade_work_cost = getattr(Config, "PHONE_UPGRADE_MEMORY_COST", 50)
    # Ключ модуля памяти, который будет использоваться. Убедитесь, что он есть в PHONE_COMPONENTS и item_data.py
    memory_module_key = getattr(Config, "MEMORY_UPGRADE_ITEM_KEY", "MEMORY_MODULE_50GB") # Используем getattr с дефолтом
    memory_module_info = PHONE_COMPONENTS.get(memory_module_key)

    if not memory_module_info:
        await message.reply(f"Ошибка: информация о модуле памяти '{html.escape(memory_module_key)}' для апгрейда не найдена в конфигурации. Обратитесь к администратору.", parse_mode="HTML")
        logger.error(f"UpgradeMemory: Static info for {memory_module_key} not found in PHONE_COMPONENTS.")
        return

    memory_increase_gb = memory_module_info.get("memory_gb") # Используем capacity_gb из данных компонента
    if not isinstance(memory_increase_gb, int) or memory_increase_gb <= 0:
        await message.reply(f"Ошибка: некорректные данные о вместимости модуля памяти '{html.escape(memory_module_key)}'. Обратитесь к администратору.", parse_mode="HTML")
        logger.error(f"UpgradeMemory: Invalid capacity_gb for {memory_module_key}: {memory_increase_gb}")
        return

    memory_module_name_display = html.escape(memory_module_info.get('name', memory_module_key)) # Используем .get


    conn = None
    try:
        conn = await database.get_connection()
        async with conn.transaction():
            phone_db_data = await database.get_phone_by_inventory_id(phone_inventory_id_arg, conn_ext=conn) # Используем conn_ext
            if not phone_db_data or phone_db_data['user_id'] != user_id:
                await message.reply(f"Телефон с ID <code>{phone_inventory_id_arg}</code> не найден в вашем инвентаре.", parse_mode="HTML")
                return
            if phone_db_data.get('is_sold', False): # Используем .get
                await message.reply(f"Телефон ID <code>{phone_inventory_id_arg}</code> уже продан.", parse_mode="HTML")
                return
            if phone_db_data.get('is_broken'):
                await message.reply(f"Телефон ID <code>{phone_inventory_id_arg}</code> сломан. Сначала почините его, чтобы улучшать память.", parse_mode="HTML")
                return

            current_memory = phone_db_data.get('current_memory_gb')
            if current_memory is None:
                phone_model_key_local = phone_db_data.get('phone_model_key') # Используем локальную переменную и .get
                if phone_model_key_local:
                    phone_static_data = PHONE_MODELS.get(phone_model_key_local) # Используем словарь
                    if phone_static_data:
                        memory_str = phone_static_data.get('memory', '0').upper() # Используем .get
                        if 'TB' in memory_str:
                           try: current_memory = int(float(memory_str.replace('TB','').strip())*1024)
                           except ValueError: current_memory = 1024
                        elif 'GB' in memory_str:
                           try: current_memory = int(float(memory_str.replace('GB','').strip()))
                           except ValueError: current_memory = 0
                        else: current_memory = 0
                        # Сохраняем начальную память в БД, если она была None
                        await database.update_phone_status_fields(phone_inventory_id_arg, {'current_memory_gb': current_memory}, conn_ext=conn)
                        phone_db_data['current_memory_gb'] = current_memory # Обновляем данные в словаре, чтобы использовать их ниже
                    else:
                        await message.reply(f"Не удалось определить текущую память телефона ID <code>{phone_inventory_id_arg}</code> (нет стат.данных). Обратитесь к администратору.", parse_mode="HTML")
                        return
                else:
                     await message.reply(f"Не удалось определить текущую память телефона ID <code>{phone_inventory_id_arg}</code> (нет ключа модели). Обратитесь к администратору.", parse_mode="HTML")
                     return


            max_phone_memory_gb = getattr(Config, "MAX_PHONE_MEMORY_GB", 1024 * 2) # Дефолт 2TB
            if current_memory + memory_increase_gb > max_phone_memory_gb:
                await message.reply(f"Нельзя увеличить память телефона ID <code>{phone_inventory_id_arg}</code> сверх {max_phone_memory_gb}GB.", parse_mode="HTML")
                return

            # Проверяем наличие модуля памяти в инвентаре
            module_in_inventory = await database.get_user_specific_item_count(user_id, memory_module_key, "memory_module", conn_ext=conn)
            if module_in_inventory < 1:
                await message.reply(f"У вас нет модуля \"<b>{memory_module_name_display}</b>\" для апгрейда. Купите его в /itemshop memory.", parse_mode="HTML")
                return

            current_balance = await database.get_user_onecoins(user_id, chat_id, conn_ext=conn) # Используем conn_ext
            if current_balance < upgrade_work_cost:
                await message.reply(
                    f"{user_link}, у вас недостаточно средств для оплаты работы по улучшению памяти.\n"
                    f"Нужно: {upgrade_work_cost} OC, у вас: {current_balance} OC.",
                    parse_mode="HTML"
                )
                return

            user_db_data_for_log = await database.get_user_data_for_update(user_id, chat_id, conn_ext=conn)
            await database.update_user_onecoins(
                user_id, chat_id, -upgrade_work_cost,
                username=user_db_data_for_log.get('username'),
                full_name=user_db_data_for_log.get('full_name'),
                chat_title=user_db_data_for_log.get('chat_title'),
                conn_ext=conn
            )

            # Списываем модуль памяти
            remove_module_success = await database.remove_item_from_user_inventory(
                user_id, memory_module_key, "memory_module", 1, conn_ext=conn
            )
            if not remove_module_success:
                raise Exception(f"Не удалось списать модуль памяти {memory_module_key} у user {user_id}")

            new_memory_total = current_memory + memory_increase_gb
            update_phone_success = await database.update_phone_status_fields(
                phone_inventory_id_arg, {'current_memory_gb': new_memory_total}, conn_ext=conn
            )
            if not update_phone_success:
                raise Exception(f"Не удалось обновить память телефона ID {phone_inventory_id_arg}")

            phone_name_static = PHONE_MODELS.get(phone_db_data.get('phone_model_key'), {}).get('name', phone_db_data.get('phone_model_key', 'N/A')) # Используем .get
            new_balance = current_balance - upgrade_work_cost

            new_memory_display = f"{new_memory_total}GB"
            if new_memory_total >=1024 and new_memory_total % 1024 == 0 : new_memory_display = f"{new_memory_total//1024}TB"

            await message.reply(
                f"{user_link}, память телефона \"<b>{html.escape(phone_name_static)}</b>\" (ID: {phone_inventory_id_arg}) успешно увеличена до {new_memory_display}!\n"
                f"Стоимость работы: {upgrade_work_cost} OC. Использован 1 x \"<b>{memory_module_name_display}</b>\".\n" # Добавлен HTML Escape и жирный шрифт
                f"Ваш новый баланс в этом чате: {new_balance} OC.",
                parse_mode="HTML"
            )
            await send_telegram_log(bot,
                f"💾 Память улучшена: {user_link} улучшил память телефона "
                f"\"{html.escape(phone_name_static)}\" (ID: {phone_inventory_id_arg}) до {new_memory_display}. "
                f"Стоимость: {upgrade_work_cost} OC. Баланс: {new_balance} OC."
            )
            
            # --- ВЫЗОВ ПРОВЕРКИ ДОСТИЖЕНИЙ ---
            
            # --- КОНЕЦ ВЫЗОВА ПРОВЕРКИ ДОСТИЖЕНИЙ ---

    except Exception as e_upgrade:
        logger.error(f"UpgradeMemory: Ошибка для user {user_id}, phone_id {phone_inventory_id_arg}: {e_upgrade}", exc_info=True)
        await message.reply("Произошла ошибка при попытке улучшить память телефона.")
    finally:
        if conn and not conn.is_closed():
            await conn.close()
            
@phone_router.message(Command("craftphone", "собратьтелефон", "скрафтитьтелефон", ignore_case=True))
async def cmd_craftphone_start(message: Message, command: CommandObject, state: FSMContext, bot: Bot):
    if not message.from_user:
        return await message.reply("Не удалось определить пользователя.")

    user_id = message.from_user.id
    chat_id = message.chat.id # Используем chat_id для возможного списания/зачисления OneCoin (хотя тут крафт)
    user_link = get_user_mention_html(user_id, message.from_user.full_name, message.from_user.username)

    args_str = command.args
    if not args_str:
        await message.reply(
            f"{user_link}, укажите серию телефона для сборки (S, A или Z).\n"
            f"Пример: /craftphone S",
            parse_mode="HTML"
        )
        return

    requested_series = args_str.strip().upper()
    if requested_series not in ["S", "A", "Z"]:
        await message.reply(
            f"{user_link}, можно собрать телефон только S, A или Z серии.\n"
            f"Пример: /craftphone S",
            parse_mode="HTML"
        )
        return

    # 1. Проверка лимита телефонов
    try:
        active_phones_count = await database.count_user_active_phones(user_id)
        max_phones = getattr(Config, "MAX_PHONES_PER_USER", 2)
        if active_phones_count >= max_phones:
            await message.reply(
                f"{user_link}, у вас уже максимальное количество телефонов ({active_phones_count}/{max_phones}). "
                f"Вы не можете собрать новый, пока не продадите один из существующих (/sellphone).",
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            return
    except Exception as e_count:
        logger.error(f"CraftPhone: Ошибка подсчета телефонов для user {user_id}: {e_count}", exc_info=True)
        await message.reply("Произошла ошибка при проверке вашего инвентаря. Попробуйте позже.")
        return

    # 2. Проверка наличия компонентов
    required_components_keys: Dict[str, str] = {} # component_type -> component_key
    missing_components_names: List[str] = []
    
    # Формируем ключи необходимых компонентов для указанной серии
    # CORE_PHONE_COMPONENT_TYPES = ["screen", "cpu", "battery", "board", "body"]
    component_key_template_map = {
        "screen": f"SCREEN_{requested_series}",
        "cpu": f"CPU_{requested_series}",
        "battery": f"BATTERY_{requested_series}",
        "board": f"BOARD_{requested_series}",
        "body": f"BODY_{requested_series}",
    }

    # Сохраним фактические ключи компонентов для передачи в FSM
    components_to_use_keys_list: List[str] = []
    components_to_use_names_list: List[str] = []

    conn_check_items = None
    try:
        conn_check_items = await database.get_connection()
        for comp_type, comp_key_template in component_key_template_map.items():
            # Убедимся, что такой компонент вообще существует в PHONE_COMPONENTS
            component_static_info = PHONE_COMPONENTS.get(comp_key_template)
            if not component_static_info:
                logger.error(f"CraftPhone: Статическая информация для компонента {comp_key_template} не найдена.")
                # Это серьезная ошибка конфигурации, но для пользователя покажем общее сообщение
                missing_components_names.append(f"данные для {comp_type} {requested_series}-серии (ошибка)")
                continue # Переходим к следующему компоненту

            required_components_keys[comp_type] = comp_key_template
            components_to_use_keys_list.append(comp_key_template)
            components_to_use_names_list.append(component_static_info.get('name', comp_key_template))

            has_component_count = await database.get_user_specific_item_count(
                user_id,
                comp_key_template,
                component_static_info.get("component_type", comp_type), # Берем тип из статики, если есть
                conn_ext=conn_check_items
            )
            if has_component_count < 1:
                missing_components_names.append(component_static_info.get('name', comp_key_template))
    except Exception as e_check_comps:
        logger.error(f"CraftPhone: Ошибка при проверке компонентов для user {user_id}, серия {requested_series}: {e_check_comps}", exc_info=True)
        await message.reply("Произошла ошибка при проверке ваших компонентов. Попробуйте позже.")
        if conn_check_items and not conn_check_items.is_closed(): await conn_check_items.close()
        return
    finally:
        if conn_check_items and not conn_check_items.is_closed():
            await conn_check_items.close()

    if missing_components_names:
        missing_list_str = "\n - ".join(missing_components_names)
        await message.reply(
            f"{user_link}, для сборки телефона {requested_series}-серии вам не хватает следующих компонентов:\n"
            f" - {missing_list_str}\n"
            f"Вы можете купить их в /itemshop components {requested_series}",
            parse_mode="HTML"
        )
        return
        
    # 3. Установка FSM и запрос подтверждения
    try:
        await state.set_state(PurchaseStates.awaiting_confirmation)
        await state.update_data(
            action_type="craft_phone",
            phone_series_to_craft=requested_series,
            components_to_use_keys=components_to_use_keys_list, # Список ключей деталей
            confirmation_initiated_at=datetime.now(dt_timezone.utc).isoformat(),
            original_chat_id=chat_id, # Сохраняем для контекста
            original_user_id=user_id
        )

        components_names_for_message = "\n - ".join(components_to_use_names_list)
        confirmation_message = (
            f"{user_link}, вы уверены, что хотите собрать телефон <b>{requested_series}-серии</b>?\n"
            f"Будут использованы следующие компоненты (по 1 шт. каждого):\n"
            f" - {components_names_for_message}\n\n"
            f"Ответьте 'Да' или 'Нет' в течение {CONFIRMATION_TIMEOUT_SECONDS_ITEM} секунд." # Таймаут для предметов/действий
        )
        await message.reply(confirmation_message, parse_mode="HTML")

    except Exception as e_fsm_setup:
        logger.error(f"CraftPhone: Ошибка при установке FSM для user {user_id}, серия {requested_series}: {e_fsm_setup}", exc_info=True)
        await message.reply("Произошла ошибка при подготовке к сборке телефона. Попробуйте позже.")
        await state.clear() # Очищаем состояние в случае ошибки            


# =============================================================================
# Функция для получения активных бонусов от телефонов пользователя
# =============================================================================
async def get_active_user_phone_bonuses(user_id: int) -> Dict[str, float]:
    active_bonuses: Dict[str, float] = {
        "onecoin_bonus_percent": 0.0,
        "oneui_version_bonus_percent": 0.0,
        "bonus_roulette_luck_percent": 0.0,
        "market_discount_percent": 0.0
    }
    user_phones_db = await database.get_user_phones(user_id, active_only=True) # Только не проданные
    if not user_phones_db:
        return active_bonuses

    now_utc = datetime.now(dt_timezone.utc)

    for phone_db in user_phones_db:
        is_operational = True # Предполагаем, что телефон исправен и заряжен

        # Проверка на поломку
        if phone_db.get('is_broken'):
            is_operational = False

        # Проверка на зарядку
        battery_dead_after = phone_db.get('battery_dead_after_utc')
        if isinstance(battery_dead_after, str):
             try: battery_dead_after = datetime.fromisoformat(battery_dead_after)
             except ValueError: battery_dead_after = None
        if battery_dead_after and battery_dead_after.tzinfo is None:
             battery_dead_after = battery_dead_after.replace(tzinfo=dt_timezone.utc)


        if not battery_dead_after: # Если никогда не заряжался / нет данных о зарядке
            is_operational = False
        elif now_utc.astimezone(dt_timezone.utc) >= battery_dead_after.astimezone(dt_timezone.utc): # Если разряжен
            is_operational = False
            # Дополнительная проверка на окончательную поломку батареи
            battery_break_after = phone_db.get('battery_break_after_utc')
            if isinstance(battery_break_after, str):
                 try: battery_break_after = datetime.fromisoformat(battery_break_after)
                 except ValueError: battery_break_after = None
            if battery_break_after and battery_break_after.tzinfo is None:
                 battery_break_after = battery_break_after.replace(tzinfo=dt_timezone.utc)

            if battery_break_after and now_utc.astimezone(dt_timezone.utc) >= battery_break_after.astimezone(dt_timezone.utc):
                 pass # is_operational уже False, и это учтено как поломка

        if not is_operational:
            continue # Переходим к следующему телефону, если этот не операционен

        equipped_case_key = phone_db.get('equipped_case_key')
        if equipped_case_key and equipped_case_key in PHONE_CASES:
            case_info = PHONE_CASES[equipped_case_key]
            for bonus_key, bonus_value in case_info.items():
                if bonus_key in active_bonuses and isinstance(bonus_value, (int, float)):
                    active_bonuses[bonus_key] += bonus_value

    logger.debug(f"User {user_id} active phone bonuses: {active_bonuses}")
    return active_bonuses


@phone_router.message(Command("repairphone", "починитьтелефон", ignore_case=True))
async def cmd_repairphone_start(message: Message, command: CommandObject, state: FSMContext, bot: Bot):
    if not message.from_user: return await message.reply("Пользователь не найден.")
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_link = get_user_mention_html(user_id, message.from_user.full_name, message.from_user.username)

    args_str = command.args
    if not args_str:
        await message.reply(f"{user_link}, укажите ID телефона для ремонта.\nПример: /repairphone 123", parse_mode="HTML")
        return
    try:
        phone_inventory_id_arg = int(args_str.strip())
    except ValueError:
        await message.reply("ID телефона должен быть числом.")
        return

    phone_db_data = await database.get_phone_by_inventory_id(phone_inventory_id_arg)
    if not phone_db_data or phone_db_data['user_id'] != user_id:
        await message.reply(f"Телефон ID <code>{phone_inventory_id_arg}</code> не найден.", parse_mode="HTML")
        return
    # Убедимся, что телефон сломан и есть ключ сломанного компонента
    if not phone_db_data.get('is_broken') or not phone_db_data.get('broken_component_key'):
        await message.reply(f"Телефон ID <code>{phone_inventory_id_arg}</code> не сломан или поломка не определена.", parse_mode="HTML")
        return

    broken_comp_key = phone_db_data['broken_component_key']
    broken_comp_info = PHONE_COMPONENTS.get(broken_comp_key)
    if not broken_comp_info:
        await message.reply(f"Ошибка: неизвестный сломанный компонент (<code>{html.escape(broken_comp_key)}</code>). Ремонт невозможен. Обратитесь к администратору.", parse_mode="HTML")
        return

    repair_comp_name = html.escape(broken_comp_info.get('name', broken_comp_key)) # Используем .get
    user_has_comp_count = await database.get_user_specific_item_count(user_id, broken_comp_key, broken_comp_info.get("component_type", "component"))
    if user_has_comp_count < 1:
        await message.reply(f"Для ремонта \"<b>{repair_comp_name}</b>\" у вас нет необходимой детали. Купите ее в /itemshop.", parse_mode="HTML")
        return

    # !!! ИСПОЛЬЗУЕМ СЛОВАРЬ ДЛЯ ПОИСКА !!!
    phone_static_data = PHONE_MODELS.get(phone_db_data.get('phone_model_key')) # Использование словаря, .get
    if not phone_static_data:
        await message.reply("Ошибка данных модели телефона. Обратитесь к администратору.")
        return
    phone_name_static = phone_static_data.get('name', phone_db_data.get('phone_model_key', 'N/A')) # Используем .get

    # Расчет идеальной текущей стоимости для стоимости ремонта (без учета этой поломки)
    temp_phone_data_for_calc = phone_db_data.copy()
    temp_phone_data_for_calc['is_broken'] = False # Моделируем состояние "не сломан" для расчета
    # Убедимся, что purchase_date_utc корректно перед передачей в calculate_phone_sell_price
    purchase_date_val = temp_phone_data_for_calc.get('purchase_date_utc')
    if isinstance(purchase_date_val, str):
        try: temp_phone_data_for_calc['purchase_date_utc'] = datetime.fromisoformat(purchase_date_val).replace(tzinfo=dt_timezone.utc)
        except ValueError: temp_phone_data_for_calc['purchase_date_utc'] = None # Некорректный формат даты

    ideal_value_for_repair_calc, _ = calculate_phone_sell_price(temp_phone_data_for_calc, phone_static_data)

    # Стоимость работы мастера - процент от идеальной текущей стоимости
    repair_work_percentage = getattr(Config, "PHONE_REPAIR_WORK_PERCENTAGE", 0.30) # Дефолт 30%
    min_repair_work_cost = getattr(Config, "PHONE_MIN_REPAIR_WORK_COST", 10) # Дефолт 10 OC

    repair_work_cost = int(round(ideal_value_for_repair_calc * repair_work_percentage))
    if repair_work_cost < min_repair_work_cost: repair_work_cost = min_repair_work_cost # Минимальная стоимость работы

    current_balance = await database.get_user_onecoins(user_id, chat_id)
    if current_balance < repair_work_cost:
        await message.reply(f"Недостаточно средств для оплаты работы мастера ({repair_work_cost} OC). У вас: {current_balance} OC.")
        return

    await state.set_state(PurchaseStates.awaiting_confirmation)
    await state.update_data(
        action_type="repair_phone", # Новый тип действия
        phone_inventory_id=phone_inventory_id_arg,
        phone_name=phone_name_static, # Сохраняем неэкранированное имя телефона для логов
        broken_component_key=broken_comp_key,
        broken_component_name=broken_comp_info.get('name', broken_comp_key), # Сохраняем неэкранированное имя компонента для логов
        repair_work_cost=repair_work_cost,
        confirmation_initiated_at=datetime.now(dt_timezone.utc).isoformat(),
        original_chat_id=chat_id,
        original_user_id=user_id
    )
    await message.reply(
        f"{user_link}, вы уверены, что хотите починить \"<b>{repair_comp_name}</b>\"\n" # Используем экранированное имя для сообщения
        f"на телефоне <b>{html.escape(phone_name_static)}</b> (ID: {phone_inventory_id_arg})?\n"
        f"Потребуется: 1 x \"<b>{repair_comp_name}</b>\" и {repair_work_cost} OC за работу.\n" # Используем экранированное имя
        f"Ответьте 'Да' или 'Нет'.",
        parse_mode="HTML"
    )



# --- КОМАНДА ПРОДАЖИ ЧЕХЛА (ОСТАВЛЕНА ДЛЯ СОВМЕСТИМОСТИ, НО sellitem МОЖЕТ ЗАМЕНИТЬ) ---
# Если хотите полностью перейти на sellitem, можно удалить эту функцию или оставить ее как алиас.
@phone_router.message(Command(*SELLCASE_COMMAND_ALIASES, ignore_case=True))
async def cmd_sellcase_start(message: Message, command: CommandObject, state: FSMContext, bot: Bot):
    if not message.from_user:
        return await message.reply("Не удалось определить пользователя.")

    user_id = message.from_user.id
    chat_id = message.chat.id
    user_link = get_user_mention_html(user_id, message.from_user.full_name, message.from_user.username)

    args_str = command.args
    if not args_str:
        await message.reply(
            f"{user_link}, укажите ID чехла из вашего инвентаря, который хотите продать.\n"
            f"Пример: /sellcase 45\n"
            f"ID ваших чехлов: /myitems (смотрите ID конкретного экземпляра чехла)",
            parse_mode="HTML"
        )
        return

    try:
        user_item_id_to_sell = int(args_str.strip())
    except ValueError:
        await message.reply("ID чехла должен быть числом.")
        return

    conn = None
    try:
        conn = await database.get_connection() # Открываем соединение здесь
        # Получаем информацию о чехле из инвентаря пользователя
        item_db_data = await database.get_user_item_by_id(user_item_id_to_sell, user_id=user_id, conn_ext=conn) # Используем conn_ext

        if not item_db_data:
            await message.reply(f"Чехол с ID <code>{user_item_id_to_sell}</code> не найден в вашем инвентаре.", parse_mode="HTML")
            if conn and not conn.is_closed(): await conn.close()
            return
        if item_db_data['item_type'] != 'case':
            await message.reply(f"Предмет с ID <code>{user_item_id_to_sell}</code> не является чехлом.", parse_mode="HTML")
            if conn and not conn.is_closed(): await conn.close()
            return
        # Проверяем, не надет ли чехол на телефон
        if item_db_data.get('equipped_phone_id') is not None:
             await message.reply(f"Чехол ID <code>{user_item_id_to_sell}</code> надет на телефон ID {item_db_data['equipped_phone_id']}. Сначала снимите его.", parse_mode="HTML")
             if conn and not conn.is_closed(): await conn.close()
             return


        item_key = item_db_data['item_key']
        item_static_info = PHONE_CASES.get(item_key)

        if not item_static_info:
            await message.reply(f"Ошибка: не найдены данные для чехла <code>{html.escape(item_key)}</code> (ID: {user_item_id_to_sell}). Продать невозможно.", parse_mode="HTML")
            if conn and not conn.is_closed(): await conn.close()
            return

        item_name_display = html.escape(item_static_info.get('name', item_key)) # Используем .get
        original_price = item_static_info.get('price', 0) # Используем .get
        # Используем Config.CASE_SELL_PERCENTAGE
        sell_percentage = getattr(Config, "CASE_SELL_PERCENTAGE", 0.20)
        sell_price = int(round(original_price * sell_percentage))
        # Используем общую минимальную цену продажи
        min_sell_price = getattr(Config, "MIN_SELL_PRICE_IF_ORIGINAL_GT_ZERO", 1)

        if sell_price < min_sell_price and original_price > 0: sell_price = min_sell_price
        elif original_price == 0: sell_price = 0


        await state.set_state(PurchaseStates.awaiting_confirmation)
        await state.update_data(
            action_type="sell_item", # Изменено на sell_item для унификации
            user_item_id_to_sell=user_item_id_to_sell,
            item_key=item_key,
            item_type='case', # Указываем тип явно
            item_name=item_name_display, # Сохраняем экранированное имя для FSM (или неэкранированное?) - пусть будет экранированное как в sellitem
            quantity_to_sell=1, # Для чехла всегда 1
            total_sell_value=sell_price, # Для чехла общая цена = цена за шт.
            sell_price_per_unit=sell_price, # для лога
            original_price_per_unit=original_price, # для лога
            confirmation_initiated_at=datetime.now(dt_timezone.utc).isoformat(),
            original_chat_id=chat_id,
            original_user_id=user_id
        )

        confirmation_message = (
            f"{user_link}, вы уверены, что хотите продать чехол:\n"
            f"  <b>{item_name_display}</b> (ID инвентаря: {user_item_id_to_sell})\n"
            f"  Цена продажи: {sell_price} OneCoin(s)?\n\n"
            f"Ответьте 'Да' или 'Нет' в течение {CONFIRMATION_TIMEOUT_SECONDS_ITEM} секунд."
        )
        await message.reply(confirmation_message, parse_mode="HTML")

    except Exception as e_sellcase_start:
        logger.error(f"SellCase: Ошибка на старте продажи для user {user_id}, case_item_id {user_item_id_to_sell}: {e_sellcase_start}", exc_info=True)
        await message.reply("Произошла ошибка при подготовке к продаже чехла.")
        await send_telegram_log(bot, f"🔴 Ошибка в /sellcase (старт) для {user_link}, чехол ID {user_item_id_to_sell}: <pre>{html.escape(str(e_sellcase_start))}</pre>")
    finally:
        if conn and not conn.is_closed():
             await conn.close()
             
             
             
@phone_router.message(Command("keepwonphone", "взятьвыигранный", "оставитьприз", ignore_case=True))
async def cmd_keep_won_phone(message: Message, command: CommandObject, bot: Bot):
    if not message.from_user:
        return await message.reply("Не удалось определить пользователя.")

    user_id = message.from_user.id
    chat_id = message.chat.id
    user_link = get_user_mention_html(user_id, message.from_user.full_name, message.from_user.username)

    args_str = command.args
    if not args_str:
        await message.reply(
            f"{user_link}, чтобы взять выигранный телефон, укажите ID старого телефона, который нужно продать.\n"
            f"Пример: <code>/keepwonphone ID_старого_телефона</code>\n"
            f"ID ваших телефонов: <code>/myphones</code>",
            parse_mode="HTML"
        )
        return

    try:
        old_phone_inventory_id_to_sell = int(args_str.strip())
    except ValueError:
        await message.reply("ID старого телефона должен быть числом.", parse_mode="HTML")
        return

    conn = None
    try:
        conn = await database.get_connection()
        async with conn.transaction(): # Используем транзакцию для атомарности
            # 1. Проверяем наличие pending приза и его срок
            pending_prize_data = await database.get_pending_phone_prize(user_id, conn_ext=conn)
            if not pending_prize_data:
                await message.reply(f"{user_link}, у вас нет телефона, ожидающего решения о призе.", parse_mode="HTML")
                return

            prize_won_at_utc = pending_prize_data['prize_won_at_utc']
            time_limit_td = timedelta(seconds=getattr(Config, "MARKET_PHONE_CONFIRMATION_TIMEOUT_SECONDS", 60)) # Используем тот же таймаут, что и для подтверждений
            now_utc = datetime.now(dt_timezone.utc)

            if now_utc - prize_won_at_utc > time_limit_td:
                # Срок истек, автоматически продаем выигранный телефон
                await message.reply(f"{user_link}, время на принятие решения по выигранному телефону истекло.", parse_mode="HTML")
                # Вызываем логику автоматической продажи
                await _auto_sell_expired_prize(user_id, bot, conn_ext=conn)
                return # Транзакция будет завершена в _auto_sell_expired_prize или при выходе из async with

            # 2. Проверяем старый телефон для продажи
            old_phone_db_data = await database.get_phone_by_inventory_id(old_phone_inventory_id_to_sell, conn_ext=conn)
            if not old_phone_db_data or old_phone_db_data['user_id'] != user_id:
                await message.reply(f"Телефон с ID <code>{old_phone_inventory_id_to_sell}</code> не найден в вашем инвентаре.", parse_mode="HTML")
                return
            if old_phone_db_data['is_sold']:
                await message.reply(f"Телефон ID <code>{old_phone_inventory_id_to_sell}</code> уже был продан.", parse_mode="HTML")
                return
            # Дополнительно: убедиться, что старый телефон не является случайно тем самым выигранным телефоном,
            # если бы он как-то попал в основной инвентарь до решения (маловероятно при текущей логике, но на всякий случай)
            # if old_phone_inventory_id_to_sell == pending_prize_data['prize_id']: # Это не сработает, т.к. prize_id != phone_inventory_id
            #     await message.reply("Вы не можете продать только что выигранный телефон таким образом.")
            #     return


            old_phone_model_key = old_phone_db_data['phone_model_key']
            old_phone_static_data = PHONE_MODELS.get(old_phone_model_key)
            if not old_phone_static_data:
                 await message.reply(f"Ошибка: не найдены данные для модели старого телефона ID <code>{old_phone_inventory_id_to_sell}</code>.", parse_mode="HTML")
                 return

            # 3. Рассчитываем цену продажи старого телефона
            old_phone_sell_price, old_phone_condition_desc = calculate_phone_sell_price(old_phone_db_data, old_phone_static_data)

            # Продаем старый телефон
            mark_sold_success = await database.update_phone_as_sold(
                phone_inventory_id=old_phone_inventory_id_to_sell,
                sold_date_utc=now_utc,
                sold_price_onecoins=old_phone_sell_price, # Записываем цену, за которую он "продан" при обмене
                conn_ext=conn
            )
            if not mark_sold_success:
                raise Exception(f"Не удалось пометить старый телефон ID {old_phone_inventory_id_to_sell} как проданный.")

            # Снимаем чехол со старого телефона, если он был
            if old_phone_db_data.get('equipped_case_key'):
                 old_case_key_on_phone = old_phone_db_data['equipped_case_key']
                 case_item_db_data_to_update = await database.get_user_item_by_equipped_phone_id(user_id, old_phone_inventory_id_to_sell, old_case_key_on_phone, conn_ext=conn)
                 if case_item_db_data_to_update:
                     update_case_item_success = await database.update_user_item_fields(
                         case_item_db_data_to_update['user_item_id'], user_id, {'equipped_phone_id': None}, conn_ext=conn
                     )
                     if not update_case_item_success:
                         logger.warning(f"KeepWonPhone: Не удалось сбросить equipped_phone_id=NULL для чехла ID {case_item_db_data_to_update['user_item_id']} со старого телефона.")
                     # TODO: Вернуть старый чехол в инвентарь (добавить новую запись), если нужно.
                     # Сейчас он просто снимается с телефона в БД user_items, но не возвращается как отдельный предмет.
                     # Если чехлы должны "возвращаться" при продаже/обмене телефона, добавьте здесь логику database.add_item_to_user_inventory.


            # Начисляем пользователю стоимость проданного старого телефона
            user_db_data_for_log = await database.get_user_data_for_update(user_id, chat_id, conn_ext=conn)
            await database.update_user_onecoins(
                user_id, chat_id, old_phone_sell_price, # Начисляем стоимость старого телефона
                username=user_db_data_for_log.get('username'), full_name=user_db_data_for_log.get('full_name'),
                chat_title=user_db_data_for_log.get('chat_title'), conn_ext=conn
            )
            new_balance_after_sell_old = await database.get_user_onecoins(user_id, chat_id, conn_ext=conn) # Получаем актуальный баланс

            # 4. Добавляем выигранный телефон в инвентарь
            won_phone_model_key = pending_prize_data['phone_model_key']
            won_phone_color = pending_prize_data['color']
            won_phone_initial_memory_gb = pending_prize_data['initial_memory_gb']
            original_roulette_chat_id = pending_prize_data['original_roulette_chat_id']

            new_won_phone_inventory_id = await database.add_phone_to_user_inventory(
                user_id=user_id,
                chat_id_acquired_in=original_roulette_chat_id, # Чат, где телефон был выигран
                phone_model_key=won_phone_model_key,
                color=won_phone_color,
                purchase_price=0, # Выигран бесплатно
                purchase_date_utc=now_utc, # Дата добавления в инвентарь = сейчас
                initial_memory_gb=won_phone_initial_memory_gb,
                is_contraband=False,
                conn_ext=conn
            )

            if not new_won_phone_inventory_id:
                 raise Exception(f"Не удалось добавить выигранный телефон {won_phone_model_key} user {user_id} в инвентарь.")


            # 5. Удаляем запись о pending призе
            remove_pending_success = await database.remove_pending_phone_prize(user_id, conn_ext=conn)
            if not remove_pending_success:
                 logger.error(f"KeepWonPhone: Не удалось удалить pending prize для user {user_id} из БД.")
                 # Не прерываем транзакцию, это не критично, но нужно залогировать.

            # 6. Уведомление пользователя и лог
            won_phone_static_data = PHONE_MODELS.get(won_phone_model_key)
            won_phone_name_display = html.escape(won_phone_static_data.get('name', won_phone_model_key)) if won_phone_static_data else won_phone_model_key

            old_phone_name_display = html.escape(old_phone_static_data.get('name', old_phone_model_key))

            await message.reply(
                f"✅ {user_link}, вы успешно обменяли старый телефон \"<b>{old_phone_name_display}</b>\" (ID: {old_phone_inventory_id_to_sell}) на выигранный!\n"
                f"Новый телефон \"<b>{won_phone_name_display}</b>\" ({won_phone_color}, {won_phone_initial_memory_gb}GB) добавлен в ваш инвентарь с ID: <code>{new_won_phone_inventory_id}</code>.\n"
                f"За старый телефон начислено {old_phone_sell_price} OC. Ваш баланс: {new_balance_after_sell_old} OC.",
                parse_mode="HTML"
            )

            log_chat_title = html.escape(message.chat.title or f"ChatID {chat_id}")
            await send_telegram_log(bot,
                f"🔄 Телефон обменян: {user_link} обменял старый телефон ID {old_phone_inventory_id_to_sell} "
                f"(\"{old_phone_name_display}\", продано за {old_phone_sell_price} OC) на выигранный телефон ID {new_won_phone_inventory_id} "
                f"(\"{won_phone_name_display}\", {won_phone_color}) в чате \"{log_chat_title}\". "
                f"Баланс: {new_balance_after_sell_old} OC."
            )

            # Транзакция завершится успешно при выходе из async with
            
            # --- ВЫЗОВ ПРОВЕРКИ ДОСТИЖЕНИЙ ---
            
            # --- КОНЕЦ ВЫЗОВА ПРОВЕРКИ ДОСТИЖЕНИЙ ---

    except Exception as e_keep:
        logger.error(f"KeepWonPhone: Ошибка для user {user_id}, old_phone_id {old_phone_inventory_id_to_sell}: {e_keep}", exc_info=True)
        await message.reply("Произошла ошибка при попытке обменять телефон. Попробуйте позже.")
        # Транзакция будет отменена при выходе из async with с исключением
    finally:
        if conn and not conn.is_closed():
            await conn.close()

@phone_router.message(Command("sellwonphone", "продатьвыигранный", ignore_case=True))
async def cmd_sell_won_phone(message: Message, bot: Bot):
    if not message.from_user:
        return await message.reply("Не удалось определить пользователя.")

    user_id = message.from_user.id
    chat_id = message.chat.id # OneCoin зачисляются на баланс текущего чата
    user_link = get_user_mention_html(user_id, message.from_user.full_name, message.from_user.username)

    conn = None
    try:
        conn = await database.get_connection()
        async with conn.transaction(): # Используем транзакцию
            # 1. Проверяем наличие pending приза и его срок
            pending_prize_data = await database.get_pending_phone_prize(user_id, conn_ext=conn)
            if not pending_prize_data:
                await message.reply(f"{user_link}, у вас нет телефона, ожидающего решения о призе.", parse_mode="HTML")
                return

            prize_won_at_utc = pending_prize_data['prize_won_at_utc']
            time_limit_td = timedelta(seconds=getattr(Config, "MARKET_PHONE_CONFIRMATION_TIMEOUT_SECONDS", 60)) # Тот же таймаут
            now_utc = datetime.now(dt_timezone.utc)

            if now_utc - prize_won_at_utc > time_limit_td:
                 # Срок истек, автоматически продаем
                await message.reply(f"{user_link}, время на принятие решения по выигранному телефону истекло.", parse_mode="HTML")
                # Вызываем логику автоматической продажи
                await _auto_sell_expired_prize(user_id, bot, conn_ext=conn)
                return # Транзакция будет завершена в _auto_sell_expired_prize или при выходе из async with


            # 2. Рассчитываем стоимость продажи выигранного телефона (80% от текущей рыночной цены)
            won_phone_model_key = pending_prize_data['phone_model_key']
            won_phone_color = pending_prize_data['color'] # Цвет нужен для отображения, но не для цены
            won_phone_initial_memory_gb = pending_prize_data['initial_memory_gb'] # Память тоже для отображения

            won_phone_static_data = PHONE_MODELS.get(won_phone_model_key)
            if not won_phone_static_data:
                # Если статические данные не найдены, рассчитываем компенсацию от какой-то базовой цены или выдаем фикс. сумму
                logger.error(f"SellWonPhone: Не найдены статические данные для выигранного телефона {won_phone_model_key} user {user_id}. Расчет цены продажи затруднен.")
                # Выдаем фикс. компенсацию как при полной инвентарной сетке
                sell_value = random.randint(50, 150)
                won_phone_name_display = won_phone_model_key # Для лога
            else:
                 won_phone_name_display = html.escape(won_phone_static_data.get('name', won_phone_model_key))
                 base_price_won = won_phone_static_data.get('price', 0)
                 current_market_price_won = await get_current_price(base_price_won, conn_ext=conn) # Цена с инфляцией
                 sell_percentage = getattr(Config, "PHONE_SELL_PERCENTAGE_WON_PRIZE", 0.80) # Константа для 80% продажи
                 sell_value = int(round(current_market_price_won * sell_percentage))
                 min_sell_price = getattr(Config, "MIN_SELL_PRICE_IF_ORIGINAL_GT_ZERO", 1)
                 if current_market_price_won > 0 and sell_value < min_sell_price: sell_value = min_sell_price
                 elif current_market_price_won == 0: sell_value = 0

            # 3. Начисляем средства пользователю
            user_db_data_for_log = await database.get_user_data_for_update(user_id, chat_id, conn_ext=conn)
            await database.update_user_onecoins(
                user_id, chat_id, sell_value,
                username=user_db_data_for_log.get('username'), full_name=user_db_data_for_log.get('full_name'),
                chat_title=user_db_data_for_log.get('chat_title'), conn_ext=conn
            )
            new_balance = await database.get_user_onecoins(user_id, chat_id, conn_ext=conn) # Получаем актуальный баланс

            # 4. Удаляем запись о pending призе
            remove_pending_success = await database.remove_pending_phone_prize(user_id, conn_ext=conn)
            if not remove_pending_success:
                 logger.error(f"SellWonPhone: Не удалось удалить pending prize для user {user_id} из БД.")
                 # Не прерываем транзакцию

            # 5. Уведомление пользователя и лог
            await message.reply(
                f"✅ {user_link}, вы решили продать выигранный телефон.\n"
                f"Телефон \"<b>{won_phone_name_display}</b>\" продан за {sell_value} OneCoin(s).\n"
                f"Ваш новый баланс в этом чате: {new_balance} OC.",
                parse_mode="HTML"
            )

            log_chat_title = html.escape(message.chat.title or f"ChatID {chat_id}")
            await send_telegram_log(bot,
                f"💸 Выигранный телефон продан: {user_link} продал выигранный телефон "
                f"(\"{won_phone_name_display}\", {won_phone_color}) за {sell_value} OC в чате \"{log_chat_title}\". "
                f"Баланс: {new_balance} OC."
            )
             # Транзакция завершится успешно

    except Exception as e_sell_won:
        logger.error(f"SellWonPhone: Ошибка для user {user_id}: {e_sell_won}", exc_info=True)
        await message.reply("Произошла ошибка при попытке продать выигранный телефон. Попробуйте позже.")
        # Транзакция будет отменена

    finally:
        if conn and not conn.is_closed():
            await conn.close()

# =============================================================================
# Функция для автоматической продажи просроченного приза (используется в шедулере и командах)
# =============================================================================
async def _auto_sell_expired_prize(user_id: int, bot_instance: Bot, conn_ext: Optional[asyncpg.Connection] = None):
    """
    Автоматически продает просроченный выигранный телефон и начисляет компенсацию.
    Может выполняться из шедулера или из команды /keepwonphone /sellwonphone при просрочке.
    Важно: должна вызываться внутри транзакции, если conn_ext предоставлен.
    """
    conn_to_use = conn_ext # Используем переданное соединение, если есть

    # Получаем данные о pending призе (предполагаем, что он существует и просрочен)
    pending_prize_data = await database.get_pending_phone_prize(user_id, conn_ext=conn_to_use)
    if not pending_prize_data:
        logger.warning(f"_auto_sell_expired_prize: Вызвана для user {user_id}, но pending приза нет.")
        return # Ничего делать не нужно

    # Рассчитываем стоимость продажи (те же 80% от текущей рыночной цены)
    won_phone_model_key = pending_prize_data['phone_model_key']
    won_phone_color = pending_prize_data['color']
    won_phone_initial_memory_gb = pending_prize_data['initial_memory_gb']
    original_roulette_chat_id = pending_prize_data['original_roulette_chat_id']

    won_phone_static_data = PHONE_MODELS.get(won_phone_model_key)
    if not won_phone_static_data:
         logger.error(f"_auto_sell_expired_prize: Не найдены стат.данные для телефона {won_phone_model_key} user {user_id}. Выдаем фикс. комп.")
         sell_value = random.randint(50, 150)
         won_phone_name_display = won_phone_model_key
    else:
        won_phone_name_display = html.escape(won_phone_static_data.get('name', won_phone_model_key))
        base_price_won = won_phone_static_data.get('price', 0)
        current_market_price_won = await get_current_price(base_price_won, conn_ext=conn_to_use)
        sell_percentage = getattr(Config, "PHONE_SELL_PERCENTAGE_WON_PRIZE", 0.80)
        sell_value = int(round(current_market_price_won * sell_percentage))
        min_sell_price = getattr(Config, "MIN_SELL_PRICE_IF_ORIGINAL_GT_ZERO", 1)
        if current_market_price_won > 0 and sell_value < min_sell_price: sell_value = min_sell_price
        elif current_market_price_won == 0: sell_value = 0


    # Начисляем средства пользователю
    # Используем оригинальный чат рулетки для начисления, если возможно, иначе личный чат пользователя
    chat_id_to_credit = original_roulette_chat_id
    user_db_data_for_log = await database.get_user_data_for_update(user_id, chat_id_to_credit, conn_ext=conn_to_use)

    # Убедимся, что есть хотя бы минимальная запись user_oneui для начисления
    if not user_db_data_for_log.get('full_name'): # Проверяем одно из полей, чтобы понять, есть ли запись
         # Если нет записи в user_oneui для original_roulette_chat_id, пробуем личный чат
         user_db_data_private = await database.get_user_data_for_update(user_id, user_id, conn_ext=conn_to_use)
         if user_db_data_private.get('full_name'):
              chat_id_to_credit = user_id # Начисляем в личный чат
              user_db_data_for_log = user_db_data_private # Обновляем данные пользователя для лога
              logger.warning(f"_auto_sell_expired_prize: User {user_id} has no user_oneui record in original chat {original_roulette_chat_id}. Crediting to private chat {user_id}.")
         else:
             # Если нет записи ни в чате рулетки, ни в личном чате, это проблема.
             # Пытаемся создать минимальную запись в чате рулетки перед начислением.
             try:
                 await database.update_user_onecoins(user_id, chat_id_to_credit, 0, conn_ext=conn_to_use) # Создаст запись, если ее нет
                 user_db_data_for_log = await database.get_user_data_for_update(user_id, chat_id_to_credit, conn_ext=conn_to_use)
                 logger.warning(f"_auto_sell_expired_prize: User {user_id} had no user_oneui record in original chat {original_roulette_chat_id}. Created minimal record before crediting.")
             except Exception as e_create_record:
                 logger.error(f"_auto_sell_expired_prize: FATAL ERROR: Failed to create minimal user_oneui record for user {user_id} in chat {chat_id_to_credit} before crediting compensation: {e_create_record}", exc_info=True)
                 # В этом случае начисление может не сработать. Продолжаем, но с пониманием риска.


    await database.update_user_onecoins(
        user_id, chat_id_to_credit, sell_value,
        username=user_db_data_for_log.get('username'), full_name=user_db_data_for_log.get('full_name'),
        chat_title=user_db_data_for_log.get('chat_title'), conn_ext=conn_to_use
    )
    new_balance = await database.get_user_onecoins(user_id, chat_id_to_credit, conn_ext=conn_to_use)

    # Удаляем запись о pending призе
    remove_pending_success = await database.remove_pending_phone_prize(user_id, conn_ext=conn_to_use)
    if not remove_pending_success:
         logger.error(f"_auto_sell_expired_prize: Не удалось удалить pending prize для user {user_id} из БД.")
         # Не прерываем, но логируем.

    # Уведомление пользователя
    user_full_name_for_msg = user_db_data_for_log.get('full_name') or f"User ID {user_id}"
    user_username_for_msg = user_db_data_for_log.get('username')
    user_mention_msg = get_user_mention_html(user_id, user_full_name_for_msg, user_username_for_msg)

    # Определяем чат для отправки уведомления. Предпочитаем оригинальный чат рулетки, если бот там есть и не заблокирован.
    # Если нет, отправляем в личный чат.
    target_notification_chat_id = original_roulette_chat_id
    try:
        # Пробуем получить информацию о чате, чтобы убедиться, что он существует и бот там может писать
        chat_info = await bot_instance.get_chat(original_roulette_chat_id)
        if chat_info.type == 'private' and original_roulette_chat_id != user_id:
             # Если это приватный чат не с самим собой, возможно, лучше отправить в ЛС пользователя.
             # Но по умолчанию отправим туда, где выиграл.
             pass # Отправляем в original_roulette_chat_id
        elif chat_info.type != 'private' and not chat_info.permissions.can_send_messages:
             # Если это группа/канал и бот не может писать, отправляем в ЛС пользователя
             target_notification_chat_id = user_id
             logger.warning(f"_auto_sell_expired_prize: User {user_id} original chat {original_roulette_chat_id} is not private and bot cannot send messages. Notifying in private chat {user_id}.")
        elif chat_info.type == 'private' and original_roulette_chat_id == user_id:
             # Если original_roulette_chat_id == user_id, то это уже личный чат
             pass
    except Exception as e_get_chat:
        logger.warning(f"_auto_sell_expired_prize: Failed to get chat info for {original_roulette_chat_id} (user {user_id}). Assuming private chat {user_id} for notification. Error: {e_get_chat}")
        target_notification_chat_id = user_id # Если не можем получить инфо о чате, пробуем ЛС

    try:
        await bot_instance.send_message(
            target_notification_chat_id,
            f"⏰ {user_mention_msg}, время на принятие решения по выигранному телефону истекло.\n"
            f"Телефон \"<b>{won_phone_name_display}</b>\" ({won_phone_color}) был автоматически продан за {sell_value} OneCoin(s).\n"
            f"Ваш баланс: {new_balance} OC.",
            parse_mode="HTML"
        )
    except Exception as e_notify:
         logger.error(f"_auto_sell_expired_prize: Не удалось уведомить user {user_id} в чате {target_notification_chat_id} об автопродаже приза: {e_notify}")


    # Лог
    log_chat_title = "N/A"
    try:
        # Пытаемся получить название чата, где телефон был выигран, для лога
        chat_info_log = await bot_instance.get_chat(original_roulette_chat_id)
        log_chat_title = html.escape(chat_info_log.title or f"ChatID {original_roulette_chat_id}")
    except Exception:
        pass # Если не удалось получить инфо о чате, используем дефолт


    await send_telegram_log(bot_instance,
        f"⏳ Автопродажа приза: У {user_mention_msg} истекло время на решение. Выигранный телефон "
        f"(\"{won_phone_name_display}\", {won_phone_color}) автоматически продан за {sell_value} OC. "
        f"Выигрыш в чате \"{log_chat_title}\" ({original_roulette_chat_id}). Баланс: {new_balance} OC."
    )

# =============================================================================
# Функция для регистрации обработчиков этого роутера в основном диспетчере
# =============================================================================
def setup_phone_handlers(dp: Router):
    """Регистрирует обработчики команд, связанных с телефонами."""
    dp.include_router(phone_router)
    logger.info("Обработчики команд для телефонов зарегистрированы.")
