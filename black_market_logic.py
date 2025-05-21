# black_market_logic.py
import asyncio
import html
import random
from datetime import datetime, timedelta, timezone as dt_timezone, date as DDate
from typing import Optional, List, Dict, Any, Tuple

from aiogram import Router, Bot, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from pytz import timezone as pytz_timezone
from achievements_logic import check_and_grant_achievements 

# Импорты из проекта
from config import Config
import database # Оставляем импорт всего модуля database
from utils import get_user_mention_html, send_telegram_log, get_current_price
import json

# Данные о товарах
from phone_data import PHONE_MODELS as PHONE_MODELS_STANDARD_LIST, PHONE_COLORS
from item_data import PHONE_COMPONENTS, PHONE_CASES
from exclusive_phone_data import EXCLUSIVE_PHONE_MODELS, VINTAGE_PHONE_KEYS_FOR_BM

import logging

logger = logging.getLogger(__name__)
black_market_router = Router()

# Преобразуем списки стандартных телефонов в словари для быстрого доступа по ключу
PHONE_MODELS_STD_DICT = {phone_info["key"]: phone_info for phone_info in PHONE_MODELS_STANDARD_LIST}
EXCLUSIVE_PHONE_MODELS_DICT = {phone_info["key"]: phone_info for phone_info in EXCLUSIVE_PHONE_MODELS}
# PHONE_COMPONENTS и PHONE_CASES уже словари


# FSM для процесса покупки на черном рынке (остается без изменений)
class BlackMarketPurchaseStates(StatesGroup):
    awaiting_confirmation = State()


# --- Вспомогательные функции (остаются, как были, если не указано иное) ---

async def check_black_market_access(user_id: int) -> Tuple[bool, str]:
    # ... (код без изменений)
    streak_data = await database.get_user_daily_streak(user_id)
    current_streak = 0
    if streak_data and streak_data.get('last_streak_check_date'):
        today_local_date = datetime.now(pytz_timezone(Config.TIMEZONE)).date()
        last_check_date = streak_data['last_streak_check_date']
        if last_check_date == today_local_date or last_check_date == (today_local_date - timedelta(days=1)):
             current_streak = streak_data.get('current_streak', 0)
    
    required_streak = Config.BLACKMARKET_ACCESS_STREAK_REQUIREMENT
    required_streak_name = ""
    for streak_goal in Config.DAILY_STREAKS_CONFIG:
        if streak_goal['target_days'] == required_streak:
            required_streak_name = streak_goal['name']
            break
            
    if current_streak >= required_streak:
        return True, ""
    else:
        message_text = (
            f"🥷 Шепот улиц еще не достиг твоих ушей. Говорят, лишь те, кто доказал свою стойкость "
            f"({required_streak_name} - {required_streak} дней подряд), могут найти сюда дорогу..."
            f" Твой текущий стрик: {current_streak} дней."
        )
        return False, message_text

def get_stolen_wear_description(wear_data_input: Optional[Any]) -> str:
    # ... (код без изменений, используется для отображения)
    wear_data_json: Optional[Dict] = None 

    if isinstance(wear_data_input, str): 
        try:
            wear_data_json = json.loads(wear_data_input) 
        except json.JSONDecodeError:
            logger.warning(f"BLACKMARKET: Не удалось распарсить JSON из wear_data_input: {wear_data_input}")
            wear_data_json = None 
    elif isinstance(wear_data_input, dict): 
        wear_data_json = wear_data_input

    if not wear_data_json: 
        return "<i>Состояние: повидавший виды, будь начеку.</i>" 

    descriptions = []
    effect_type = wear_data_json.get("effect_type") 

    if effect_type == "reduced_battery_factor":
        value = wear_data_json.get("value", 1.0) 
        config_effect_info = Config.BLACKMARKET_STOLEN_ITEM_WEAR_EFFECTS.get("reduced_battery_factor", {})
        desc_template = config_effect_info.get("description_template")
        if desc_template:
            descriptions.append(desc_template.format(value * 100)) 
        else:
            descriptions.append(f"Батарея слегка изношена")
    elif effect_type == "increased_break_chance_factor":
        value = wear_data_json.get("value", 1.0)
        config_effect_info = Config.BLACKMARKET_STOLEN_ITEM_WEAR_EFFECTS.get("increased_break_chance_factor", {})
        desc_template = config_effect_info.get("description_template")
        if desc_template:
            descriptions.append(desc_template.format(value))
        else:
            descriptions.append(f"Будь аккуратным.")
    elif effect_type == "cosmetic_defect":
        defect_desc = wear_data_json.get("description", "незначительные потертости")
        descriptions.append(f"Косметический дефект: {html.escape(defect_desc)}.")

    if not descriptions:
        return "<i>Имеются следы былого использования.</i>"
    return "<i>" + " ".join(descriptions) + "</i>"

