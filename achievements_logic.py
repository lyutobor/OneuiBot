# achievements_logic.py

import logging
import html
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Set
import pytz # Импортируем pytz для работы с часовыми поясами
from datetime import timezone as dt_timezone # Импортируем конкретно timezone из datetime

from aiogram import Router, Bot
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, Chat


# Импорты из вашего проекта
from config import Config # Мы всё ещё импортируем Config для других настроек
import database # Импортируем модуль database целиком
from utils import get_user_mention_html, send_telegram_log, fetch_user_display_data, resolve_target_user
from business_data import BUSINESS_DATA, BUSINESS_UPGRADES # Для проверки achievement_type: business_buy_all_upgrades_for_one
from item_data import PHONE_COMPONENTS, PHONE_CASES # Для проверки наличия всех апгрейдов по бизнесу и информации о телефонах
from exclusive_phone_data import VINTAGE_PHONE_KEYS_FOR_BM # Для BM достижений

logger = logging.getLogger(__name__)
achievements_router = Router()

# --- ВЫНОСИМ ОБЪЕКТЫ ЧАСОВЫХ ПОЯСОВ НАПРЯМУЮ СЮДА ---
# Создаем объект часового пояса для использования в этом модуле,
# используя Config.TIMEZONE.
LOCAL_TIMEZONE_OBJ = pytz.timezone(Config.TIMEZONE)
UTC_TIMEZONE_OBJ = dt_timezone.utc
# --- КОНЕЦ ВЫНОСА ---


