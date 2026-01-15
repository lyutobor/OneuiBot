# business_logic.py
import html
import random
import asyncio
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Optional, List, Dict, Any, Tuple
from pytz import timezone
from achievements_logic import check_and_grant_achievements 

from aiogram import Router, Bot, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery # CallbackQuery понадобится для интерактивных кнопок

# Импорты из твоих файлов
from config import Config
import database
from business_data import BUSINESS_DATA, BUSINESS_UPGRADES, BANK_DATA, BUSINESS_EVENTS # Новые данные
from utils import get_user_mention_html, send_telegram_log, fetch_user_display_data

import logging

logger = logging.getLogger(__name__)

# --- Роутер для бизнес-команд ---
business_router = Router()

# --- Вспомогательные функции (могут быть и в utils.py, но пока оставим здесь для наглядности) ---

async def _get_user_info_for_db(user_id: int, chat_id: int) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Получает username, full_name пользователя и chat_title для записи в БД."""
    conn = None
    try:
        conn = await database.get_connection()
        user_data_from_db = await database.get_user_data_for_update(user_id, chat_id, conn_ext=conn)
        username = user_data_from_db.get('username')
        full_name = user_data_from_db.get('full_name')
        chat_title = user_data_from_db.get('chat_title')
        return username, full_name, chat_title
    except Exception as e:
        logger.error(f"Error fetching user/chat info for DB for user {user_id} chat {chat_id}: {e}", exc_info=True)
        return None, None, None # Возвращаем None, если произошла ошибка
    finally:
        if conn and not conn.is_closed():
            await conn.close()

def _get_business_index(business_key: str) -> int:
    """Возвращает порядковый номер бизнеса (от 1 до 18) по его ключу."""
    business_keys_list = list(BUSINESS_DATA.keys())
    try:
        return business_keys_list.index(business_key) + 1
    except ValueError:
        logger.warning(f"Business key '{business_key}' not found in BUSINESS_DATA. Returning -1.")
        return -1

def _calculate_staff_income_percentage(business_index: int) -> float:
    """
    Рассчитывает процент дохода, который приносит один сотрудник,
    в зависимости от порядкового номера бизнеса.
    Для 1-го бизнеса: Config.BUSINESS_STAFF_INCOME_MAX_BOOST_PERCENT (например, 20%)
    Для 18-го бизнеса: Config.BUSINESS_STAFF_INCOME_MIN_BOOST_PERCENT (например, 1%)
    Линейное уменьшение для промежуточных бизнесов.
    """
    if business_index < 1 or business_index > 18:
        # Это не должно произойти, если _get_business_index работает корректно
        return Config.BUSINESS_STAFF_INCOME_MAX_BOOST_PERCENT

    if business_index == 1:
        return Config.BUSINESS_STAFF_INCOME_MAX_BOOST_PERCENT
    if business_index == 18:
        return Config.BUSINESS_STAFF_INCOME_MIN_BOOST_PERCENT

    # Формула для линейного уменьшения
    # current_index = business_index - 1 (для диапазона 0-17)
    # max_index = 17 (для 18 бизнесов)
    # slope = (min_pct - max_pct) / max_index
    # percentage = max_pct + current_index * slope

    max_pct = Config.BUSINESS_STAFF_INCOME_MAX_BOOST_PERCENT
    min_pct = Config.BUSINESS_STAFF_INCOME_MIN_BOOST_PERCENT
    num_businesses = len(BUSINESS_DATA) # Общее количество бизнесов
    
    # Расчет для N бизнесов, где 1-й имеет MAX, последний MIN
    # Формула: MAX_BOOST - (индекс_бизнеса_от_0) * (разница / (кол-во_бизнесов - 1))
    # business_index от 1 до 18, приводим к 0-17
    adjusted_index = business_index - 1 
    
    if num_businesses > 1: # Избегаем деления на ноль, если бизнесов 1
        percentage_per_staff = max_pct - adjusted_index * \
                                ((max_pct - min_pct) / (num_businesses - 1))
    else: # Если только один бизнес
        percentage_per_staff = max_pct
        
    return max(min_pct, percentage_per_staff) # Убедимся, что не опустится ниже минимального
    
    
@business_router.message(Command("buybusiness", "купитьбизнес", "построитьбизнес", ignore_case=True))
async def buy_business_command(message: Message, command: CommandObject, bot: Bot):
    if not message.from_user:
        await message.reply("Не могу определить пользователя.")
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    user_full_name = message.from_user.full_name
    user_username = message.from_user.username
    user_link = get_user_mention_html(user_id, user_full_name, user_username)

    if not command.args:
        await message.reply(
            f"{user_link}, чтобы купить бизнес, укажи его ID (ключ). Например: <code>/buybusiness business_1_home_samsung_region_change</code>\n\n"
            "Список доступных бизнесов: <code>/businessshop</code>"
        )
        return

    business_key = command.args.strip()
    business_info = BUSINESS_DATA.get(business_key)

    if not business_info:
        await message.reply(f"{user_link}, бизнес с ключом <code>{html.escape(business_key)}</code> не найден. Проверьте <code>/businessshop</code>.")
        return

    # Получаем информацию о чате для записи в БД
    chat_title_for_db = message.chat.title
    if message.chat.type == "private":
        chat_title_for_db = f"Личный чат ({chat_id})"

    current_user_chat_lock = await database.get_user_chat_lock(user_id, chat_id)
    async with current_user_chat_lock:
        try:
            # 1. Проверяем, сколько бизнесов уже есть у пользователя в этом чате
            user_businesses_in_chat = await database.get_user_businesses(user_id, chat_id)
            if len(user_businesses_in_chat) >= Config.BUSINESS_MAX_PER_USER_PER_CHAT:
                await message.reply(f"{user_link}, вы уже достигли лимита в {Config.BUSINESS_MAX_PER_USER_PER_CHAT} бизнесов в этом чате. Вы не можете купить новый бизнес здесь.")
                return

            # 2. Проверяем, есть ли уже такой бизнес у пользователя в этом чате
            for biz in user_businesses_in_chat:
                if biz['business_key'] == business_key:
                    await message.reply(f"{user_link}, у вас уже есть бизнес <b>{html.escape(business_info['name'])}</b> в этом чате. Вы можете его улучшить или продать.")
                    return
            
            # --- НОВАЯ ЛОГИКА: Прогрессивное открытие бизнесов ---
            # Определяем порядковый номер покупаемого бизнеса
            target_business_index = _get_business_index(business_key)

            if target_business_index == -1: # Это уже должно было быть отловлено выше, но на всякий случай
                await message.reply(f"{user_link}, произошла ошибка при определении номера бизнеса. Попробуйте другой ключ.")
                return

            if target_business_index > 1: # Если это не первый бизнес, проверяем предыдущий
                # Находим ключ предыдущего бизнеса
                previous_business_key = list(BUSINESS_DATA.keys())[target_business_index - 2] # -2 потому что index() возвращает 0-based, а мы хотим N-1 бизнес
                
                # Проверяем, куплен ли предыдущий бизнес
                previous_business_owned = False
                for biz in user_businesses_in_chat:
                    if biz['business_key'] == previous_business_key:
                        previous_business_owned = True
                        break
                
                if not previous_business_owned:
                    previous_business_name = BUSINESS_DATA.get(previous_business_key, {}).get('name', f"Бизнес #{target_business_index - 1}")
                    await message.reply(
                        f"{user_link}, чтобы купить бизнес <b>{html.escape(business_info['name'])}</b>, "
                        f"вы должны сначала приобрести предыдущий бизнес: <b>{html.escape(previous_business_name)}</b>."
                    )
                    return
            # --- КОНЕЦ НОВОЙ ЛОГИКИ: Прогрессивное открытие бизнесов ---


            # 3. Получаем стоимость бизнеса (уровень 0)
            business_level_0_info = business_info['levels'].get(0)
            if not business_level_0_info:
                await message.reply(f"Ошибка конфигурации для бизнеса <code>{html.escape(business_key)}</code>: нет данных для уровня 0.")
                await send_telegram_log(bot, f"🔴 Ошибка конфига: Бизнес {business_key} не имеет уровня 0. User: {user_id}")
                return

            purchase_price = business_level_0_info['price']
            business_display_name = business_level_0_info['display_name']

            # 4. Проверяем баланс игрока
            user_balance = await database.get_user_onecoins(user_id, chat_id)
            if user_balance < purchase_price:
                await message.reply(f"{user_link}, у вас недостаточно OneCoin для покупки <b>{html.escape(business_display_name)}</b> (требуется {purchase_price:,} OneCoin, у вас {user_balance:,}).")
                return

            # 5. Проводим транзакцию (списываем деньги и добавляем бизнес)
            new_balance = await database.update_user_onecoins(user_id, chat_id, -purchase_price,
                                                            username=user_username, full_name=user_full_name, chat_title=chat_title_for_db)
            if new_balance is None or new_balance < 0: # Проверка на случай ошибки обновления баланса
                await message.reply(f"Произошла ошибка при списании OneCoin. Покупка не удалась. Ваш баланс: {user_balance:,}.")
                await send_telegram_log(bot, f"🔴 Ошибка списания: User {user_id}, chat {chat_id}, -{purchase_price} OneCoin. Balance was {user_balance}, now {new_balance}. Business {business_key}")
                return

            # Получаем актуальные user_info для записи в новую таблицу (включая username, full_name, chat_title)
            # В данном случае, мы уже имеем их из message.from_user, но для консистентности и будущих update_user_business_info
            # лучше использовать ту же логику, что в get_user_data_for_update, но тут мы просто их передадим.
            actual_username = user_username
            actual_full_name = user_full_name
            actual_chat_title = chat_title_for_db

            # Добавляем бизнес в БД
            new_business_id = await database.add_user_business(
                user_id, chat_id, actual_username, actual_full_name, actual_chat_title,
                business_key,
                purchase_price # Сохраняем цену покупки для будущих расчетов (например, продажи)
            )

            if new_business_id:
                # >>> НАЧАЛО ИЗМЕНЕНИЙ <<<
                # Гарантируем существование банка 0-го уровня
                await database.create_or_update_user_bank( #
                    user_id,
                    chat_id,
                    actual_username,
                    actual_full_name,
                    actual_chat_title,
                    current_balance_change=0, # Не меняем баланс банка, только обеспечиваем его наличие
                    new_bank_level=0 # Создаем банк 0-го уровня, если его нет
                )
                logger.info(f"Ensured bank (level 0) exists for user {user_id} in chat {chat_id} after business purchase.")
                # >>> КОНЕЦ ИЗМЕНЕНИЙ <<<

                await message.reply(
                    f"🎉 Поздравляю, {user_link}! Вы успешно приобрели бизнес <b>{html.escape(business_display_name)}</b> "
                    f"за <code>{purchase_price:,}</code> OneCoin. Ваш новый баланс: <code>{new_balance:,}</code> OneCoin.\n"
                    f"ID вашего нового бизнеса: <code>{new_business_id}</code>. Он уже начал приносить доход (ваш банк готов к поступлениям)!"
                )
                logger.info(f"User {user_id} bought business {business_key} (ID: {new_business_id}) in chat {chat_id} for {purchase_price} OneCoin.")
                await send_telegram_log(bot,
                    f"💰 Новый бизнес: {user_link} купил <b>{html.escape(business_display_name)}</b> "
                    f"(ID: <code>{new_business_id}</code>) в чате <b>{html.escape(chat_title_for_db)}</b> "
                    f"за <code>{purchase_price:,}</code> OC."
                )
                # --- ВЫЗОВ ПРОВЕРКИ ДОСТИЖЕНИЙ ---
                await check_and_grant_achievements(
                    user_id,
                    chat_id, # chat_id из сообщения
                    bot,
                    business_bought_just_now=True, # Для "Зерно Империи"
                    business_key_bought=business_key, # Для проверки "Коллекционер Активов"
                    business_chat_id=chat_id # Для проверки "Строитель Влияния"
                )
                # --- КОНЕЦ ВЫЗОВА ПРОВЕРКИ ДОСТИЖЕНИЙ ---
            else:
                # Если добавление бизнеса в БД не удалось, пытаемся вернуть деньги
                await database.update_user_onecoins(user_id, chat_id, purchase_price,
                                                    username=user_username, full_name=user_full_name, chat_title=chat_title_for_db)
                await message.reply(f"Произошла ошибка при регистрации бизнеса. Средства были возвращены. Пожалуйста, попробуйте еще раз.")
                await send_telegram_log(bot, f"🔴 Ошибка регистрации бизнеса: User {user_id} chat {chat_id}. Бизнес {business_key}. Возвращены средства. Причина: Ошибка add_user_business.")

        except Exception as e:
            logger.error(f"Error in /buybusiness for user {user_id} in chat {chat_id}: {e}", exc_info=True)
            await message.reply("Произошла внутренняя ошибка при покупке бизнеса. Попробуйте позже.")
            await send_telegram_log(bot, f"🔴 <b>Ошибка /buybusiness</b>\nUser: {user_link} ({user_id})\nChat: {html.escape(chat_title_for_db or str(chat_id))} ({chat_id})\nErr: <pre>{html.escape(str(e))}</pre>")


@business_router.message(Command("businessshop", "магазинбизнесов", "списокбизнесов", "бизнесы", ignore_case=True))
async def business_shop_command(message: Message):
    if not message.from_user:
        await message.reply("Не могу определить пользователя.")
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    user_link = get_user_mention_html(user_id, message.from_user.full_name, message.from_user.username)

    user_businesses = await database.get_user_businesses(user_id, chat_id)
    owned_business_keys = {biz['business_key'] for biz in user_businesses}

    all_business_keys_ordered = list(BUSINESS_DATA.keys())
    
    response_lines = [f"<b>🏢 {user_link}, доступные бизнесы для покупки:</b>\n"]
    
    # Определяем индекс последнего купленного бизнеса (или -1, если бизнесов нет)
    last_owned_business_index = -1
    if owned_business_keys:
        for i, key in enumerate(all_business_keys_ordered):
            if key in owned_business_keys:
                last_owned_business_index = i
    
    # --- НОВАЯ ЛОГИКА ОТОБРАЖЕНИЯ ---

    # Если бизнесов нет вообще, показываем первые N бизнесов
    if last_owned_business_index == -1:
        # Показываем первые 3 бизнеса
        num_to_display = min(3, len(all_business_keys_ordered))
        response_lines.append("<b>➡️ Ваши первые шаги:</b>")
        for i in range(num_to_display):
            biz_key = all_business_keys_ordered[i]
            biz_info = BUSINESS_DATA.get(biz_key) # <<-- Вот здесь мы инициализируем biz_info
            if biz_info and biz_info['levels'].get(0):
                response_lines.append(f"  <b>{_get_business_index(biz_key)}. {html.escape(biz_info['levels'][0]['display_name'])}</b>")
                response_lines.append(f"    💰 Цена: <code>{biz_info['levels'][0]['price']:,}</code> OneCoin")
                response_lines.append(f"    📈 Базовый доход (Ур.0): <code>{biz_info['levels'][0]['base_income_per_hour']:,}</code> OC/час")
                response_lines.append(f"    🔑 Ключ: <code>{html.escape(biz_key)}</code>")
                # Добавляем описание здесь:
                response_lines.append(f"    <i>{html.escape(biz_info['description'].split('.')[0])}.</i>")
                response_lines.append("")
            else:
                logger.warning(f"Business {biz_key} has no level 0 data. Skipping from initial display.")
        
    else: # У пользователя есть хотя бы один бизнес
        # Показываем последний купленный бизнес
        last_owned_key = all_business_keys_ordered[last_owned_business_index]
        last_owned_info = BUSINESS_DATA.get(last_owned_key)
        if last_owned_info and last_owned_info['levels'].get(0):
            response_lines.append(f"<b>✅ Ваш текущий бизнес:</b>")
            response_lines.append(f"  <b>{_get_business_index(last_owned_key)}. {html.escape(last_owned_info['levels'][0]['display_name'])}</b> (Куплен)")
            response_lines.append("")

        # Определяем, какой бизнес следующий доступен для покупки (сразу после последнего купленного)
        next_available_business_index = last_owned_business_index + 1

        # Показываем "Следующий доступный" бизнес
        if next_available_business_index < len(all_business_keys_ordered):
            next_biz_key = all_business_keys_ordered[next_available_business_index]
            next_biz_info = BUSINESS_DATA.get(next_biz_key)
            if next_biz_info and next_biz_info['levels'].get(0):
                response_lines.append(f"<b>➡️ Следующий доступный:</b>")
                response_lines.append(f"  <b>{_get_business_index(next_biz_key)}. {html.escape(next_biz_info['levels'][0]['display_name'])}</b>")
                response_lines.append(f"  💰 Цена: <code>{next_biz_info['levels'][0]['price']:,}</code> OneCoin")
                response_lines.append(f"  📈 Базовый доход (Ур.0): <code>{next_biz_info['levels'][0]['base_income_per_hour']:,}</code> OC/час")
                response_lines.append(f"  🔑 Ключ: <code>{html.escape(next_biz_key)}</code>")
                # Добавляем описание здесь:
                response_lines.append(f"  <i>{html.escape(next_biz_info['description'].split('.')[0])}.</i>")
                response_lines.append("")
            else:
                logger.warning(f"Business {next_biz_key} has no level 0 data. Skipping from next available display.")
            
            # Показываем следующие 2 потенциальных бизнеса после "следующего доступного"
            response_lines.append(f"<b>🔮 Предстоящие бизнесы:</b>")
            potential_start_index = next_available_business_index + 1
            # Показываем до 2 бизнесов после next_available_business_index
            potential_end_index = min(potential_start_index + 1, len(all_business_keys_ordered))

            if potential_start_index >= potential_end_index: # Если больше нет предстоящих бизнесов
                 if next_available_business_index == len(all_business_keys_ordered):
                      response_lines.append(f"  Все бизнесы куплены. Поздравляю!")
                 else:
                      response_lines.append(f"  Пока нет данных о следующих бизнесах.")
            else:
                for i in range(potential_start_index, potential_end_index):
                    potential_biz_key = all_business_keys_ordered[i]
                    potential_biz_info = BUSINESS_DATA.get(potential_biz_key) # <<-- И здесь тоже
                    if potential_biz_info and potential_biz_info['levels'].get(0):
                        response_lines.append(f"  <b>{_get_business_index(potential_biz_key)}. {html.escape(potential_biz_info['levels'][0]['display_name'])}</b>")
                        response_lines.append(f"    💰 Цена: <code>{potential_biz_info['levels'][0]['price']:,}</code> OC (Ур.0)")
                        response_lines.append(f"    📈 Баз. доход: <code>{potential_biz_info['levels'][0]['base_income_per_hour']:,}</code> OC/час")
                        response_lines.append(f"    🔑 Ключ: <code>{html.escape(potential_biz_key)}</code>")
                        response_lines.append(f"    <i>{html.escape(potential_biz_info['description'].split('.')[0])}.</i>")
                        response_lines.append("")
                    else:
                        logger.warning(f"Business {potential_biz_key} has no level 0 data. Skipping from potential display.")
        else: # Если все бизнесы уже куплены
            response_lines.append(f"<b>🎉 Поздравляю, вы купили все доступные бизнесы!</b>")
            response_lines.append("")

    # --- КОНЕЦ НОВОЙ ЛОГИКИ ОТОБРАЖЕНИЯ ---

    response_lines.append(f"Используйте: <code>/buybusiness</code> <u>ключ_бизнеса</u>")
    response_lines.append(f"Пример: <code>/buybusiness</code> <u>business_1_home_samsung_region_change</u>")

    await message.reply("\n".join(response_lines), parse_mode="HTML", disable_web_page_preview=True)

# Список команд-триггеров (и с слэшем, и без)
MY_BUSINESSES_TRIGGERS = {
    "mybusinesses", "моибизнесы", 
    "мойбизнес", "бизнесстатус", 
    "бизнесы", "биз", "biz", "mybiz", 
    "businesses", "bstatus", 
    "моиактивы", "активы", "assets",
    "империя", "empire",
    "предприятия", "моипредприятия",
    "statbiz", "статбиз"
}

@business_router.message(Command(*MY_BUSINESSES_TRIGGERS, ignore_case=True))
@business_router.message(F.text.lower().in_(MY_BUSINESSES_TRIGGERS))
async def my_businesses_command(message: Message, bot: Bot):
    # Дальше код функции остается без изменений...
    if not message.from_user:
        await message.reply("Не могу определить пользователя.")
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    user_full_name = message.from_user.full_name
    user_username = message.from_user.username
    user_link = get_user_mention_html(user_id, user_full_name, user_username)

    try:
        user_businesses = await database.get_user_businesses(user_id, chat_id)

        if not user_businesses:
            await message.reply(
                f"{user_link}, у вас пока нет бизнесов в этом чате. Чтобы купить, используйте <code>/businessshop</code>."
            )
            return

        response_lines = [f"<b>🏢 {user_link}, ваши бизнесы в этом чате ({html.escape(message.chat.title or str(chat_id))}):</b>\n"]

        for biz in user_businesses:
            business_id = biz['business_id']
            business_key = biz['business_key']
            current_level = biz['current_level']
            staff_hired_slots = biz['staff_hired_slots']
            name_override = biz['name_override']

            business_info_static = BUSINESS_DATA.get(business_key)
            if not business_info_static:
                logger.warning(f"Static data for business key {business_key} not found. Skipping display for business ID {business_id}.")
                continue

            level_info = business_info_static['levels'].get(current_level)
            if not level_info:
                logger.warning(f"Level {current_level} data for business key {business_key} not found. Skipping display for business ID {business_id}.")
                continue

            display_name = name_override or level_info['display_name']
            base_income_per_hour = level_info['base_income_per_hour']
            max_staff_slots = level_info['max_staff_slots']

            # Рассчитываем доход от сотрудников
            business_index = _get_business_index(business_key)
            staff_income_percentage_per_unit = _calculate_staff_income_percentage(business_index)
            
            # Общий бонус к доходу от сотрудников
            staff_income_bonus = staff_hired_slots * (base_income_per_hour * staff_income_percentage_per_unit)
            
            # Общий базовый доход (без учета событий)
            total_base_income_per_hour = base_income_per_hour + staff_income_bonus
            daily_income_before_tax = int(total_base_income_per_hour * 24) # Умножаем на 24 часа

            response_lines.append(f"<b>ID: <code>{business_id}</code> - {html.escape(display_name)}</b>")
            response_lines.append(f"  Уровень: <code>{current_level}</code>")
            response_lines.append(f"  Доход: <code>{int(total_base_income_per_hour)}</code> OC/час (<code>{daily_income_before_tax}</code> OC/день)")
            response_lines.append(f"  Сотрудники: <code>{staff_hired_slots}</code> / <code>{max_staff_slots}</code> "
                                  f"(+{staff_income_percentage_per_unit * 100:.0f}% за ед.)")
            
            # Отображение апгрейдов
            upgrades = await database.get_business_upgrades(business_id, user_id)
            if upgrades:
                upgrade_names = [BUSINESS_UPGRADES.get(upg['upgrade_key'], {}).get('name', upg['upgrade_key']) for upg in upgrades]
                response_lines.append(f"  Улучшения: {', '.join([html.escape(name) for name in upgrade_names])}")
            else:
                response_lines.append(f"  Улучшения: нет")
            
            # Время последнего начисления
            last_calc_utc = biz['last_income_calculation_utc']
            local_tz = timezone(Config.TIMEZONE)
            last_calc_local = last_calc_utc.astimezone(local_tz)
            response_lines.append(f"  Начислено: {last_calc_local.strftime('%d.%m.%Y %H:%M %Z')}")

            response_lines.append("") # Пустая строка для разделения бизнесов

        await message.reply("\n".join(response_lines), parse_mode="HTML", disable_web_page_preview=True)

    except Exception as e:
        logger.error(f"Error in /mybusinesses for user {user_id} in chat {chat_id}: {e}", exc_info=True)
        await message.reply("Произошла внутренняя ошибка при получении списка ваших бизнесов. Попробуйте позже.")
        await send_telegram_log(bot, f"🔴 <b>Ошибка /mybusinesses</b>\nUser: {user_link} ({user_id})\nChat: {html.escape(message.chat.title or str(chat_id))} ({chat_id})\nErr: <pre>{html.escape(str(e))}</pre>")    
        
@business_router.message(Command("mybank", "мойбанк", "банк", "счет", ignore_case=True))
async def my_bank_command(message: Message, bot: Bot):
    if not message.from_user:
        await message.reply("Не могу определить пользователя.")
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    user_full_name = message.from_user.full_name
    user_username = message.from_user.username
    user_link = get_user_mention_html(user_id, user_full_name, user_username)

    try:
        user_bank_data = await database.get_user_bank(user_id, chat_id)
        
        current_level = user_bank_data['bank_level'] if user_bank_data else 0
        current_balance = user_bank_data['current_balance'] if user_bank_data else 0

        bank_info_static = BANK_DATA.get(current_level)
        if not bank_info_static:
            # Если уровень 0 или какой-то некорректный, берем данные по умолчанию
            bank_info_static = {"name": "Неизвестный Банк", "max_capacity": 0} 
            if current_level == 0:
                 bank_info_static = BANK_DATA.get(0, {"name": "Начальная копилка", "max_capacity": 1000})


        bank_name = bank_info_static['name']
        max_capacity = bank_info_static['max_capacity']

        response_lines = [f"<b>🏦 {user_link}, ваш банк в чате \"{html.escape(message.chat.title or str(chat_id))}\":</b>"]
        response_lines.append(f"  Название: <b>{html.escape(bank_name)}</b>")
        response_lines.append(f"  Уровень: <code>{current_level}</code>")
        response_lines.append(f"  Баланс: <code>{current_balance:,}</code> OneCoin")
        response_lines.append(f"  Вместимость: <code>{max_capacity:,}</code> OneCoin")

        if max_capacity > 0:
            fill_percentage = (current_balance / max_capacity) * 100
            response_lines.append(f"  Заполнено: <code>{fill_percentage:.2f}%</code>")

        # Информация о следующем уровне
        next_level_info = BANK_DATA.get(current_level + 1)
        if next_level_info:
            response_lines.append(f"\nСледующий уровень (<b>{next_level_info['name']}</b> Ур.<code>{current_level + 1}</code>):")
            response_lines.append(f"  Вместимость: <code>{next_level_info['max_capacity']:,}</code> OneCoin")
            response_lines.append(f"  Стоимость улучшения: <code>{next_level_info['price']:,}</code> OneCoin")
            response_lines.append(f"  Используйте: <code>/upgradebank</code>")
        else:
            response_lines.append("\n🎉 Ваш банк достиг максимального уровня!")

        response_lines.append(f"\nЧтобы вывести средства: <code>/withdrawbank all</code>")
        
        await message.reply("\n".join(response_lines), parse_mode="HTML", disable_web_page_preview=True)

    except Exception as e:
        logger.error(f"Error in /mybank for user {user_id} in chat {chat_id}: {e}", exc_info=True)
        await message.reply("Произошла внутренняя ошибка при получении информации о вашем банке. Попробуйте позже.")
        await send_telegram_log(bot, f"🔴 <b>Ошибка /mybank</b>\nUser: {user_link} ({user_id})\nChat: {html.escape(message.chat.title or str(chat_id))} ({chat_id})\nErr: <pre>{html.escape(str(e))}</pre>")


@business_router.message(Command("upgradebank", "улучшитьбанк", "прокачатьбанк", ignore_case=True))
async def upgrade_bank_command(message: Message, bot: Bot):
    if not message.from_user:
        await message.reply("Не могу определить пользователя.")
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    user_full_name = message.from_user.full_name
    user_username = message.from_user.username
    user_link = get_user_mention_html(user_id, user_full_name, user_username)

    current_user_chat_lock = await database.get_user_chat_lock(user_id, chat_id)
    async with current_user_chat_lock:
        try:
            user_bank_data = await database.get_user_bank(user_id, chat_id)
            current_level = user_bank_data['bank_level'] if user_bank_data else 0
            user_onecoins_balance = await database.get_user_onecoins(user_id, chat_id)

            next_level = current_level + 1
            next_level_info = BANK_DATA.get(next_level)

            if not next_level_info:
                await message.reply(f"{user_link}, ваш банк уже достиг максимального уровня (<code>{current_level}</code>). Дальнейшие улучшения недоступны.")
                return

            upgrade_cost = next_level_info['price']
            next_level_name = next_level_info['name']

            if user_onecoins_balance < upgrade_cost:
                await message.reply(f"{user_link}, у вас недостаточно OneCoin для улучшения банка до уровня <code>{next_level}</code> (требуется <code>{upgrade_cost:,}</code> OC, у вас <code>{user_onecoins_balance:,}</code> OC).")
                return

            # Проводим транзакцию
            new_user_onecoins_balance = await database.update_user_onecoins(user_id, chat_id, -upgrade_cost,
                                                                          username=user_username, full_name=user_full_name, chat_title=message.chat.title)
            if new_user_onecoins_balance is None or new_user_onecoins_balance < 0:
                 await message.reply(f"Произошла ошибка при списании OneCoin. Улучшение не удалось. Ваш баланс: {user_onecoins_balance}.")
                 await send_telegram_log(bot, f"🔴 Ошибка списания (upgradebank): User {user_id}, chat {chat_id}, -{upgrade_cost} OneCoin. Balance was {user_onecoins_balance}, now {new_user_onecoins_balance}.")
                 return

            # Обновляем уровень банка (создаем, если не было, или повышаем)
            updated_bank_data = await database.create_or_update_user_bank(
                user_id, chat_id, user_username, user_full_name, message.chat.title,
                current_balance_change=0, # Только уровень, баланс не меняем здесь
                new_bank_level=next_level
            )

            if updated_bank_data:
                await message.reply(
                    f"🎉 Поздравляю, {user_link}! Ваш банк успешно улучшен до уровня <b>{next_level} - \"{html.escape(next_level_name)}\"</b>!\n"
                    f"Новая вместимость: <code>{next_level_info['max_capacity']:,}</code> OneCoin.\n"
                    f"Ваш баланс: <code>{new_user_onecoins_balance:,}</code> OneCoin."
                )
                logger.info(f"User {user_id} upgraded bank to level {next_level} in chat {chat_id}.")
                await send_telegram_log(bot,
                    f"🏦 Улучшение банка: {user_link} улучшил банк до <b>Ур.{next_level} ({html.escape(next_level_name)})</b> "
                    f"в чате <b>{html.escape(message.chat.title or str(chat_id))}</b> за <code>{upgrade_cost:,}</code> OC."
                )
                
                # --- ВЫЗОВ ПРОВЕРКИ ДОСТИЖЕНИЙ ---
                await check_and_grant_achievements(
                    user_id,
                    chat_id,
                    bot,
                    bank_upgraded_to_level=next_level # Передаем новый уровень банка
                )
                # --- КОНЕЦ ВЫЗОВА ПРОВЕРКИ ДОСТИЖЕНИЙ ---
                
            else:
                # Если обновление банка не удалось, пытаемся вернуть деньги
                await database.update_user_onecoins(user_id, chat_id, upgrade_cost,
                                                    username=user_username, full_name=user_full_name, chat_title=message.chat.title)
                await message.reply(f"Произошла ошибка при улучшении банка. Средства были возвращены. Пожалуйста, попробуйте еще раз.")
                await send_telegram_log(bot, f"🔴 Ошибка улучшения банка: User {user_id} chat {chat_id}. Возвращены средства. Причина: Ошибка create_or_update_user_bank.")

        except Exception as e:
            logger.error(f"Error in /upgradebank for user {user_id} in chat {chat_id}: {e}", exc_info=True)
            await message.reply("Произошла внутренняя ошибка при улучшении банка. Попробуйте позже.")
            await send_telegram_log(bot, f"🔴 <b>Ошибка /upgradebank</b>\nUser: {user_link} ({user_id})\nChat: {html.escape(message.chat.title or str(chat_id))} ({chat_id})\nErr: <pre>{html.escape(str(e))}</pre>")


@business_router.message(Command("withdrawbank", "снятьсбанка", "вывести", "снять", ignore_case=True))
async def withdraw_bank_command(message: Message, command: CommandObject, bot: Bot):
    if not message.from_user:
        await message.reply("Не могу определить пользователя.")
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    user_full_name = message.from_user.full_name
    user_username = message.from_user.username
    user_link = get_user_mention_html(user_id, user_full_name, user_username)

    current_user_chat_lock = await database.get_user_chat_lock(user_id, chat_id)
    async with current_user_chat_lock:
        try:
            user_bank_data = await database.get_user_bank(user_id, chat_id)
            
            if not user_bank_data or user_bank_data['current_balance'] == 0:
                await message.reply(f"{user_link}, ваш банк в этом чате пуст. Выводить нечего.")
                return

            amount_str = command.args.strip() if command.args else None
            withdraw_amount = 0

            if not amount_str:
                await message.reply(f"{user_link}, укажите сумму для вывода или 'all', чтобы вывести все.\nПример: <code>/withdrawbank 1000</code> или <code>/withdrawbank all</code>.")
                return

            if amount_str.lower() == "all":
                withdraw_amount = user_bank_data['current_balance']
            else:
                try:
                    withdraw_amount = int(amount_str)
                    if withdraw_amount <= 0:
                        await message.reply(f"{user_link}, сумма для вывода должна быть положительной.")
                        return
                except ValueError:
                    await message.reply(f"{user_link}, укажите корректную сумму (число) или 'all'.")
                    return
            
            if withdraw_amount > user_bank_data['current_balance']:
                await message.reply(f"{user_link}, у вас в банке только <code>{user_bank_data['current_balance']:,}</code> OneCoin. Вы не можете вывести больше.")
                return

            # Обновляем баланс банка (уменьшаем)
            updated_bank_data = await database.create_or_update_user_bank(
                user_id, chat_id, user_username, user_full_name, message.chat.title,
                current_balance_change=-withdraw_amount,
                new_bank_level=None # Уровень не меняем
            )
            
            if not updated_bank_data:
                await message.reply(f"Произошла ошибка при обновлении баланса банка. Попробуйте еще раз.")
                await send_telegram_log(bot, f"🔴 Ошибка обновления банка (withdraw): User {user_id}, chat {chat_id}, -{withdraw_amount} OC. updated_bank_data is None.")
                return

            # Обновляем основной баланс OneCoin игрока (увеличиваем)
            new_user_onecoins_balance = await database.update_user_onecoins(user_id, chat_id, withdraw_amount,
                                                                          username=user_username, full_name=user_full_name, chat_title=message.chat.title)
            
            if new_user_onecoins_balance is None: # На случай ошибки при зачислении
                await message.reply(f"Произошла ошибка при зачислении средств на ваш основной баланс. Обратитесь к администратору.")
                await send_telegram_log(bot, f"🔴 КРИТИЧЕСКАЯ ОШИБКА (withdraw): User {user_id}, chat {chat_id}, +{withdraw_amount} OC. new_user_onecoins_balance is None.")
                return


            await message.reply(
                f"✅ {user_link}, вы успешно вывели <code>{withdraw_amount:,}</code> OneCoin из вашего банка в этом чате.\n"
                f"Баланс банка: <code>{updated_bank_data['current_balance']:,}</code> OneCoin.\n"
                f"Ваш основной баланс: <code>{new_user_onecoins_balance:,}</code> OneCoin."
            )
            logger.info(f"User {user_id} withdrew {withdraw_amount} OneCoin from bank in chat {chat_id}.")
            await send_telegram_log(bot,
                f"💸 Вывод из банка: {user_link} вывел <code>{withdraw_amount:,}</code> OC из банка "
                f"в чате <b>{html.escape(message.chat.title or str(chat_id))}</b>. "
                f"Банк: <code>{updated_bank_data['current_balance']:,}</code> OC."
            )

        except Exception as e:
            logger.error(f"Error in /withdrawbank for user {user_id} in chat {chat_id}: {e}", exc_info=True)
            await message.reply("Произошла внутренняя ошибка при выводе средств из банка. Попробуйте позже.")
            await send_telegram_log(bot, f"🔴 <b>Ошибка /withdrawbank</b>\nUser: {user_link} ({user_id})\nChat: {html.escape(message.chat.title or str(chat_id))} ({chat_id})\nErr: <pre>{html.escape(str(e))}</pre>")
            
            
@business_router.message(Command("hirestaff", "нанятьсотрудников", "нанять", "сотрудникинанять", ignore_case=True))
async def hire_staff_command(message: Message, command: CommandObject, bot: Bot):
    if not message.from_user:
        await message.reply("Не могу определить пользователя.")
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    user_full_name = message.from_user.full_name
    user_username = message.from_user.username
    user_link = get_user_mention_html(user_id, user_full_name, user_username)

    if not command.args:
        await message.reply(
            f"{user_link}, чтобы нанять сотрудников, укажите ID вашего бизнеса и количество сотрудников.\n"
            f"Пример: <code>/hirestaff [ID_бизнеса] [количество_сотрудников]</code>\n"
            f"Ваши бизнесы: <code>/mybusinesses</code>"
        )
        return

    args = command.args.split()
    if len(args) < 2:
        await message.reply(f"{user_link}, неверный формат. Укажите ID бизнеса и количество сотрудников. Пример: <code>/hirestaff 123 5</code>")
        return

    try:
        business_id = int(args[0])
        amount_to_hire = int(args[1])
        if amount_to_hire <= 0:
            await message.reply(f"{user_link}, количество нанимаемых сотрудников должно быть положительным числом.")
            return
    except ValueError:
        await message.reply(f"{user_link}, ID бизнеса и количество сотрудников должны быть числами.")
        return

    current_user_chat_lock = await database.get_user_chat_lock(user_id, chat_id)
    async with current_user_chat_lock:
        try:
            business = await database.get_user_business_by_id(business_id, user_id)
            if not business or business['chat_id'] != chat_id:
                await message.reply(f"{user_link}, бизнес с ID <code>{business_id}</code> не найден в этом чате или не принадлежит вам.")
                return

            business_static_info = BUSINESS_DATA.get(business['business_key'])
            if not business_static_info:
                await message.reply("Ошибка: Статические данные для этого бизнеса не найдены.")
                return

            level_info = business_static_info['levels'].get(business['current_level'])
            if not level_info:
                await message.reply(f"Ошибка: Данные для уровня {business['current_level']} бизнеса не найдены.")
                return

            max_staff_slots = level_info['max_staff_slots']
            current_staff = business['staff_hired_slots']

            if current_staff + amount_to_hire > max_staff_slots:
                await message.reply(
                    f"{user_link}, вы не можете нанять <code>{amount_to_hire}</code> сотрудников. "
                    f"В вашем бизнесе \"{html.escape(business['name_override'] or level_info['display_name'])}\" (ID: <code>{business_id}</code>) "
                    f"доступно только <code>{max_staff_slots - current_staff}</code> свободных слотов из <code>{max_staff_slots}</code>."
                )
                return

            purchase_price_for_staff = level_info.get('price') or level_info.get('upgrade_cost') # Цена бизнеса на текущем уровне
            cost_per_staff = int(purchase_price_for_staff * Config.BUSINESS_STAFF_COST_MULTIPLIER)
            total_cost = cost_per_staff * amount_to_hire

            user_onecoins_balance = await database.get_user_onecoins(user_id, chat_id)
            if user_onecoins_balance < total_cost:
                await message.reply(
                    f"{user_link}, у вас недостаточно OneCoin для найма <code>{amount_to_hire}</code> сотрудников "
                    f"(стоимость: <code>{total_cost:,}</code> OC, у вас: <code>{user_onecoins_balance:,}</code> OC). "
                    f"Стоимость 1 сотрудника: <code>{cost_per_staff:,}</code> OC."
                )
                return

            # Списываем деньги
            new_user_onecoins_balance = await database.update_user_onecoins(user_id, chat_id, -total_cost,
                                                                          username=user_username, full_name=user_full_name, chat_title=message.chat.title)
            if new_user_onecoins_balance is None or new_user_onecoins_balance < 0:
                 await message.reply(f"Произошла ошибка при списании OneCoin. Найм не удался. Ваш баланс: {user_onecoins_balance}.")
                 await send_telegram_log(bot, f"🔴 Ошибка списания (hirestaff): User {user_id}, chat {chat_id}, -{total_cost} OneCoin. Balance was {user_onecoins_balance}, now {new_user_onecoins_balance}.")
                 return

            # Обновляем количество сотрудников
            new_staff_count = current_staff + amount_to_hire
            success = await database.update_user_business(
                business_id, user_id, {'staff_hired_slots': new_staff_count}
            )

            if success:
                business_display_name = business['name_override'] or level_info['display_name']
                await message.reply(
                    f"✅ {user_link}, вы успешно наняли <code>{amount_to_hire}</code> сотрудников для бизнеса \"<b>{html.escape(business_display_name)}</b>\" (ID: <code>{business_id}</code>) за <code>{total_cost:,}</code> OneCoin!\n"
                    f"Всего сотрудников: <code>{new_staff_count}</code> / <code>{max_staff_slots}</code>.\n"
                    f"Ваш основной баланс: <code>{new_user_onecoins_balance:,}</code> OneCoin."
                )
                logger.info(f"User {user_id} hired {amount_to_hire} staff for business {business_id} in chat {chat_id}. New total: {new_staff_count}.")
                await send_telegram_log(bot,
                    f"👥 Найм сотрудников: {user_link} нанял <code>{amount_to_hire}</code> сотр. "
                    f"для бизнеса <b>{html.escape(business_display_name)}</b> (ID: <code>{business_id}</code>) "
                    f"в чате <b>{html.escape(message.chat.title or str(chat_id))}</b> за <code>{total_cost:,}</code> OC."
                )
                
                # --- ВЫЗОВ ПРОВЕРКИ ДОСТИЖЕНИЙ ---
                await check_and_grant_achievements(
                    user_id,
                    chat_id,
                    bot,
                    business_hired_max_staff_just_now=(new_staff_count == max_staff_slots), # Для "Мастер Легионов"
                    business_total_staff_hired_count=new_staff_count # Для "Провидец Подпольного Мира" (нужно будет получать суммарно со всех бизнесов)
                )
                # --- КОНЕЦ ВЫЗОВА ПРОВЕРКИ ДОСТИЖЕНИЙ ---
            else:
                # Если обновление бизнеса не удалось, пытаемся вернуть деньги
                await database.update_user_onecoins(user_id, chat_id, total_cost,
                                                    username=user_username, full_name=user_full_name, chat_title=message.chat.title)
                await message.reply(f"Произошла ошибка при найме сотрудников. Средства были возвращены. Пожалуйста, попробуйте еще раз.")
                await send_telegram_log(bot, f"🔴 Ошибка найма сотрудников: User {user_id} chat {chat_id}. Причина: Ошибка update_user_business.")

        except Exception as e:
            logger.error(f"Error in /hirestaff for user {user_id} in chat {chat_id}: {e}", exc_info=True)
            await message.reply("Произошла внутренняя ошибка при найме сотрудников. Попробуйте позже.")
            await send_telegram_log(bot, f"🔴 <b>Ошибка /hirestaff</b>\nUser: {user_link} ({user_id})\nChat: {html.escape(message.chat.title or str(chat_id))} ({chat_id})\nErr: <pre>{html.escape(str(e))}</pre>")


@business_router.message(Command("firestaff", "уволитьсотрудников", "уволить", ignore_case=True))
async def fire_staff_command(message: Message, command: CommandObject, bot: Bot):
    if not message.from_user:
        await message.reply("Не могу определить пользователя.")
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    user_full_name = message.from_user.full_name
    user_username = message.from_user.username
    user_link = get_user_mention_html(user_id, user_full_name, user_username)

    if not command.args:
        await message.reply(
            f"{user_link}, чтобы уволить сотрудников, укажите ID вашего бизнеса и количество сотрудников.\n"
            f"Пример: <code>/firestaff [ID_бизнеса] [количество_сотрудников]</code>\n"
            f"Ваши бизнесы: <code>/mybusinesses</code>"
        )
        return

    args = command.args.split()
    if len(args) < 2:
        await message.reply(f"{user_link}, неверный формат. Укажите ID бизнеса и количество сотрудников. Пример: <code>/firestaff 123 2</code>")
        return

    try:
        business_id = int(args[0])
        amount_to_fire = int(args[1])
        if amount_to_fire <= 0:
            await message.reply(f"{user_link}, количество увольняемых сотрудников должно быть положительным числом.")
            return
    except ValueError:
        await message.reply(f"{user_link}, ID бизнеса и количество сотрудников должны быть числами.")
        return

    current_user_chat_lock = await database.get_user_chat_lock(user_id, chat_id)
    async with current_user_chat_lock:
        try:
            business = await database.get_user_business_by_id(business_id, user_id)
            if not business or business['chat_id'] != chat_id:
                await message.reply(f"{user_link}, бизнес с ID <code>{business_id}</code> не найден в этом чате или не принадлежит вам.")
                return

            level_info = BUSINESS_DATA.get(business['business_key'], {}).get('levels', {}).get(business['current_level'])
            if not level_info:
                await message.reply(f"Ошибка: Данные для уровня {business['current_level']} бизнеса не найдены.")
                return

            current_staff = business['staff_hired_slots']

            if amount_to_fire > current_staff:
                await message.reply(
                    f"{user_link}, вы не можете уволить <code>{amount_to_fire}</code> сотрудников, "
                    f"так как у вас их всего <code>{current_staff}</code>."
                )
                return
            
            # Увольнение сотрудников не приносит денег обратно, это просто списание из штата
            new_staff_count = current_staff - amount_to_fire
            success = await database.update_user_business(
                business_id, user_id, {'staff_hired_slots': new_staff_count}
            )

            if success:
                business_display_name = business['name_override'] or level_info['display_name']
                await message.reply(
                    f"✅ {user_link}, вы успешно уволили <code>{amount_to_fire}</code> сотрудников из бизнеса \"<b>{html.escape(business_display_name)}</b>\" (ID: <code>{business_id}</code>).\n"
                    f"Осталось сотрудников: <code>{new_staff_count}</code>."
                )
                logger.info(f"User {user_id} fired {amount_to_fire} staff from business {business_id} in chat {chat_id}. New total: {new_staff_count}.")
                await send_telegram_log(bot,
                    f"👥 Увольнение сотрудников: {user_link} уволил <code>{amount_to_fire}</code> сотр. "
                    f"из бизнеса <b>{html.escape(business_display_name)}</b> (ID: <code>{business_id}</code>) "
                    f"в чате <b>{html.escape(message.chat.title or str(chat_id))}</b>. "
                    f"Осталось: <code>{new_staff_count}</code>."
                )
            else:
                await message.reply(f"Произошла ошибка при увольнении сотрудников. Пожалуйста, попробуйте еще раз.")
                await send_telegram_log(bot, f"🔴 Ошибка увольнения сотрудников: User {user_id} chat {chat_id}. Причина: Ошибка update_user_business.")

        except Exception as e:
            logger.error(f"Error in /firestaff for user {user_id} in chat {chat_id}: {e}", exc_info=True)
            await message.reply("Произошла внутренняя ошибка при увольнении сотрудников. Попробуйте позже.")
            await send_telegram_log(bot, f"🔴 <b>Ошибка /firestaff</b>\nUser: {user_link} ({user_id})\nChat: {html.escape(message.chat.title or str(chat_id))} ({chat_id})\nErr: <pre>{html.escape(str(e))}</pre>")


@business_router.message(Command("buyupgrade", "купитьапгрейд", "улучшениебизнеса", ignore_case=True))
async def buy_upgrade_command(message: Message, command: CommandObject, bot: Bot):
    if not message.from_user:
        await message.reply("Не могу определить пользователя.")
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    user_full_name = message.from_user.full_name
    user_username = message.from_user.username
    user_link = get_user_mention_html(user_id, user_full_name, user_username)

    args = command.args.split() if command.args else []

    if not args:
        # Сценарий: /buyupgrade (без аргументов)
        user_businesses = await database.get_user_businesses(user_id, chat_id)

        response_lines = [
            f"<b>🛠️ {user_link}, чтобы посмотреть доступные апгрейды для вашего бизнеса или купить их:</b>\n",
            "Используйте: <code>/buyupgrade [ID_бизнеса]</code> - покажет доступные апгрейды для выбранного бизнеса.",
            "Используйте: <code>/buyupgrade [ID_бизнеса] [ключ_апгрейда]</code> - купит апгрейд для выбранного бизнеса.\n"
        ]

        if not user_businesses:
            response_lines.append(f"У вас пока нет бизнесов в этом чате. Приобретите их с помощью <code>/buybusiness</code>.")
        else:
            response_lines.append("<b>Ваши бизнесы (выберите ID):</b>")
            for biz in user_businesses:
                business_static_info = BUSINESS_DATA.get(biz['business_key'])
                business_display_name = biz['name_override'] or business_static_info.get('levels', {}).get(biz['current_level'], {}).get('display_name') or business_static_info.get('name', 'Неизвестный бизнес')
                response_lines.append(f"  <b>{html.escape(business_display_name)}</b> (ID: <code>{biz['business_id']}</code>)") # Используем business_id из БД

        await message.reply("\n".join(response_lines), parse_mode="HTML", disable_web_page_preview=True)
        return

    # Если аргументы есть, продолжаем логику
    if len(args) == 1:
        # Сценарий: /buyupgrade [ID_бизнеса] - показать апгрейды только для этого бизнеса
        try:
            business_id_to_check = int(args[0])
        except ValueError:
            # Если ID бизнеса введен неправильно, показываем список бизнесов пользователя
            user_businesses = await database.get_user_businesses(user_id, chat_id)
            if not user_businesses:
                await message.reply(f"{user_link}, неверный формат ID бизнеса. У вас нет бизнесов в этом чате. Используйте <code>/buybusiness</code>, чтобы приобрести.")
                return

            response_lines = [
                f"{user_link}, неверный формат ID бизнеса. Ваши бизнесы (для удобства):",
            ]
            for biz in user_businesses:
                business_static_info = BUSINESS_DATA.get(biz['business_key'])
                business_display_name = biz['name_override'] or business_static_info.get('levels', {}).get(biz['current_level'], {}).get('display_name') or business_static_info.get('name', 'Неизвестный бизнес')
                response_lines.append(f"  <b>{html.escape(business_display_name)}</b> (ID: <code>{biz['business_id']}</code>)")

            response_lines.append("\nИспользуйте: <code>/buyupgrade [ID_бизнеса]</code>, чтобы увидеть доступные апгрейды для конкретного бизнеса.")
            await message.reply("\n".join(response_lines), parse_mode="HTML", disable_web_page_preview=True)
            return

        # Получаем данные о бизнесе
        business = await database.get_user_business_by_id(business_id_to_check, user_id)
        if not business or business['chat_id'] != chat_id:
            # Если бизнес не найден или не принадлежит пользователю, показываем список бизнесов
            user_businesses = await database.get_user_businesses(user_id, chat_id)
            if not user_businesses:
                await message.reply(f"{user_link}, бизнес с ID <code>{business_id_to_check}</code> не найден в этом чате или не принадлежит вам. У вас нет бизнесов в этом чате. Используйте <code>/buybusiness</code>, чтобы приобрести.")
                return

            response_lines = [
                f"{user_link}, бизнес с ID <code>{business_id_to_check}</code> не найден в этом чате или не принадлежит вам. Ваши бизнесы (для удобства):",
            ]
            for biz in user_businesses:
                business_static_info = BUSINESS_DATA.get(biz['business_key'])
                business_display_name = biz['name_override'] or business_static_info.get('levels', {}).get(biz['current_level'], {}).get('display_name') or business_static_info.get('name', 'Неизвестный бизнес')
                response_lines.append(f"  <b>{html.escape(business_display_name)}</b> (ID: <code>{biz['business_id']}</code>)")

            response_lines.append("\nИспользуйте: <code>/buyupgrade [ID_бизнеса]</code>, чтобы увидеть доступные апгрейды для конкретного бизнеса.")
            await message.reply("\n".join(response_lines), parse_mode="HTML", disable_web_page_preview=True)
            return

        business_static_info = BUSINESS_DATA.get(business['business_key'])
        if not business_static_info:
            await message.reply("Ошибка: Статические данные для этого бизнеса не найдены.")
            return

        business_display_name = business['name_override'] or business_static_info.get('levels', {}).get(business['current_level'], {}).get('display_name') or business_static_info.get('name', 'Неизвестный бизнес')

        response_lines = [
            f"<b>🛠️ {user_link}, доступные апгрейды для \"{html.escape(business_display_name)}\" (ID: <code>{business_id_to_check}</code>):</b>\n",
            "Для покупки используйте: <code>/buyupgrade [ID_бизнеса] [ключ_апгрейда]</code>\n"
        ]

        found_applicable_upgrades = False
        for key, info in BUSINESS_UPGRADES.items():
            # Проверяем применимость к данному бизнесу
            is_applicable_to_this_business = (
                not info.get("applicable_business_keys") or  # Если applicable_business_keys пуст, то апгрейд для всех
                business['business_key'] in info["applicable_business_keys"]  # Иначе проверяем конкретный ключ
            )

            if is_applicable_to_this_business:
                # Проверяем, установлен ли уже этот апгрейд на бизнесе
                existing_upgrades = await database.get_business_upgrades(business_id_to_check, user_id)
                already_installed = any(upg['upgrade_key'] == key for upg in existing_upgrades)

                if not already_installed:
                    found_applicable_upgrades = True
                    upgrade_name = html.escape(info['name'])
                    upgrade_price = info['price']
                    upgrade_description = html.escape(info['description'])

                    response_lines.append(f"  <b>🔑 {upgrade_name}</b>")
                    response_lines.append(f"    💰 Цена: <code>{upgrade_price:,}</code> OneCoin")
                    response_lines.append(f"    📝 Описание: {upgrade_description}")
                    response_lines.append(f"    Используйте ключ: <code>{key}</code>\n")

        if not found_applicable_upgrades:
            response_lines.append(f"  Нет доступных апгрейдов для этого бизнеса, которые еще не установлены.")
            response_lines.append(f"  (Возможно, вы уже купили все доступные для него апгрейды).")

        await message.reply("\n".join(response_lines), parse_mode="HTML", disable_web_page_preview=True)
        return

    # Сценарий: /buyupgrade [ID_бизнеса] [ключ_апгрейда] - это уже логика покупки апгрейда
    # Этот блок остается как был, так как он обрабатывает саму покупку
    try:
        business_id = int(args[0])
        upgrade_key = args[1].strip()
    except ValueError:
        await message.reply(f"{user_link}, ID бизнеса должен быть числом. Пример: <code>/buyupgrade 123 UPGRADE_FIRE_EXTINGUISHER</code>")
        return
    except IndexError:  # Этот случай уже отловлен (len(args) < 2), но на всякий случай
        await message.reply(f"{user_link}, неверный формат. Укажите ID бизнеса и ключ апгрейда. Пример: <code>/buyupgrade 123 UPGRADE_FIRE_EXTINGUISHER</code>")
        return

    current_user_chat_lock = await database.get_user_chat_lock(user_id, chat_id)
    async with current_user_chat_lock:
        try:
            business = await database.get_user_business_by_id(business_id, user_id)
            if not business or business['chat_id'] != chat_id:
                await message.reply(f"{user_link}, бизнес с ID <code>{business_id}</code> не найден в этом чате или не принадлежит вам.")
                return

            upgrade_info_static = BUSINESS_UPGRADES.get(upgrade_key)
            if not upgrade_info_static:
                await message.reply(f"{user_link}, апгрейд с ключом <code>{html.escape(upgrade_key)}</code> не найден. Проверьте правильность написания.")
                return

            # Проверяем, применим ли апгрейд к данному бизнесу
            if upgrade_info_static.get("applicable_business_keys") and \
                    business['business_key'] not in upgrade_info_static["applicable_business_keys"]:
                await message.reply(
                    f"{user_link}, апгрейд \"<b>{html.escape(upgrade_info_static['name'])}</b>\" "
                    f"неприменим к вашему бизнесу \"<b>{html.escape(business['name_override'] or BUSINESS_DATA.get(business['business_key'])['name'])}</b>\"."
                )
                return

            # Проверяем, установлен ли уже этот апгрейд на бизнесе
            existing_upgrades = await database.get_business_upgrades(business_id, user_id)
            for existing_upg in existing_upgrades:
                if existing_upg['upgrade_key'] == upgrade_key:
                    await message.reply(f"{user_link}, апгрейд \"<b>{html.escape(upgrade_info_static['name'])}</b>\" уже установлен на этом бизнесе.")
                    return

            upgrade_cost = upgrade_info_static['price']
            user_onecoins_balance = await database.get_user_onecoins(user_id, chat_id)

            if user_onecoins_balance < upgrade_cost:
                await message.reply(
                    f"{user_link}, у вас недостаточно OneCoin для покупки апгрейда \"<b>{html.escape(upgrade_info_static['name'])}</b>\" "
                    f"(стоимость: <code>{upgrade_cost:,}</code> OC, у вас: <code>{user_onecoins_balance:,}</code> OC)."
                )
                return

            # Списываем деньги
            new_user_onecoins_balance = await database.update_user_onecoins(user_id, chat_id, -upgrade_cost,
                                                                          username=user_username, full_name=user_full_name,
                                                                          chat_title=message.chat.title)
            if new_user_onecoins_balance is None or new_user_onecoins_balance < 0:
                await message.reply(f"Произошла ошибка при списании OneCoin. Покупка апгрейда не удалась. Ваш баланс: {user_onecoins_balance}.")
                await send_telegram_log(bot,
                                        f"🔴 Ошибка списания (buyupgrade): User {user_id}, chat {chat_id}, -{upgrade_cost} OneCoin. Balance was {user_onecoins_balance}, now {new_user_onecoins_balance}.")
                return

            # Добавляем апгрейд в БД
            new_upgrade_db_id = await database.add_business_upgrade(user_id, business_id, upgrade_key)

            if new_upgrade_db_id:
                business_display_name = business['name_override'] or BUSINESS_DATA.get(business['business_key'])['name']
                await message.reply(
                    f"✅ {user_link}, вы успешно установили апгрейд \"<b>{html.escape(upgrade_info_static['name'])}</b>\" "
                    f"для бизнеса \"<b>{html.escape(business_display_name)}</b>\" (ID: <code>{business_id}</code>) за <code>{upgrade_cost:,}</code> OneCoin!\n"
                    f"Ваш основной баланс: <code>{new_user_onecoins_balance:,}</code> OneCoin."
                )
                logger.info(
                    f"User {user_id} bought upgrade {upgrade_key} (DB ID: {new_upgrade_db_id}) for business {business_id} in chat {chat_id}.")
                await send_telegram_log(bot,
                                        f"🛠️ Новый апгрейд: {user_link} купил <b>{html.escape(upgrade_info_static['name'])}</b> "
                                        f"для бизнеса <b>{html.escape(business_display_name)}</b> (ID: <code>{business_id}</code>) "
                                        f"в чате <b>{html.escape(message.chat.title or str(chat_id))}</b> за <code>{upgrade_cost:,}</code> OC.")
            
                # нужно будет передавать количество купленных апгрейдов и проверять, все ли куплены для одного бизнеса
                await check_and_grant_achievements(
                    user_id,
                    chat_id,
                    bot,
                    business_upgrade_bought_just_now=True, # Для одноразового (если есть)
                    business_upgrades_bought_total_count=1, # Заглушка, нужно получать суммарно
                    business_id_upgraded=business_id, # Для проверки "все апгрейды для одного"
                    upgrade_key_bought=upgrade_key # Для проверки "все апгрейды для одного"
                )
                # --- КОНЕЦ ВЫЗОВА ПРОВЕРКИ ДОСТИЖЕНИЙ ---
            
            else:
                # Если добавление апгрейда не удалось, пытаемся вернуть деньги
                await database.update_user_onecoins(user_id, chat_id, upgrade_cost,
                                                    username=user_username, full_name=user_full_name,
                                                    chat_title=message.chat.title)
                await message.reply(f"Произошла ошибка при установке апгрейда. Средства были возвращены. Пожалуйста, попробуйте еще раз.")
                await send_telegram_log(bot,
                                        f"🔴 Ошибка установки апгрейда: User {user_id} chat {chat_id}. Возвращены средства. Причина: Ошибка add_business_upgrade.")

        except Exception as e:
            logger.error(f"Error in /buyupgrade for user {user_id} in chat {chat_id}: {e}", exc_info=True)
            await message.reply("Произошла внутренняя ошибка при покупке апгрейда. Попробуйте позже.")
            await send_telegram_log(bot,
                                    f"🔴 <b>Ошибка /buyupgrade</b>\nUser: {user_link} ({user_id})\nChat: {html.escape(message.chat.title or str(chat_id))} ({chat_id})\nErr: <pre>{html.escape(str(e))}</pre>")
            
@business_router.message(Command("upgradebusiness", "улучшитьбизнес", "прокачатьбизнес", ignore_case=True))
async def upgrade_business_command(message: Message, command: CommandObject, bot: Bot):
    if not message.from_user:
        await message.reply("Не могу определить пользователя.")
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    user_full_name = message.from_user.full_name
    user_username = message.from_user.username
    user_link = get_user_mention_html(user_id, user_full_name, user_username)

    if not command.args:
        await message.reply(
            f"{user_link}, чтобы улучшить бизнес, укажите его ID.\n"
            f"Пример: <code>/upgradebusiness [ID_бизнеса]</code>\n"
            f"Ваши бизнесы: <code>/mybusinesses</code>"
        )
        return

    try:
        business_id = int(command.args.strip())
    except ValueError:
        await message.reply(f"{user_link}, ID бизнеса должен быть числом.")
        return

    current_user_chat_lock = await database.get_user_chat_lock(user_id, chat_id)
    async with current_user_chat_lock:
        try:
            business = await database.get_user_business_by_id(business_id, user_id)
            if not business or business['chat_id'] != chat_id:
                await message.reply(f"{user_link}, бизнес с ID <code>{business_id}</code> не найден в этом чате или не принадлежит вам.")
                return

            business_static_info = BUSINESS_DATA.get(business['business_key'])
            if not business_static_info:
                await message.reply("Ошибка: Статические данные для этого бизнеса не найдены.")
                return

            current_level = business['current_level']
            next_level = current_level + 1
            
            next_level_info = business_static_info['levels'].get(next_level)
            if not next_level_info:
                await message.reply(f"{user_link}, ваш бизнес \"<b>{html.escape(business['name_override'] or business_static_info['name'])}</b>\" (ID: <code>{business_id}</code>) уже достиг максимального уровня (<code>{current_level}</code>).")
                return
            
            upgrade_cost = next_level_info['upgrade_cost']
            user_onecoins_balance = await database.get_user_onecoins(user_id, chat_id)

            if user_onecoins_balance < upgrade_cost:
                await message.reply(
                    f"{user_link}, у вас недостаточно OneCoin для улучшения бизнеса до уровня <code>{next_level}</code> "
                    f"(требуется <code>{upgrade_cost:,}</code> OC, у вас: <code>{user_onecoins_balance:,}</code> OC)."
                )
                return

            # Списываем деньги
            new_user_onecoins_balance = await database.update_user_onecoins(user_id, chat_id, -upgrade_cost,
                                                                          username=user_username, full_name=user_full_name, chat_title=message.chat.title)
            if new_user_onecoins_balance is None or new_user_onecoins_balance < 0:
                 await message.reply(f"Произошла ошибка при списании OneCoin. Улучшение не удалось. Ваш баланс: {user_onecoins_balance}.")
                 await send_telegram_log(bot, f"🔴 Ошибка списания (upgradebusiness): User {user_id}, chat {chat_id}, -{upgrade_cost} OneCoin. Balance was {user_onecoins_balance}, now {new_user_onecoins_balance}.")
                 return
            
            # Обновляем уровень бизнеса и время последнего начисления
            # При улучшении мы сбрасываем last_income_calculation_utc на текущее время,
            # чтобы избежать двойного начисления за уже прошедшие часы на новом уровне.
            success = await database.update_user_business(
                business_id, user_id, {
                    'current_level': next_level,
                    'last_income_calculation_utc': datetime.now(dt_timezone.utc) # Обновляем время
                }
            )

            if success:
                business_display_name = business['name_override'] or business_static_info['name']
                await message.reply(
                    f"✅ {user_link}, ваш бизнес \"<b>{html.escape(business_display_name)}</b>\" (ID: <code>{business_id}</code>) "
                    f"успешно улучшен до уровня <b><code>{next_level}</code> - \"{html.escape(next_level_info['display_name'])}\"</b> "
                    f"за <code>{upgrade_cost:,}</code> OneCoin!\n"
                    f"Ваш основной баланс: <code>{new_user_onecoins_balance:,}</code> OneCoin."
                )
                logger.info(f"User {user_id} upgraded business {business_id} to level {next_level} in chat {chat_id} for {upgrade_cost} OneCoin.")
                await send_telegram_log(bot,
                    f"⬆️ Улучшение бизнеса: {user_link} улучшил бизнес <b>{html.escape(business_display_name)}</b> "
                    f"(ID: <code>{business_id}</code>) до Ур.<code>{next_level}</code> "
                    f"в чате <b>{html.escape(message.chat.title or str(chat_id))}</b> за <code>{upgrade_cost:,}</code> OC."
                )
                
                # --- ВЫЗОВ ПРОВЕРКИ ДОСТИЖЕНИЙ ---
                await check_and_grant_achievements(
                    user_id,
                    chat_id,
                    bot,
                    business_upgraded_to_max_level_just_now=(next_level == 3), # Если достигнут макс. уровень
                    business_upgraded_specific_key=business['business_key'], # Ключ бизнеса
                    business_upgraded_to_level=next_level # Новый уровень
                )
                # --- КОНЕЦ ВЫЗОВА ПРОВЕРКИ ДОСТИЖЕНИЙ ---
            else:
                # Если обновление бизнеса не удалось, пытаемся вернуть деньги
                await database.update_user_onecoins(user_id, chat_id, upgrade_cost,
                                                    username=user_username, full_name=user_full_name, chat_title=message.chat.title)
                await message.reply(f"Произошла ошибка при улучшении бизнеса. Средства были возвращены. Пожалуйста, попробуйте еще раз.")
                await send_telegram_log(bot, f"🔴 Ошибка улучшения бизнеса: User {user_id} chat {chat_id}. Причина: Ошибка update_user_business.")

        except Exception as e:
            logger.error(f"Error in /upgradebusiness for user {user_id} in chat {chat_id}: {e}", exc_info=True)
            await message.reply("Произошла внутренняя ошибка при улучшении бизнеса. Попробуйте позже.")
            await send_telegram_log(bot, f"🔴 <b>Ошибка /upgradebusiness</b>\nUser: {user_link} ({user_id})\nChat: {html.escape(message.chat.title or str(chat_id))} ({chat_id})\nErr: <pre>{html.escape(str(e))}</pre>")


@business_router.message(Command("sellbusiness", "продатьбизнес", "избавитьсяотбизнеса", ignore_case=True))
async def sell_business_command(message: Message, command: CommandObject, bot: Bot):
    if not message.from_user:
        await message.reply("Не могу определить пользователя.")
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    user_full_name = message.from_user.full_name
    user_username = message.from_user.username
    user_link = get_user_mention_html(user_id, user_full_name, user_username)

    if not command.args:
        await message.reply(
            f"{user_link}, чтобы продать бизнес, укажите его ID.\n"
            f"Пример: <code>/sellbusiness</code> <u>[ID_бизнеса]</u>\n"
            f"<b>Внимание: это действие необратимо!</b> Проверьте ID вашего бизнеса командой <code>/mybusinesses</code>.", # <--- ВОТ ЗДЕСЬ ДОБАВИЛИ ЗАПЯТУЮ!
            
            disable_web_page_preview=True # Это второй дополнительный параметр
        )
        return

    try:
        business_id = int(command.args.strip())
    except ValueError:
        await message.reply(f"{user_link}, ID бизнеса должен быть числом.")
        return

    current_user_chat_lock = await database.get_user_chat_lock(user_id, chat_id)
    async with current_user_chat_lock:
        try:
            business = await database.get_user_business_by_id(business_id, user_id)
            if not business or business['chat_id'] != chat_id:
                await message.reply(f"{user_link}, бизнес с ID <code>{business_id}</code> не найден в этом чате или не принадлежит вам.")
                return

            business_static_info = BUSINESS_DATA.get(business['business_key'])
            if not business_static_info:
                await message.reply("Ошибка: Статические данные для этого бизнеса не найдены.")
                return

            # --- Расчет суммы продажи ---
            total_invested_in_levels = 0
            
            # Добавляем стоимость покупки (уровень 0)
            level_0_info = business_static_info['levels'].get(0)
            if level_0_info:
                total_invested_in_levels += level_0_info['price']
            
            # Добавляем стоимость всех последующих улучшений до текущего уровня
            for level_num in range(1, business['current_level'] + 1):
                level_info = business_static_info['levels'].get(level_num)
                if level_info and 'upgrade_cost' in level_info:
                    total_invested_in_levels += level_info['upgrade_cost']
            
            sell_price = int(total_invested_in_levels * 0.50) # 50% от инвестиций в уровни
            # --- Конец расчета суммы продажи ---

            business_display_name = business['name_override'] or business_static_info['name']
            
            # Просим подтверждение, так как продажа необратима
            confirmation_message = (
                f"{user_link}, вы уверены, что хотите продать бизнес \"<b>{html.escape(business_display_name)}</b>\" (ID: <code>{business_id}</code>)?\n"
                f"Вы получите <b><code>{sell_price:,}</code></b> OneCoin.\n"
                f"Это действие <b>необратимо</b>.\n\n"
                f"Для подтверждения отправьте: <code>/confirm_sell_business {business_id}</code>"
            )
            await message.reply(confirmation_message, parse_mode="HTML")
            return

        except Exception as e:
            logger.error(f"Error in /sellbusiness for user {user_id} in chat {chat_id}: {e}", exc_info=True)
            await message.reply("Произошла внутренняя ошибка при подготовке продажи бизнеса. Попробуйте позже.")
            await send_telegram_log(bot, f"🔴 <b>Ошибка /sellbusiness</b>\nUser: {user_link} ({user_id})\nChat: {html.escape(message.chat.title or str(chat_id))} ({chat_id})\nErr: <pre>{html.escape(str(e))}</pre>")


@business_router.message(Command("confirm_sell_business", ignore_case=True))
async def confirm_sell_business_command(message: Message, command: CommandObject, bot: Bot):
    if not message.from_user:
        await message.reply("Не могу определить пользователя.")
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    user_full_name = message.from_user.full_name
    user_username = message.from_user.username
    user_link = get_user_mention_html(user_id, user_full_name, user_username)

    if not command.args:
        await message.reply(f"{user_link}, для подтверждения продажи бизнеса, укажите ID бизнеса: <code>/confirm_sell_business [ID_бизнеса]</code>.")
        return

    try:
        business_id_to_sell = int(command.args.strip())
    except ValueError:
        await message.reply(f"{user_link}, ID бизнеса должен быть числом.")
        return

    current_user_chat_lock = await database.get_user_chat_lock(user_id, chat_id)
    async with current_user_chat_lock:
        try:
            business = await database.get_user_business_by_id(business_id_to_sell, user_id)
            if not business or business['chat_id'] != chat_id:
                await message.reply(f"{user_link}, бизнес с ID <code>{business_id_to_sell}</code> не найден в этом чате или не принадлежит вам.")
                return

            business_static_info = BUSINESS_DATA.get(business['business_key'])
            if not business_static_info:
                await message.reply("Ошибка: Статические данные для этого бизнеса не найдены.")
                return
            
            # Повторно рассчитываем сумму продажи, чтобы избежать манипуляций
            total_invested_in_levels = 0
            level_0_info = business_static_info['levels'].get(0)
            if level_0_info:
                total_invested_in_levels += level_0_info['price']
            for level_num in range(1, business['current_level'] + 1):
                level_info = business_static_info['levels'].get(level_num)
                if level_info and 'upgrade_cost' in level_info:
                    total_invested_in_levels += level_info['upgrade_cost']
            sell_price = int(total_invested_in_levels * 0.50)

            # Проводим транзакцию: удаляем бизнес и начисляем деньги
            delete_success = await database.delete_user_business(business_id_to_sell, user_id)

            if delete_success:
                new_user_onecoins_balance = await database.update_user_onecoins(user_id, chat_id, sell_price,
                                                                              username=user_username, full_name=user_full_name, chat_title=message.chat.title)
                if new_user_onecoins_balance is None: # На случай ошибки при зачислении
                     await message.reply(f"Произошла ошибка при зачислении средств за проданный бизнес. Обратитесь к администратору.")
                     await send_telegram_log(bot, f"🔴 КРИТИЧЕСКАЯ ОШИБКА (sellbusiness): User {user_id}, chat {chat_id}, +{sell_price} OC. new_user_onecoins_balance is None after delete.")
                     return

                business_display_name = business['name_override'] or business_static_info['name']
                await message.reply(
                    f"✅ {user_link}, вы успешно продали бизнес \"<b>{html.escape(business_display_name)}</b>\" (ID: <code>{business_id_to_sell}</code>) "
                    f"за <code>{sell_price:,}</code> OneCoin!\n"
                    f"Ваш основной баланс: <code>{new_user_onecoins_balance:,}</code> OneCoin."
                )
                logger.info(f"User {user_id} sold business {business_id_to_sell} in chat {chat_id} for {sell_price} OneCoin.")
                await send_telegram_log(bot,
                    f"📉 Продажа бизнеса: {user_link} продал бизнес <b>{html.escape(business_display_name)}</b> "
                    f"(ID: <code>{business_id_to_sell}</code>) в чате <b>{html.escape(message.chat.title or str(chat_id))}</b> "
                    f"за <code>{sell_price:,}</code> OC."
                )
            else:
                await message.reply(f"Произошла ошибка при продаже бизнеса. Пожалуйста, попробуйте еще раз.")
                await send_telegram_log(bot, f"🔴 Ошибка удаления бизнеса: User {user_id} chat {chat_id}. Причина: Ошибка delete_user_business.")

        except Exception as e:
            logger.error(f"Error in /confirm_sell_business for user {user_id} in chat {chat_id}: {e}", exc_info=True)
            await message.reply("Произошла внутренняя ошибка при подтверждении продажи бизнеса. Попробуйте позже.")
            await send_telegram_log(bot, f"🔴 <b>Ошибка /confirm_sell_business</b>\nUser: {user_link} ({user_id})\nChat: {html.escape(message.chat.title or str(chat_id))} ({chat_id})\nErr: <pre>{html.escape(str(e))}</pre>")            
            
            
async def _process_business_event(
    user_id: int,
    business_id: int,
    business_key: str,
    business_level: int,
    user_upgrades: List[Dict[str, Any]],
    base_income_per_hour: float,
    user_full_name: str,
    user_username: Optional[str],
    chat_title: str,
    chat_id: int,
    bot: Bot,
    conn_ext: Any # asyncpg.Connection
) -> Tuple[float, Optional[str]]:
    """
    Обрабатывает случайное событие для бизнеса.
    Возвращает множитель дохода за счет события и сообщение о событии.
    """
    event_chance_roll = random.random() # Случайное число от 0.0 до 1.0
    
    # Сначала определяем, произойдет ли событие вообще (70/30)
    if event_chance_roll > Config.BUSINESS_EVENT_CHANCE_PERCENT: # Например, 0.30 для 30%
        return 1.0, None # Событие не произошло, множитель 1.0, сообщения нет

    # Если событие произошло, выбираем его тип (позитивное/негативное 50/50)
    is_positive_event = random.random() < Config.BUSINESS_EVENT_TYPE_CHANCE_POSITIVE # Например, 0.50 для 50%
    
    applicable_events = []
    for event in BUSINESS_EVENTS:
        # Проверяем, применимо ли событие к этому бизнесу
        if business_key in event.get("affected_business_keys", []):
            if (is_positive_event and event['type'] == 'positive') or \
               (not is_positive_event and event['type'] == 'negative'):
                applicable_events.append(event)
    
    if not applicable_events:
        logger.info(f"No applicable {'positive' if is_positive_event else 'negative'} events found for business {business_key}. Skipping event for business {business_id}.")
        return 1.0, None # Нет применимых событий, ничего не происходит

    chosen_event = random.choice(applicable_events)
    event_message_parts = []
    event_effect_multiplier = random.uniform(chosen_event['effect_multiplier_min'], chosen_event['effect_multiplier_max'])

    business_display_name = BUSINESS_DATA.get(business_key, {}).get('levels', {}).get(business_level, {}).get('display_name', business_key)
    if business_display_name == business_key:
        business_display_name = BUSINESS_DATA.get(business_key, {}).get('name', business_key) # Fallback to base name

    user_mention = get_user_mention_html(user_id, user_full_name, user_username)
    
    event_status_icon = "✨" if chosen_event['type'] == 'positive' else "🚨"
    event_effect_sign = "+" if chosen_event['type'] == 'positive' else "" # Знак для отрицательного будет автоматически

    # Проверка на защиту от негативного события
    if chosen_event['type'] == 'negative' and chosen_event.get('protection_upgrade_key'):
        protection_upgrade_key = chosen_event['protection_upgrade_key']
        
        # Проверяем, установлен ли апгрейд для этого бизнеса
        has_protection = False
        for upg in user_upgrades:
            if upg['upgrade_key'] == protection_upgrade_key:
                has_protection = True
                break

        if has_protection:
            protection_succeeded = random.random() < Config.BUSINESS_UPGRADE_PROTECTION_CHANCE_SUCCESS # 70% шанс успеха
            if protection_succeeded:
                # Апгрейд сработал, событие предотвращено
                protected_upgrade_name = BUSINESS_UPGRADES.get(protection_upgrade_key, {}).get('name', protection_upgrade_key)
                event_message_parts.append(
                    f"{event_status_icon} Ваш бизнес \"<b>{html.escape(business_display_name)}</b>\" (ID: <code>{business_id}</code>) "
                    f"пыталось настичь событие \"<b>{html.escape(chosen_event['name'])}</b>\"!\n"
                    f"Но благодаря апгрейду \"<b>{html.escape(protected_upgrade_name)}</b>\" (сработал на <code>{Config.BUSINESS_UPGRADE_PROTECTION_CHANCE_SUCCESS * 100:.0f}%</code> шанс), оно было <b>предотвращено</b>! Доход не пострадал."
                )
                logger.info(f"Business {business_id} protected from event {chosen_event['key']} by {protection_upgrade_key}.")
                return 1.0, "\n".join(event_message_parts) # Эффект отменен, возвращаем множитель 1.0
            else:
                # Апгрейд не сработал
                protected_upgrade_name = BUSINESS_UPGRADES.get(protection_upgrade_key, {}).get('name', protection_upgrade_key)
                event_message_parts.append(
                    f"⚠️ Ваш апгрейд \"<b>{html.escape(protected_upgrade_name)}</b>\" (сработал на <code>{Config.BUSINESS_UPGRADE_PROTECTION_CHANCE_SUCCESS * 100:.0f}%</code> шанс) "
                    f"для бизнеса \"<b>{html.escape(business_display_name)}</b>\" (ID: <code>{business_id}</code>) "
                    f"<b>не смог предотвратить</b> событие \"<b>{html.escape(chosen_event['name'])}</b>\" (шанс <code>{100 - Config.BUSINESS_UPGRADE_PROTECTION_CHANCE_SUCCESS * 100:.0f}%</code>)! \n"
                )
                logger.info(f"Business {business_id} NOT protected from event {chosen_event['key']} by {protection_upgrade_key} (failed roll).")
    
    # Основное сообщение о событии
    event_message_parts.append(
        f"{event_status_icon} В вашем бизнесе \"<b>{html.escape(business_display_name)}</b>\" (ID: <code>{business_id}</code>) "
        f"произошло событие: <b>{html.escape(chosen_event['name'])}</b>!\n"
        f"{html.escape(chosen_event['description'])}\n"
        f"Это изменило доход на <b>{event_effect_sign}{event_effect_multiplier * 100:.2f}%</b> от базового."
    )
    
    return 1.0 + event_effect_multiplier, "\n".join(event_message_parts)


async def process_daily_business_income_and_events(bot: Bot):
    logger.info("SCHEDULER: Запуск ежедневной задачи по начислению дохода бизнесов и генерации событий.")
    
    all_users_with_businesses = {} 
    all_event_messages = []  # <--- ИНИЦИАЛИЗАЦИЯ ПЕРЕМЕЩЕНА СЮДА
    total_income_processed = 0   # <--- ИНИЦИАЛИЗАЦИЯ ПЕРЕМЕЩЕНА СЮДА
    total_businesses_processed = 0 # <--- ИНИЦИАЛИЗАЦИЯ ПЕРЕМЕЩЕНА СЮДА

    conn = None
    try:
        conn = await database.get_connection() # Получаем одно соединение для всей операции
        
        raw_businesses = await conn.fetch("SELECT * FROM user_businesses WHERE is_active = TRUE")

        # Группируем бизнесы по user_id и chat_id для удобства обработки
        for biz_row in raw_businesses:
            biz_data = dict(biz_row)
            # Убеждаемся, что даты aware (как мы делаем в database.py функциях)
            if biz_data.get('last_income_calculation_utc') and isinstance(biz_data['last_income_calculation_utc'], datetime):
                ts = biz_data['last_income_calculation_utc']
                biz_data['last_income_calculation_utc'] = ts.replace(tzinfo=dt_timezone.utc) if ts.tzinfo is None else ts.astimezone(dt_timezone.utc)
            if biz_data.get('time_purchased_utc') and isinstance(biz_data['time_purchased_utc'], datetime):
                ts = biz_data['time_purchased_utc']
                biz_data['time_purchased_utc'] = ts.replace(tzinfo=dt_timezone.utc) if ts.tzinfo is None else ts.astimezone(dt_timezone.utc)

            user_id_biz = biz_data['user_id'] # Используем другое имя переменной, чтобы не конфликтовать с user_id в цикле выше
            chat_id_biz = biz_data['chat_id'] # Аналогично
            if user_id_biz not in all_users_with_businesses:
                all_users_with_businesses[user_id_biz] = {}
            if chat_id_biz not in all_users_with_businesses[user_id_biz]:
                all_users_with_businesses[user_id_biz][chat_id_biz] = []
            all_users_with_businesses[user_id_biz][chat_id_biz].append(biz_data)

        # Шаг 2: Обработка каждого бизнеса
        for user_id, chats_data in all_users_with_businesses.items():
            user_full_name, user_username = await fetch_user_display_data(bot, user_id) 
            user_link = get_user_mention_html(user_id, user_full_name, user_username)

            for chat_id, businesses_in_chat in chats_data.items(): # Переименовал 'businesses' во избежание путаницы с 'raw_businesses'
                chat_title = businesses_in_chat[0].get('chat_title') or str(chat_id) 
                
                user_bank = await database.get_user_bank(user_id, chat_id, conn_ext=conn)
                
                if user_bank is None: 
                    logger.info(f"SCHEDULER: Bank not found for user {user_id} in chat {chat_id}. Creating default bank (level 0).")
                    user_bank = await database.create_or_update_user_bank(
                        user_id, chat_id, user_username, user_full_name, chat_title,
                        current_balance_change=0, 
                        new_bank_level=0,         
                        conn_ext=conn
                    )
                    if user_bank:
                        logger.info(f"SCHEDULER: Default bank operation successful for user {user_id}, chat {chat_id}. New Bank Data: {user_bank}")
                    else: 
                        logger.error(f"SCHEDULER: CRITICAL - Failed to create/get default bank for user {user_id} chat {chat_id}. Skipping income processing for this chat.")
                        continue 

                bank_level = user_bank.get('bank_level', 0) 
                bank_static_info = BANK_DATA.get(bank_level, BANK_DATA.get(0)) 
                bank_max_capacity = bank_static_info.get('max_capacity', 0) if bank_static_info else 0

                for biz in businesses_in_chat: # Используем businesses_in_chat
                    business_id = biz['business_id']
                    business_key = biz['business_key']
                    current_level = biz['current_level']
                    staff_hired_slots = biz['staff_hired_slots']
                    last_income_calc_utc = biz['last_income_calculation_utc']

                    business_static_info = BUSINESS_DATA.get(business_key)
                    if not business_static_info:
                        logger.warning(f"Static data for business key {business_key} not found for business ID {business_id}. Skipping.")
                        continue
                    
                    level_info = business_static_info['levels'].get(current_level)
                    if not level_info:
                        logger.warning(f"Level {current_level} data for business key {business_key} not found for business ID {business_id}. Skipping.")
                        continue

                    base_income_per_hour = level_info['base_income_per_hour']
                    max_staff_slots_for_biz = level_info['max_staff_slots'] # Избегаем конфликта с переменной выше
                    business_idx = _get_business_index(business_key)

                    now_utc = datetime.now(dt_timezone.utc)
                    hours_passed = (now_utc - last_income_calc_utc).total_seconds() / 3600
                    hours_passed = max(0, min(24.0, hours_passed)) 

                    if hours_passed < 1.0: 
                        logger.debug(f"Business {business_id} for user {user_id}: hours_passed={hours_passed:.2f}, skipping income calculation for now.")
                        continue 

                    staff_income_percentage_per_unit = _calculate_staff_income_percentage(business_idx)
                    staff_income_bonus_per_hour = staff_hired_slots * (base_income_per_hour * staff_income_percentage_per_unit)
                    gross_income_per_hour = base_income_per_hour + staff_income_bonus_per_hour
                    
                    event_multiplier = 1.0
                    event_msg_to_user = None
                    user_upgrades_for_biz = await database.get_business_upgrades(business_id, user_id, conn_ext=conn)

                    event_multiplier, event_msg_to_user = await _process_business_event(
                        user_id, business_id, business_key, current_level, user_upgrades_for_biz,
                        base_income_per_hour, user_full_name, user_username, chat_title, chat_id, bot, conn_ext=conn
                    )
                    
                    if event_msg_to_user:
                        all_event_messages.append({"user_id": user_id, "message": event_msg_to_user, "chat_id": chat_id}) # Добавил chat_id для контекста
                        logger.info(f"Generated event message for user {user_id}, business {business_id}: {event_msg_to_user[:100]}...")
                    
                    if event_multiplier == 1.0 and event_msg_to_user and "предотвращено" in event_msg_to_user:
                        await check_and_grant_achievements(
                            user_id, chat_id, bot,
                            business_event_prevented_just_now=True, 
                            business_events_prevented_total_count=1 
                        )
                    
                    effective_income_per_hour = gross_income_per_hour * event_multiplier # Умножаем, а не (1 + event_multiplier - 1)
                    effective_income_per_hour = max(0, effective_income_per_hour) 

                    tax_rate = Config.BUSINESS_TAX_BASE_PERCENT
                    if business_idx >= Config.BUSINESS_TAX_FULL_STAFF_START_BUSINESS_INDEX and \
                       staff_hired_slots == max_staff_slots_for_biz and max_staff_slots_for_biz > 0: 
                        tax_rate = Config.BUSINESS_TAX_FULL_STAFF_PERCENT
                    
                    tax_amount_per_hour = effective_income_per_hour * tax_rate
                    net_income_per_hour = effective_income_per_hour - tax_amount_per_hour
                    net_income_per_hour = max(0, net_income_per_hour) 

                    income_to_deposit = int(net_income_per_hour * hours_passed)
                    income_to_deposit = max(0, income_to_deposit) 

                    current_bank_balance = user_bank.get('current_balance', 0)
                    deposited_amount = 0 

                    if income_to_deposit > 0:
                        if current_bank_balance < bank_max_capacity:
                            space_left_in_bank = bank_max_capacity - current_bank_balance
                            amount_to_actually_deposit = min(income_to_deposit, space_left_in_bank)

                            if amount_to_actually_deposit > 0:
                                updated_bank_after_deposit = await database.create_or_update_user_bank(
                                    user_id, chat_id, user_username, user_full_name, chat_title,
                                    current_balance_change=amount_to_actually_deposit,
                                    conn_ext=conn
                                )
                                if updated_bank_after_deposit:
                                    user_bank = updated_bank_after_deposit 
                                    deposited_amount = amount_to_actually_deposit
                                    logger.info(f"Deposited {deposited_amount} OC to bank for user {user_id} in chat {chat_id} from business {business_id}. New bank balance: {user_bank.get('current_balance')}")
                                else:
                                    logger.error(f"Failed to update bank balance for user {user_id} chat {chat_id} after deposit attempt for business {business_id}. deposited_amount remains 0.")
                            else: 
                                logger.info(f"Bank full (or no space for positive income) for user {user_id} in chat {chat_id}. Income {income_to_deposit} from biz {business_id} lost.")
                                lost_income_message = (
                                    f"⚠️ {user_link}, ваш бизнес \"<b>{html.escape(biz.get('name_override') or BUSINESS_DATA.get(business_key, {}).get('name', business_key))}</b>\" (ID: <code>{business_id}</code>) "
                                    f"сгенерировал <code>{income_to_deposit:,}</code> OneCoin, но ваш банк в чате \"{html.escape(chat_title)}\" "
                                    f"<b>переполнен</b> (<code>{current_bank_balance:,}</code>/<code>{bank_max_capacity:,}</code> OC)! "
                                    f"Этот доход <b>сгорел</b>. Выведите средства командой <code>/withdrawbank</code> и улучшите банк <code>/upgradebank</code>!"
                                )
                                all_event_messages.append({"user_id": user_id, "message": lost_income_message, "chat_id": chat_id})
                        else: 
                            logger.info(f"Bank full for user {user_id} in chat {chat_id} (Balance: {current_bank_balance}, Capacity: {bank_max_capacity}). Income {income_to_deposit} OC from biz {business_id} lost.")
                            lost_income_message = (
                                f"⚠️ {user_link}, ваш бизнес \"<b>{html.escape(biz.get('name_override') or BUSINESS_DATA.get(business_key, {}).get('name', business_key))}</b>\" (ID: <code>{business_id}</code>) "
                                f"сгенерировал <code>{income_to_deposit:,}</code> OneCoin, но ваш банк в чате \"{html.escape(chat_title)}\" "
                                f"<b>переполнен</b> (<code>{current_bank_balance:,}</code>/<code>{bank_max_capacity:,}</code> OC)! "
                                f"Этот доход <b>сгорел</b>. Выведите средства командой <code>/withdrawbank</code> и улучшите банк <code>/upgradebank</code>!"
                            )
                            all_event_messages.append({"user_id": user_id, "message": lost_income_message, "chat_id": chat_id})
                    
                    await database.update_user_business(
                        business_id, user_id, {'last_income_calculation_utc': now_utc}, conn_ext=conn
                    )
                    
                    total_income_processed += deposited_amount 
                    total_businesses_processed += 1
                           
                    if deposited_amount > 0:
                        current_total_income_for_user = await database.update_user_total_business_income(user_id, deposited_amount, conn_ext=conn)
                        await check_and_grant_achievements(
                            user_id, chat_id, bot,
                            business_total_income_earned_value=current_total_income_for_user
                        )

        # Этот лог теперь находится внутри try, чтобы total_businesses_processed и total_income_processed были определены
        logger.info(f"SCHEDULER: Завершено начисление дохода и обработка событий. Всего бизнесов: {total_businesses_processed}, начислено OC: {total_income_processed:,}.")
        if total_businesses_processed > 0:
            await send_telegram_log(bot, f"📊 Ежедневное начисление дохода с бизнесов завершено. Обработано <b>{total_businesses_processed}</b> бизнесов, зачислено <b>{total_income_processed:,}</b> OC.")
        else:
            await send_telegram_log(bot, "📊 Ежедневное начисление дохода с бизнесов: активных бизнесов не найдено.")

    except Exception as e:
        logger.error(f"SCHEDULER: Критическая ошибка в process_daily_business_income_and_events: {e}", exc_info=True)
        await send_telegram_log(bot, f"🔴 SCHEDULER: Критическая ошибка в ежедневной задаче бизнесов:\n<pre>{html.escape(str(e))}</pre>")
    finally:
        if conn and not conn.is_closed():
            await conn.close()

    # Отправка сообщений пользователям теперь после блока try/finally для conn
    if all_event_messages: 
        logger.info(f"SCHEDULER: Попытка отправить {len(all_event_messages)} сообщений о событиях/уведомлениях.")
        for msg_data in all_event_messages: # ЭТО СТРОКА 1731 В ТВОЕМ ТРЕЙСБЕКЕ
            try:
                target_user_id_for_msg = msg_data.get('user_id')
                message_text_to_send = msg_data.get('message')
                # target_chat_id_for_msg = msg_data.get('chat_id') # Если нужно отправлять в чат события

                if target_user_id_for_msg and message_text_to_send:
                    # По умолчанию отправляем в ЛС пользователя
                    await bot.send_message(target_user_id_for_msg, message_text_to_send, parse_mode="HTML", disable_web_page_preview=True)
            except Exception as e_send_msg:
                logger.warning(f"SCHEDULER: Не удалось отправить запланированное сообщение пользователю {msg_data.get('user_id')}: {e_send_msg}")
    else:
        logger.info("SCHEDULER: Нет сообщений о событиях/уведомлениях для отправки.")


# --- Функция для регистрации хендлеров ---
def setup_business_handlers(dp):
    dp.include_router(business_router)
    print("Обработчики команд для Бизнесов и Банка зарегистрированы.")