# --- НОВАЯ ФУНКЦИЯ ГЕНЕРАЦИИ ПЕРСОНАЛЬНЫХ ПРЕДЛОЖЕНИЙ ---
async def _generate_personal_bm_offers_for_user(user_id: int, conn_ext: Optional[database.asyncpg.Connection] = None) -> List[Dict[str, Any]]:
    """
    Генерирует персональный набор предложений Черного Рынка для пользователя.
    Возвращает список словарей, каждый из которых представляет данные для одного слота.
    """
    logger.info(f"BLACKMARKET: Генерация персональных предложений для user_id: {user_id}...")
    
    # Эту функцию нужно будет вызывать с conn_ext, если она вызывается из другой функции, уже имеющей соединение
    conn = conn_ext
    close_conn_finally = False
    if conn is None:
        conn = await database.get_connection()
        close_conn_finally = True

    generated_offers_data_list: List[Dict[str, Any]] = []
    generated_at_timestamp = datetime.now(dt_timezone.utc)

    try:
        # --- Логика, очень похожая на refresh_black_market_offers, но без очистки и записи в БД напрямую ---
        
        all_possible_regular_items = []
        for phone_key, phone_data in PHONE_MODELS_STD_DICT.items():
            all_possible_regular_items.append({"key": phone_key, "type": "phone", "data": phone_data})
        for comp_key, comp_data in PHONE_COMPONENTS.items():
            if comp_data.get("component_type") == "component":
                all_possible_regular_items.append({"key": comp_key, "type": "component", "data": comp_data})
        for case_key, case_data in PHONE_CASES.items():
            all_possible_regular_items.append({"key": case_key, "type": "case", "data": case_data})

        current_offers_for_list: List[Dict[str, Any]] = []

        # 1. Генерация "Краденого" телефона (1 слот)
        if Config.BLACKMARKET_NUM_STOLEN_ITEMS > 0 and PHONE_MODELS_STD_DICT:
            stolen_phone_key = random.choice(list(PHONE_MODELS_STD_DICT.keys()))
            stolen_phone_data = PHONE_MODELS_STD_DICT[stolen_phone_key]
            
            base_price = stolen_phone_data['price']
            price_after_inflation = await get_current_price(base_price, conn_ext=conn)
            
            ch_discount = random.uniform(Config.BLACKMARKET_REGULAR_ITEM_DISCOUNT_MIN, 
                                         Config.BLACKMARKET_REGULAR_ITEM_DISCOUNT_MAX)
            price_after_ch_discount = int(round(price_after_inflation * (1 - ch_discount)))

            stolen_add_discount = random.uniform(Config.BLACKMARKET_STOLEN_ITEM_ADDITIONAL_DISCOUNT_MIN,
                                                 Config.BLACKMARKET_STOLEN_ITEM_ADDITIONAL_DISCOUNT_MAX)
            final_stolen_price = int(round(price_after_ch_discount * (1 - stolen_add_discount)))
            if final_stolen_price < 1 and price_after_inflation > 0: final_stolen_price = 1

            wear_data = {}
            wear_effect_keys = list(Config.BLACKMARKET_STOLEN_ITEM_WEAR_EFFECTS.keys())
            # Убедимся, что cosmetic_defect_descriptions это список, а не ключ словаря
            valid_wear_effect_keys = [k for k in wear_effect_keys if k != "cosmetic_defect_descriptions"] # Исключаем его из прямого выбора
            if Config.BLACKMARKET_STOLEN_ITEM_WEAR_EFFECTS.get("cosmetic_defect_descriptions"):
                 valid_wear_effect_keys.append("cosmetic_defect_from_list") # Добавляем специальный ключ

            chosen_wear_effect_key = random.choice(valid_wear_effect_keys)
            
            if chosen_wear_effect_key == "reduced_battery_factor":
                min_f = Config.BLACKMARKET_STOLEN_ITEM_WEAR_EFFECTS["reduced_battery_factor"]["min_factor"]
                max_f = Config.BLACKMARKET_STOLEN_ITEM_WEAR_EFFECTS["reduced_battery_factor"]["max_factor"]
                wear_data = {"effect_type": "reduced_battery_factor", "value": round(random.uniform(min_f, max_f), 2)}
            elif chosen_wear_effect_key == "increased_break_chance_factor":
                min_f = Config.BLACKMARKET_STOLEN_ITEM_WEAR_EFFECTS["increased_break_chance_factor"]["min_factor"]
                max_f = Config.BLACKMARKET_STOLEN_ITEM_WEAR_EFFECTS["increased_break_chance_factor"]["max_factor"]
                wear_data = {"effect_type": "increased_break_chance_factor", "value": round(random.uniform(min_f, max_f), 2)}
            elif chosen_wear_effect_key == "cosmetic_defect_from_list": # Обработка нового ключа
                defect_desc_list = Config.BLACKMARKET_STOLEN_ITEM_WEAR_EFFECTS.get("cosmetic_defect_descriptions", [])
                if defect_desc_list:
                    defect_desc = random.choice(defect_desc_list)
                    wear_data = {"effect_type": "cosmetic_defect", "description": defect_desc}
            
            current_offers_for_list.append({
                "item_key": stolen_phone_key, "item_type": "phone",
                "display_name_override": f"{stolen_phone_data['name']} (Краденый)",
                "current_price": final_stolen_price,
                "original_price_before_bm": price_after_inflation,
                "is_stolen": True, "is_exclusive": False, "quantity_available": 1,
                "wear_data": wear_data if wear_data else None, "custom_data": None,
                "generated_at_utc": generated_at_timestamp # Добавляем время генерации
            })
            all_possible_regular_items = [item for item in all_possible_regular_items if item["key"] != stolen_phone_key or item["type"] != "phone"]

        # 2. Генерация "Обычных контрабандных" товаров
        num_regular_to_generate = Config.BLACKMARKET_TOTAL_SLOTS - len(current_offers_for_list)
        
        if all_possible_regular_items and num_regular_to_generate > 0:
            chosen_regular_items_data = random.sample(
                all_possible_regular_items, 
                min(num_regular_to_generate, len(all_possible_regular_items))
            )
            for item_info in chosen_regular_items_data:
                item_key = item_info["key"]
                item_type = item_info["type"]
                static_data = item_info["data"]
                
                base_price = static_data['price']
                price_after_inflation = await get_current_price(base_price, conn_ext=conn)
                
                ch_discount = random.uniform(Config.BLACKMARKET_REGULAR_ITEM_DISCOUNT_MIN, 
                                             Config.BLACKMARKET_REGULAR_ITEM_DISCOUNT_MAX)
                final_price = int(round(price_after_inflation * (1 - ch_discount)))
                if final_price < 1 and price_after_inflation > 0: final_price = 1

                quantity = 1
                if item_type == "component": quantity = random.randint(1, 3) 

                current_offers_for_list.append({
                    "item_key": item_key, "item_type": item_type,
                    "display_name_override": static_data.get('name'),
                    "current_price": final_price,
                    "original_price_before_bm": price_after_inflation,
                    "is_stolen": False, "is_exclusive": False, "quantity_available": quantity,
                    "wear_data": None, "custom_data": None,
                    "generated_at_utc": generated_at_timestamp
                })
        
        # 3. Шанс на замену одного "обычного" слота эксклюзивом
        if EXCLUSIVE_PHONE_MODELS_DICT or VINTAGE_PHONE_KEYS_FOR_BM:
            if random.random() < Config.BLACKMARKET_EXCLUSIVE_ITEM_CHANCE:
                eligible_slots_indices = [
                    idx for idx, offer in enumerate(current_offers_for_list) 
                    if not offer["is_stolen"] and not offer["is_exclusive"]
                ]
                if eligible_slots_indices:
                    slot_to_replace_idx = random.choice(eligible_slots_indices)
                    exclusive_type_choice = "custom"
                    if VINTAGE_PHONE_KEYS_FOR_BM and EXCLUSIVE_PHONE_MODELS_DICT:
                        exclusive_type_choice = random.choice(["custom", "vintage"])
                    elif VINTAGE_PHONE_KEYS_FOR_BM:
                        exclusive_type_choice = "vintage"
                    
                    exclusive_offer_data_dict: Optional[Dict[str, Any]] = None # Переименовано

                    if exclusive_type_choice == "custom" and EXCLUSIVE_PHONE_MODELS_DICT:
                        exclusive_key = random.choice(list(EXCLUSIVE_PHONE_MODELS_DICT.keys()))
                        excl_data = EXCLUSIVE_PHONE_MODELS_DICT[exclusive_key]
                        base_price_excl = excl_data['base_price']
                        price_after_inflation_excl = await get_current_price(base_price_excl, conn_ext=conn)
                        ch_discount_excl = random.uniform(Config.BLACKMARKET_REGULAR_ITEM_DISCOUNT_MIN, 
                                                          Config.BLACKMARKET_REGULAR_ITEM_DISCOUNT_MAX)
                        final_price_excl = int(round(price_after_inflation_excl * (1 - ch_discount_excl)))
                        if final_price_excl < 1 and price_after_inflation_excl > 0: final_price_excl = 1
                        
                        # Собираем custom_data для БД, включая bm_description
                        custom_data_for_db = excl_data.get("special_properties", {}).copy()
                        custom_data_for_db["bm_description"] = excl_data.get("bm_description", "Особый товар.")
                        # Если есть custom_bonus_description в special_properties, он уже там.
                        # Если он отдельно в excl_data, то:
                        # if "custom_bonus_description" in excl_data:
                        #    custom_data_for_db["custom_bonus_description"] = excl_data["custom_bonus_description"]

                        exclusive_offer_data_dict = {
                            "item_key": exclusive_key, "item_type": "phone",
                            "display_name_override": excl_data.get('display_name', excl_data['name']),
                            "current_price": final_price_excl,
                            "original_price_before_bm": price_after_inflation_excl,
                            "is_stolen": False, "is_exclusive": True, "quantity_available": 1,
                            "wear_data": None, 
                            "custom_data": custom_data_for_db, # Передаем собранные данные
                            "generated_at_utc": generated_at_timestamp
                        }
                    elif exclusive_type_choice == "vintage" and VINTAGE_PHONE_KEYS_FOR_BM:
                        vintage_key = random.choice(VINTAGE_PHONE_KEYS_FOR_BM)
                        if vintage_key in PHONE_MODELS_STD_DICT:
                            vintage_data = PHONE_MODELS_STD_DICT[vintage_key]
                            base_price_vint = vintage_data['price']
                            price_after_inflation_vint = await get_current_price(base_price_vint, conn_ext=conn)
                            ch_discount_vint = random.uniform(Config.BLACKMARKET_REGULAR_ITEM_DISCOUNT_MIN, 
                                                              Config.BLACKMARKET_REGULAR_ITEM_DISCOUNT_MAX)
                            final_price_vint = int(round(price_after_inflation_vint * (1 - ch_discount_vint)))
                            if final_price_vint < 1 and price_after_inflation_vint > 0: final_price_vint = 1

                            vintage_custom_data = {
                                "bm_description": f"Редкий винтажный экземпляр: {vintage_data.get('name', vintage_key)}. Находка для коллекционера!"
                            }
                            vintage_wear_data = {"effect_type": "cosmetic_defect", "description": "Заметные следы времени, но полностью функционален."}

                            exclusive_offer_data_dict = {
                                "item_key": vintage_key, "item_type": "phone",
                                "display_name_override": f"{vintage_data['name']} (Винтаж)",
                                "current_price": final_price_vint,
                                "original_price_before_bm": price_after_inflation_vint,
                                "is_stolen": False, "is_exclusive": True, "quantity_available": 1,
                                "wear_data": vintage_wear_data, 
                                "custom_data": vintage_custom_data,
                                "generated_at_utc": generated_at_timestamp
                            }
                    
                    if exclusive_offer_data_dict:
                        current_offers_for_list[slot_to_replace_idx] = exclusive_offer_data_dict
                        logger.info(f"BLACKMARKET (User: {user_id}): Слот {slot_to_replace_idx + 1} заменен эксклюзивом: {exclusive_offer_data_dict['item_key']}")
        
        # 4. Перемешивание и нумерация слотов
        # Краденый, если есть, всегда первый, остальные перемешиваются
        stolen_offer_data = None
        other_offers_data = []

        for offer in current_offers_for_list:
            if offer["is_stolen"]:
                stolen_offer_data = offer
            else:
                other_offers_data.append(offer)
        
        random.shuffle(other_offers_data)

        if stolen_offer_data:
            generated_offers_data_list.append(stolen_offer_data)
        generated_offers_data_list.extend(other_offers_data)

        # Обрезаем до Config.BLACKMARKET_TOTAL_SLOTS
        generated_offers_data_list = generated_offers_data_list[:Config.BLACKMARKET_TOTAL_SLOTS]
        
        # Присваиваем номера слотов (для удобства, хотя они уже в порядке)
        for idx, offer_d in enumerate(generated_offers_data_list):
            offer_d["slot_number"] = idx + 1

        logger.info(f"BLACKMARKET: Для user {user_id} сгенерировано {len(generated_offers_data_list)} персональных предложений.")

    except Exception as e:
        logger.error(f"BLACKMARKET: КРИТИЧЕСКАЯ ОШИБКА при генерации персональных предложений для user {user_id}: {e}", exc_info=True)
        # В случае ошибки возвращаем пустой список, чтобы не сломать вызывающую функцию
        return []
    finally:
        if close_conn_finally and conn and not conn.is_closed():
            await conn.close()
            
    return generated_offers_data_list