async def check_and_grant_achievements(
    user_id: int,
    chat_id: int, # chat_id, где произошло действие, чтобы ответить туда же
    bot_instance: Bot,
    # **kwargs_for_checks позволяет передавать любые данные, специфичные для текущего действия.
    # Например: current_oneui_version=X.X, onecoin_change=Y, phone_type_bought="A", etc.
    message_thread_id: Optional[int] = None,
    **kwargs_for_checks: Any
):
    """
    Центральная функция для проверки и выдачи достижений.
    Вызывается после каждого действия пользователя, которое может привести к получению достижения.
    """
    user_link = ""
    try:
        # Получаем актуальные данные пользователя для упоминания
        user_data_db = await database.get_user_data_for_update(user_id, chat_id)
        user_full_name = user_data_db.get('full_name')
        user_username = user_data_db.get('username')
        user_link = get_user_mention_html(user_id, user_full_name, user_username)

        # Получаем все уже полученные достижения пользователя
        user_unlocked_achievements = await database.get_user_achievements(user_id)
        unlocked_keys = {a['achievement_key'] for a in user_unlocked_achievements}
        
        # Для прогрессивных достижений, которые уже начаты, но не завершены
        # achievements_with_progress теперь используется для получения текущего прогресса достижения
        achievements_with_progress: Dict[str, Dict[str, Any]] = {
            a['achievement_key']: a for a in user_unlocked_achievements if a['progress_data'] is not None
        }

        user_metrics: Dict[str, Any] = {} # Кэш для метрик пользователя

        # Собираем актуальные данные, необходимые для проверок
        # Делаем это ОДИН РАЗ, если соответствующее достижение еще не разблокировано.
        async def get_metric(metric_key: str):
            if metric_key not in user_metrics:
                if metric_key == "current_oneui_version":
                    user_metrics[metric_key] = await database.get_user_version(user_id, chat_id)
                elif metric_key == "current_onecoin_balance":
                    user_metrics[metric_key] = await database.get_user_onecoins(user_id, chat_id)
                elif metric_key == "current_daily_streak":
                    streak_data = await database.get_user_daily_streak(user_id, chat_id)
                    current_streak = 0
                    if streak_data and streak_data.get('last_streak_check_date'):
                        today_local_date = datetime.now(LOCAL_TIMEZONE_OBJ).date()
                        last_check_date = streak_data['last_streak_check_date']
                        if last_check_date == today_local_date or last_check_date == (today_local_date - timedelta(days=1)):
                            current_streak = streak_data.get('current_streak', 0)
                    user_metrics[metric_key] = current_streak
                elif metric_key == "user_businesses_active":
                    user_metrics[metric_key] = await database.get_user_businesses(user_id, chat_id)
                elif metric_key == "user_phones_active":
                    user_metrics[metric_key] = await database.get_user_phones(user_id, active_only=True)
                elif metric_key == "user_phones_all_time": # Для коллекционеров серий
                    user_metrics[metric_key] = await database.get_user_phones(user_id, active_only=False)
                elif metric_key == "user_bank_level":
                    bank_data = await database.get_user_bank(user_id, chat_id)
                    user_metrics[metric_key] = bank_data['bank_level'] if bank_data else 0
                elif metric_key == "business_total_staff_hired":
                    all_user_biz = await database.get_user_businesses(user_id, chat_id)
                    user_metrics[metric_key] = sum(b['staff_hired_slots'] for b in all_user_biz)
                elif metric_key == "business_owned_all_count":
                    all_user_biz = await database.get_user_businesses(user_id, chat_id)
                    user_metrics[metric_key] = len({b['business_key'] for b in all_user_biz}) # Количество уникальных бизнесов
                elif metric_key == "family_leader_members_count" or metric_key == "family_total_members_count":
                    family_membership = await database.get_user_family_membership(user_id)
                    if family_membership:
                        members_data = await database.get_family_members(family_membership['family_id'])
                        user_metrics[metric_key] = len(members_data)
                    else:
                        user_metrics[metric_key] = 0
                elif metric_key == "phone_series_collected_A_keys":
                    user_phones_all = await database.get_user_phones(user_id, active_only=False)
                    # Используем set, чтобы автоматически обрабатывать уникальность
                    user_metrics[metric_key] = {p['phone_model_key'] for p in user_phones_all if p['phone_model_key'].startswith('galaxy_a')}
                elif metric_key == "phone_series_collected_S_keys":
                    user_phones_all = await database.get_user_phones(user_id, active_only=False)
                    user_metrics[metric_key] = {p['phone_model_key'] for p in user_phones_all if p['phone_model_key'].startswith('galaxy_s')}
                elif metric_key == "phone_series_collected_Z_keys":
                    user_phones_all = await database.get_user_phones(user_id, active_only=False)
                    user_metrics[metric_key] = {p['phone_model_key'] for p in user_phones_all if p['phone_model_key'].startswith('galaxy_z')}
                # ... добавить другие метрики, которые могут понадобиться ...
            return user_metrics.get(metric_key)

        for achievement_key, achievement_info in Config.ACHIEVEMENTS_DATA.items():
            if achievement_key in unlocked_keys:
                continue # Пропускаем уже полученные достижения

            unlocked = False
            progress_data_to_save: Optional[Dict] = None
            
            # --- Логика проверки условий для каждого типа достижения ---

            # OneUI-Мастерство
            if achievement_info["type"] == "oneui_version":
                current_version = kwargs_for_checks.get("current_oneui_version")
                if current_version is None: current_version = await get_metric("current_oneui_version")
                if current_version is not None and current_version >= achievement_info["target_value"]:
                    unlocked = True
            elif achievement_info["type"] == "oneui_version_negative":
                current_version = kwargs_for_checks.get("current_oneui_version")
                if current_version is None: current_version = await get_metric("current_oneui_version")
                if current_version is not None and current_version < achievement_info["target_value"]:
                    unlocked = True
            elif achievement_info["type"] == "oneui_version_negative_threshold":
                current_version = kwargs_for_checks.get("current_oneui_version")
                if current_version is None: current_version = await get_metric("current_oneui_version")
                if current_version is not None and current_version <= achievement_info["target_value"]:
                    unlocked = True

            # Финансовые Успехи
            elif achievement_info["type"] == "onecoin_balance":
                current_balance = kwargs_for_checks.get("current_onecoin_balance")
                if current_balance is None: current_balance = await get_metric("current_onecoin_balance")
                if current_balance is not None and current_balance >= achievement_info["target_value"]:
                    unlocked = True

            # Достижения Стриков
            elif achievement_info["type"] == "daily_streak":
                current_streak = kwargs_for_checks.get("current_daily_streak")
                if current_streak is None: current_streak = await get_metric("current_daily_streak")
                if current_streak is not None and current_streak >= achievement_info["target_value"]:
                    unlocked = True

            # Телефонные Достижения
            elif achievement_info["type"] == "phone_owned_total":
                if kwargs_for_checks.get("phone_bought_just_now"):
                    all_user_phones = await get_metric("user_phones_all_time")
                    total_phones_owned_lifetime = len(all_user_phones)
                    if total_phones_owned_lifetime >= achievement_info["target_value"]:
                        unlocked = True
            elif achievement_info["type"] == "phone_sold_total":
                if kwargs_for_checks.get("phone_sold_just_now"):
                    current_count = achievements_with_progress.get(achievement_key, {}).get('progress_data', {}).get('count', 0)
                    current_count += 1
                    if current_count >= achievement_info["target_value"]:
                        unlocked = True
                    progress_data_to_save = {"count": current_count}
                    if not unlocked and achievement_key not in unlocked_keys:
                        await database.add_achievement(user_id, achievement_key, progress_data_to_save)
                        continue
            elif achievement_info["type"] == "phone_owned_max_current":
                active_phones_count = len(kwargs_for_checks.get("user_phones_active", []))
                if active_phones_count == 0: active_phones_count = len(await get_metric("user_phones_active"))
                if active_phones_count >= achievement_info["target_value"]:
                    unlocked = True
            elif achievement_info["type"] == "phone_series_collected_A":
                if kwargs_for_checks.get("phone_model_key_bought"):
                    model_key_bought = kwargs_for_checks.get("phone_model_key_bought")
                    if model_key_bought.startswith('galaxy_a'):
                        current_a_series_keys: Set[str] = set(achievements_with_progress.get(achievement_key, {}).get('progress_data', {}).get('keys', []))
                        current_a_series_keys.add(model_key_bought)
                        if len(current_a_series_keys) >= achievement_info["target_value"]:
                            unlocked = True
                        progress_data_to_save = {"keys": list(current_a_series_keys)}
                        if not unlocked and achievement_key not in unlocked_keys:
                            await database.add_achievement(user_id, achievement_key, progress_data_to_save)
                            continue
            elif achievement_info["type"] == "phone_series_collected_S":
                if kwargs_for_checks.get("phone_model_key_bought"):
                    model_key_bought = kwargs_for_checks.get("phone_model_key_bought")
                    if model_key_bought.startswith('galaxy_s'):
                        current_s_series_keys: Set[str] = set(achievements_with_progress.get(achievement_key, {}).get('progress_data', {}).get('keys', []))
                        current_s_series_keys.add(model_key_bought)
                        if len(current_s_series_keys) >= achievement_info["target_value"]:
                            unlocked = True
                        progress_data_to_save = {"keys": list(current_s_series_keys)}
                        if not unlocked and achievement_key not in unlocked_keys:
                            await database.add_achievement(user_id, achievement_key, progress_data_to_save)
                            continue
            elif achievement_info["type"] == "phone_series_collected_Z":
                if kwargs_for_checks.get("phone_model_key_bought"):
                    model_key_bought = kwargs_for_checks.get("phone_model_key_bought")
                    if model_key_bought.startswith('galaxy_z'):
                        current_z_series_keys: Set[str] = set(achievements_with_progress.get(achievement_key, {}).get('progress_data', {}).get('keys', []))
                        current_z_series_keys.add(model_key_bought)
                        if len(current_z_series_keys) >= achievement_info["target_value"]:
                            unlocked = True
                        progress_data_to_save = {"keys": list(current_z_series_keys)}
                        if not unlocked and achievement_key not in unlocked_keys:
                            await database.add_achievement(user_id, achievement_key, progress_data_to_save)
                            continue
            elif achievement_info["type"] == "phone_memory_upgrade_target":
                upgraded_memory_gb = kwargs_for_checks.get("phone_upgraded_memory_gb")
                if upgraded_memory_gb is not None and upgraded_memory_gb >= achievement_info["target_value"]:
                    unlocked = True
            elif achievement_info["type"] == "phone_repaired_total":
                if kwargs_for_checks.get("phone_repaired_just_now"):
                    current_count = achievements_with_progress.get(achievement_key, {}).get('progress_data', {}).get('count', 0)
                    current_count += 1
                    if current_count >= achievement_info["target_value"]:
                        unlocked = True
                    progress_data_to_save = {"count": current_count}
                    if not unlocked and achievement_key not in unlocked_keys:
                        await database.add_achievement(user_id, achievement_key, progress_data_to_save)
                        continue
            elif achievement_info["type"] == "phone_charged_total":
                if kwargs_for_checks.get("phone_charged_just_now"):
                    current_count = achievements_with_progress.get(achievement_key, {}).get('progress_data', {}).get('count', 0)
                    current_count += 1
                    if current_count >= achievement_info["target_value"]:
                        unlocked = True
                    progress_data_to_save = {"count": current_count}
                    if not unlocked and achievement_key not in unlocked_keys:
                        await database.add_achievement(user_id, achievement_key, progress_data_to_save)
                        continue
            elif achievement_info["type"] == "phone_insured_first":
                if kwargs_for_checks.get("phone_insured_just_now") and achievement_info["target_value"] == True:
                    unlocked = True
            elif achievement_info["type"] == "phone_insured_all_current":
                if kwargs_for_checks.get("phone_insured_just_now") or kwargs_for_checks.get("phone_bought_just_now"):
                    active_phones = await get_metric("user_phones_active")
                    insured_count = sum(1 for p in active_phones if p.get('insurance_active_until') and p['insurance_active_until'] > datetime.now(UTC_TIMEZONE_OBJ))
                    if insured_count >= achievement_info["target_value"]:
                        unlocked = True
            elif achievement_info["type"] == "phone_repaired_with_bm_component":
                if kwargs_for_checks.get("repaired_with_bm_component") and achievement_info["target_value"] == True:
                    unlocked = True
            elif achievement_info["type"] == "phone_crafted_first":
                if kwargs_for_checks.get("phone_crafted_just_now") and achievement_info["target_value"] == True:
                    unlocked = True
            elif achievement_info["type"] == "phone_crafted_all_series":
                if kwargs_for_checks.get("phone_crafted_just_now"):
                    current_crafted_series: Set[str] = set(achievements_with_progress.get(achievement_key, {}).get('progress_data', {}).get('series', []))
                    new_crafted_series = kwargs_for_checks.get("crafted_series_just_now")
                    if new_crafted_series: current_crafted_series.add(new_crafted_series)
                    
                    target_series_set = set(achievement_info["target_value"])
                    if current_crafted_series.issuperset(target_series_set):
                        unlocked = True
                    progress_data_to_save = {"series": list(current_crafted_series)}
                    if not unlocked and achievement_key not in unlocked_keys:
                        await database.add_achievement(user_id, achievement_key, progress_data_to_save)
                        continue
            elif achievement_info["type"] == "phone_crafted_total":
                if kwargs_for_checks.get("phone_crafted_just_now"):
                    current_count = achievements_with_progress.get(achievement_key, {}).get('progress_data', {}).get('count', 0)
                    current_count += 1
                    if current_count >= achievement_info["target_value"]:
                        unlocked = True
                    progress_data_to_save = {"count": current_count}
                    if not unlocked and achievement_key not in unlocked_keys:
                        await database.add_achievement(user_id, achievement_key, progress_data_to_save)
                        continue
            elif achievement_info["type"] == "phone_repaired_battery_breakdown":
                if kwargs_for_checks.get("repaired_battery_breakdown_just_now") and achievement_info["target_value"] == True:
                    unlocked = True


            # Рыночные Достижения
            elif achievement_info["type"] == "market_buy_first":
                if kwargs_for_checks.get("market_buy_just_now") and achievement_info["target_value"] == True:
                    unlocked = True
            elif achievement_info["type"] == "market_buy_total":
                if kwargs_for_checks.get("market_buy_just_now"):
                    current_count = achievements_with_progress.get(achievement_key, {}).get('progress_data', {}).get('count', 0)
                    current_count += 1
                    if current_count >= achievement_info["target_value"]:
                        unlocked = True
                    progress_data_to_save = {"count": current_count}
                    if not unlocked and achievement_key not in unlocked_keys:
                        await database.add_achievement(user_id, achievement_key, progress_data_to_save)
                        continue
            elif achievement_info["type"] == "market_spend_total":
                if kwargs_for_checks.get("market_spend_total_amount") is not None:
                    current_total = achievements_with_progress.get(achievement_key, {}).get('progress_data', {}).get('amount', 0)
                    current_total += kwargs_for_checks["market_spend_total_amount"]
                    if current_total >= achievement_info["target_value"]:
                        unlocked = True
                    progress_data_to_save = {"amount": current_total}
                    if not unlocked and achievement_key not in unlocked_keys:
                        await database.add_achievement(user_id, achievement_key, progress_data_to_save)
                        continue
            elif achievement_info["type"] == "market_sell_total":
                if kwargs_for_checks.get("market_sell_just_now"):
                    current_count = achievements_with_progress.get(achievement_key, {}).get('progress_data', {}).get('count', 0)
                    current_count += 1
                    if current_count >= achievement_info["target_value"]:
                        unlocked = True
                    progress_data_to_save = {"count": current_count}
                    if not unlocked and achievement_key not in unlocked_keys:
                        await database.add_achievement(user_id, achievement_key, progress_data_to_save)
                        continue
            elif achievement_info["type"] == "bm_buy_first":
                if kwargs_for_checks.get("bm_buy_just_now") and achievement_info["target_value"] == True:
                    unlocked = True
            elif achievement_info["type"] == "bm_buy_stolen_phone":
                if kwargs_for_checks.get("bm_bought_stolen_phone"):
                    current_count = achievements_with_progress.get(achievement_key, {}).get('progress_data', {}).get('count', 0)
                    current_count += 1
                    if current_count >= achievement_info["target_value"]:
                        unlocked = True
                    progress_data_to_save = {"count": current_count}
                    if not unlocked and achievement_key not in unlocked_keys:
                        await database.add_achievement(user_id, achievement_key, progress_data_to_save)
                        continue
            elif achievement_info["type"] == "bm_buy_exclusive_phone":
                if kwargs_for_checks.get("bm_bought_exclusive_phone"):
                    current_count = achievements_with_progress.get(achievement_key, {}).get('progress_data', {}).get('count', 0)
                    current_count += 1
                    if current_count >= achievement_info["target_value"]:
                        unlocked = True
                    progress_data_to_save = {"count": current_count}
                    if not unlocked and achievement_key not in unlocked_keys:
                        await database.add_achievement(user_id, achievement_key, progress_data_to_save)
                        continue
            elif achievement_info["type"] == "bm_buy_component_not_defective":
                if kwargs_for_checks.get("bm_buy_component_not_defective_just_now") and achievement_info["target_value"] == True:
                    unlocked = True
            elif achievement_info["type"] == "roulette_won_phone_sell_high":
                if kwargs_for_checks.get("phone_sold_won_for_price") is not None and kwargs_for_checks["phone_sold_won_for_price"] >= achievement_info["target_value"]:
                    unlocked = True
            elif achievement_info["type"] == "roulette_won_phone_exchange_old":
                if kwargs_for_checks.get("phone_exchanged_won_for_old") and achievement_info["target_value"] == True:
                    unlocked = True
            elif achievement_info["type"] == "bm_buy_vintage_phone":
                if kwargs_for_checks.get("bm_buy_vintage_phone_just_now") and achievement_info["target_value"] == True:
                    unlocked = True
            elif achievement_info["type"] == "bm_buy_component_defective":
                if kwargs_for_checks.get("bm_buy_component_defective_just_now"):
                    current_count = achievements_with_progress.get(achievement_key, {}).get('progress_data', {}).get('count', 0)
                    current_count += 1
                    if current_count >= achievement_info["target_value"]:
                        unlocked = True
                    progress_data_to_save = {"count": current_count}
                    if not unlocked and achievement_key not in unlocked_keys:
                        await database.add_achievement(user_id, achievement_key, progress_data_to_save)
                        continue
            elif achievement_info["type"] == "bm_buy_total":
                if kwargs_for_checks.get("bm_buy_just_now"):
                    current_count = achievements_with_progress.get(achievement_key, {}).get('progress_data', {}).get('count', 0)
                    current_count += 1
                    if current_count >= achievement_info["target_value"]:
                        unlocked = True
                    progress_data_to_save = {"count": current_count}
                    if not unlocked and achievement_key not in unlocked_keys:
                        await database.add_achievement(user_id, achievement_key, progress_data_to_save)
                        continue
            elif achievement_info["type"] == "bm_buy_components_total":
                if kwargs_for_checks.get("bm_bought_components"): # Проверяем, если купили компоненты (тут ожидается, что kwargs передаст КОЛИЧЕСТВО)
                    current_count = achievements_with_progress.get(achievement_key, {}).get('progress_data', {}).get('count', 0)
                    current_count += kwargs_for_checks["bm_bought_components"] # Добавляем количество
                    if current_count >= achievement_info["target_value"]:
                        unlocked = True
                    progress_data_to_save = {"count": current_count}
                    if not unlocked and achievement_key not in unlocked_keys:
                        await database.add_achievement(user_id, achievement_key, progress_data_to_save)
                        continue
            elif achievement_info["type"] == "bm_buy_case_first":
                if kwargs_for_checks.get("bm_buy_case_just_now") and achievement_info["target_value"] == True:
                    unlocked = True

            # Бонусные Достижения
            elif achievement_info["type"] == "bonus_multiplier_high":
                multiplier_value = kwargs_for_checks.get("bonus_multiplier_value")
                if multiplier_value is not None and multiplier_value >= achievement_info["target_value"]:
                    unlocked = True
            elif achievement_info["type"] == "bonus_multiplier_negative":
                multiplier_value = kwargs_for_checks.get("bonus_multiplier_value")
                if multiplier_value is not None and multiplier_value <= achievement_info["target_value"]:
                    unlocked = True
            elif achievement_info["type"] == "roulette_spins_total":
                if kwargs_for_checks.get("roulette_spun_just_now"):
                    current_count = achievements_with_progress.get(achievement_key, {}).get('progress_data', {}).get('count', 0)
                    current_count += 1
                    if current_count >= achievement_info["target_value"]:
                        unlocked = True
                    progress_data_to_save = {"count": current_count}
                    if not unlocked and achievement_key not in unlocked_keys:
                        await database.add_achievement(user_id, achievement_key, progress_data_to_save)
                        continue
            elif achievement_info["type"] == "roulette_win_phone_first":
                if kwargs_for_checks.get("roulette_won_phone_just_now") and achievement_info["target_value"] == True:
                    unlocked = True
            elif achievement_info["type"] == "roulette_win_phone_total":
                if kwargs_for_checks.get("roulette_won_phone_just_now"):
                    current_count = achievements_with_progress.get(achievement_key, {}).get('progress_data', {}).get('count', 0)
                    current_count += 1
                    if current_count >= achievement_info["target_value"]:
                        unlocked = True
                    progress_data_to_save = {"count": current_count}
                    if not unlocked and achievement_key not in unlocked_keys:
                        await database.add_achievement(user_id, achievement_key, progress_data_to_save)
                        continue
            elif achievement_info["type"] == "roulette_use_multiplier_boost_first":
                if kwargs_for_checks.get("roulette_used_multiplier_boost_just_now") and achievement_info["target_value"] == True:
                    unlocked = True
            elif achievement_info["type"] == "roulette_use_negative_protection_first":
                if kwargs_for_checks.get("roulette_used_negative_protection_just_now") and achievement_info["target_value"] == True:
                    unlocked = True
            elif achievement_info["type"] == "bonus_extra_attempts_total":
                if kwargs_for_checks.get("bonus_extra_attempts_current_count") is not None:
                    if kwargs_for_checks["bonus_extra_attempts_current_count"] >= achievement_info["target_value"]:
                        unlocked = True
            elif achievement_info["type"] == "oneui_extra_attempts_total":
                if kwargs_for_checks.get("oneui_extra_attempts_current_count") is not None:
                    if kwargs_for_checks["oneui_extra_attempts_current_count"] >= achievement_info["target_value"]:
                        unlocked = True
            elif achievement_info["type"] == "bonus_multiplier_zero":
                multiplier_value = kwargs_for_checks.get("bonus_multiplier_value")
                if multiplier_value is not None and multiplier_value == achievement_info["target_value"]:
                    unlocked = True
            elif achievement_info["type"] == "bonus_multiplier_very_negative":
                multiplier_value = kwargs_for_checks.get("bonus_multiplier_value")
                if multiplier_value is not None and multiplier_value <= achievement_info["target_value"]:
                    unlocked = True

            # Семейные Достижения
            elif achievement_info["type"] == "family_create_first":
                if kwargs_for_checks.get("family_created_just_now") and achievement_info["target_value"] == True:
                    unlocked = True
            elif achievement_info["type"] == "family_join_first":
                if kwargs_for_checks.get("family_joined_just_now") and achievement_info["target_value"] == True:
                    unlocked = True
            elif achievement_info["type"] == "family_leader_members_count":
                current_members = await get_metric("family_leader_members_count")
                if current_members is not None and current_members >= achievement_info["target_value"]:
                    unlocked = True
            elif achievement_info["type"] == "family_total_members_count":
                current_members = await get_metric("family_total_members_count")
                if current_members is not None and current_members >= achievement_info["target_value"]:
                    unlocked = True
            elif achievement_info["type"] == "family_invite_total":
                if kwargs_for_checks.get("family_invited_just_now"):
                    current_count = achievements_with_progress.get(achievement_key, {}).get('progress_data', {}).get('count', 0)
                    current_count += kwargs_for_checks.get("family_invited_count", 1)
                    if current_count >= achievement_info["target_value"]:
                        unlocked = True
                    progress_data_to_save = {"count": current_count}
                    if not unlocked and achievement_key not in unlocked_keys:
                        await database.add_achievement(user_id, achievement_key, progress_data_to_save)
                        continue
            elif achievement_info["type"] == "family_competition_contribute_first":
                if kwargs_for_checks.get("competition_contributed_just_now") and achievement_info["target_value"] == True:
                    unlocked = True
            elif achievement_info["type"] == "family_rename_first":
                if kwargs_for_checks.get("family_renamed_just_now") and achievement_info["target_value"] == True:
                    unlocked = True
            elif achievement_info["type"] == "family_join_active_competition":
                if kwargs_for_checks.get("family_joined_active_competition_just_now") and achievement_info["target_value"] == True:
                    unlocked = True
            elif achievement_info["type"] == "family_leave_first":
                if kwargs_for_checks.get("family_left_just_now") and achievement_info["target_value"] == True:
                    unlocked = True
            elif achievement_info["type"] == "family_kicked_first":
                if kwargs_for_checks.get("family_kicked_just_now") and achievement_info["target_value"] == True:
                    unlocked = True


            # Бизнес Достижения
            elif achievement_info["type"] == "business_buy_first":
                if kwargs_for_checks.get("business_bought_just_now") and achievement_info["target_value"] == True:
                    unlocked = True
            elif achievement_info["type"] == "business_owned_max_current":
                active_businesses_count = len(kwargs_for_checks.get("user_businesses_active", []))
                if active_businesses_count == 0: active_businesses_count = len(await get_metric("user_businesses_active"))
                if active_businesses_count >= achievement_info["target_value"]:
                    unlocked = True
            elif achievement_info["type"] == "business_upgrade_to_max_level_first":
                if kwargs_for_checks.get("business_upgraded_to_max_level_just_now") and achievement_info["target_value"] == True:
                    unlocked = True
            elif achievement_info["type"] == "business_hire_max_staff_first":
                if kwargs_for_checks.get("business_hired_max_staff_just_now") and achievement_info["target_value"] == True:
                    unlocked = True
            elif achievement_info["type"] == "business_total_staff_hired":
                if kwargs_for_checks.get("business_hired_just_now"):
                    current_total_staff = await get_metric("business_total_staff_hired")
                    if current_total_staff is not None and current_total_staff >= achievement_info["target_value"]:
                        unlocked = True
            elif achievement_info["type"] == "bank_upgrade_level":
                current_bank_level = kwargs_for_checks.get("bank_upgraded_to_level")
                if current_bank_level is None: current_bank_level = await get_metric("user_bank_level")
                if current_bank_level is not None and current_bank_level >= achievement_info["target_value"]:
                    unlocked = True
            elif achievement_info["type"] == "business_buy_upgrades_total":
                if kwargs_for_checks.get("business_upgrade_bought_just_now"):
                    current_count = achievements_with_progress.get(achievement_key, {}).get('progress_data', {}).get('count', 0)
                    current_count += 1
                    if current_count >= achievement_info["target_value"]:
                        unlocked = True
                    progress_data_to_save = {"count": current_count}
                    if not unlocked and achievement_key not in unlocked_keys:
                        await database.add_achievement(user_id, achievement_key, progress_data_to_save)
                        continue
            elif achievement_info["type"] == "business_buy_all_upgrades_for_one":
                if kwargs_for_checks.get("business_upgrade_bought_just_now"):
                    business_id_upgraded = kwargs_for_checks.get("business_id_upgraded")
                    if business_id_upgraded:
                        current_upgrades_for_biz = await database.get_business_upgrades(business_id_upgraded, user_id)
                        current_biz_info = await database.get_user_business_by_id(business_id_upgraded, user_id)
                        current_biz_key = current_biz_info.get('business_key') if current_biz_info else None
                        
                        if current_biz_key:
                            all_applicable_upgrades_for_this_biz = {
                                upg_key for upg_key, upg_info in BUSINESS_UPGRADES.items()
                                if (not upg_info.get("applicable_business_keys") or current_biz_key in upg_info["applicable_business_keys"])
                            }
                            installed_upgrades_keys = {upg['upgrade_key'] for upg in current_upgrades_for_biz}

                            if all_applicable_upgrades_for_this_biz.issubset(installed_upgrades_keys) and \
                               len(all_applicable_upgrades_for_this_biz) > 0:
                                unlocked = True
            elif achievement_info["type"] == "business_prevent_negative_events":
                if kwargs_for_checks.get("business_event_prevented_just_now"):
                    current_count = achievements_with_progress.get(achievement_key, {}).get('progress_data', {}).get('count', 0)
                    current_count += 1
                    if current_count >= achievement_info["target_value"]:
                        unlocked = True
                    progress_data_to_save = {"count": current_count}
                    if not unlocked and achievement_key not in unlocked_keys:
                        await database.add_achievement(user_id, achievement_key, progress_data_to_save)
                        continue
            elif achievement_info["type"] == "business_total_income_earned":
                current_total_income = kwargs_for_checks.get("business_total_income_earned_value")
                if current_total_income is None: # Получаем из БД, если не передано в kwargs
                    user_oneui_data = await database.get_user_data_for_update(user_id, chat_id)
                    current_total_income = user_oneui_data.get('total_income_earned_from_businesses', 0) # Это поле теперь есть в user_oneui
                if current_total_income is not None and current_total_income >= achievement_info["target_value"]:
                    unlocked = True
            elif achievement_info["type"] == "business_specific_max_level":
                if kwargs_for_checks.get("business_upgraded_to_level") == achievement_info["target_value"] and \
                   kwargs_for_checks.get("business_upgraded_specific_key") == achievement_info["target_key"]:
                    unlocked = True
            elif achievement_info["type"] == "business_owned_all":
                if kwargs_for_checks.get("business_bought_just_now"):
                    current_owned_unique_biz_count = await get_metric("business_owned_all_count")
                    if current_owned_unique_biz_count is not None and current_owned_unique_biz_count >= achievement_info["target_value"]:
                        unlocked = True

            # Достижения Соревнований
            elif achievement_info["type"] == "competition_contribute_first":
                if kwargs_for_checks.get("competition_contributed_just_now") and achievement_info["target_value"] == True:
                    unlocked = True
            elif achievement_info["type"] == "competition_contribute_total":
                if kwargs_for_checks.get("competition_contributed_just_now"):
                    current_count = achievements_with_progress.get(achievement_key, {}).get('progress_data', {}).get('count', 0)
                    current_count += 1
                    if current_count >= achievement_info["target_value"]:
                        unlocked = True
                    progress_data_to_save = {"count": current_count}
                    if not unlocked and achievement_key not in unlocked_keys:
                        await database.add_achievement(user_id, achievement_key, progress_data_to_save)
                        continue
            elif achievement_info["type"] == "competition_win_first":
                if kwargs_for_checks.get("competition_won_just_now") and achievement_info["target_value"] == True:
                    unlocked = True
            elif achievement_info["type"] == "competition_win_total":
                if kwargs_for_checks.get("competition_won_just_now"):
                    current_count = achievements_with_progress.get(achievement_key, {}).get('progress_data', {}).get('count', 0)
                    current_count += 1
                    if current_count >= achievement_info["target_value"]:
                        unlocked = True
                    progress_data_to_save = {"count": current_count}
                    if not unlocked and achievement_key not in unlocked_keys:
                        await database.add_achievement(user_id, achievement_key, progress_data_to_save)
                        continue

            # Взаимодействие с Ботом (Особые Отметки) - "Секретные"
            elif achievement_info["type"] == "bot_command_foreign_chat":
                if kwargs_for_checks.get("command_from_foreign_chat_just_now") and achievement_info["target_value"] == True:
                    unlocked = True
            elif achievement_info["type"] == "bot_reply_to_bot_first":
                if kwargs_for_checks.get("replied_to_bot_just_now") and achievement_info["target_value"] == True:
                    unlocked = True
            elif achievement_info["type"] == "bot_use_help_first":
                if kwargs_for_checks.get("used_help_first_time") and achievement_info["target_value"] == True:
                    unlocked = True

            # "Секретные" и Исследовательские Достижения
            elif achievement_info["type"] == "bonus_multiplier_zero_applied":
                if kwargs_for_checks.get("bonus_multiplier_applied_is_zero") and achievement_info["target_value"] == True:
                    unlocked = True
            elif achievement_info["type"] == "phone_battery_breakdown_due_to_drain":
                if kwargs_for_checks.get("battery_breakdown_from_drain_just_now") and achievement_info["target_value"] == True:
                    unlocked = True
            elif achievement_info["type"] == "bm_buy_defective_component_total":
                if kwargs_for_checks.get("bm_buy_component_defective_just_now"):
                    current_count = achievements_with_progress.get(achievement_key, {}).get('progress_data', {}).get('count', 0)
                    current_count += 1
                    if current_count >= achievement_info["target_value"]:
                        unlocked = True
                    progress_data_to_save = {"count": current_count}
                    if not unlocked and achievement_key not in unlocked_keys:
                        await database.add_achievement(user_id, achievement_key, progress_data_to_save)
                        continue
            elif achievement_info["type"] == "bm_buy_phone_cosmetic_defect":
                if kwargs_for_checks.get("bm_buy_phone_cosmetic_defect_just_now") and achievement_info["target_value"] == True:
                    unlocked = True
            elif achievement_info["type"] == "bm_buy_phone_wrong_color":
                if kwargs_for_checks.get("bm_buy_phone_wrong_color_just_now") and achievement_info["target_value"] == True:
                    unlocked = True
            elif achievement_info["type"] == "exclusive_phone_ability_rewind":
                if kwargs_for_checks.get("ability_rewind_used_just_now") and achievement_info["target_value"] == True:
                    unlocked = True
            elif achievement_info["type"] == "exclusive_phone_ability_void_gazer":
                if kwargs_for_checks.get("ability_void_gazer_used_just_now") and achievement_info["target_value"] == True:
                    unlocked = True
            elif achievement_info["type"] == "exclusive_phone_ability_cyborg_enhance":
                if kwargs_for_checks.get("ability_cyborg_enhance_used_just_now") and achievement_info["target_value"] == True:
                    unlocked = True
            elif achievement_info["type"] == "oneui_version_negative":
                current_version = kwargs_for_checks.get("current_oneui_version") or await get_metric("current_oneui_version")
                if current_version is not None and current_version < achievement_info["target_value"]:
                    unlocked = True
            elif achievement_info["type"] == "oneui_version_negative_threshold":
                current_version = kwargs_for_checks.get("current_oneui_version") or await get_metric("current_oneui_version")
                if current_version is not None and current_version <= achievement_info["target_value"]:
                    unlocked = True

            # --- Конец проверки условий ---

            if unlocked:
                success = await database.add_achievement(user_id, achievement_key, progress_data_to_save)
                if success:
                    achievement_message = (
                        f"🎉 Новое достижение! {user_link}, вы получили:\n"
                        f"{achievement_info['icon']} <b>«{achievement_info['name']}»</b>\n"
                        f"<i>{achievement_info['description']}</i>"
                    )
                    try:
                        await bot_instance.send_message(
                        chat_id, 
                        achievement_message, 
                        parse_mode="HTML",
                        message_thread_id=message_thread_id,
                        disable_web_page_preview=True
                        )
                        logger.info(f"Achievement '{achievement_info['name']}' unlocked and notified for user {user_id} in chat {chat_id}.")
                    except Exception as e_send_msg:
                        logger.error(f"Failed to send achievement notification to user {user_id} in chat {chat_id}: {e_send_msg}", exc_info=True)
                    await send_telegram_log(bot_instance, f"🏆 Достижение разблокировано: {user_link} получил '{achievement_info['name']}' (Ключ: {achievement_key})")

    except Exception as e:
        logger.error(f"Error in check_and_grant_achievements for user {user_id}: {e}", exc_info=True)


# --- Команда для просмотра достижений ---

@achievements_router.message(Command("selectachievement", "выбратьдостижение", "моёдостижение", "достижения", ignore_case=True))
async def cmd_select_achievement(message: Message, command: CommandObject, bot: Bot):
    if not message.from_user:
        await message.reply("Не могу определить пользователя.")
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    user_link = get_user_mention_html(user_id, message.from_user.full_name, message.from_user.username)

    try:
        args = command.args
        if not args:
            user_achievements = await database.get_user_achievements(user_id)
            if not user_achievements:
                await message.reply(f"{user_link}, у вас пока нет достижений, чтобы их выбирать! Заработайте их с помощью хаоса!")
                return

            response_lines = [f"🏆 <b>{user_link}, выберите достижение для профиля.</b> 🏆"]
            response_lines.append("---")
            response_lines.append("Используйте <code>/selectachievement</code> [Номер] достяжения`")
            response_lines.append("Или <code>/selectachievement none</code>, чтобы сбросить выбранное.")
            response_lines.append("\n<b>Ваши полученные достижения:</b>")

            for i, ach_record in enumerate(user_achievements):
                ach_key = ach_record['achievement_key']
                ach_info = Config.ACHIEVEMENTS_DATA.get(ach_key)
                if ach_info:
                    display_name = ach_info['icon'] + " " + ach_info['name']
                    response_lines.append(f"  {i + 1}. {display_name} (Ключ: <code>{ach_key}</code>)")
                else: # Добавим лог, если достижение в БД есть, а в конфиге нет
                    logger.warning(f"Achievement key '{ach_key}' for user {user_id} found in DB but not in Config.ACHIEVEMENTS_DATA.")
                    response_lines.append(f"  {i + 1}. ❓ Неизвестное достижение (Ключ: <code>{ach_key}</code>)")


            await message.reply("\n".join(response_lines), parse_mode="HTML", disable_web_page_preview=True)
            return

        selected_arg = args.strip()
        selected_achievement_key: Optional[str] = None

        if selected_arg.lower() == "none":
            selected_achievement_key = None
        else:
            try:
                ach_id = int(selected_arg)
                user_achievements = await database.get_user_achievements(user_id)
                if 1 <= ach_id <= len(user_achievements):
                    selected_achievement_key = user_achievements[ach_id - 1]['achievement_key']
                else:
                    await message.reply(f"{user_link}, достижение с ID {ach_id} не найдено в вашем списке.")
                    return
            except ValueError:
                potential_key = selected_arg
                ach_info = Config.ACHIEVEMENTS_DATA.get(potential_key)
                if ach_info:
                    user_unlocked_keys = {ach['achievement_key'] for ach in await database.get_user_achievements(user_id)}
                    if potential_key in user_unlocked_keys:
                        selected_achievement_key = potential_key
                    else:
                        await message.reply(f"{user_link}, достижение с ключом <code>{html.escape(potential_key)}</code> не найдено в вашем списке полученных достижений.")
                        return
                else:
                    await message.reply(f"{user_link}, достижение с ключом <code>{html.escape(potential_key)}</code> не найдено в системе достижений. Проверьте ключ.")
                    return

        # Устанавливаем выбранное достижение в БД
        success = await database.set_user_selected_achievement(user_id, selected_achievement_key)

        if success:
            if selected_achievement_key:
                ach_info = Config.ACHIEVEMENTS_DATA.get(selected_achievement_key)
                # **Добавим тут дополнительное логирование для отладки**
                if not ach_info:
                    logger.error(f"FATAL: selected_achievement_key '{selected_achievement_key}' not found in Config.ACHIEVEMENTS_DATA after successful DB update for user {user_id}. This should not happen.")
                    display_name = f"Неизвестное достижение (Ключ: <code>{html.escape(selected_achievement_key)}</code>)"
                else:
                    display_name = ach_info['icon'] + " " + ach_info['name']

                # **Попробуем обернуть отправку сообщения в свой try-except блок**
                try:
                    await message.reply(f"✅ {user_link}, ваше выбранное достижение для профиля: <b>{display_name}</b>", parse_mode="HTML", disable_web_page_preview=True)
                    logger.info(f"User {user_id} selected achievement '{selected_achievement_key}' for display.")
                except Exception as e_send_reply:
                    logger.error(f"Failed to send success message for selected achievement to user {user_id}: {e_send_reply}", exc_info=True)
                    # Если отправка сообщения пользователю провалилась, но в БД все обновилось,
                    # можно отправить сообщение об ошибке в лог телеграма, но не пользователю
                    # (потому что ошибка произошла при попытке отправить сообщение пользователю).
                    await send_telegram_log(bot, f"🔴 Ошибка отправки подтверждения выбора достижения для {user_link}: <pre>{html.escape(str(e_send_reply))}</pre>")
                    # Мы не должны здесь возвращаться или отвечать пользователю, так как он уже получил ошибку.
                    # Но для ясности, что БД обновилась:
                    logger.info(f"DB update for selected achievement for user {user_id} was successful, but notification failed.")
            else:
                await message.reply(f"✅ {user_link}, ваше выбранное достижение для профиля <b>сброшено</b>.", parse_mode="HTML", disable_web_page_preview=True)
                logger.info(f"User {user_id} cleared selected achievement.")
        else:
            await message.reply(f"Произошла ошибка при сохранении выбранного достижения.")
            logger.error(f"Error setting selected achievement for user {user_id} to '{selected_achievement_key}'.")

    except Exception as e:
        logger.error(f"Error in cmd_select_achievement for user {user_id}: {e}", exc_info=True)
        # Отправляем сообщение об ошибке пользователю только в том случае, если это глобальная ошибка,
        # которая не была поймана внутренним try-except блоком.
        await message.reply("Произошла ошибка при выборе достижения. Попробуйте позже.")
        await send_telegram_log(bot, f"🔴 Ошибка /selectachievement для {user_link}: <pre>{html.escape(str(e))}</pre>")


def setup_achievements_handlers(dp: Router):
    """Регистрирует обработчики команд для достижений."""
    dp.include_router(achievements_router)
    logger.info("Обработчики команд достижений зарегистрированы.")