# --- ОБНОВЛЕННЫЕ КОМАНДЫ /blackmarket и /buybm ---

@black_market_router.message(Command(*Config.BLACKMARKET_COMMAND_ALIASES, ignore_case=True))
async def cmd_blackmarket_show(message: Message, bot: Bot): # bot нужен для send_telegram_log
    if not message.from_user:
        await message.reply("🥷 Не могу распознать, кто ты, чужак.")
        return

    user_id = message.from_user.id
    user_link = get_user_mention_html(user_id, message.from_user.full_name, message.from_user.username)

    can_access, access_denied_message = await check_black_market_access(user_id)
    if not can_access:
        await message.reply(access_denied_message, parse_mode="HTML")
        return

    conn = None
    try:
        conn = await database.get_connection()
        user_offers = await database.get_user_black_market_slots(user_id, conn_ext=conn)
        
        # Определяем начало текущего "периода ЧР"
        now_local = datetime.now(pytz_timezone(Config.TIMEZONE))
        reset_hour = Config.BLACKMARKET_RESET_HOUR
        current_period_start_local = now_local.replace(hour=reset_hour, minute=0, second=0, microsecond=0)
        if now_local.hour < reset_hour:
            current_period_start_local -= timedelta(days=1)
        current_period_start_utc = current_period_start_local.astimezone(dt_timezone.utc)

        # Проверяем, актуальны ли слоты или нужно их генерировать/регенерировать
        regenerate_slots = True # По умолчанию считаем, что нужно регенерировать
        if user_offers:
            # Проверяем дату генерации первого слота (предполагаем, что все слоты пользователя генерятся одновременно)
            first_slot_generated_at = user_offers[0].get('generated_at_utc')
            if first_slot_generated_at and isinstance(first_slot_generated_at, datetime):
                # Убедимся, что время из БД aware
                if first_slot_generated_at.tzinfo is None:
                     first_slot_generated_at = first_slot_generated_at.replace(tzinfo=dt_timezone.utc)
                else:
                     first_slot_generated_at = first_slot_generated_at.astimezone(dt_timezone.utc)

                if first_slot_generated_at >= current_period_start_utc:
                    regenerate_slots = False # Слоты актуальны
                else:
                    logger.info(f"BLACKMARKET: Слоты для user {user_id} устарели (сген: {first_slot_generated_at}, тек.период: {current_period_start_utc}). Регенерация.")
            else:
                logger.warning(f"BLACKMARKET: Некорректная дата генерации слотов для user {user_id}. Регенерация.")
        else: # Слотов нет
            logger.info(f"BLACKMARKET: Нет слотов для user {user_id}. Генерация.")


        if regenerate_slots:
            logger.info(f"BLACKMARKET: (Пере)генерация персональных слотов для user {user_id}...")
            # Используем conn, так как он уже открыт
            new_offers_data = await _generate_personal_bm_offers_for_user(user_id, conn_ext=conn)
            
            # Удаляем старые слоты пользователя (если были) и записываем новые в одной транзакции
            async with conn.transaction():
                await database.clear_user_black_market_slots(user_id, conn_ext=conn)
                for offer_slot_data in new_offers_data:
                    await database.add_user_black_market_slot(
                        user_id=user_id,
                        slot_number=offer_slot_data["slot_number"],
                        item_key=offer_slot_data["item_key"],
                        item_type=offer_slot_data["item_type"],
                        display_name_override=offer_slot_data.get("display_name_override"),
                        current_price=offer_slot_data["current_price"],
                        original_price_before_bm=offer_slot_data["original_price_before_bm"],
                        is_stolen=offer_slot_data["is_stolen"],
                        is_exclusive=offer_slot_data["is_exclusive"],
                        quantity_available=offer_slot_data["quantity_available"],
                        wear_data=offer_slot_data.get("wear_data"),
                        custom_data=offer_slot_data.get("custom_data"),
                        generated_at_utc=offer_slot_data["generated_at_utc"], # Передаем время генерации
                        conn_ext=conn
                    )
            user_offers = await database.get_user_black_market_slots(user_id, conn_ext=conn) # Получаем свежие слоты

        if not user_offers:
            await message.reply(
                f"🥷 {user_link}, похоже, сегодня на Чёрном Рынке для тебя пусто... или кто-то уже все раскупил.\n"
                f"Товар обновляется для каждого индивидуально при первом заходе после {Config.BLACKMARKET_RESET_HOUR:02d}:00 ({Config.TIMEZONE})."
            )
            return

        response_parts = [
            f"🥷 <b>Твой Персональный Чёрный Рынок</b> 🥷",
            f"{user_link}, вот что тени принесли сегодня на твои прилавки (цены уже включают 'особую' скидку):",
            "--------------------"
        ]

        # Сортируем user_offers по slot_number на всякий случай, хотя они должны приходить отсортированными
        user_offers.sort(key=lambda x: x.get('slot_number', 0))

        for offer in user_offers:
            if offer.get('is_purchased', False): # Пропускаем уже купленные слоты
                # Можно добавить сообщение о том, что слот куплен, или просто пропустить
                # response_parts.append(f"<b>Слот {offer['slot_number']}:</b> -- ПРОДАНО --")
                # response_parts.append("---")
                continue

            slot_num = offer['slot_number']
            item_key = offer['item_key']
            item_type = offer['item_type']
            display_name_override = offer.get('display_name_override')
            current_price = offer['current_price']
            original_price = offer['original_price_before_bm']
            quantity_available = offer['quantity_available'] # Для персональных слотов скорее всего всегда 1
            
            is_stolen = offer.get('is_stolen', False)
            is_exclusive = offer.get('is_exclusive', False)
            wear_data_from_db = offer.get('wear_data') 
            custom_data_from_db = offer.get('custom_data')

            item_name_display = ""
            item_description_details = []

            if display_name_override:
                item_name_display = html.escape(display_name_override)
            elif item_type == "phone":
                phone_info_std = PHONE_MODELS_STD_DICT.get(item_key)
                phone_info_excl = EXCLUSIVE_PHONE_MODELS_DICT.get(item_key)
                if phone_info_excl:
                    item_name_display = html.escape(phone_info_excl.get('display_name', phone_info_excl.get('name', item_key)))
                elif phone_info_std:
                    item_name_display = html.escape(phone_info_std.get('display_name', phone_info_std.get('name', item_key)))
                else:
                    item_name_display = f"Неизвестный телефон (<code>{html.escape(item_key)}</code>)"
            elif item_type == "component":
                comp_info = PHONE_COMPONENTS.get(item_key)
                item_name_display = html.escape(comp_info['name']) if comp_info else f"Компонент (<code>{html.escape(item_key)}</code>)"
            elif item_type == "case":
                case_info = PHONE_CASES.get(item_key)
                item_name_display = html.escape(case_info['name']) if case_info else f"Чехол (<code>{html.escape(item_key)}</code>)"
            else:
                item_name_display = f"Неизвестный товар (<code>{html.escape(item_key)}</code>)"

            offer_line = f"<b>Слот {slot_num}: {item_name_display}</b>"
            offer_line += f"\n   💰 Цена: <code>{current_price}</code> OC (<s>{original_price} OC</s>)"
            if quantity_available > 1 : # На всякий случай, если для компонентов оставим > 1
                 offer_line += f" | Доступно: {quantity_available} шт."
            else: # Для телефонов и чехлов, где quantity=1, "Доступно: 1 шт." можно опустить для краткости
                 pass


            if is_exclusive:
                offer_line += "\n   ✨ Эксклюзив Чёрного Рынка!"
                if custom_data_from_db and custom_data_from_db.get("bm_description"):
                    item_description_details.append(html.escape(custom_data_from_db["bm_description"]))
                if custom_data_from_db and custom_data_from_db.get("custom_bonus_description"):
                     item_description_details.append(f"Особое свойство: {html.escape(custom_data_from_db['custom_bonus_description'])}")

            if is_stolen:
                offer_line += "\n   훔 Краденый товар!"
                item_description_details.append(get_stolen_wear_description(wear_data_from_db))
            
            if item_type == "component":
                item_description_details.append(f"Риск брака (проявится при использовании)")
            elif item_type == "phone" and not is_stolen and not is_exclusive : # Обычный телефон с ЧР
                 item_description_details.append("Возможен сюрприз от продавца!")


            if item_description_details:
                offer_line += "\n   📝 " + " ".join(filter(None,item_description_details))
            
            offer_line += f"\n   <code>/{Config.BLACKMARKET_BUY_SLOT_ALIASES[0]} {slot_num}</code> - Купить"
            
            response_parts.append(offer_line)
            response_parts.append("---")
        
        response_parts.append("🥷 Помни, сделки здесь на твой страх и риск. Возврата нет.")

        full_response = "\n".join(response_parts)
        # ... (логика разбивки длинного сообщения, как в старой версии) ...
        MAX_MESSAGE_LENGTH = 4096
        if len(full_response) > MAX_MESSAGE_LENGTH:
            temp_parts = []
            current_part_msg = "" 
            for line in full_response.split('\n'):
                if len(current_part_msg) + len(line) + 1 > MAX_MESSAGE_LENGTH:
                    if current_part_msg: temp_parts.append(current_part_msg)
                    current_part_msg = line
                else:
                    if current_part_msg: current_part_msg += "\n" + line
                    else: current_part_msg = line
            if current_part_msg: temp_parts.append(current_part_msg)
            for part_msg_item in temp_parts: 
                if part_msg_item.strip(): await message.answer(part_msg_item, parse_mode="HTML", disable_web_page_preview=True); await asyncio.sleep(0.1)
        else:
            if full_response.strip(): await message.answer(full_response, parse_mode="HTML", disable_web_page_preview=True)

    except Exception as e_show_bm:
        logger.error(f"BlackMarketShow: Ошибка для user {user_id}: {e_show_bm}", exc_info=True)
        await message.reply("🥷 Тени сегодня неспокойны... Ошибка при показе рынка. Попробуй позже.")
    finally:
        if conn and not conn.is_closed():
            await conn.close()

@black_market_router.message(Command(*Config.BLACKMARKET_BUY_SLOT_ALIASES, ignore_case=True))
async def cmd_buy_bm_slot_start(message: Message, command: CommandObject, state: FSMContext, bot: Bot): # bot нужен для лога
    if not message.from_user:
        await message.reply("🥷 Я не знаю, кто ты. Представься сначала.")
        return

    user_id = message.from_user.id
    chat_id = message.chat.id 
    user_link = get_user_mention_html(user_id, message.from_user.full_name, message.from_user.username)

    can_access, access_denied_message = await check_black_market_access(user_id)
    if not can_access:
        await message.reply(access_denied_message, parse_mode="HTML")
        return

    args = command.args
    if not args:
        await message.reply(
            f"🥷 {user_link}, укажи номер слота, который приглянулся.\n"
            f"Пример: `/{Config.BLACKMARKET_BUY_SLOT_ALIASES[0]} 3`\n"
            f"Посмотреть товары: `/{Config.BLACKMARKET_COMMAND_ALIASES[0]}`"
        )
        return
    
    try:
        slot_to_buy = int(args.strip())
        if not (1 <= slot_to_buy <= Config.BLACKMARKET_TOTAL_SLOTS):
            raise ValueError("Неверный номер слота")
    except ValueError:
        await message.reply(f"🥷 {user_link}, номер слота должен быть числом от 1 до {Config.BLACKMARKET_TOTAL_SLOTS}.")
        return

    conn_buy_bm_start = None
    try:
        conn_buy_bm_start = await database.get_connection()
        # Получаем ПЕРСОНАЛЬНЫЙ слот пользователя
        offer_data = await database.get_specific_user_black_market_slot(user_id, slot_to_buy, conn_ext=conn_buy_bm_start)

        if not offer_data:
            await message.reply(f"🥷 {user_link}, товар в слоте {slot_to_buy} для тебя не найден или уже продан...")
            if conn_buy_bm_start and not conn_buy_bm_start.is_closed(): await conn_buy_bm_start.close()
            return
        
        if offer_data.get('is_purchased', False): # Проверяем флаг покупки
            await message.reply(f"🥷 {user_link}, ты уже купил товар из слота {slot_to_buy}.")
            if conn_buy_bm_start and not conn_buy_bm_start.is_closed(): await conn_buy_bm_start.close()
            return

        item_key = offer_data['item_key']
        item_type = offer_data['item_type']
        item_price = offer_data['current_price']
        item_name_display = offer_data.get('display_name_override') 

        if not item_name_display: # Логика получения имени, если нет display_name_override
            if item_type == "phone":
                phone_info = PHONE_MODELS_STD_DICT.get(item_key) or EXCLUSIVE_PHONE_MODELS_DICT.get(item_key)
                item_name_display = html.escape(phone_info.get('name', item_key)) if phone_info else f"Телефон ({item_key})"
            elif item_type == "component":
                item_name_display = html.escape(PHONE_COMPONENTS.get(item_key, {}).get('name', item_key))
            elif item_type == "case":
                item_name_display = html.escape(PHONE_CASES.get(item_key, {}).get('name', item_key))
            else: item_name_display = item_key
        else: item_name_display = html.escape(item_name_display)


        if item_type == 'phone':
            active_phones_count = await database.count_user_active_phones(user_id, conn_ext=conn_buy_bm_start)
            if active_phones_count >= Config.MAX_PHONES_PER_USER:
                await message.reply(
                    f"🥷 {user_link}, у тебя уже полный арсенал ({active_phones_count}/{Config.MAX_PHONES_PER_USER} телефонов). "
                    f"Избавься от старого, прежде чем брать новый."
                )
                if conn_buy_bm_start and not conn_buy_bm_start.is_closed(): await conn_buy_bm_start.close()
                return

            current_year_month = datetime.now(pytz_timezone(Config.TIMEZONE)).strftime("%Y-%m")
            phones_this_month = await database.get_user_bm_monthly_purchases(user_id, current_year_month, conn_ext=conn_buy_bm_start)
            if phones_this_month >= Config.BLACKMARKET_MAX_PHONES_PER_MONTH:
                await message.reply(
                    f"🥷 {user_link}, ты уже слишком много телефонов прикупил на Чёрном Рынке в этом месяце ({phones_this_month}/{Config.BLACKMARKET_MAX_PHONES_PER_MONTH}). "
                    f"Приходи в следующем."
                )
                if conn_buy_bm_start and not conn_buy_bm_start.is_closed(): await conn_buy_bm_start.close()
                return
        
        current_balance = await database.get_user_onecoins(user_id, chat_id, conn_ext=conn_buy_bm_start)
        if current_balance < item_price:
            await message.reply(
                f"🥷 {user_link}, не хватает монет для \"<b>{item_name_display}</b>\".\n"
                f"Нужно: {item_price} OC, у тебя: {current_balance} OC. Подкопи и возвращайся."
            )
            if conn_buy_bm_start and not conn_buy_bm_start.is_closed(): await conn_buy_bm_start.close()
            return
        
        await state.set_state(BlackMarketPurchaseStates.awaiting_confirmation)
        # Сохраняем весь offer_data, так как он содержит все нужные поля, включая wear_data и custom_data
        state_data_to_store = {
            "user_offer_data": offer_data, # Важно: передаем весь словарь оффера пользователя
            "confirmation_initiated_at": datetime.now(dt_timezone.utc).isoformat(),
            "original_chat_id": chat_id, 
            "original_user_id": user_id,
            "action_type": "buy_bm_slot_personal" # Новый тип для персональной покупки
        }
        await state.update_data(**state_data_to_store)

        confirmation_lines = [
            f"🥷 {user_link}, ты собираешься приобрести:",
            f"  <b>{item_name_display}</b> (Слот {slot_to_buy})",
            f"  Цена: <code>{item_price}</code> OneCoin(s)"
        ]
        if offer_data.get('is_exclusive'):
            confirmation_lines.append("  ✨ <i>Это эксклюзивный товар!</i>")
            if offer_data.get('custom_data') and offer_data['custom_data'].get('bm_description'):
                 confirmation_lines.append(f"  📝 <i>{html.escape(offer_data['custom_data']['bm_description'])}</i>")
            if offer_data.get('custom_data') and offer_data['custom_data'].get('custom_bonus_description'):
                 confirmation_lines.append(f"  💡 <i>Особое свойство: {html.escape(offer_data['custom_data']['custom_bonus_description'])}</i>")
        if offer_data.get('is_stolen'):
            confirmation_lines.append("  훔 Это краденый товар!")
            confirmation_lines.append(f"  {get_stolen_wear_description(offer_data.get('wear_data'))}")
        if item_type == "component":
             confirmation_lines.append(f"  Риск брака: {Config.BLACKMARKET_COMPONENT_DEFECT_CHANCE*100:.0f}% (проявится при использовании)!")
        elif item_type == "phone" and not offer_data.get('is_stolen') and not offer_data.get('is_exclusive'):
             confirmation_lines.append("  Возможен сюрприз от продавца (например, другой цвет или дефект)!")

        confirmation_lines.append(f"\nТвой баланс: {current_balance} OneCoin(s).")
        confirmation_lines.append(f"Ответь '<b>Да</b>' или '<b>Нет</b>' в течение {Config.MARKET_PHONE_CONFIRMATION_TIMEOUT_SECONDS} секунд.")
        
        await message.reply("\n".join(confirmation_lines), parse_mode="HTML")

    except Exception as e_buy_bm_start:
        logger.error(f"BuyBlackMarketSlot (Personal): Ошибка на старте покупки для user {user_id}, слот {slot_to_buy}: {e_buy_bm_start}", exc_info=True)
        await message.reply("🥷 Что-то пошло не так в тенях... Попробуй позже.")
        await state.clear() 
    finally:
        if conn_buy_bm_start and not conn_buy_bm_start.is_closed():
            await conn_buy_bm_start.close()


# --- Хендлеры FSM для BlackMarketPurchaseStates ---
# В cmd_bm_purchase_confirm_yes меняем логику получения оффера и его обновления

@black_market_router.message(BlackMarketPurchaseStates.awaiting_confirmation, F.text.lower() == "да")
async def cmd_bm_purchase_confirm_yes(message: Message, state: FSMContext, bot: Bot):
    if not message.from_user: 
        await message.reply("🥷 Не могу понять, кто ты. Похоже, сделка сорвалась.")
        await state.clear(); return

    user_id = message.from_user.id
    user_data_from_state = await state.get_data()
    state_user_id = user_data_from_state.get('original_user_id')
    original_chat_id_for_onecoin = user_data_from_state.get('original_chat_id')
    action_type = user_data_from_state.get('action_type')
    
    if state_user_id != user_id or action_type != "buy_bm_slot_personal": # Проверяем новый тип действия
        logger.warning(f"BLACKMARKET FSM (Personal): Попытка подтверждения от user {user_id} для state user {state_user_id} или action_type '{action_type}'. Игнорируется.")
        return

    user_link = get_user_mention_html(user_id, message.from_user.full_name, message.from_user.username)
    
    # Получаем данные ОФФЕРА ПОЛЬЗОВАТЕЛЯ из state
    user_offer_data_from_state: Optional[Dict] = user_data_from_state.get('user_offer_data') 
    confirmation_initiated_at_iso = user_data_from_state.get('confirmation_initiated_at')
    
    item_name_for_msg = html.escape(user_offer_data_from_state.get('display_name_override') or user_offer_data_from_state.get('item_key', 'товар с ЧР')) if user_offer_data_from_state else 'товар с ЧР'

    if not user_offer_data_from_state or not confirmation_initiated_at_iso:
        await message.reply("🥷 Сделка провалилась из-за ошибки в данных. Попробуй снова.")
        logger.error(f"BLACKMARKET FSM (Personal) Confirm YES: Отсутствуют user_offer_data или confirmation_initiated_at_iso в state для user {user_id}")
        await state.clear(); return

    timeout_seconds = Config.MARKET_PHONE_CONFIRMATION_TIMEOUT_SECONDS 
    try:
        confirmation_initiated_at = datetime.fromisoformat(confirmation_initiated_at_iso)
        if (datetime.now(dt_timezone.utc) - confirmation_initiated_at) > timedelta(seconds=timeout_seconds):
            await message.reply(f"🥷 Время на раздумья вышло, {user_link}. Товар \"<b>{item_name_for_msg}</b>\" уплыл обратно в тени.", parse_mode="HTML")
            await state.clear(); return
    except ValueError:
        await message.reply("🥷 Ошибка во времени сделки. Начните сначала.")
        logger.error(f"BLACKMARKET FSM (Personal) Confirm YES: ValueError парсинга confirmation_initiated_at_iso для user {user_id}.")
        await state.clear(); return

    conn = None
    try:
        conn = await database.get_connection()
        async with conn.transaction():
            slot_number_to_buy = user_offer_data_from_state['slot_number']
            
            # Повторная проверка доступности ПЕРСОНАЛЬНОГО слота и что он не куплен
            live_user_offer_data = await database.get_specific_user_black_market_slot(user_id, slot_number_to_buy, conn_ext=conn)

            if not live_user_offer_data or live_user_offer_data.get('is_purchased', True): # Если не найден или уже куплен
                await message.reply(f"🥷 Упс, {user_link}! Пока ты думал, товар \"<b>{item_name_for_msg}</b>\" из этого слота уже был куплен тобой или исчез!", parse_mode="HTML")
                await state.clear(); return 
            
            # Проверяем, не изменился ли сам товар в слоте (маловероятно для персональных, но на всякий случай)
            if live_user_offer_data['item_key'] != user_offer_data_from_state['item_key'] or \
               live_user_offer_data['current_price'] != user_offer_data_from_state['current_price']:
                await message.reply(f"🥷 Странно... Товар в слоте {slot_number_to_buy} изменился, пока ты раздумывал. Посмотри снова: `/{Config.BLACKMARKET_COMMAND_ALIASES[0]}`")
                logger.warning(f"BLACKMARKET FSM (Personal): Товар в слоте {slot_number_to_buy} для user {user_id} изменился между FSM start и confirm.")
                await state.clear(); return

            item_price = live_user_offer_data['current_price']
            item_type = live_user_offer_data['item_type']
            item_key = live_user_offer_data['item_key']

            current_balance = await database.get_user_onecoins(user_id, original_chat_id_for_onecoin, conn_ext=conn)
            if current_balance < item_price:
                await message.reply(f"🥷 {user_link}, твои карманы пусты! Нужно {item_price} OC для \"<b>{item_name_for_msg}</b>\", а у тебя лишь {current_balance}.", parse_mode="HTML")
                await state.clear(); return

            if item_type == 'phone':
                active_phones_count = await database.count_user_active_phones(user_id, conn_ext=conn)
                if active_phones_count >= Config.MAX_PHONES_PER_USER:
                    await message.reply(f"🥷 {user_link}, у тебя и так слишком много телефонов ({active_phones_count}/{Config.MAX_PHONES_PER_USER}).")
                    await state.clear(); return
                
                current_year_month = datetime.now(pytz_timezone(Config.TIMEZONE)).strftime("%Y-%m")
                phones_this_month = await database.get_user_bm_monthly_purchases(user_id, current_year_month, conn_ext=conn)
                if phones_this_month >= Config.BLACKMARKET_MAX_PHONES_PER_MONTH:
                    await message.reply(f"🥷 {user_link}, ты исчерпал свой лимит на телефоны с ЧР в этом месяце.")
                    await state.clear(); return
            
            # 1. Помечаем ПЕРСОНАЛЬНЫЙ слот как купленный
            slot_marked_purchased = await database.mark_user_bm_slot_as_purchased(user_id, slot_number_to_buy, conn_ext=conn)
            if not slot_marked_purchased: 
                await message.reply(f"🥷 Невероятно! Товар \"<b>{item_name_for_msg}</b>\" не удалось отметить как купленный! Попробуй другой.", parse_mode="HTML")
                logger.error(f"BLACKMARKET FSM (Personal): Не удалось пометить слот {slot_number_to_buy} user {user_id} как купленный.")
                await state.clear(); return

            # 2. Списываем OneCoin
            user_db_data_for_log = await database.get_user_data_for_update(user_id, original_chat_id_for_onecoin, conn_ext=conn)
            new_balance = await database.update_user_onecoins(
                user_id, original_chat_id_for_onecoin, -item_price,
                username=user_db_data_for_log.get('username'), 
                full_name=user_db_data_for_log.get('full_name'),
                chat_title=user_db_data_for_log.get('chat_title'), 
                conn_ext=conn
            )

            # 3. Добавляем товар игроку (логика как раньше, но данные из live_user_offer_data)
            purchase_time_utc = datetime.now(dt_timezone.utc)
            final_item_data_to_store_in_db: Optional[Dict] = None 
            
            log_item_name = live_user_offer_data.get('display_name_override') or item_key
            log_item_details = f"(Слот: {slot_number_to_buy}, Ключ: {item_key}, Тип: {item_type}"
            if live_user_offer_data.get('is_stolen'): log_item_details += ", Краденый"
            if live_user_offer_data.get('is_exclusive'): log_item_details += ", Эксклюзив"
            log_item_details += ")"

            if item_type == 'phone':
                phone_static_data_std = PHONE_MODELS_STD_DICT.get(item_key)
                phone_static_data_excl = EXCLUSIVE_PHONE_MODELS_DICT.get(item_key)
                phone_static_data_source = phone_static_data_excl or phone_static_data_std

                if not phone_static_data_source:
                    logger.error(f"BLACKMARKET FSM (Personal): Не найдены статические данные для телефона {item_key} при покупке user {user_id}.")
                    raise Exception("Ошибка данных телефона при покупке.")

                initial_memory_gb_str = phone_static_data_source.get('memory', '0GB')
                initial_memory_gb = 0 # ... (логика парсинга initial_memory_gb как раньше) ...
                if 'TB' in initial_memory_gb_str.upper():
                    try: initial_memory_gb = int(float(initial_memory_gb_str.upper().replace('TB','').strip())*1024)
                    except ValueError: initial_memory_gb = 1024 
                elif 'GB' in initial_memory_gb_str.upper():
                    try: initial_memory_gb = int(float(initial_memory_gb_str.upper().replace('GB','').strip()))
                    except ValueError: initial_memory_gb = 0 


                phone_color = random.choice(PHONE_COLORS) 
                # final_item_data_to_store_in_db теперь берется из custom_data и wear_data оффера пользователя
                final_item_data_to_store_in_db = (live_user_offer_data.get('custom_data') or {}).copy()
                if live_user_offer_data.get('wear_data'):
                    final_item_data_to_store_in_db.update(live_user_offer_data['wear_data'])

                if live_user_offer_data.get('is_exclusive') and final_item_data_to_store_in_db.get('fixed_color'):
                    phone_color = final_item_data_to_store_in_db['fixed_color']
                    log_item_details += f", Фикс. цвет: {phone_color}"
                else: 
                    if random.random() < Config.BLACKMARKET_UNTRUSTED_SELLER_CHANCE:
                        original_intended_color = phone_color
                        phone_color = random.choice(PHONE_COLORS) 
                        if "cosmetic_defect" not in final_item_data_to_store_in_db and \
                           "cosmetic_defect_descriptions" in Config.BLACKMARKET_STOLEN_ITEM_WEAR_EFFECTS and \
                           Config.BLACKMARKET_STOLEN_ITEM_WEAR_EFFECTS["cosmetic_defect_descriptions"]: # Проверка на пустоту
                            defect_desc_seller = random.choice(Config.BLACKMARKET_STOLEN_ITEM_WEAR_EFFECTS["cosmetic_defect_descriptions"])
                            final_item_data_to_store_in_db["cosmetic_defect"] = defect_desc_seller
                            final_item_data_to_store_in_db["effect_type"] = "cosmetic_defect" # Добавляем тип эффекта, если его не было
                            final_item_data_to_store_in_db["description"] = defect_desc_seller # И описание
                            logger.info(f"BLACKMARKET (Personal): Ненадежный продавец! User {user_id} товар {item_key} с дефектом: '{defect_desc_seller}' или цветом {phone_color} (вместо {original_intended_color}).")
                            log_item_details += f", Сюрприз от продавца (цвет/дефект)!"
                        else: 
                             logger.info(f"BLACKMARKET (Personal): Ненадежный продавец! User {user_id} товар {item_key} цветом {phone_color} (вместо {original_intended_color}).")
                             log_item_details += f", Сюрприз от продавца (цвет)!"

                new_phone_id = await database.add_phone_to_user_inventory(
                    user_id, original_chat_id_for_onecoin, item_key, phone_color,
                    item_price, purchase_time_utc, initial_memory_gb, 
                    is_contraband=True, # Все с ЧР - контрабанда
                    custom_phone_data_json=final_item_data_to_store_in_db if final_item_data_to_store_in_db else None,
                    conn_ext=conn
                )
                if not new_phone_id:
                    raise Exception(f"Не удалось добавить телефон {item_key} в инвентарь user {user_id}.")
                
                await database.increment_user_bm_monthly_purchase(user_id, current_year_month, conn_ext=conn)
                log_item_details += f", Инв.ID: {new_phone_id}"

            elif item_type == 'component':
                final_item_data_to_store_in_db = {"is_bm_contraband": True, "is_defective": False}
                if random.random() < Config.BLACKMARKET_COMPONENT_DEFECT_CHANCE:
                    final_item_data_to_store_in_db["is_defective"] = True
                    log_item_details += ", БРАКОВАННЫЙ!"
                
                add_comp_success = await database.add_item_to_user_inventory(
                    user_id, item_key, item_type, 
                    quantity_to_add=live_user_offer_data['quantity_available'], 
                    item_data_json=final_item_data_to_store_in_db, 
                    conn_ext=conn
                )
                if not add_comp_success:
                     raise Exception(f"Не удалось добавить компонент {item_key} в инвентарь user {user_id}.")
            
            elif item_type == 'case':
                final_item_data_to_store_in_db = {"is_bm_contraband": True}
                add_case_success = await database.add_item_to_user_inventory(
                    user_id, item_key, item_type, 
                    quantity_to_add=1, 
                    item_data_json=final_item_data_to_store_in_db,
                    conn_ext=conn
                )
                if not add_case_success:
                    raise Exception(f"Не удалось добавить чехол {item_key} в инвентарь user {user_id}.")
            
            success_message_parts = [
                f"🥷 Сделка совершена, {user_link}!",
                f"Ты заполучил \"<b>{item_name_for_msg}</b>\" за <code>{item_price}</code> OneCoin(s).",
            ]
            if item_type == "phone": success_message_parts.append("<i>Не забывай, контрабанда – это всегда повышенный риск поломки!</i>")
            if item_type == "component" and final_item_data_to_store_in_db and final_item_data_to_store_in_db.get("is_defective"):
                success_message_parts.append("<i>Хм, этот компонент выглядит подозрительно... Надеюсь, он сработает.</i>")
            elif item_type == "component":
                 success_message_parts.append("<i>Надеюсь, этот компонент не подведет...</i>")
            success_message_parts.append(f"Твой новый баланс: <code>{new_balance}</code> OneCoin(s).")
            await message.reply("\n".join(success_message_parts), parse_mode="HTML")

            chat_title_log = html.escape(message.chat.title or f"Чат ID {original_chat_id_for_onecoin}")
            await send_telegram_log(
                bot,
                f"🥷 <b>Покупка на Персональном ЧР</b>\n"
                f"Пользователь: {user_link} (ID: <code>{user_id}</code>)\n"
                f"Чат: {chat_title_log} (ID: <code>{original_chat_id_for_onecoin}</code>)\n"
                f"Товар: \"{item_name_for_msg}\" {log_item_details}\n"
                f"Цена: <code>{item_price}</code> OC. Новый баланс: <code>{new_balance}</code> OC."
            )
            
            # --- ВЫЗОВ ПРОВЕРКИ ДОСТИЖЕНИЙ ---
            kwargs_for_achievements = {
                "bm_buy_just_now": True, # Для "Шепот Из Тьмы"
                "bm_buy_total_count": 1, # Заглушка, нужно получать из БД
                "bm_buy_components_total_count": 0, # Заглушка
                "bm_buy_case_just_now": False, # Заглушка
                "bm_buy_phone_wrong_color_just_now": False, # Заглушка
                "bm_buy_phone_cosmetic_defect_just_now": False, # Заглушка
                "bm_buy_vintage_phone_just_now": False, # Заглушка
                "bm_buy_component_defective_just_now": False, # Заглушка
                "bm_buy_component_not_defective_just_now": False, # Заглушка
                "bm_buy_stolen_phone_total_count": 0, # Заглушка
                "bm_buy_exclusive_phone_total_count": 0, # Заглушка
            }

            if item_type == 'phone':
                # Для достижений, связанных с типами телефонов из ЧР
                if live_user_offer_data.get('is_stolen'):
                    kwargs_for_achievements["bm_buy_stolen_phone_total_count"] = 1 # Заглушка
                if live_user_offer_data.get('is_exclusive'):
                    kwargs_for_achievements["bm_buy_exclusive_phone_total_count"] = 1 # Заглушка
                # Достижение "Искатель Потерянных Святынь"
                if item_key in VINTAGE_PHONE_KEYS_FOR_BM: # VINTAGE_PHONE_KEYS_FOR_BM должен быть импортирован или доступен
                     kwargs_for_achievements["bm_buy_vintage_phone_just_now"] = True
                # Достижения по дефектам/цвету
                if final_item_data_to_store_in_db and final_item_data_to_store_in_db.get("cosmetic_defect"):
                    kwargs_for_achievements["bm_buy_phone_cosmetic_defect_just_now"] = True
                # Проверка на "не тот" цвет требует сравнения с оригинальным, что не передается в state.
                # Для "Ненадежный Поставщик" (цвет) нужно будет добавить флаг, когда это произойдет
                # Например, если random.random() < Config.BLACKMARKET_UNTRUSTED_SELLER_CHANCE сработал
                # и color != original_intended_color. Это уже было в логике black_market_logic.py
                # где-то до этого.
                if "bm_buy_phone_wrong_color_just_now" in kwargs_for_checks:
                     kwargs_for_achievements["bm_buy_phone_wrong_color_just_now"] = kwargs_for_checks["bm_buy_phone_wrong_color_just_now"]


            elif item_type == 'component':
                kwargs_for_achievements["bm_buy_components_total_count"] = 1 # Заглушка
                if final_item_data_to_store_in_db and final_item_data_to_store_in_db.get("is_defective"):
                    kwargs_for_achievements["bm_buy_component_defective_just_now"] = True
                    kwargs_for_achievements["bm_buy_defective_component_total_count"] = 1 # Заглушка
                else:
                    kwargs_for_achievements["bm_buy_component_not_defective_just_now"] = True
            elif item_type == 'case':
                kwargs_for_achievements["bm_buy_case_just_now"] = True

            await check_and_grant_achievements(
                user_id,
                original_chat_id_for_onecoin,
                bot,
                **kwargs_for_achievements
            )
            # --- КОНЕЦ ВЫЗОВА ПРОВЕРКИ ДОСТИЖЕНИЙ ---
            
    except Exception as e_confirm_bm_yes:
        logger.error(f"BLACKMARKET FSM (Personal) Confirm YES: Ошибка при подтверждении покупки для user {user_id}, товар '{item_name_for_msg}': {e_confirm_bm_yes}", exc_info=True)
        await message.reply(f"🥷 Ошибка в тенях! Сделка по \"<b>{item_name_for_msg}</b>\" сорвалась. Твои монеты на месте... пока что.", parse_mode="HTML")
    finally:
        if conn and not conn.is_closed():
            await conn.close()
        await state.clear()

@black_market_router.message(BlackMarketPurchaseStates.awaiting_confirmation, F.text.lower() == "нет")
async def cmd_bm_purchase_confirm_no(message: Message, state: FSMContext):
    # ... (код без изменений, только в логе можно указать (Personal))
    if not message.from_user: return
    user_id = message.from_user.id
    user_data_from_state = await state.get_data()
    state_user_id = user_data_from_state.get('original_user_id')
    action_type = user_data_from_state.get('action_type')

    if state_user_id != user_id or action_type != "buy_bm_slot_personal": return # Проверяем новый тип

    offer_data_from_state: Optional[Dict] = user_data_from_state.get('user_offer_data') # Используем user_offer_data
    item_name_for_msg = "товар с ЧР"
    if offer_data_from_state:
        item_name_for_msg = html.escape(offer_data_from_state.get('display_name_override') or offer_data_from_state.get('item_key', 'товар с ЧР'))
    
    user_link = get_user_mention_html(user_id, message.from_user.full_name, message.from_user.username)
    await message.reply(f"🥷 Мудрое решение, {user_link}. Сделка по \"<b>{item_name_for_msg}</b>\" отменена. Тени отступают... на время.", parse_mode="HTML")
    await state.clear()

@black_market_router.message(BlackMarketPurchaseStates.awaiting_confirmation)
async def cmd_bm_purchase_invalid_confirmation(message: Message, state: FSMContext):
    # ... (код без изменений, только в логе можно указать (Personal))
    if not message.from_user: return
    user_id = message.from_user.id
    user_data_from_state = await state.get_data()
    state_user_id = user_data_from_state.get('original_user_id')
    action_type = user_data_from_state.get('action_type')

    if state_user_id != user_id or action_type != "buy_bm_slot_personal": return # Проверяем новый тип

    confirmation_initiated_at_iso = user_data_from_state.get('confirmation_initiated_at')
    offer_data_from_state: Optional[Dict] = user_data_from_state.get('user_offer_data') # Используем user_offer_data
    item_name_for_msg = "товар с ЧР"
    if offer_data_from_state:
        item_name_for_msg = html.escape(offer_data_from_state.get('display_name_override') or offer_data_from_state.get('item_key', 'товар с ЧР'))

    timeout_seconds = Config.MARKET_PHONE_CONFIRMATION_TIMEOUT_SECONDS

    if confirmation_initiated_at_iso:
        try:
            confirmation_initiated_at = datetime.fromisoformat(confirmation_initiated_at_iso)
            if (datetime.now(dt_timezone.utc) - confirmation_initiated_at) > timedelta(seconds=timeout_seconds):
                await state.clear()
                await message.reply(f"🥷 Тени не ждут вечно. Время на сделку по \"<b>{item_name_for_msg}</b>\" истекло.", parse_mode="HTML")
                return
        except ValueError: 
            await state.clear()
            await message.reply("🥷 Временной парадокс! Ошибка состояния сделки. Начните сначала.")
            return
    
    await message.reply("🥷 Решайся, да или нет? Тени не любят неопределенности.")


# Функция refresh_black_market_offers (ГЛОБАЛЬНАЯ) больше не нужна для персонального ЧР.
# Удаляем ее или комментируем. Если вы хотите оставить возможность глобального принудительного
# сброса персональных слотов для ВСЕХ пользователей (например, админ-командой),
# то можно будет создать отдельную функцию для этого.

async def refresh_black_market_offers(bot: Optional[Bot] = None): # <--- НАЧИНАЕТСЯ С КРАЯ
    logger.info("BLACKMARKET: Начало обновления ассортимента Черного Рынка...") # <--- ОТСТУП ВНУТРИ ФУНКЦИИ
    conn = None
    generated_offers_count = 0
    try: # <--- ОТСТУП ВНУТРИ ФУНКЦИИ
        conn = await database.get_connection()
        # ... остальной код функции refresh_black_market_offers с таким же отступом ...
    except Exception as e: # <--- ОТСТУП ВНУТРИ ФУНКЦИИ
        logger.error(f"BLACKMARKET: КРИТИЧЕСКАЯ ОШИБКА ...", exc_info=True)
    finally: # <--- ОТСТУП ВНУТРИ ФУНКЦИИ
        if conn and not conn.is_closed():
            await conn.close()


def setup_black_market_handlers(dp: Router):
    dp.include_router(black_market_router)
    logger.info("Обработчики команд Чёрного Рынка (персонального) зарегистрированы.")