# database.py
import os
import asyncpg
from dotenv import load_dotenv
import asyncio
from datetime import datetime, timedelta, timezone as dt_timezone, date as DDate
from pytz import timezone as pytz_timezone
from typing import Optional, List, Dict, Any, Tuple
import logging
from decimal import Decimal, ROUND_HALF_UP
import json 
from item_data import PHONE_COMPONENTS
from phone_data import PHONE_MODELS as PHONE_MODELS_LIST_DB # Импортируем список
from item_data import PHONE_COMPONENTS as PHONE_COMPONENTS_DB # Импортируем компоненты

# Убедитесь, что Config импортируется правильно. Если Config находится в корне проекта,
# и database.py тоже, то "from config import Config" должно работать.
# Если database.py в подпапке, возможно, потребуется "from ..config import Config"
# или настройка PYTHONPATH. Для простоты предполагаем, что импорт корректен.
from config import Config

load_dotenv()
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")

# --- Словари для блокировок команд (перемещено из main.py) ---
user_command_locks: Dict[Tuple[int, int], asyncio.Lock] = {}
locks_dict_creation_lock = asyncio.Lock()

async def get_user_chat_lock(user_id: int, chat_id: int) -> asyncio.Lock:
    key = (user_id, chat_id)
    async with locks_dict_creation_lock:
        if key not in user_command_locks:
            user_command_locks[key] = asyncio.Lock()
        return user_command_locks[key]

# Константа для минимальной версии OneUI для создания семьи, если она не определена в Config
FAMILY_CREATION_MIN_VERSION = getattr(Config, 'FAMILY_CREATION_MIN_VERSION', 5.0)
PHONE_MODELS = {phone_info["key"]: phone_info for phone_info in PHONE_MODELS_LIST_DB}
PHONE_COMPONENTS = PHONE_COMPONENTS_DB # Просто присваиваем, если он уже словарь


async def get_connection() -> asyncpg.Connection:
    if not DATABASE_URL:
        logger.critical("DATABASE_URL environment variable not set.")
        raise ValueError("DATABASE_URL environment variable not set.")
    try:
        return await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
    except Exception as e:
        logger.critical(f"Failed to connect to database: {e}", exc_info=True)
        raise

async def init_db():
    conn = await get_connection()
    try:
        # --- Таблица user_oneui (основная таблица для версий и монет) ---
        table_exists = await conn.fetchval("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'user_oneui');")
        if not table_exists:
             await conn.execute("""
                 CREATE TABLE user_oneui (
                     user_id BIGINT NOT NULL,
                     chat_id BIGINT NOT NULL,
                     PRIMARY KEY (user_id, chat_id)
                 )
             """)
             logger.info("Таблица 'user_oneui' создана с минимальной структурой.")
        else:
            logger.info("Таблица 'user_oneui' уже существует.")
            
                


        
        # ДОБАВЬ ЭТОТ БЛОК ДЛЯ СОЗДАНИЯ ТАБЛИЦЫ ОГРАБЛЕНИЙ
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_robbank_status (
                user_id BIGINT NOT NULL,
                chat_id BIGINT NOT NULL,
                last_robbank_attempt_utc TIMESTAMP WITH TIME ZONE,
                robbank_oneui_blocked_until_utc TIMESTAMP WITH TIME ZONE,
                current_operation_name TEXT,
                current_operation_start_utc TIMESTAMP WITH TIME ZONE,
                current_operation_base_reward INTEGER,
                PRIMARY KEY (user_id, chat_id),
                FOREIGN KEY (user_id, chat_id) REFERENCES user_oneui (user_id, chat_id) ON DELETE CASCADE
            );
        """)
        logger.info("Таблица 'user_robbank_status' проверена/создана.")
        # Индексы для user_robbank_status (опционально, но полезно для производительности)
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_robbank_status_blocked ON user_robbank_status (robbank_oneui_blocked_until_utc);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_robbank_status_pending_op ON user_robbank_status (current_operation_start_utc);")
        # --- КОНЕЦ БЛОКА ДЛЯ ТАБЛИЦЫ ОГРАБЛЕНИЙ ---    
            
            

        # Функции для добавления колонок (они должны быть определены ниже в этом файле)
        await add_username_column(conn_ext=conn)
        await add_full_name_column(conn_ext=conn)
        await add_chat_title_column(conn_ext=conn)
        await add_version_column(conn_ext=conn)
        await add_last_used_column(conn_ext=conn)
        await add_onecoins_column(conn_ext=conn)
        await add_telegram_chat_link_column(conn_ext=conn)
        await _add_column_if_not_exists(conn, "user_oneui", "total_income_earned_from_businesses", "BIGINT DEFAULT 0 NOT NULL") # <<< НОВОЕ ПОЛЕ
        
        logger.info("Колонки таблицы 'user_oneui' проверены/добавлены.")

        # --- Таблица user_bonus_multipliers ---
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_bonus_multipliers (
                user_id BIGINT NOT NULL,
                chat_id BIGINT NOT NULL,
                current_bonus_multiplier NUMERIC(3, 2),
                is_bonus_consumed BOOLEAN DEFAULT TRUE NOT NULL,
                last_claimed_timestamp TIMESTAMP WITH TIME ZONE,
                PRIMARY KEY (user_id, chat_id)
            )
        """)
        logger.info("Таблица 'user_bonus_multipliers' проверена/создана (с chat_id).")
        
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_display_achievement (
                user_id BIGINT PRIMARY KEY,
                selected_achievement_key TEXT DEFAULT NULL,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)
        logger.info("Таблица 'user_display_achievement' проверена/создана.")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_display_achievement_user_id ON user_display_achievement (user_id);")
        logger.info("Индексы для 'user_display_achievement' проверены/созданы.")
        
        
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_phones (
                phone_inventory_id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                chat_id_acquired_in BIGINT NOT NULL,
                phone_model_key TEXT NOT NULL,
                color TEXT NOT NULL,
                purchase_price_onecoins INTEGER NOT NULL,
                purchase_date_utc TIMESTAMP WITH TIME ZONE NOT NULL,
                is_sold BOOLEAN DEFAULT FALSE NOT NULL,
                sold_date_utc TIMESTAMP WITH TIME ZONE,
                sold_price_onecoins INTEGER
            )
        """)
        logger.info("Таблица 'user_phones' проверена/создана.")

        # Индексы для таблицы user_phones (НОВОЕ)
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_phones_user_id ON user_phones (user_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_phones_user_active ON user_phones (user_id, is_sold)")
        logger.info("Индексы для 'user_phones' проверены/созданы.")


        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_achievements (
                user_id BIGINT NOT NULL,
                achievement_key TEXT NOT NULL,
                achieved_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                progress_data JSONB DEFAULT NULL, -- Для достижений с прогрессом (если решим использовать)
                PRIMARY KEY (user_id, achievement_key)
            );
        """)
        logger.info("Таблица 'user_achievements' проверена/создана.")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_achievements_user_id ON user_achievements (user_id);")
        # --- КОНЕЦ НОВОЙ ТАБЛИЦЫ ДЛЯ ДОСТИЖЕНИЙ ---

        logger.info("Все таблицы проверены/созданы и при необходимости изменены.") 


        # --- Таблица user_version_history ---
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_version_history (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                chat_id BIGINT NOT NULL,
                version NUMERIC(10, 1),
                full_name_at_change TEXT, -- <<<< НОВАЯ КОЛОНКА
                changed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (user_id, chat_id, changed_at) -- Убедитесь, что UNIQUE constraint не мешает, если full_name_at_change может быть разным при одинаковых user, chat, time
                                                    -- Вряд ли, так как changed_at обычно уникально до микросекунд, но стоит помнить.
                                                    -- Если changed_at может быть не уникальным, можно убрать его из UNIQUE или добавить id в UNIQUE.
                                                    -- Однако, DEFAULT CURRENT_TIMESTAMP обычно достаточно уникален.
            )
        """)
        logger.info("Таблица 'user_version_history' проверена/создана (с full_name_at_change).")
        
        # --- Таблица для инвентаря предметов пользователя (детали, чехлы, модули памяти) ---
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_items (
                user_item_id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                item_key TEXT NOT NULL,
                item_type TEXT NOT NULL,
                quantity INTEGER DEFAULT 1 NOT NULL,
                data JSONB DEFAULT NULL, -- <<< ИСПРАВЛЕНИЕ: ДОБАВЛЕНА ЗАПЯТАЯ
                equipped_phone_id INTEGER DEFAULT NULL
            )
        """)
        logger.info("Таблица 'user_items' проверена/создана (без UNIQUE для item_key).")
        # Основной индекс по user_id оставляем
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_items_user_id ON user_items (user_id)")
        # Индекс (user_id, item_key) все еще полезен для быстрого поиска всех предметов определенного типа у пользователя,
        # даже если они не уникальны в комбинации.
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_items_user_item_type ON user_items (user_id, item_key, item_type)")
        logger.info("Индексы для 'user_items' проверены/созданы.")

        # --- Добавление новых полей в таблицу user_phones ---
        phone_columns_to_add = [
            ("current_memory_gb", "INTEGER DEFAULT NULL"), # Изначально NULL, будет установлено при покупке из phone_data.py
            ("is_broken", "BOOLEAN DEFAULT FALSE NOT NULL"),
            ("broken_component_key", "TEXT DEFAULT NULL"), # Ключ сломанного компонента из PHONE_COMPONENTS
            ("insurance_active_until", "TIMESTAMP WITH TIME ZONE DEFAULT NULL"),
            ("equipped_case_key", "TEXT DEFAULT NULL"), # Ключ надетого чехла из PHONE_CASES
            ("is_contraband", "BOOLEAN DEFAULT FALSE NOT NULL"),
            ("last_charged_utc", "TIMESTAMP WITH TIME ZONE DEFAULT NULL"),
            ("battery_dead_after_utc", "TIMESTAMP WITH TIME ZONE DEFAULT NULL"),
            ("battery_break_after_utc", "TIMESTAMP WITH TIME ZONE DEFAULT NULL"),
            ("data", "JSONB DEFAULT NULL") 
        ]

        for col_name, col_def in phone_columns_to_add:
            await _add_column_if_not_exists(conn, "user_phones", col_name, col_def)
        logger.info("Новые колонки для 'user_phones' проверены/добавлены.")

        # Добавляем колонку, если она еще не существует (для старых БД)
        await _add_column_if_not_exists(conn, "user_version_history", "full_name_at_change", "TEXT")
        # logger.info("Колонка 'full_name_at_change' проверена/добавлена в 'user_version_history'.") # Уже есть в _add_column_if_not_exists


        # --- Остальная часть init_db без изменений ---
        # (проверка FOREIGN KEY и типа changed_at, создание других таблиц)
        fk_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
                WHERE tc.table_name = 'user_version_history' AND tc.constraint_type = 'FOREIGN KEY'
                AND (kcu.constraint_name LIKE 'user_version_history_user_id_fkey%' OR kcu.constraint_name LIKE 'user_version_history_user_chat_fkey%')
            );
        """)
        if not fk_exists:
            try:
                 await conn.execute("ALTER TABLE user_version_history ADD CONSTRAINT user_version_history_user_chat_fkey FOREIGN KEY (user_id, chat_id) REFERENCES user_oneui (user_id, chat_id) ON DELETE CASCADE;")
                 logger.info("Добавлен FOREIGN KEY для user_version_history -> user_oneui.")
            except Exception as e_fk:
                 logger.warning(f"Не удалось добавить FOREIGN KEY для user_version_history: {e_fk}. Убедитесь, что user_oneui существует.")

        try:
            col_type_info = await conn.fetchrow("SELECT data_type FROM information_schema.columns WHERE table_name = 'user_version_history' AND column_name = 'changed_at'")
            if col_type_info and col_type_info['data_type'] == 'timestamp without time zone':
                await conn.execute("ALTER TABLE user_version_history ALTER COLUMN changed_at TYPE TIMESTAMP WITH TIME ZONE USING changed_at AT TIME ZONE 'UTC';")
                logger.info("ИЗМЕНЕНО: Колонка 'user_version_history.changed_at' конвертирована в TIMESTAMP WITH TIME ZONE.")
        except Exception as e_alter_ca:
            logger.warning(f"ЗАМЕЧАНИЕ: Не удалось проверить/изменить тип 'user_version_history.changed_at': {e_alter_ca}")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_pending_phone_prizes (
                prize_id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                phone_model_key TEXT NOT NULL,
                color TEXT NOT NULL,
                initial_memory_gb INTEGER NOT NULL,
                prize_won_at_utc TIMESTAMP WITH TIME ZONE NOT NULL,
                original_roulette_chat_id BIGINT NOT NULL,
                -- Можно добавить другие поля, если нужны
                --data JSONB DEFAULT NULL
                UNIQUE (user_id) -- У пользователя может быть только один такой приз, ожидающий решения
            )
        """)
        logger.info("Таблица 'user_pending_phone_prizes' проверена/создана.")
        # --- НОВЫЕ ТАБЛИЦЫ ДЛЯ БИЗНЕСОВ И БАНКА ---
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_businesses (
                business_id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                chat_id BIGINT NOT NULL,
                username TEXT DEFAULT NULL, -- Добавлено
                full_name TEXT DEFAULT NULL, -- Добавлено
                chat_title TEXT DEFAULT NULL, -- Добавлено
                business_key TEXT NOT NULL,
                current_level INTEGER DEFAULT 0 NOT NULL,
                staff_hired_slots INTEGER DEFAULT 0 NOT NULL,
                last_income_calculation_utc TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                time_purchased_utc TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                is_active BOOLEAN DEFAULT TRUE NOT NULL,
                name_override TEXT DEFAULT NULL,
                UNIQUE (user_id, chat_id, business_key)
            );
        """)
        logger.info("Таблица 'user_businesses' проверена/создана.")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_businesses_user_chat ON user_businesses (user_id, chat_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_businesses_active ON user_businesses (is_active)")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_business_upgrades (
                upgrade_id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,                
                business_internal_id INTEGER NOT NULL REFERENCES user_businesses(business_id) ON DELETE CASCADE,
                upgrade_key TEXT NOT NULL,
                time_installed_utc TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                UNIQUE (business_internal_id, upgrade_key)
            );
        """)
        logger.info("Таблица 'user_business_upgrades' проверена/создана.")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_business_upgrades_business_id ON user_business_upgrades (business_internal_id)")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_bank (
                user_id BIGINT NOT NULL,
                chat_id BIGINT NOT NULL, -- Добавлено поле chat_id для привязки к чату
                username TEXT DEFAULT NULL, -- Добавлено
                full_name TEXT DEFAULT NULL, -- Добавлено
                chat_title TEXT DEFAULT NULL, -- Добавлено
                current_balance BIGINT DEFAULT 0 NOT NULL,
                bank_level INTEGER DEFAULT 0 NOT NULL,
                last_deposit_utc TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                PRIMARY KEY (user_id, chat_id) -- Первичный ключ теперь состоит из двух полей
            );
        """)
        logger.info("Таблица 'user_bank' проверена/создана (теперь с привязкой к чату).")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_bank_user_id ON user_bank (user_id)") # Добавим индекс для быстрого поиска всех банков пользователя
        # --- КОНЕЦ НОВЫХ ТАБЛИЦ ---

        # Добавляем индекс по user_id для быстрого поиска pending призов
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_pending_phone_prizes_user_id ON user_pending_phone_prizes (user_id)")
        # Добавляем индекс по времени выигрыша для поиска просроченных призов
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_pending_phone_prizes_won_at_utc ON user_pending_phone_prizes (prize_won_at_utc)")
        logger.info("Индексы для 'user_pending_phone_prizes' проверены/созданы.") 



        
        
        
        
        # --- Таблицы семей ---
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS families (
                family_id SERIAL PRIMARY KEY, name TEXT UNIQUE NOT NULL, leader_id BIGINT NOT NULL,
                chat_id_created_in BIGINT NOT NULL, chat_title_created_in TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)
        logger.info("Таблица 'families' проверена/создана.")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS family_members (
                member_entry_id SERIAL PRIMARY KEY, family_id INTEGER NOT NULL REFERENCES families(family_id) ON DELETE CASCADE,
                user_id BIGINT NOT NULL, full_name_when_joined TEXT, chat_id_joined_from BIGINT NOT NULL,
                joined_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, is_active BOOLEAN DEFAULT TRUE,
                UNIQUE (family_id, user_id)
            )
        """)
        logger.info("Таблица 'family_members' проверена/создана.")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_family_members_active ON family_members (family_id, user_id, is_active)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_family_members_user_active ON family_members (user_id, is_active)")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS family_logs (
                log_id SERIAL PRIMARY KEY, family_id INTEGER NOT NULL REFERENCES families(family_id) ON DELETE CASCADE,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, action_type TEXT NOT NULL,
                actor_user_id BIGINT, actor_full_name TEXT, target_user_id BIGINT NULL, target_full_name TEXT NULL,
                chat_id_context BIGINT, chat_title_context TEXT, description TEXT NOT NULL
            )
        """)
        logger.info("Таблица 'family_logs' проверена/создана.")

        # --- Таблицы соревнований ---
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS family_competitions (
                competition_id SERIAL PRIMARY KEY,
                start_ts TIMESTAMP WITH TIME ZONE,
                end_ts TIMESTAMP WITH TIME ZONE,
                is_active BOOLEAN DEFAULT FALSE,
                winner_family_id INTEGER NULL REFERENCES families(family_id) ON DELETE SET NULL,
                started_by_admin_id BIGINT,
                rewards_distributed BOOLEAN DEFAULT FALSE
            )
        """)
        logger.info("Таблица 'family_competitions' проверена/создана.")
        
        

        async def ensure_fc_column_and_type(col_name, col_def_type_no_constraints, col_def_full_with_constraints):
            exists_query = "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='family_competitions' AND column_name=$1);"
            exists = await conn.fetchval(exists_query, col_name)
            renamed_from_old = False
            if not exists:
                old_col_name = None
                if col_name == 'start_ts': old_col_name = 'start_time'
                elif col_name == 'end_ts': old_col_name = 'end_time'
                if old_col_name and await conn.fetchval(exists_query, old_col_name):
                    await conn.execute(f"ALTER TABLE family_competitions RENAME COLUMN {old_col_name} TO {col_name};")
                    logger.info(f"ИЗМЕНЕНО: Колонка '{old_col_name}' переименована в '{col_name}' в 'family_competitions'.")
                    renamed_from_old = True
                if not renamed_from_old: # Только если не было переименования, пытаемся добавить
                    await conn.execute(f"ALTER TABLE family_competitions ADD COLUMN IF NOT EXISTS {col_name} {col_def_full_with_constraints};")
                    # Проверяем еще раз после ADD COLUMN
                    if await conn.fetchval(exists_query, col_name): # Используем exists_query с новым именем
                         logger.info(f"ИЗМЕНЕНО: Добавлена колонка '{col_name}' в 'family_competitions'.")
                    else:
                         logger.warning(f"Колонка '{col_name}' НЕ была добавлена в 'family_competitions' после ALTER ADD.")

            if "TIMESTAMP" in col_def_type_no_constraints.upper(): # Проверка типа, если колонка существует
                if await conn.fetchval(exists_query, col_name):
                    current_type_info = await conn.fetchrow(f"SELECT data_type FROM information_schema.columns WHERE table_name='family_competitions' AND column_name='{col_name}';")
                    if current_type_info and current_type_info['data_type'] == 'timestamp without time zone':
                        await conn.execute(f"ALTER TABLE family_competitions ALTER COLUMN {col_name} TYPE TIMESTAMP WITH TIME ZONE USING {col_name} AT TIME ZONE 'UTC';")
                        logger.info(f"ИЗМЕНЕНО: Колонка 'family_competitions.{col_name}' конвертирована в TIMESTAMP WITH TIME ZONE.")
                else:
                    logger.warning(f"Колонка '{col_name}' не найдена в 'family_competitions' после попыток добавления/переименования. Проверка типа пропущена.")

        await ensure_fc_column_and_type('start_ts', 'TIMESTAMP WITH TIME ZONE', 'TIMESTAMP WITH TIME ZONE')
        await ensure_fc_column_and_type('end_ts', 'TIMESTAMP WITH TIME ZONE', 'TIMESTAMP WITH TIME ZONE')
        await ensure_fc_column_and_type('is_active', 'BOOLEAN', 'BOOLEAN DEFAULT FALSE')
        await ensure_fc_column_and_type('winner_family_id', 'INTEGER', 'INTEGER NULL REFERENCES families(family_id) ON DELETE SET NULL')
        await ensure_fc_column_and_type('started_by_admin_id', 'BIGINT', 'BIGINT')
        await ensure_fc_column_and_type('rewards_distributed', 'BOOLEAN', 'BOOLEAN DEFAULT FALSE')

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS family_competition_scores (
                score_entry_id SERIAL PRIMARY KEY,
                competition_id INTEGER NOT NULL REFERENCES family_competitions(competition_id) ON DELETE CASCADE,
                family_id INTEGER NOT NULL REFERENCES families(family_id) ON DELETE CASCADE,
                total_score NUMERIC(10, 1) DEFAULT 0.0,
                UNIQUE (competition_id, family_id)
            )
        """)
        logger.info("Таблица 'family_competition_scores' проверена/создана.")
        await conn.execute("ALTER TABLE family_competition_scores ADD COLUMN IF NOT EXISTS total_score NUMERIC(10,1) DEFAULT 0.0;")


        await conn.execute("""
            CREATE TABLE IF NOT EXISTS family_competition_daily_contributions (
                contribution_id SERIAL PRIMARY KEY,
                competition_id INTEGER NOT NULL REFERENCES family_competitions(competition_id) ON DELETE CASCADE,
                family_id INTEGER NOT NULL REFERENCES families(family_id) ON DELETE CASCADE,
                user_id BIGINT NOT NULL,
                contribution_date DATE NOT NULL,
                max_oneui_version_today NUMERIC(10, 1) NOT NULL,
                UNIQUE (competition_id, family_id, user_id, contribution_date)
            )
        """)
        logger.info("Таблица 'family_competition_daily_contributions' проверена/создана.")

        # --- Таблицы для бонусных систем ---
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value_text TEXT,
                setting_value_timestamp TIMESTAMP WITH TIME ZONE,
                setting_value_int INTEGER,
                setting_value_bool BOOLEAN
            )
        """)
        logger.info("Таблица 'system_settings' проверена/создана.")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_daily_streaks (
                user_id BIGINT NOT NULL,
                chat_id BIGINT NOT NULL, -- << НОВОЕ ПОЛЕ
                current_streak INTEGER DEFAULT 0 NOT NULL,
                last_streak_check_date DATE,
                last_streak_timestamp_utc TIMESTAMP WITH TIME ZONE,
                username_at_last_check TEXT,
                full_name_at_last_check TEXT,
                chat_title_at_last_check TEXT,
                PRIMARY KEY (user_id, chat_id) -- << ИЗМЕНЕННЫЙ КЛЮЧ
            );
        """)
        logger.info("Таблица 'user_daily_streaks' проверена/создана (с chat_id и составным ключом).")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_daily_streaks_last_date ON user_daily_streaks (last_streak_check_date);")

        # === ТАБЛИЦА ДЛЯ РУЛЕТКИ (ROULETTE_STATUS) ===
        # ИЗМЕНЕНО: Добавлено поле extra_roulette_spins
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS roulette_status (
                user_id BIGINT NOT NULL,
                chat_id BIGINT NOT NULL,
                last_roulette_spin_timestamp TIMESTAMP WITH TIME ZONE,
                extra_bonus_attempts INTEGER DEFAULT 0 NOT NULL,
                extra_oneui_attempts INTEGER DEFAULT 0 NOT NULL,
                pending_bonus_multiplier_boost NUMERIC(3,1),
                negative_change_protection_charges INTEGER DEFAULT 0 NOT NULL,
                extra_roulette_spins INTEGER DEFAULT 0 NOT NULL, -- <<<< НОВОЕ ПОЛЕ ДОБАВЛЕНО ЗДЕСЬ
                PRIMARY KEY (user_id, chat_id),
                FOREIGN KEY (user_id, chat_id) REFERENCES user_oneui (user_id, chat_id) ON DELETE CASCADE
            )
        """)
        logger.info("Таблица 'roulette_status' проверена/создана (с полем extra_roulette_spins).")
        
        # Команда для добавления колонки, если таблица уже существовала без нее:
        try:
            await conn.execute("ALTER TABLE roulette_status ADD COLUMN IF NOT EXISTS extra_roulette_spins INTEGER DEFAULT 0 NOT NULL;")
            logger.info("Колонка 'extra_roulette_spins' проверена/добавлена в 'roulette_status'.")
        except Exception as e_alter_rs:
            logger.warning(f"Не удалось добавить/проверить колонку 'extra_roulette_spins' в 'roulette_status' через ALTER: {e_alter_rs}")
        # === КОНЕЦ ТАБЛИЦЫ ДЛЯ РУЛЕТКИ ===
        
        # <<< НАЧАЛО ВСТАВКИ ДЛЯ ИНФЛЯЦИИ В INIT_DB >>>
        logger.info("DB Init: Проверка/установка начального множителя инфляции...")
        # Используем conn, который уже открыт для init_db
        current_inflation_multiplier_from_db = await get_setting_float(
            Config.INFLATION_SETTING_KEY,
            conn_ext=conn # Передаем существующее соединение
        )

        if current_inflation_multiplier_from_db is None:
            # Если значение не найдено в БД (даже после попытки получить default из get_setting_float,
            # что означает, что самого ключа нет), устанавливаем значение из Config.
            await set_setting_float(
                Config.INFLATION_SETTING_KEY,
                Config.DEFAULT_INFLATION_MULTIPLIER,
                conn_ext=conn # Передаем существующее соединение
            )
            logger.info(f"DB Init: Установлен начальный множитель инфляции (ключ: '{Config.INFLATION_SETTING_KEY}') в БД: {Config.DEFAULT_INFLATION_MULTIPLIER}")
        else:
            logger.info(f"DB Init: Текущий множитель инфляции (ключ: '{Config.INFLATION_SETTING_KEY}') из БД: {current_inflation_multiplier_from_db}")
        # <<< КОНЕЦ ВСТАВКИ ДЛЯ ИНФЛЯЦИИ В INIT_DB >>>
        
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_black_market_monthly_stats (
                user_id BIGINT NOT NULL,
                year_month TEXT NOT NULL, -- Формат "YYYY-MM"
                phones_purchased_count INTEGER DEFAULT 0 NOT NULL,
                PRIMARY KEY (user_id, year_month)
            )
        """)         
        logger.info("Таблица 'user_black_market_monthly_stats' проверена/создана.")
        
        
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_daily_onecoin_claims (
                user_id BIGINT NOT NULL,
                chat_id BIGINT NOT NULL,
                last_claim_utc TIMESTAMP WITH TIME ZONE DEFAULT NULL,
                PRIMARY KEY (user_id, chat_id),
                CONSTRAINT fk_user_oneui_onecoin_claim
                FOREIGN KEY (user_id, chat_id)
                REFERENCES user_oneui (user_id, chat_id)
                ON DELETE CASCADE
            )
        """)
        logger.info("Таблица 'user_daily_onecoin_claims' проверена/создана.")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_daily_onecoin_claims_user_chat ON user_daily_onecoin_claims (user_id, chat_id);")


        logger.info("Индексы для 'user_daily_onecoin_claims' проверены/созданы.")
        
        
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_black_market_slots (
                user_id BIGINT NOT NULL,
                slot_number INTEGER NOT NULL, -- 1, 2, ..., Config.BLACKMARKET_TOTAL_SLOTS
                item_key TEXT NOT NULL,
                item_type TEXT NOT NULL,
                display_name_override TEXT,
                current_price INTEGER NOT NULL,
                original_price_before_bm INTEGER NOT NULL,
                is_stolen BOOLEAN DEFAULT FALSE NOT NULL,
                is_exclusive BOOLEAN DEFAULT FALSE NOT NULL,
                quantity_available INTEGER DEFAULT 1 NOT NULL,
                wear_data JSONB,
                custom_data JSONB,
                generated_at_utc TIMESTAMP WITH TIME ZONE NOT NULL,
                is_purchased BOOLEAN DEFAULT FALSE NOT NULL,
                PRIMARY KEY (user_id, slot_number)
            )
        """)
        logger.info("Таблица 'user_black_market_slots' проверена/создана.")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_bm_slots_user_generated_at ON user_black_market_slots (user_id, generated_at_utc)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_bm_slots_user_purchased ON user_black_market_slots (user_id, slot_number, is_purchased)")
        
        
        logger.info("Все таблицы проверены/созданы и при необходимости изменены.")

    except Exception as e:
        logger.critical(f"КРИТИЧЕСКАЯ ОШИБКА во время init_db: {e}", exc_info=True)
        # Можно перевыбросить ошибку, если это критично для запуска бота
        # raise
    finally:
        if conn and not conn.is_closed():
            await conn.close()
            
async def get_all_user_activity_chats(user_id: int, conn_ext: Optional[asyncpg.Connection] = None) -> List[int]:
    """
    Получает список ID всех чатов, где у пользователя есть какая-либо запись в user_oneui.
    """
    conn = conn_ext if conn_ext else await get_connection()
    try:
        # Выбираем только уникальные chat_id
        rows = await conn.fetch("SELECT DISTINCT chat_id FROM user_oneui WHERE user_id = $1", user_id)
        return [row['chat_id'] for row in rows]
    except Exception as e:
        logger.error(f"DB: Ошибка получения активных чатов для user {user_id}: {e}", exc_info=True)
        return []
    finally:
        if not conn_ext and conn and not conn.is_closed():
            await conn.close()            
            
            
async def get_user_bm_monthly_purchases(user_id: int, year_month: str, conn_ext: Optional[asyncpg.Connection] = None) -> int:
    """Возвращает phones_purchased_count для пользователя за указанный year_month. Если записи нет, возвращает 0."""
    conn = conn_ext if conn_ext else await get_connection()
    try:
        count = await conn.fetchval(
            "SELECT phones_purchased_count FROM user_black_market_monthly_stats WHERE user_id = $1 AND year_month = $2",
            user_id, year_month
        )
        return count if count is not None else 0
    except Exception as e:
        logger.error(f"DB: Ошибка получения месячных покупок ЧР для user {user_id}, месяц {year_month}: {e}", exc_info=True)
        return 0 # Безопасное значение при ошибке
    finally:
        if not conn_ext and conn and not conn.is_closed():
            await conn.close()

async def increment_user_bm_monthly_purchase(user_id: int, year_month: str, conn_ext: Optional[asyncpg.Connection] = None):
    """INSERT ... ON CONFLICT (user_id, year_month) DO UPDATE SET phones_purchased_count = user_black_market_monthly_stats.phones_purchased_count + 1."""
    conn = conn_ext if conn_ext else await get_connection()
    try:
        await conn.execute("""
            INSERT INTO user_black_market_monthly_stats (user_id, year_month, phones_purchased_count)
            VALUES ($1, $2, 1)
            ON CONFLICT (user_id, year_month) DO UPDATE SET
                phones_purchased_count = user_black_market_monthly_stats.phones_purchased_count + 1;
            """, user_id, year_month
        )
    except Exception as e:
        logger.error(f"DB: Ошибка инкремента месячных покупок ЧР для user {user_id}, месяц {year_month}: {e}", exc_info=True)
        # Здесь можно добавить re-raise, если это критично
    finally:
        if not conn_ext and conn and not conn.is_closed():
            await conn.close()

async def get_user_daily_onecoin_claim_status(user_id: int, chat_id: int, conn_ext: Optional[asyncpg.Connection] = None) -> Optional[datetime]:
    """
    Получает время последнего использования команды /onecoin (ежедневной награды) для пользователя в чате.
    Возвращает datetime UTC или None, если команда еще не использовалась.
    """
    conn = conn_ext if conn_ext else await get_connection()
    try:
        # Убедимся, что основная запись user_oneui существует
        await conn.execute("""
            INSERT INTO user_oneui (user_id, chat_id) VALUES ($1, $2)
            ON CONFLICT (user_id, chat_id) DO NOTHING;
        """, user_id, chat_id)

        # Создаем запись в user_daily_onecoin_claims, если ее нет (для новых пользователей/чатов)
        await conn.execute("""
            INSERT INTO user_daily_onecoin_claims (user_id, chat_id, last_claim_utc)
            VALUES ($1, $2, NULL)
            ON CONFLICT (user_id, chat_id) DO NOTHING;
        """, user_id, chat_id)

        timestamp_val = await conn.fetchval(
            "SELECT last_claim_utc FROM user_daily_onecoin_claims WHERE user_id = $1 AND chat_id = $2",
            user_id, chat_id
        )
        if timestamp_val and isinstance(timestamp_val, datetime):
            return timestamp_val.replace(tzinfo=dt_timezone.utc) if timestamp_val.tzinfo is None else timestamp_val.astimezone(dt_timezone.utc)
        return None
    except Exception as e:
        logger.error(f"DB: Ошибка получения статуса daily_onecoin_claim для user {user_id} chat {chat_id}: {e}", exc_info=True)
        return None
    finally:
        if not conn_ext and conn and not conn.is_closed():
            await conn.close()

async def update_user_daily_onecoin_claim_time(user_id: int, chat_id: int, claim_time_utc: datetime, conn_ext: Optional[asyncpg.Connection] = None):
    """
    Обновляет время последнего использования команды /onecoin (ежедневной награды).
    """
    conn = conn_ext if conn_ext else await get_connection()
    try:
        # Убедимся, что основная запись user_oneui существует
        await conn.execute("""
            INSERT INTO user_oneui (user_id, chat_id) VALUES ($1, $2)
            ON CONFLICT (user_id, chat_id) DO NOTHING;
        """, user_id, chat_id)

        ts_aware = claim_time_utc.astimezone(dt_timezone.utc) if claim_time_utc.tzinfo else claim_time_utc.replace(tzinfo=dt_timezone.utc)

        await conn.execute(
            """
            INSERT INTO user_daily_onecoin_claims (user_id, chat_id, last_claim_utc)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id, chat_id) DO UPDATE SET
                last_claim_utc = EXCLUDED.last_claim_utc;
            """,
            user_id, chat_id, ts_aware
        )
    except Exception as e:
        logger.error(f"DB: Ошибка обновления времени daily_onecoin_claim для user {user_id} chat {chat_id}: {e}", exc_info=True)
        # raise # Можно не перевыбрасывать, чтобы не ломать основной поток команды
    finally:
        if not conn_ext and conn and not conn.is_closed():
            await conn.close()


# --- НОВЫЕ ФУНКЦИИ ДЛЯ ПЕРСОНАЛЬНЫХ СЛОТОВ ЧЕРНОГО РЫНКА ---

async def get_user_black_market_slots(user_id: int, conn_ext: Optional[asyncpg.Connection] = None) -> List[Dict[str, Any]]:
    """
    Получает все слоты Черного Рынка для указанного пользователя,
    отсортированные по номеру слота.
    """
    conn = conn_ext if conn_ext else await get_connection()
    try:
        rows = await conn.fetch(
            """
            SELECT * FROM user_black_market_slots 
            WHERE user_id = $1 
            ORDER BY slot_number ASC
            """, user_id
        )
        # Преобразуем JSONB поля обратно в dict, если они не None
        result = []
        for row in rows:
            slot_data = dict(row)
            if slot_data.get('wear_data') and isinstance(slot_data['wear_data'], str): # json.loads ожидает строку
                try:
                    slot_data['wear_data'] = json.loads(slot_data['wear_data'])
                except json.JSONDecodeError:
                    logger.warning(f"DB (get_user_bm_slots): Ошибка декодирования JSON для wear_data user {user_id}, slot {slot_data.get('slot_number')}")
                    slot_data['wear_data'] = None # или {}
            if slot_data.get('custom_data') and isinstance(slot_data['custom_data'], str):
                try:
                    slot_data['custom_data'] = json.loads(slot_data['custom_data'])
                except json.JSONDecodeError:
                    logger.warning(f"DB (get_user_bm_slots): Ошибка декодирования JSON для custom_data user {user_id}, slot {slot_data.get('slot_number')}")
                    slot_data['custom_data'] = None # или {}
            result.append(slot_data)
        return result
    except Exception as e:
        logger.error(f"DB: Ошибка получения слотов ЧР для user {user_id}: {e}", exc_info=True)
        return []
    finally:
        if not conn_ext and conn and not conn.is_closed():
            await conn.close()

async def add_user_black_market_slot(
    user_id: int,
    slot_number: int, 
    item_key: str, 
    item_type: str,
    current_price: int, 
    original_price_before_bm: int,
    is_stolen: bool, 
    is_exclusive: bool, 
    quantity_available: int,
    generated_at_utc: datetime,
    display_name_override: Optional[str] = None,
    wear_data: Optional[Dict] = None, 
    custom_data: Optional[Dict] = None,
    conn_ext: Optional[asyncpg.Connection] = None
):
    """
    Добавляет или обновляет слот Черного Рынка для пользователя.
    """
    conn = conn_ext if conn_ext else await get_connection()
    try:
        wear_data_to_db = json.dumps(wear_data) if wear_data is not None else None
        custom_data_to_db = json.dumps(custom_data) if custom_data is not None else None
        
        if generated_at_utc.tzinfo is None: # Убедимся, что время aware
            generated_at_utc_aware = generated_at_utc.replace(tzinfo=dt_timezone.utc)
        else:
            generated_at_utc_aware = generated_at_utc.astimezone(dt_timezone.utc)

        await conn.execute(
            """
            INSERT INTO user_black_market_slots 
                (user_id, slot_number, item_key, item_type, display_name_override, 
                 current_price, original_price_before_bm, is_stolen, is_exclusive, 
                 quantity_available, wear_data, custom_data, generated_at_utc, is_purchased)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, FALSE)
            ON CONFLICT (user_id, slot_number) DO UPDATE SET
                item_key = EXCLUDED.item_key,
                item_type = EXCLUDED.item_type,
                display_name_override = EXCLUDED.display_name_override,
                current_price = EXCLUDED.current_price,
                original_price_before_bm = EXCLUDED.original_price_before_bm,
                is_stolen = EXCLUDED.is_stolen,
                is_exclusive = EXCLUDED.is_exclusive,
                quantity_available = EXCLUDED.quantity_available,
                wear_data = EXCLUDED.wear_data,
                custom_data = EXCLUDED.custom_data,
                generated_at_utc = EXCLUDED.generated_at_utc,
                is_purchased = FALSE; 
            """, # При обновлении сбрасываем is_purchased в FALSE
            user_id, slot_number, item_key, item_type, display_name_override,
            current_price, original_price_before_bm, is_stolen, is_exclusive,
            quantity_available, wear_data_to_db, custom_data_to_db, generated_at_utc_aware
        )
    except Exception as e:
        logger.error(f"DB: Ошибка при добавлении/обновлении слота ЧР ({slot_number}) для user {user_id}, ключ {item_key}: {e}", exc_info=True)
        # Можно перевыбросить исключение, если это критично
        # raise
    finally:
        if not conn_ext and conn and not conn.is_closed():
            await conn.close()

async def mark_user_bm_slot_as_purchased(user_id: int, slot_number: int, conn_ext: Optional[asyncpg.Connection] = None) -> bool:
    """
    Помечает слот Черного Рынка пользователя как купленный.
    Возвращает True, если строка была обновлена, иначе False.
    """
    conn = conn_ext if conn_ext else await get_connection()
    try:
        result = await conn.execute(
            """
            UPDATE user_black_market_slots
            SET is_purchased = TRUE
            WHERE user_id = $1 AND slot_number = $2 AND is_purchased = FALSE 
            """, # Добавляем AND is_purchased = FALSE для идемпотентности и чтобы не обновлять уже купленное
            user_id, slot_number
        )
        # Результат execute для UPDATE это строка вида "UPDATE N", где N - количество обновленных строк
        return result == "UPDATE 1"
    except Exception as e:
        logger.error(f"DB: Ошибка при пометке слота ЧР ({slot_number}) как купленного для user {user_id}: {e}", exc_info=True)
        return False
    finally:
        if not conn_ext and conn and not conn.is_closed():
            await conn.close()

async def clear_user_black_market_slots(user_id: int, conn_ext: Optional[asyncpg.Connection] = None):
    """
    Удаляет все слоты Черного Рынка для указанного пользователя.
    """
    conn = conn_ext if conn_ext else await get_connection()
    try:
        await conn.execute("DELETE FROM user_black_market_slots WHERE user_id = $1;", user_id)
        logger.info(f"DB: Все персональные слоты ЧР удалены для user {user_id}.")
    except Exception as e:
        logger.error(f"DB: Ошибка при очистке персональных слотов ЧР для user {user_id}: {e}", exc_info=True)
    finally:
        if not conn_ext and conn and not conn.is_closed():
            await conn.close()

async def get_specific_user_black_market_slot(user_id: int, slot_number: int, conn_ext: Optional[asyncpg.Connection] = None) -> Optional[Dict[str, Any]]:
    """
    Получает конкретный слот Черного Рынка для пользователя.
    """
    conn = conn_ext if conn_ext else await get_connection()
    try:
        row = await conn.fetchrow(
            "SELECT * FROM user_black_market_slots WHERE user_id = $1 AND slot_number = $2;",
            user_id, slot_number
        )
        if row:
            slot_data = dict(row)
            # Преобразование JSONB полей (аналогично get_user_black_market_slots)
            if slot_data.get('wear_data') and isinstance(slot_data['wear_data'], str):
                try: slot_data['wear_data'] = json.loads(slot_data['wear_data'])
                except json.JSONDecodeError: slot_data['wear_data'] = None
            if slot_data.get('custom_data') and isinstance(slot_data['custom_data'], str):
                try: slot_data['custom_data'] = json.loads(slot_data['custom_data'])
                except json.JSONDecodeError: slot_data['custom_data'] = None
            return slot_data
        return None
    except Exception as e:
        logger.error(f"DB: Ошибка получения конкретного слота ЧР ({slot_number}) для user {user_id}: {e}", exc_info=True)
        return None
    finally:
        if not conn_ext and conn and not conn.is_closed():
            await conn.close()





  

async def add_pending_phone_prize(
    user_id: int,
    phone_model_key: str,
    color: str,
    initial_memory_gb: int,
    prize_won_at_utc: datetime,
    original_roulette_chat_id: int,
    conn_ext: Optional[asyncpg.Connection] = None
) -> Optional[int]:
    """
    Добавляет запись о выигранном телефоне, ожидающем решения пользователя.
    """
    conn_to_use = conn_ext if conn_ext else await get_connection()
    try:
        # Проверяем, нет ли уже pending приза у этого пользователя
        existing_prize = await conn_to_use.fetchrow(
            "SELECT prize_id FROM user_pending_phone_prizes WHERE user_id = $1",
            user_id
        )
        if existing_prize:
            logger.warning(f"DB: User {user_id} already has a pending phone prize (ID: {existing_prize['prize_id']}). Cannot add another.")
            return None # Не позволяем иметь несколько pending призов

        # Гарантируем, что prize_won_at_utc имеет таймзону UTC
        if prize_won_at_utc.tzinfo is None:
            prize_won_at_utc = prize_won_at_utc.replace(tzinfo=dt_timezone.utc)
        else:
            prize_won_at_utc = prize_won_at_utc.astimezone(dt_timezone.utc)

        prize_id = await conn_to_use.fetchval(
            """
            INSERT INTO user_pending_phone_prizes
                (user_id, phone_model_key, color, initial_memory_gb, prize_won_at_utc, original_roulette_chat_id)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING prize_id
            """,
            user_id, phone_model_key, color, initial_memory_gb, prize_won_at_utc, original_roulette_chat_id
        )
        return prize_id
    except Exception as e:
        logger.error(f"DB: Ошибка при добавлении pending phone prize для user {user_id}, model {phone_model_key}: {e}", exc_info=True)
        return None
    finally:
        if not conn_ext and conn_to_use and not conn_to_use.is_closed():
            await conn_to_use.close()

async def get_pending_phone_prize(user_id: int, conn_ext: Optional[asyncpg.Connection] = None) -> Optional[Dict[str, Any]]:
    """
    Получает информацию об ожидающем решения призе пользователя.
    """
    conn_to_use = conn_ext if conn_ext else await get_connection()
    try:
        row = await conn_to_use.fetchrow(
            "SELECT * FROM user_pending_phone_prizes WHERE user_id = $1",
            user_id
        )
        if row:
            data = dict(row)
             # Гарантируем aware datetime для prize_won_at_utc
            if data.get('prize_won_at_utc') and isinstance(data['prize_won_at_utc'], datetime):
                ts = data['prize_won_at_utc']
                data['prize_won_at_utc'] = ts.replace(tzinfo=dt_timezone.utc) if ts.tzinfo is None else ts.astimezone(dt_timezone.utc)
            return data
        return None
    except Exception as e:
        logger.error(f"DB: Ошибка при получении pending phone prize для user {user_id}: {e}", exc_info=True)
        return None
    finally:
        if not conn_ext and conn_to_use and not conn_to_use.is_closed():
            await conn_to_use.close()

async def remove_pending_phone_prize(user_id: int, conn_ext: Optional[asyncpg.Connection] = None) -> bool:
    """
    Удаляет запись об ожидающем решения призе пользователя.
    """
    conn_to_use = conn_ext if conn_ext else await get_connection()
    try:
        result = await conn_to_use.execute(
            "DELETE FROM user_pending_phone_prizes WHERE user_id = $1",
            user_id
        )
        return result == "DELETE 1"
    except Exception as e:
        logger.error(f"DB: Ошибка при удалении pending phone prize для user {user_id}: {e}", exc_info=True)
        return False
    finally:
        if not conn_ext and conn_to_use and not conn_to_use.is_closed():
            await conn_to_use.close()

async def get_expired_pending_phone_prizes(expiry_time_ago_td: timedelta, conn_ext: Optional[asyncpg.Connection] = None) -> List[Dict[str, Any]]:
    """
    Получает список ожидающих призов, у которых истек срок принятия решения.
    """
    conn_to_use = conn_ext if conn_ext else await get_connection()
    try:
        now_utc = datetime.now(dt_timezone.utc)
        expiry_threshold_utc = now_utc - expiry_time_ago_td

        rows = await conn_to_use.fetch(
            "SELECT * FROM user_pending_phone_prizes WHERE prize_won_at_utc <= $1",
            expiry_threshold_utc
        )
        # Гарантируем aware datetime
        result = []
        for row_dict in (dict(r) for r in rows):
             if row_dict.get('prize_won_at_utc') and isinstance(row_dict['prize_won_at_utc'], datetime):
                ts = row_dict['prize_won_at_utc']
                row_dict['prize_won_at_utc'] = ts.replace(tzinfo=dt_timezone.utc) if ts.tzinfo is None else ts.astimezone(dt_timezone.utc)
             result.append(row_dict)
        return result
    except Exception as e:
        logger.error(f"DB: Ошибка при получении expired pending phone prizes: {e}", exc_info=True)
        return []
    finally:
        if not conn_ext and conn_to_use and not conn_to_use.is_closed():
            await conn_to_use.close()


async def _add_column_if_not_exists(conn: asyncpg.Connection, table_name: str, column_name: str, column_definition: str):
    """Вспомогательная функция для добавления колонки, если она не существует."""
    exists = await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = $1 AND column_name = $2)",
        table_name, column_name
    )
    if not exists:
        try:
            await conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")
            logger.info(f"Добавлена колонка '{column_name}' в таблицу '{table_name}'.")
        except Exception as e:
            logger.error(f"Не удалось добавить колонку '{column_name}' в таблицу '{table_name}': {e}")
    # else:
    # logger.debug(f"Колонка '{column_name}' уже существует в таблице '{table_name}'.")


async def add_onecoins_column(conn_ext: Optional[asyncpg.Connection] = None):
    conn = conn_ext if conn_ext else await get_connection()
    try:
        await _add_column_if_not_exists(conn, "user_oneui", "onecoins", "INTEGER DEFAULT 0 NOT NULL")
    finally:
        if not conn_ext and conn and not conn.is_closed(): await conn.close()

async def add_telegram_chat_link_column(conn_ext: Optional[asyncpg.Connection] = None):
    conn = conn_ext if conn_ext else await get_connection()
    try:
        await _add_column_if_not_exists(conn, "user_oneui", "telegram_chat_link", "TEXT DEFAULT NULL")
    finally:
        if not conn_ext and conn and not conn.is_closed(): await conn.close()

async def add_username_column(conn_ext: Optional[asyncpg.Connection] = None):
    conn = conn_ext if conn_ext else await get_connection()
    try:
        await _add_column_if_not_exists(conn, "user_oneui", "username", "TEXT")
    finally:
        if not conn_ext and conn and not conn.is_closed(): await conn.close()

async def add_full_name_column(conn_ext: Optional[asyncpg.Connection] = None):
    conn = conn_ext if conn_ext else await get_connection()
    try:
        await _add_column_if_not_exists(conn, "user_oneui", "full_name", "TEXT")
    finally:
        if not conn_ext and conn and not conn.is_closed(): await conn.close()

async def add_chat_title_column(conn_ext: Optional[asyncpg.Connection] = None):
    conn = conn_ext if conn_ext else await get_connection()
    try:
        await _add_column_if_not_exists(conn, "user_oneui", "chat_title", "TEXT")
    finally:
        if not conn_ext and conn and not conn.is_closed(): await conn.close()

async def add_version_column(conn_ext: Optional[asyncpg.Connection] = None):
    conn = conn_ext if conn_ext else await get_connection()
    try:
        await _add_column_if_not_exists(conn, "user_oneui", "version", "NUMERIC(10, 1) DEFAULT 0.0")
    finally:
        if not conn_ext and conn and not conn.is_closed(): await conn.close()

async def add_last_used_column(conn_ext: Optional[asyncpg.Connection] = None):
    conn = conn_ext if conn_ext else await get_connection()
    try:
        col_info = await conn.fetchrow("SELECT data_type FROM information_schema.columns WHERE table_name='user_oneui' AND column_name='last_used';")
        if col_info:
            if col_info['data_type'] == 'timestamp without time zone':
                await conn.execute("ALTER TABLE user_oneui ALTER COLUMN last_used TYPE TIMESTAMP WITH TIME ZONE USING last_used AT TIME ZONE 'UTC';")
                logger.info("ИЗМЕНЕНО (в add_last_used_column): 'user_oneui.last_used' конвертирована в TIMESTAMP WITH TIME ZONE.")
        else: # Если колонки нет, создаем ее с нужным типом
            await _add_column_if_not_exists(conn, "user_oneui", "last_used", "TIMESTAMP WITH TIME ZONE DEFAULT NULL")
            logger.info("НОВОЕ/ИЗМЕНЕНО (в add_last_used_column): Добавлена/проверена колонка 'last_used' TIMESTAMP WITH TIME ZONE.")
    finally:
        if not conn_ext and conn and not conn.is_closed(): await conn.close()


async def get_user_version(user_id: int, chat_id: int) -> float:
    MAX_RETRIES = 2
    last_exception = None
    for attempt in range(MAX_RETRIES + 1):
        conn = None
        try:
            conn = await get_connection()
            row = await conn.fetchrow(
                "SELECT version FROM user_oneui WHERE user_id = $1 AND chat_id = $2",
                user_id, chat_id
            )
            if row and row['version'] is not None:
                return float(row['version'])
            return 0.0 # Возвращаем 0.0, если нет записи или версия None
        except asyncpg.exceptions.InvalidCachedStatementError as e:
            last_exception = e
            logger.warning(f"DB: InvalidCachedStatementError in get_user_version for user {user_id}, chat {chat_id} on attempt {attempt+1}. Retrying...")
        except Exception as e:
            last_exception = e
            logger.error(f"DB: Exception in get_user_version for user {user_id}, chat {chat_id} on attempt {attempt+1}: {e}", exc_info=True)
        finally:
            if conn and not conn.is_closed():
                await conn.close()
        if attempt < MAX_RETRIES:
            await asyncio.sleep(0.1 * (2 ** attempt)) # Экспоненциальная задержка
        elif last_exception: # Если все попытки исчерпаны и была ошибка
            logger.error(f"DB: Failed get_user_version for user {user_id}, chat {chat_id} after {MAX_RETRIES+1} retries. Last error: {last_exception}")
            # Можно перевыбросить last_exception, если это критично, или вернуть дефолтное значение.
            # Для get_user_version, возврат 0.0 является приемлемым дефолтом при ошибке.
            return 0.0
    return 0.0 # Если цикл завершился без ошибок, но и без результата (маловероятно)

async def get_user_robbank_status(user_id: int, chat_id: int, conn_ext: Optional[asyncpg.Connection] = None) -> Optional[Dict[str, Any]]:
    conn = conn_ext if conn_ext else await get_connection()
    try:
        row = await conn.fetchrow(
            "SELECT * FROM user_robbank_status WHERE user_id = $1 AND chat_id = $2",
            user_id, chat_id
        )
        if row:
            data = dict(row)
            # Преобразование timestamp в aware datetime
            for ts_key in ['last_robbank_attempt_utc', 'robbank_oneui_blocked_until_utc', 'current_operation_start_utc']:
                if data.get(ts_key) and isinstance(data[ts_key], datetime):
                    ts_val = data[ts_key]
                    # Если время naive, делаем его aware UTC, иначе приводим к UTC
                    data[ts_key] = ts_val.replace(tzinfo=dt_timezone.utc) if ts_val.tzinfo is None else ts_val.astimezone(dt_timezone.utc)
            return data
        return None # Возвращаем None, если запись не найдена
    except Exception as e:
        logger.error(f"DB: Ошибка получения статуса ограбления для user {user_id}, chat {chat_id}: {e}", exc_info=True)
        return None
    finally:
        if not conn_ext and conn and not conn.is_closed():
            await conn.close()

async def update_user_robbank_status(
    user_id: int,
    chat_id: int,
    last_robbank_attempt_utc: Optional[datetime] = None,
    robbank_oneui_blocked_until_utc: Optional[datetime] = None,
    current_operation_name: Optional[str] = ..., # Используем ... как маркер "не передано"
    current_operation_start_utc: Optional[datetime] = ...,
    current_operation_base_reward: Optional[int] = ...,
    conn_ext: Optional[asyncpg.Connection] = None
):
    conn = conn_ext if conn_ext else await get_connection()
    try:
        # Получаем текущие значения, чтобы не перезаписать их None, если они не переданы для обновления
        current_status = await get_user_robbank_status(user_id, chat_id, conn_ext=conn)
        if not current_status: # Если записи нет, все передаваемые значения будут для INSERT
            current_status = {
                'last_robbank_attempt_utc': None,
                'robbank_oneui_blocked_until_utc': None,
                'current_operation_name': None,
                'current_operation_start_utc': None,
                'current_operation_base_reward': None
            }

        # Определяем значения для SQL-запроса
        # Если значение передано (не ...), используем его. Иначе, используем существующее из БД.
        val_last_attempt = last_robbank_attempt_utc if last_robbank_attempt_utc is not None else current_status.get('last_robbank_attempt_utc')
        val_blocked_until = robbank_oneui_blocked_until_utc if robbank_oneui_blocked_until_utc is not None else current_status.get('robbank_oneui_blocked_until_utc')
        
        # Для operation_*, если передается явный None, это означает очистку.
        # Если параметр не был передан (остался ...), то значение не меняется.
        val_op_name = current_operation_name if current_operation_name is not ... else current_status.get('current_operation_name')
        val_op_start = current_operation_start_utc if current_operation_start_utc is not ... else current_status.get('current_operation_start_utc')
        val_op_reward = current_operation_base_reward if current_operation_base_reward is not ... else current_status.get('current_operation_base_reward')

        # Преобразуем в aware UTC, если не None
        if val_last_attempt and val_last_attempt.tzinfo is None: val_last_attempt = val_last_attempt.replace(tzinfo=dt_timezone.utc)
        if val_blocked_until and val_blocked_until.tzinfo is None: val_blocked_until = val_blocked_until.replace(tzinfo=dt_timezone.utc)
        if val_op_start and val_op_start.tzinfo is None: val_op_start = val_op_start.replace(tzinfo=dt_timezone.utc)

        await conn.execute(
            """
            INSERT INTO user_robbank_status (
                user_id, chat_id, last_robbank_attempt_utc, robbank_oneui_blocked_until_utc,
                current_operation_name, current_operation_start_utc, current_operation_base_reward
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (user_id, chat_id) DO UPDATE SET
                last_robbank_attempt_utc = EXCLUDED.last_robbank_attempt_utc,
                robbank_oneui_blocked_until_utc = EXCLUDED.robbank_oneui_blocked_until_utc,
                current_operation_name = EXCLUDED.current_operation_name,
                current_operation_start_utc = EXCLUDED.current_operation_start_utc,
                current_operation_base_reward = EXCLUDED.current_operation_base_reward;
            """,
            user_id, chat_id, val_last_attempt, val_blocked_until,
            val_op_name, val_op_start, val_op_reward
        )
    except Exception as e:
        logger.error(f"DB: Ошибка обновления статуса ограбления для user {user_id}, chat {chat_id}: {e}", exc_info=True)
        # Можно перебросить исключение, если это критично для логики вызывающей функции
        # raise
    finally:
        if not conn_ext and conn and not conn.is_closed():
            await conn.close()
# В файле database.py

# ... (остальные импорты и функции НАД этой функцией) ...

async def update_user_version(user_id: int, chat_id: int, new_version: float,
                              username: Optional[str], full_name: Optional[str], chat_title: Optional[str],
                              telegram_chat_link: Optional[str] = None, conn_ext: Optional[asyncpg.Connection] = None,
                              set_last_used_time_utc: Optional[datetime] = None, # Время для установки, ЕСЛИ обновляем last_used
                              force_update_last_used: bool = True): # Флаг, действительно ли обновлять last_used
    rounded_version = round(new_version, 1)
    conn_to_use = conn_ext if conn_ext else await get_connection()

    # Это значение будет использовано в VALUES(...) для last_used.
    # Если force_update_last_used=False и set_last_used_time_utc=None (случай доп. попытки),
    # то оно останется None.
    timestamp_for_last_used_value: Optional[datetime] = None

    if force_update_last_used:
        # Для основной попытки: используем переданное время (которое должно быть current_time из oneui_command)
        # или текущее время, если set_last_used_time_utc не было передано (хотя оно должно быть).
        timestamp_for_last_used_value = set_last_used_time_utc if set_last_used_time_utc else datetime.now(dt_timezone.utc)
    elif set_last_used_time_utc is not None:
        # Случай, когда force_update_last_used=False, НО время все же передано.
        # В нашей текущей логике /oneui такого быть не должно при доп. попытке,
        # но для общей гибкости, если кто-то вызовет эту функцию так, мы запишем время.
        timestamp_for_last_used_value = set_last_used_time_utc
    # Если force_update_last_used=False и set_last_used_time_utc=None (доп. попытка),
    # timestamp_for_last_used_value останется None.

    # Гарантируем, что время в UTC, если оно установлено
    if timestamp_for_last_used_value and timestamp_for_last_used_value.tzinfo is None:
        timestamp_for_last_used_value = timestamp_for_last_used_value.replace(tzinfo=dt_timezone.utc)

    try:
        # Базовые поля для INSERT
        insert_columns_list = [
            "user_id", "chat_id", "username", "full_name", "chat_title",
            "version", "onecoins", "telegram_chat_link"
        ]
        # onecoins по умолчанию 0 для новой записи.
        insert_values_for_query_list = [
            user_id, chat_id, username, full_name, chat_title,
            rounded_version, 0, telegram_chat_link # onecoins = 0 по умолчанию
        ]

        # Динамически добавляем last_used в INSERT VALUES и список колонок,
        # только если timestamp_for_last_used_value установлено (т.е. мы ХОТИМ его записать).
        # Это важно для новых записей: если это доп. попытка и первая команда юзера, last_used будет NULL.
        if timestamp_for_last_used_value:
            insert_columns_list.append("last_used")
            insert_values_for_query_list.append(timestamp_for_last_used_value)

        insert_columns_str = ", ".join(insert_columns_list)
        insert_placeholders_str = ", ".join([f"${i+1}" for i in range(len(insert_values_for_query_list))])

        # Поля для UPDATE части ON CONFLICT
        update_set_parts = [
            "username = COALESCE(EXCLUDED.username, user_oneui.username)",
            "full_name = COALESCE(EXCLUDED.full_name, user_oneui.full_name)",
            "chat_title = COALESCE(EXCLUDED.chat_title, user_oneui.chat_title)",
            "version = EXCLUDED.version", # Всегда обновляем версию
            "telegram_chat_link = COALESCE(EXCLUDED.telegram_chat_link, user_oneui.telegram_chat_link)"
        ]

        # Обновляем last_used в секции UPDATE SET только если timestamp_for_last_used_value установлено.
        # EXCLUDED.last_used возьмет значение из VALUES (которое будет timestamp_for_last_used_value).
        if timestamp_for_last_used_value:
            update_set_parts.append("last_used = EXCLUDED.last_used")
        # Если timestamp_for_last_used_value is None (доп. попытка), то last_used НЕ обновляется в существующей записи.

        update_set_clause_str = ", ".join(update_set_parts)

        query = f"""
            INSERT INTO user_oneui ({insert_columns_str})
            VALUES ({insert_placeholders_str})
            ON CONFLICT (user_id, chat_id) DO UPDATE SET
                {update_set_clause_str};
        """

        await conn_to_use.execute(query, *insert_values_for_query_list)

        # --- Логика записи в историю ---
        # Время для записи в историю:
        # Если last_used обновлялся (timestamp_for_last_used_value не None, т.е. это была основная попытка),
        # используем это же время для консистентности.
        # Иначе (доп. попытка, last_used не трогали), используем текущее время для истории,
        # так как само событие изменения версии все равно произошло сейчас.
        history_timestamp_for_query: datetime
        if timestamp_for_last_used_value:
            history_timestamp_for_query = timestamp_for_last_used_value
        else:
            history_timestamp_for_query = datetime.now(dt_timezone.utc)

        if history_timestamp_for_query.tzinfo is None: # Гарантируем tzinfo для истории
            history_timestamp_for_query = history_timestamp_for_query.replace(tzinfo=dt_timezone.utc)

        await conn_to_use.execute("""
            INSERT INTO user_version_history (user_id, chat_id, version, changed_at, full_name_at_change)
            VALUES ($1, $2, $3, $4, $5)
        """, user_id, chat_id, rounded_version, history_timestamp_for_query, full_name)

    except Exception as e:
        logger.error(f"DB: Error in update_user_version for user {user_id}, chat {chat_id}: {e}", exc_info=True)
        raise
    finally:
        if not conn_ext and conn_to_use and not conn_to_use.is_closed():
            await conn_to_use.close()
            
async def check_cooldown(user_id: int, chat_id: int) -> Tuple[bool, Optional[datetime]]:
    conn = await get_connection()
    try:
        last_used_utc_db: Optional[datetime] = await conn.fetchval(
            "SELECT last_used FROM user_oneui WHERE user_id = $1 AND chat_id = $2",
            user_id, chat_id
        )

        if last_used_utc_db is None: return False, None # Нет записи, нет кулдауна
        if not isinstance(last_used_utc_db, datetime):
            logger.warning(f"DB: Invalid last_used type for user {user_id} chat {chat_id}: {type(last_used_utc_db)}")
            return False, None # Ошибка типа, считаем, что нет кулдауна

        # Гарантируем aware datetime
        last_used_utc = last_used_utc_db.astimezone(dt_timezone.utc) if last_used_utc_db.tzinfo else last_used_utc_db.replace(tzinfo=dt_timezone.utc)

        target_tz = pytz_timezone(Config.TIMEZONE)
        reset_hour_local = Config.RESET_HOUR

        now_utc = datetime.now(dt_timezone.utc)
        now_target_tz = now_utc.astimezone(target_tz)

        # Время сброса СЕГОДНЯ по местному времени
        reset_time_today_local = now_target_tz.replace(hour=reset_hour_local, minute=0, second=0, microsecond=0)

        # Определяем, какой был ПОСЛЕДНИЙ ФАКТИЧЕСКИЙ сброс
        # Если текущее время МЕНЬШЕ чем время сброса сегодня, значит последний сброс был ВЧЕРА в это же время
        if now_target_tz < reset_time_today_local:
            last_actual_reset_local = reset_time_today_local - timedelta(days=1)
        else: # Иначе, последний сброс был СЕГОДНЯ
            last_actual_reset_local = reset_time_today_local

        last_actual_reset_utc = last_actual_reset_local.astimezone(dt_timezone.utc) # Конвертируем в UTC для сравнения

        on_cooldown = last_used_utc > last_actual_reset_utc

        if on_cooldown:
            # Если на кулдауне, сообщаем, когда будет СЛЕДУЮЩИЙ сброс
            next_reset_local = reset_time_today_local if now_target_tz < reset_time_today_local else reset_time_today_local + timedelta(days=1)
            return True, next_reset_local.astimezone(dt_timezone.utc) # Возвращаем следующий сброс в UTC
        else:
            return False, None
    except Exception as e:
        logger.error(f"DB: Error in check_cooldown for user {user_id}, chat {chat_id}: {e}", exc_info=True)
        return False, None # При любой ошибке считаем, что кулдауна нет
    finally:
        if conn and not conn.is_closed(): await conn.close()            


async def get_top_users_in_chat(chat_id, limit=10) -> List[Dict[str, Any]]:
    conn = await get_connection()
    try:
        rows = await conn.fetch("""
            SELECT user_id, full_name, username, version, telegram_chat_link
            FROM user_oneui
            WHERE chat_id = $1 AND version IS NOT NULL -- Добавлено условие version IS NOT NULL
            ORDER BY version DESC, user_id ASC
            LIMIT $2
        """, chat_id, limit)
        return [dict(r) for r in rows]
    finally:
        if conn and not conn.is_closed(): await conn.close()

async def get_global_top_users(limit=10) -> List[Dict[str, Any]]:
    conn = await get_connection()
    try:
        rows = await conn.fetch("""
            WITH UserMaxVersion AS (
                SELECT user_id, MAX(version) as max_version 
                FROM user_oneui 
                WHERE version IS NOT NULL -- Учитываем только записи с версией
                GROUP BY user_id
            ),
            RankedUserChats AS (
                SELECT u.user_id, u.full_name, u.username, u.version, u.chat_id, u.chat_title, u.telegram_chat_link,
                       ROW_NUMBER() OVER (PARTITION BY u.user_id ORDER BY u.version DESC, u.last_used DESC NULLS LAST) as rn
                FROM user_oneui u 
                JOIN UserMaxVersion umv ON u.user_id = umv.user_id AND u.version = umv.max_version
                WHERE u.version IS NOT NULL -- Дополнительная проверка
            )
            SELECT ruc.user_id, ruc.full_name, ruc.username, ruc.version, ruc.chat_id, ruc.chat_title, ruc.telegram_chat_link
            FROM RankedUserChats ruc
            WHERE ruc.rn = 1
            ORDER BY ruc.version DESC, ruc.user_id ASC
            LIMIT $1
        """, limit)
        return [dict(r) for r in rows]
    finally:
        if conn and not conn.is_closed(): await conn.close()

async def get_user_top_versions(user_id, limit=5) -> List[Dict[str, Any]]:
    conn = await get_connection()
    try:
        rows = await conn.fetch("""
            SELECT chat_id, chat_title, version, telegram_chat_link
            FROM user_oneui
            WHERE user_id = $1 AND version IS NOT NULL -- Добавлено условие version IS NOT NULL
            ORDER BY version DESC, chat_id ASC
            LIMIT $2
        """, user_id, limit)
        return [dict(r) for r in rows]
    finally:
        if conn and not conn.is_closed(): await conn.close()

# В файле database.py

async def get_user_version_history(user_id: int, chat_id: Optional[int] = None, limit: int = 15) -> List[Dict[str, Any]]:
    conn = await get_connection()
    try:
        query_parts = []
        params = [user_id]
        
        # Базовый SELECT для получения нужных колонок
        select_clause = """
            SELECT
                version,
                changed_at,
                chat_id,
                full_name_at_change
        """
        
        # Условие WHERE
        where_clause = "WHERE user_id = $1 AND version IS NOT NULL"
        
        if chat_id:
            select_clause += ", NULL as chat_title_from_user_oneui" # Добавим, чтобы структура совпадала
            where_clause += " AND chat_id = $2"
            params.append(chat_id)
            
            # Для истории в конкретном чате, просто выбираем данные
            query = f"""
                {select_clause}
                FROM user_version_history
                {where_clause}
                ORDER BY changed_at DESC
                LIMIT $3
            """
            params.append(limit) # Лимит всегда последний
        else:
            # Для глобальной истории, присоединяем user_oneui для chat_title
            select_clause += """,
                COALESCE(uo.chat_title, 'Неизвестный чат') as chat_title_from_user_oneui
            """
            query = f"""
                {select_clause}
                FROM user_version_history uvh
                LEFT JOIN user_oneui uo ON uvh.user_id = uo.user_id AND uvh.chat_id = uo.chat_id
                {where_clause}
                ORDER BY uvh.changed_at DESC
                LIMIT $2
            """
            params.append(limit) # Лимит всегда последний

        result_records = await conn.fetch(query, *params)
        
        processed_records = []
        if result_records:
            # Переворачиваем для обработки от старых к новым
            # records_for_calc = [dict(r) for r in reversed(result_records)]
            
            # Теперь, когда мы получаем данные, отсортированные по DESC и ограниченные LIMIT,
            # мы хотим рассчитать разницу между последовательными записями в этом *результирующем наборе*.
            # Для этого нам нужно пройти по ним в обратном порядке (от самой старой в наборе к самой новой).
            
            # Сохраним предыдущую версию для вычисления разницы в рамках отображаемого списка
            # Изначально устанавливаем null или какое-то значение-маркер, чтобы не показывать разницу для самой старой записи
            previous_version_in_display = None 
            
            # Проходим по записям в обратном порядке (от самой старой к самой новой, которую мы хотим вывести вверху)
            # Чтобы в цикле иметь доступ к предыдущей версии, мы должны обрабатывать их от самой старой к самой новой.
            # Поэтому мы переворачиваем result_records, обрабатываем, а потом снова переворачиваем.

            # Создаем список словарей из полученных записей
            temp_records_list = [dict(r) for r in result_records]
            
            # Переворачиваем, чтобы начать с самой старой записи из полученного списка
            temp_records_list.reverse() 
            
            for i, record_dict in enumerate(temp_records_list):
                current_version = float(record_dict['version'])
                
                # Для первой записи в отсортированном по ASC списке (то есть, самой старой в LIMIT)
                # или если предыдущей версии нет (первая запись в истории вообще)
                if previous_version_in_display is None:
                    record_dict['version_diff'] = None # Разница не определена для первой записи
                else:
                    record_dict['version_diff'] = round(current_version - previous_version_in_display, 1)
                
                previous_version_in_display = current_version
                processed_records.append(record_dict)
        
        # Возвращаем список в обратном порядке, чтобы самые свежие записи были сверху
        processed_records.reverse()
        return processed_records
    except Exception as e:
        logger.error(f"DB: Ошибка в get_user_version_history для user {user_id} (chat_id: {chat_id}): {e}", exc_info=True)
        return []
    finally:
        if conn and not conn.is_closed():
            await conn.close()

async def add_family_log_entry(conn: asyncpg.Connection, family_id: int, action_type: str, description: str,
                               actor_user_id: Optional[int] = None, actor_full_name: Optional[str] = None,
                               target_user_id: Optional[int] = None, target_full_name: Optional[str] = None,
                               chat_id_context: Optional[int] = None, chat_title_context: Optional[str] = None):
    await conn.execute(
        """
        INSERT INTO family_logs (family_id, action_type, description, actor_user_id, actor_full_name,
                                 target_user_id, target_full_name, chat_id_context, chat_title_context, timestamp)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """, family_id, action_type, description, actor_user_id, actor_full_name,
        target_user_id, target_full_name, chat_id_context, chat_title_context, datetime.now(dt_timezone.utc)
    )

async def create_family(name: str, leader_id: int, leader_full_name: str, chat_id: int, chat_title: str) -> Tuple[bool, Any]:
    conn = await get_connection()
    try:
        async with conn.transaction():
            # Проверка на членство в другой семье
            existing_membership = await conn.fetchrow(
                "SELECT f.name FROM family_members fm JOIN families f ON fm.family_id = f.family_id WHERE fm.user_id = $1 AND fm.is_active = TRUE", leader_id
            )
            if existing_membership: return False, f"Вы уже состоите в семье '{existing_membership['name']}'."

            # Семья создается, поэтому member_count изначально 0, эта проверка здесь не нужна.
            # member_count_record = await conn.fetchrow("SELECT COUNT(*) as count FROM family_members WHERE family_id = $1 AND is_active = TRUE", family_id) # family_id еще не существует
            # member_count = member_count_record['count'] if member_count_record else 0
            # max_members = getattr(Config, 'FAMILY_MAX_MEMBERS', 10)
            # if member_count >= max_members: return False, f"В семье уже максимальное количество участников ({max_members})."

            now_utc = datetime.now(dt_timezone.utc)
            family_id_val = await conn.fetchval(
                """
                INSERT INTO families (name, leader_id, chat_id_created_in, chat_title_created_in, created_at)
                VALUES ($1, $2, $3, $4, $5) RETURNING family_id
                """, name, leader_id, chat_id, chat_title, now_utc
            )
            if family_id_val:
                await conn.execute(
                    """
                    INSERT INTO family_members (family_id, user_id, full_name_when_joined, chat_id_joined_from, joined_at, is_active)
                    VALUES ($1, $2, $3, $4, $5, TRUE)
                    ON CONFLICT (family_id, user_id) DO UPDATE SET
                        is_active = TRUE,
                        joined_at = EXCLUDED.joined_at,
                        full_name_when_joined = EXCLUDED.full_name_when_joined,
                        chat_id_joined_from = EXCLUDED.chat_id_joined_from
                    """, 
                    family_id_val, leader_id, leader_full_name, chat_id, now_utc
                )
                await add_family_log_entry(conn, family_id_val, "CREATE", f"Семья '{name}' создана лидером {leader_full_name}.",
                                           actor_user_id=leader_id, actor_full_name=leader_full_name,
                                           chat_id_context=chat_id, chat_title_context=chat_title)
                return True, family_id_val
            return False, "Не удалось создать семью (ошибка БД)."
    except asyncpg.exceptions.UniqueViolationError:
        return False, f"Семья с названием '{name}' уже существует."
    except Exception as e:
        logger.error(f"DB: Ошибка при создании семьи '{name}': {e}", exc_info=True)
        return False, str(e)
    finally:
        if conn and not conn.is_closed(): await conn.close()

async def add_user_to_family(user_id: int, user_full_name: str, family_id: int, chat_id: int, chat_title: str) -> Tuple[bool, str]:
    conn = await get_connection()
    try:
        async with conn.transaction():
            existing_membership = await conn.fetchrow(
                "SELECT f.name FROM family_members fm JOIN families f ON fm.family_id = f.family_id WHERE fm.user_id = $1 AND fm.is_active = TRUE", user_id
            )
            if existing_membership: return False, f"Вы уже состоите в семье '{existing_membership['name']}'."

            member_count_record = await conn.fetchrow("SELECT COUNT(*) as count FROM family_members WHERE family_id = $1 AND is_active = TRUE", family_id)
            member_count = member_count_record['count'] if member_count_record else 0

            max_members = getattr(Config, 'FAMILY_MAX_MEMBERS', 10)
            if member_count >= max_members: return False, f"В семье уже максимальное количество участников ({max_members})."

            now_utc = datetime.now(dt_timezone.utc)
            await conn.execute(
                """
                INSERT INTO family_members (family_id, user_id, full_name_when_joined, chat_id_joined_from, joined_at, is_active)
                VALUES ($1, $2, $3, $4, $5, TRUE)
                ON CONFLICT (family_id, user_id) DO UPDATE SET
                    is_active = TRUE,
                    joined_at = EXCLUDED.joined_at,
                    full_name_when_joined = EXCLUDED.full_name_when_joined,
                    chat_id_joined_from = EXCLUDED.chat_id_joined_from
                """, 
                family_id, user_id, user_full_name, chat_id, now_utc
            )
            family_info = await conn.fetchrow("SELECT name FROM families WHERE family_id = $1", family_id)
            if family_info:
                await add_family_log_entry(conn, family_id, "JOIN", f"Пользователь {user_full_name} вступил в семью.",
                                           actor_user_id=user_id, actor_full_name=user_full_name,
                                           chat_id_context=chat_id, chat_title_context=chat_title)
                return True, f"Вы успешно вступили в семью '{family_info['name']}'!"
            return False, "Ошибка при вступлении в семью (не найдена информация о семье после добавления)."
    except asyncpg.exceptions.ForeignKeyViolationError: # Сработает, если family_id не существует в families
        return False, "Семья не найдена (FK)."
    except Exception as e:
        logger.error(f"DB: Ошибка при вступлении пользователя {user_id} в семью {family_id}: {e}", exc_info=True)
        return False, f"Произошла ошибка: {str(e)}"
    finally:
        if conn and not conn.is_closed(): await conn.close()

async def remove_user_from_family(user_id_to_remove: int, family_id: int,
                                  actor_user_id: int, actor_full_name: str, action_type: str,
                                  chat_id: int, chat_title: str,
                                  target_full_name_override: Optional[str] = None) -> Tuple[bool, str]:
    conn = await get_connection()
    try:
        async with conn.transaction():
            member_to_remove = await conn.fetchrow(
                "SELECT user_id, full_name_when_joined FROM family_members WHERE user_id = $1 AND family_id = $2 AND is_active = TRUE",
                user_id_to_remove, family_id
            )
            if not member_to_remove: return False, "Пользователь не найден в этой семье или уже неактивен."

            target_display_name = target_full_name_override or member_to_remove['full_name_when_joined'] or f"User ID {user_id_to_remove}"

            # Вместо DELETE, устанавливаем is_active = FALSE, если хотим сохранить историю членства.
            # Если нужно полное удаление, то result = await conn.execute("DELETE FROM family_members WHERE ...")
            result = await conn.execute(
                "UPDATE family_members SET is_active = FALSE WHERE user_id = $1 AND family_id = $2",
                user_id_to_remove, family_id
            )
            
            if result == "UPDATE 0": # или "DELETE 0", если используется DELETE
                 logger.warning(f"DB: remove_user_from_family - пользователь {user_id_to_remove} не был обновлен/удален из семьи {family_id}, хотя проверка прошла. Result: {result}")
                 return False, "Не удалось удалить пользователя из семьи (возможно, он уже был удален)."


            family_info = await conn.fetchrow("SELECT name, leader_id FROM families WHERE family_id = $1", family_id)
            if not family_info: return False, "Семья не найдена (внутренняя ошибка)."

            # Проверяем, был ли удален лидер. Если да, и в семье остались участники, семья должна быть распущена или передан лидер.
            # Текущая логика этого не обрабатывает, но это важное соображение.
            # Пока что, если лидер покидает семью, она остается без лидера (что не очень хорошо).
            if family_info['leader_id'] == user_id_to_remove:
                 # TODO: Добавить логику обработки ухода/кика лидера (роспуск семьи или передача лидерства)
                 logger.warning(f"Лидер (ID: {user_id_to_remove}) покинул/был удален из семьи '{family_info['name']}' (ID: {family_id}). Требуется логика обработки.")


            log_message, response_message = "", ""
            if action_type.upper() == "LEAVE":
                log_message = f"Пользователь {target_display_name} покинул семью."
                response_message = f"Вы успешно покинули семью '{family_info['name']}'."
            elif action_type.upper() == "KICK":
                log_message = f"Пользователь {target_display_name} был исключен из семьи лидером {actor_full_name}."
                response_message = f"Пользователь {target_display_name} был успешно исключен из семьи '{family_info['name']}'."
            else:
                return False, "Неизвестный тип действия при удалении из семьи."

            await add_family_log_entry(conn, family_id, action_type.upper(), log_message,
                                       actor_user_id=actor_user_id, actor_full_name=actor_full_name,
                                       target_user_id=user_id_to_remove, target_full_name=target_display_name,
                                       chat_id_context=chat_id, chat_title_context=chat_title)
            return True, response_message
    except Exception as e:
        logger.error(f"DB: Ошибка при удалении пользователя {user_id_to_remove} из семьи {family_id}: {e}", exc_info=True)
        return False, str(e)
    finally:
        if conn and not conn.is_closed(): await conn.close()

async def update_family_name(family_id: int, new_name: str, actor_user_id: int, actor_full_name: str, chat_id: int, chat_title: str) -> Tuple[bool, str]:
    conn = await get_connection()
    try:
        async with conn.transaction():
            family = await conn.fetchrow("SELECT name, leader_id FROM families WHERE family_id = $1", family_id)
            if not family: return False, "Семья не найдена."
            if family['leader_id'] != actor_user_id: return False, "Только лидер может переименовать семью."

            old_name = family['name']
            if old_name == new_name: return True, f"Название семьи уже '{new_name}'."

            await conn.execute("UPDATE families SET name = $1 WHERE family_id = $2", new_name, family_id)
            await add_family_log_entry(conn, family_id, "RENAME", f"Название семьи изменено с '{old_name}' на '{new_name}' лидером {actor_full_name}.",
                                       actor_user_id=actor_user_id, actor_full_name=actor_full_name,
                                       chat_id_context=chat_id, chat_title_context=chat_title)
            return True, f"Название семьи успешно изменено на '{new_name}'."
    except asyncpg.exceptions.UniqueViolationError:
        return False, f"Семья с названием '{new_name}' уже существует."
    except Exception as e:
        logger.error(f"DB: Ошибка при переименовании семьи {family_id}: {e}", exc_info=True)
        return False, str(e)
    finally:
        if conn and not conn.is_closed(): await conn.close()

async def get_family_by_name(name: str, chat_id: Optional[int] = None) -> Optional[Dict[str, Any]]: # chat_id здесь не используется, можно убрать
    conn = await get_connection()
    try:
        row = await conn.fetchrow("SELECT * FROM families WHERE name = $1", name)
        return dict(row) if row else None
    finally:
        if conn and not conn.is_closed(): await conn.close()

async def get_family_by_id(family_id: int) -> Optional[Dict[str, Any]]:
    conn = await get_connection()
    try:
        row = await conn.fetchrow("SELECT * FROM families WHERE family_id = $1", family_id)
        return dict(row) if row else None
    finally:
        if conn and not conn.is_closed(): await conn.close()

async def get_user_family_membership(user_id: int) -> Optional[Dict[str, Any]]:
    conn = await get_connection()
    try:
        row = await conn.fetchrow(
            """
            SELECT fm.family_id, fm.user_id, fm.joined_at,
                   f.name as family_name, f.leader_id
            FROM family_members fm
            JOIN families f ON fm.family_id = f.family_id
            WHERE fm.user_id = $1 AND fm.is_active = TRUE
            """, user_id
        )
        return dict(row) if row else None
    finally:
        if conn and not conn.is_closed(): await conn.close()

async def get_family_members(family_id: int, active_only: bool = True) -> List[Dict[str, Any]]:
    conn = await get_connection()
    try:
        query = """
            SELECT
                fm.user_id,
                fm.full_name_when_joined,
                fm.joined_at,
                (SELECT uo.username
                 FROM user_oneui uo
                 WHERE uo.user_id = fm.user_id
                 ORDER BY uo.last_used DESC NULLS LAST -- Берем самый свежий username
                 LIMIT 1) as username
            FROM family_members fm
            WHERE fm.family_id = $1
        """
        params: List[Any] = [family_id]
        if active_only:
            query += " AND fm.is_active = TRUE"
        query += " ORDER BY fm.joined_at ASC"

        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"DB: Ошибка при получении участников семьи {family_id}: {e}", exc_info=True)
        return []
    finally:
        if conn and not conn.is_closed(): await conn.close()

async def get_top_families_by_total_contribution(limit: int = 10) -> List[Dict[str, Any]]: # Эта функция, видимо, для другого топа (не соревнований)
    conn = await get_connection()
    try:
        # Этот запрос показывает топ семей по количеству активных участников.
        # Возможно, имелось в виду что-то другое под "total_contribution".
        # Если нужен топ по сумме версий OneUI или OneCoin всех участников, запрос будет сложнее.
        query = """
            SELECT
                f.family_id, f.name, f.leader_id,
                (SELECT uo.full_name FROM user_oneui uo WHERE uo.user_id = f.leader_id ORDER BY uo.last_used DESC NULLS LAST LIMIT 1) as leader_full_name,
                (SELECT COUNT(*) FROM family_members fm_count WHERE fm_count.family_id = f.family_id AND fm_count.is_active = TRUE) as member_count
            FROM families f
            ORDER BY member_count DESC, f.name ASC
            LIMIT $1;
        """
        rows = await conn.fetch(query, limit)
        return [dict(row) for row in rows]
    finally:
        if conn and not conn.is_closed(): await conn.close()

async def get_family_logs(family_id: int, limit: int = 15) -> List[Dict[str, Any]]:
    conn = await get_connection()
    try:
        rows = await conn.fetch(
            "SELECT * FROM family_logs WHERE family_id = $1 ORDER BY timestamp DESC LIMIT $2",
            family_id, limit
        )
        return [dict(r) for r in rows] # Преобразуем каждую запись в dict
    finally:
        if conn and not conn.is_closed(): await conn.close()

async def get_user_onecoins(user_id: int, chat_id: int, conn_ext: Optional[asyncpg.Connection] = None) -> int:
    # Используем переданное соединение, если оно есть, иначе получаем новое
    conn_to_use = conn_ext if conn_ext else await get_connection()
    conn_was_none = conn_ext is None # Флаг, чтобы знать, нужно ли закрывать соединение в finally

    try:
        # Убедимся, что запись пользователя существует.
        # Если запись не существует, создаем минимальную, чтобы избежать ошибок.
        # Вставляем только user_id и chat_id при первом создании, остальные поля возьмут DEFAULT.
        await conn_to_use.execute("""
            INSERT INTO user_oneui (user_id, chat_id)
            VALUES ($1, $2)
            ON CONFLICT (user_id, chat_id) DO NOTHING; -- DO NOTHING, чтобы не сбрасывать существующие данные
        """, user_id, chat_id)

        # Теперь безопасно получаем баланс
        balance = await conn_to_use.fetchval(
            "SELECT onecoins FROM user_oneui WHERE user_id = $1 AND chat_id = $2",
            user_id, chat_id
        )
        return balance if balance is not None else 0 # Возвращаем 0, если onecoins почему-то NULL
    except Exception as e:
        logger.error(f"DB: Error in get_user_onecoins for user {user_id}, chat {chat_id}: {e}", exc_info=True)
        return 0 # При любой ошибке возвращаем 0
    finally:
        # Закрываем соединение только если оно было создано ВНУТРИ этой функции
        if conn_was_none and conn_to_use and not conn_to_use.is_closed():
            await conn_to_use.close()

async def update_user_onecoins(user_id: int, chat_id: int, amount_change: int,
                               username: Optional[str] = None, full_name: Optional[str] = None,
                               chat_title: Optional[str] = None, conn_ext: Optional[asyncpg.Connection] = None) -> int:
    conn_to_use = conn_ext if conn_ext else await get_connection()
    try:
        # Сначала убедимся, что запись пользователя существует и содержит актуальные username, full_name, chat_title
        # Этот INSERT ... ON CONFLICT обновит данные пользователя, если они изменились, но не затронет onecoins и version.
        await conn_to_use.execute("""
            INSERT INTO user_oneui (user_id, chat_id, username, full_name, chat_title, version, onecoins, last_used)
            VALUES (
                $1, $2, $3, $4, $5,
                COALESCE((SELECT version FROM user_oneui WHERE user_id = $1 AND chat_id = $2 LIMIT 1), 0.0), 
                COALESCE((SELECT onecoins FROM user_oneui WHERE user_id = $1 AND chat_id = $2 LIMIT 1), 0), 
                COALESCE((SELECT last_used FROM user_oneui WHERE user_id = $1 AND chat_id = $2 LIMIT 1), $6)
            )
            ON CONFLICT (user_id, chat_id) DO UPDATE SET
                username = COALESCE(EXCLUDED.username, user_oneui.username),
                full_name = COALESCE(EXCLUDED.full_name, user_oneui.full_name),
                chat_title = COALESCE(EXCLUDED.chat_title, user_oneui.chat_title);
            """, user_id, chat_id, username, full_name, chat_title, datetime.now(dt_timezone.utc)
        )

        # Теперь обновляем баланс OneCoin
        new_balance_record = await conn_to_use.fetchrow("""
            UPDATE user_oneui
            SET onecoins = onecoins + $3
            WHERE user_id = $1 AND chat_id = $2
            RETURNING onecoins;
            """, user_id, chat_id, amount_change
        )

        if new_balance_record and new_balance_record['onecoins'] is not None:
            return new_balance_record['onecoins']
        else: # Редкий случай, если RETURNING не сработал как ожидалось
            current_balance = await conn_to_use.fetchval(
                 "SELECT onecoins FROM user_oneui WHERE user_id = $1 AND chat_id = $2", user_id, chat_id
            )
            logger.warning(f"DB: update_user_onecoins for user {user_id} chat {chat_id} did not return balance from UPDATE. Fallback read: {current_balance}")
            return current_balance if current_balance is not None else 0
    except Exception as e:
        logger.error(f"DB: Error updating onecoins for user {user_id} chat {chat_id}: {e}", exc_info=True)
        try: # Попытка прочитать баланс даже после ошибки
            current_balance_after_fail = await conn_to_use.fetchval(
                "SELECT onecoins FROM user_oneui WHERE user_id = $1 AND chat_id = $2", user_id, chat_id
            )
            return current_balance_after_fail if current_balance_after_fail is not None else 0
        except:
            logger.error(f"DB: Failed to read onecoins after update error for user {user_id} chat {chat_id}.")
            return 0 # Безопасное значение по умолчанию
    finally:
        if not conn_ext and conn_to_use and not conn_to_use.is_closed():
            await conn_to_use.close()
            
async def update_user_total_business_income(user_id: int, amount_change: int, conn_ext: Optional[asyncpg.Connection] = None) -> int:
    """
    Увеличивает общий заработанный доход пользователя с бизнесов.
    Возвращает новый общий доход.
    """
    conn_to_use = conn_ext if conn_ext else await get_connection()
    try:
        new_total_income = await conn_to_use.fetchval("""
            UPDATE user_oneui
            SET total_income_earned_from_businesses = COALESCE(total_income_earned_from_businesses, 0) + $2
            WHERE user_id = $1
            RETURNING total_income_earned_from_businesses;
            """, user_id, amount_change
        )
        return new_total_income if new_total_income is not None else 0
    except Exception as e:
        logger.error(f"DB: Error updating total business income for user {user_id}: {e}", exc_info=True)
        return 0
    finally:
        if not conn_ext and conn_to_use and not conn_to_use.is_closed():
            await conn_to_use.close()            
            

async def get_top_onecoins_in_chat(chat_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    conn = await get_connection()
    try:
        rows = await conn.fetch("""
            SELECT user_id, full_name, username, onecoins, telegram_chat_link
            FROM user_oneui
            WHERE chat_id = $1 AND onecoins > 0
            ORDER BY onecoins DESC, user_id ASC
            LIMIT $2
        """, chat_id, limit)
        return [dict(r) for r in rows]
    finally:
        if conn and not conn.is_closed(): await conn.close()
        
async def set_user_selected_achievement(user_id: int, achievement_key: Optional[str], conn_ext: Optional[asyncpg.Connection] = None) -> bool:
    """
    Устанавливает (или сбрасывает) выбранное пользователем достижение в таблице user_display_achievement.
    """
    conn = conn_ext if conn_ext else await get_connection()
    try:
        # Убедимся, что dt_timezone импортирован: from datetime import timezone as dt_timezone
        now_utc = datetime.now(dt_timezone.utc) 
        await conn.execute(
            """
            INSERT INTO user_display_achievement (user_id, selected_achievement_key, updated_at)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id) DO UPDATE SET
                selected_achievement_key = EXCLUDED.selected_achievement_key,
                updated_at = EXCLUDED.updated_at;
            """,
            user_id, achievement_key, now_utc
        )
        logger.info(f"DB: Selected achievement for user {user_id} set to '{achievement_key}' in user_display_achievement.")
        return True
    except Exception as e:
        logger.error(f"DB: Error setting selected achievement for user {user_id} to '{achievement_key}' in user_display_achievement: {e}", exc_info=True)
        return False
    finally:
        if not conn_ext and conn and not conn.is_closed():
            await conn.close()

async def get_user_selected_achievement(user_id: int, conn_ext: Optional[asyncpg.Connection] = None) -> Optional[str]:
    """
    Получает ключ выбранного достижения для пользователя из таблицы user_display_achievement.
    """
    conn = conn_ext if conn_ext else await get_connection()
    try:
        selected_key = await conn.fetchval(
            "SELECT selected_achievement_key FROM user_display_achievement WHERE user_id = $1",
            user_id
        )
        return selected_key
    except Exception as e:
        logger.error(f"DB: Error getting selected achievement for user {user_id} from user_display_achievement: {e}", exc_info=True)
        return None
    finally:
        if not conn_ext and conn and not conn.is_closed():
            await conn.close()

async def get_user_max_version_global(user_id: int) -> float:
    conn = await get_connection()
    try:
        max_version = await conn.fetchval(
            "SELECT MAX(version) FROM user_oneui WHERE user_id = $1 AND version IS NOT NULL", user_id
        )
        return float(max_version) if max_version is not None else 0.0
    except Exception as e:
        logger.warning(f"DB: Could not get user_max_version_global for {user_id}: {e}")
        return 0.0
    finally:
        if conn and not conn.is_closed(): await conn.close()
        
async def get_global_top_onecoins(limit: int = 10, conn_ext: Optional[asyncpg.Connection] = None) -> List[Dict[str, Any]]:
    """
    Получает глобальный топ пользователей по их максимальному балансу OneCoin в одном из чатов.
    Для каждого пользователя выбирается чат с наибольшим количеством OneCoin.
    """
    conn = conn_ext if conn_ext else await get_connection()
    try:
        query = """
            WITH RankedUserMaxCoinsInOneChat AS (
                SELECT
                    user_id,
                    full_name,
                    username,
                    chat_id,
                    chat_title,
                    telegram_chat_link,
                    onecoins, -- Это будет максимальный onecoins в одном чате для этого user_id
                    last_used,
                    -- Ранжируем чаты пользователя по количеству onecoins (по убыванию),
                    -- а затем по last_used, чтобы при равных onecoins выбрать более свежий
                    ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY onecoins DESC, last_used DESC NULLS LAST) as rn_max_coins_chat
                FROM user_oneui
                WHERE onecoins > 0 -- Учитываем только положительные балансы
            )
            SELECT
                user_id,
                full_name,
                username,
                onecoins, -- Это и будет максимальный баланс в одном из чатов
                chat_id,
                chat_title,
                telegram_chat_link
            FROM RankedUserMaxCoinsInOneChat
            WHERE rn_max_coins_chat = 1 -- Выбираем для каждого пользователя только чат с максимальным балансом
            ORDER BY onecoins DESC, user_id ASC -- Сортируем по этому максимальному балансу
            LIMIT $1;
        """
        rows = await conn.fetch(query, limit)
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"DB: Error in get_global_top_onecoins (max in one chat): {e}", exc_info=True)
        return []
    finally:
        if not conn_ext and conn and not conn.is_closed():
            await conn.close()        

async def get_user_max_oneui_for_day_in_competition(user_id: int, target_date_local: DDate) -> Optional[float]:
    conn = await get_connection()
    try:
        app_tz = pytz_timezone(Config.TIMEZONE)
        reset_hour = Config.RESET_HOUR
        
        # День начинается в час сброса предыдущего дня и заканчивается непосредственно перед часом сброса текущего дня
        start_of_target_day_local_naive = datetime.combine(target_date_local, datetime.min.time()).replace(hour=reset_hour)
        start_of_target_day_local = app_tz.localize(start_of_target_day_local_naive) - timedelta(days=1)
        end_of_target_day_local = start_of_target_day_local + timedelta(days=1)

        start_utc = start_of_target_day_local.astimezone(dt_timezone.utc)
        end_utc = end_of_target_day_local.astimezone(dt_timezone.utc)

        max_version = await conn.fetchval(
            """
            SELECT MAX(version) FROM user_version_history
            WHERE user_id = $1 AND changed_at >= $2 AND changed_at < $3 AND version IS NOT NULL
            """,
            user_id, start_utc, end_utc
        )
        return float(max_version) if max_version is not None else 0.0
    except Exception as e:
        logger.error(f"DB: Error in get_user_max_oneui_for_day_in_competition for user {user_id}, date {target_date_local}: {e}", exc_info=True)
        return 0.0
    finally:
        if conn and not conn.is_closed(): await conn.close()

async def create_family_competition(admin_id: int, duration_days: int) -> Optional[int]:
    conn = await get_connection()
    try:
        active_comp_check = await conn.fetchval(
            "SELECT competition_id FROM family_competitions WHERE is_active = TRUE AND end_ts > $1",
            datetime.now(dt_timezone.utc)
        )
        if active_comp_check: return None

        start_ts = datetime.now(dt_timezone.utc)
        end_ts = start_ts + timedelta(days=duration_days)
        
        competition_id = await conn.fetchval(
            """
            INSERT INTO family_competitions (start_ts, end_ts, is_active, started_by_admin_id, rewards_distributed)
            VALUES ($1, $2, TRUE, $3, FALSE)
            RETURNING competition_id
            """,
            start_ts, end_ts, admin_id
        )
        return competition_id
    except Exception as e:
        logger.error(f"DB: ERROR in create_family_competition: {e}", exc_info=True)
        return None
    finally:
        if conn and not conn.is_closed(): await conn.close()

async def get_active_family_competition() -> Optional[Dict[str, Any]]:
    conn = await get_connection()
    try:
        row = await conn.fetchrow(
            "SELECT * FROM family_competitions WHERE is_active = TRUE AND end_ts > $1 ORDER BY start_ts DESC LIMIT 1",
            datetime.now(dt_timezone.utc)
        )
        if row:
             data = dict(row)
             if data.get('start_ts'): data['start_ts'] = data['start_ts'].replace(tzinfo=dt_timezone.utc) if data['start_ts'].tzinfo is None else data['start_ts'].astimezone(dt_timezone.utc)
             if data.get('end_ts'): data['end_ts'] = data['end_ts'].replace(tzinfo=dt_timezone.utc) if data['end_ts'].tzinfo is None else data['end_ts'].astimezone(dt_timezone.utc)
             return data
        return None
    finally:
        if conn and not conn.is_closed(): await conn.close()

async def get_latest_completed_unrewarded_competition() -> Optional[Dict[str,Any]]:
    conn = await get_connection()
    try:
        row = await conn.fetchrow(
            "SELECT * FROM family_competitions WHERE is_active = FALSE AND rewards_distributed = FALSE ORDER BY end_ts DESC LIMIT 1"
        )
        if row:
             data = dict(row)
             if data.get('start_ts'): data['start_ts'] = data['start_ts'].replace(tzinfo=dt_timezone.utc) if data['start_ts'].tzinfo is None else data['start_ts'].astimezone(dt_timezone.utc)
             if data.get('end_ts'): data['end_ts'] = data['end_ts'].replace(tzinfo=dt_timezone.utc) if data['end_ts'].tzinfo is None else data['end_ts'].astimezone(dt_timezone.utc)
             return data
        return None
    finally:
        if conn and not conn.is_closed(): await conn.close()

async def record_family_daily_contribution(competition_id: int, family_id: int, user_id: int, contribution_date: DDate, max_version_today: float, conn_ext: Optional[asyncpg.Connection] = None):
    conn = conn_ext if conn_ext else await get_connection()
    try:
        await conn.execute(
            """
            INSERT INTO family_competition_daily_contributions
                (competition_id, family_id, user_id, contribution_date, max_oneui_version_today)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (competition_id, family_id, user_id, contribution_date) DO UPDATE SET
                max_oneui_version_today = GREATEST(EXCLUDED.max_oneui_version_today, family_competition_daily_contributions.max_oneui_version_today)
            """,
            competition_id, family_id, user_id, contribution_date, max_version_today
        )
    except Exception as e:
        logger.error(f"DB: Error recording daily contribution for comp {competition_id}, fam {family_id}, user {user_id}: {e}", exc_info=True)
    finally:
        if not conn_ext and conn and not conn.is_closed(): await conn.close()


async def calculate_and_set_family_competition_total_scores(competition_id: int, conn_ext: Optional[asyncpg.Connection] = None):
    conn = conn_ext if conn_ext else await get_connection()
    try:
        await conn.execute("DELETE FROM family_competition_scores WHERE competition_id = $1", competition_id)
        family_scores_data = await conn.fetch(
            """
            SELECT family_id, SUM(max_oneui_version_today) as calculated_total_score
            FROM family_competition_daily_contributions
            WHERE competition_id = $1 GROUP BY family_id
            HAVING SUM(max_oneui_version_today) IS NOT NULL
            """, competition_id
        )
        for record in family_scores_data:
            await conn.execute(
                "INSERT INTO family_competition_scores (competition_id, family_id, total_score) VALUES ($1, $2, $3)",
                competition_id, record['family_id'], record['calculated_total_score']
            )
        logger.info(f"DB: Recalculated and set scores for competition {competition_id}.")
    except Exception as e:
        logger.error(f"DB: Error calculating total scores for competition {competition_id}: {e}", exc_info=True)
    finally:
        if not conn_ext and conn and not conn.is_closed(): await conn.close()

async def get_competition_leaderboard(competition_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    conn = await get_connection()
    try:
        rows = await conn.fetch(
            """
            SELECT fcs.family_id, f.name as family_name, fcs.total_score
            FROM family_competition_scores fcs
            JOIN families f ON fcs.family_id = f.family_id
            WHERE fcs.competition_id = $1
            ORDER BY fcs.total_score DESC, f.name ASC LIMIT $2
            """, competition_id, limit
        )
        return [dict(r) for r in rows]
    finally:
        if conn and not conn.is_closed(): await conn.close()

async def set_competition_winner_and_finish_status(competition_id: int, winner_family_id: Optional[int], conn_ext: Optional[asyncpg.Connection] = None):
    conn = conn_ext if conn_ext else await get_connection()
    try:
        await conn.execute(
            "UPDATE family_competitions SET winner_family_id = $2, is_active = FALSE WHERE competition_id = $1",
            competition_id, winner_family_id
        )
        logger.info(f"DB: Marked competition {competition_id} as finished. Winner Family ID: {winner_family_id}.")
    except Exception as e:
        logger.error(f"DB: ERROR in set_competition_winner_and_finish_status for competition {competition_id}: {e}", exc_info=True)
    finally:
         if not conn_ext and conn and not conn.is_closed(): await conn.close()

async def mark_competition_rewards_distributed(competition_id: int, conn_ext: Optional[asyncpg.Connection] = None):
    conn = conn_ext if conn_ext else await get_connection()
    try:
        await conn.execute(
            "UPDATE family_competitions SET rewards_distributed = TRUE WHERE competition_id = $1",
            competition_id
        )
        logger.info(f"DB: Marked rewards distributed for competition {competition_id}.")
    except Exception as e:
        logger.error(f"DB: Error marking rewards distributed for competition {competition_id}: {e}", exc_info=True)
    finally:
        if not conn_ext and conn and not conn.is_closed(): await conn.close()

async def get_user_chat_records(user_id: int, conn_ext: Optional[asyncpg.Connection] = None) -> List[Dict[str, Any]]:
    conn = conn_ext if conn_ext else await get_connection()
    try:
        rows = await conn.fetch(
            "SELECT user_id, chat_id, version, onecoins, username, full_name, chat_title, telegram_chat_link, last_used FROM user_oneui WHERE user_id = $1",
            user_id
        )
        # Преобразуем last_used в aware datetime
        result = []
        for row_dict in (dict(r) for r in rows):
            if row_dict.get('last_used') and isinstance(row_dict['last_used'], datetime):
                lu_ts = row_dict['last_used']
                row_dict['last_used'] = lu_ts.replace(tzinfo=dt_timezone.utc) if lu_ts.tzinfo is None else lu_ts.astimezone(dt_timezone.utc)
            result.append(row_dict)
        return result
    finally:
        if not conn_ext and conn and not conn.is_closed(): await conn.close()

async def get_all_families_with_active_members() -> List[Dict[str, Any]]:
    conn = await get_connection()
    try:
        all_family_ids_rows = await conn.fetch("SELECT family_id, name FROM families")
        if not all_family_ids_rows: return []
        family_map = {row['family_id']: {'name': row['name'], 'member_ids': []} for row in all_family_ids_rows}
        all_members_rows = await conn.fetch("SELECT family_id, user_id FROM family_members WHERE is_active = TRUE")
        for member_row in all_members_rows:
            if member_row['family_id'] in family_map:
                family_map[member_row['family_id']]['member_ids'].append(member_row['user_id'])
        return [{"family_id": fid, "name": data['name'], "member_ids": data['member_ids']}
                for fid, data in family_map.items() if data['member_ids']]
    except Exception as e:
        logger.error(f"DB: Error getting all families with active members: {e}", exc_info=True)
        return []
    finally:
        if conn and not conn.is_closed(): await conn.close()

async def get_competitions_to_finalize() -> List[Dict[str, Any]]:
    conn = await get_connection()
    try:
        rows = await conn.fetch(
            "SELECT * FROM family_competitions WHERE is_active = TRUE AND end_ts <= $1 AND rewards_distributed = FALSE ORDER BY end_ts ASC",
            datetime.now(dt_timezone.utc)
        )
        result = []
        for row_dict in (dict(r) for r in rows):
             if row_dict.get('start_ts'): row_dict['start_ts'] = row_dict['start_ts'].replace(tzinfo=dt_timezone.utc) if row_dict['start_ts'].tzinfo is None else row_dict['start_ts'].astimezone(dt_timezone.utc)
             if row_dict.get('end_ts'): row_dict['end_ts'] = row_dict['end_ts'].replace(tzinfo=dt_timezone.utc) if row_dict['end_ts'].tzinfo is None else row_dict['end_ts'].astimezone(dt_timezone.utc)
             result.append(row_dict)
        return result
    except Exception as e:
        logger.error(f"DB: Error getting competitions to finalize: {e}", exc_info=True)
        return []
    finally:
        if conn and not conn.is_closed(): await conn.close()

async def get_setting_timestamp(key: str, conn_ext: Optional[asyncpg.Connection] = None) -> Optional[datetime]:
    conn_to_use = conn_ext if conn_ext else await get_connection()
    try:
        ts_val = await conn_to_use.fetchval("SELECT setting_value_timestamp FROM system_settings WHERE setting_key = $1", key)
        if ts_val and isinstance(ts_val, datetime):
            return ts_val.replace(tzinfo=dt_timezone.utc) if ts_val.tzinfo is None else ts_val.astimezone(dt_timezone.utc)
        return None
    except Exception as e:
        logger.error(f"DB: Ошибка получения настройки времени '{key}': {e}", exc_info=True)
        return None
    finally:
        if not conn_ext and conn_to_use and not conn_to_use.is_closed(): await conn_to_use.close()

async def set_setting_timestamp(key: str, value: datetime, conn_ext: Optional[asyncpg.Connection] = None):
    conn_to_use = conn_ext if conn_ext else await get_connection()
    try:
        value_utc = value.astimezone(dt_timezone.utc) if value.tzinfo else value.replace(tzinfo=dt_timezone.utc)
        await conn_to_use.execute(
            "INSERT INTO system_settings (setting_key, setting_value_timestamp) VALUES ($1, $2) "
            "ON CONFLICT (setting_key) DO UPDATE SET setting_value_timestamp = EXCLUDED.setting_value_timestamp",
            key, value_utc
        )
    except Exception as e:
        logger.error(f"DB: Ошибка установки настройки времени '{key}': {e}", exc_info=True)
    finally:
        if not conn_ext and conn_to_use and not conn_to_use.is_closed(): await conn_to_use.close()

async def get_user_bonus_multiplier_status(user_id: int, chat_id: int, conn_ext: Optional[asyncpg.Connection] = None) -> Optional[Dict[str, Any]]:
    conn_to_use = conn_ext if conn_ext else await get_connection()
    try:
        row = await conn_to_use.fetchrow(
            "SELECT current_bonus_multiplier, is_bonus_consumed, last_claimed_timestamp "
            "FROM user_bonus_multipliers WHERE user_id = $1 AND chat_id = $2", user_id, chat_id
        )
        if row:
            data = dict(row)
            if data.get('last_claimed_timestamp') and isinstance(data['last_claimed_timestamp'], datetime):
                ts = data['last_claimed_timestamp']
                data['last_claimed_timestamp'] = ts.replace(tzinfo=dt_timezone.utc) if ts.tzinfo is None else ts.astimezone(dt_timezone.utc)
            return data
        return None
    except Exception as e:
        logger.error(f"DB: Ошибка получения статуса бонус-множителя для user {user_id} chat {chat_id}: {e}", exc_info=True)
        return None
    finally:
        if not conn_ext and conn_to_use and not conn_to_use.is_closed(): await conn_to_use.close()

async def update_user_bonus_multiplier_status(user_id: int, chat_id: int, multiplier: Optional[float], consumed: bool,
                                            claimed_timestamp: Optional[datetime], conn_ext: Optional[asyncpg.Connection] = None):
    conn_to_use = conn_ext if conn_ext else await get_connection()
    try:
        claimed_ts_utc = None
        if claimed_timestamp:
            claimed_ts_utc = claimed_timestamp.astimezone(dt_timezone.utc) if claimed_timestamp.tzinfo else claimed_timestamp.replace(tzinfo=dt_timezone.utc)

        await conn_to_use.execute(
            "INSERT INTO user_bonus_multipliers (user_id, chat_id, current_bonus_multiplier, is_bonus_consumed, last_claimed_timestamp) "
            "VALUES ($1, $2, $3, $4, $5) ON CONFLICT (user_id, chat_id) DO UPDATE SET "
            "current_bonus_multiplier = COALESCE(EXCLUDED.current_bonus_multiplier, user_bonus_multipliers.current_bonus_multiplier), "
            "is_bonus_consumed = EXCLUDED.is_bonus_consumed, "
            "last_claimed_timestamp = COALESCE(EXCLUDED.last_claimed_timestamp, user_bonus_multipliers.last_claimed_timestamp)"
            , user_id, chat_id, multiplier, consumed, claimed_ts_utc
        )
    except Exception as e:
        logger.error(f"DB: Ошибка обновления статуса бонус-множителя для user {user_id} chat {chat_id}: {e}", exc_info=True)
    finally:
        if not conn_ext and conn_to_use and not conn_to_use.is_closed(): await conn_to_use.close()

async def get_user_daily_streak(user_id: int, chat_id: int) -> Optional[Dict[str, Any]]:
    conn = await get_connection()
    try:
        row = await conn.fetchrow(
            "SELECT current_streak, last_streak_check_date, last_streak_timestamp_utc FROM user_daily_streaks WHERE user_id = $1 AND chat_id = $2",
            user_id, chat_id
        )
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"Ошибка при получении ежедневного стрика для user_id {user_id}, chat_id {chat_id}: {e}", exc_info=True)
        return None
    finally:
        await conn.close()

async def update_user_daily_streak(
    user_id: int,
    chat_id: int,
    streak: int,
    check_date: DDate,
    timestamp_utc: datetime,
    username: Optional[str] = None,
    full_name: Optional[str] = None,
    chat_title: Optional[str] = None
) -> None:
    conn = await get_connection()
    try:
        await conn.execute(
            """
            INSERT INTO user_daily_streaks (user_id, chat_id, current_streak, last_streak_check_date, last_streak_timestamp_utc, username_at_last_check, full_name_at_last_check, chat_title_at_last_check)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (user_id, chat_id) DO UPDATE SET
                current_streak = EXCLUDED.current_streak,
                last_streak_check_date = EXCLUDED.last_streak_check_date,
                last_streak_timestamp_utc = EXCLUDED.last_streak_timestamp_utc,
                username_at_last_check = EXCLUDED.username_at_last_check,
                full_name_at_last_check = EXCLUDED.full_name_at_last_check,
                chat_title_at_last_check = EXCLUDED.chat_title_at_last_check;
            """,
            user_id, chat_id, streak, check_date, timestamp_utc, username, full_name, chat_title
        )
    except Exception as e:
        logger.error(f"Ошибка при обновлении ежедневного стрика для user_id {user_id}, chat_id {chat_id}: {e}", exc_info=True)
    finally:
        await conn.close()

async def get_roulette_status(user_id: int, chat_id: int, conn_ext: Optional[asyncpg.Connection] = None) -> Optional[Dict[str, Any]]:
    conn_to_use = conn_ext if conn_ext else await get_connection()
    try:
        row = await conn_to_use.fetchrow(
            "SELECT * FROM roulette_status WHERE user_id = $1 AND chat_id = $2", # Загружаем все поля
            user_id, chat_id
        )
        if row:
            data = dict(row)
            if data.get('last_roulette_spin_timestamp') and isinstance(data['last_roulette_spin_timestamp'], datetime):
                ts = data['last_roulette_spin_timestamp']
                data['last_roulette_spin_timestamp'] = ts.replace(tzinfo=dt_timezone.utc) if ts.tzinfo is None else ts.astimezone(dt_timezone.utc)
            # Убедимся, что все ожидаемые поля существуют в словаре, даже если в БД их еще нет (после ALTER ADD)
            # и они равны NULL. Для INTEGER полей, если они NULL, .get(field, 0) вернет 0.
            # Для NUMERIC(3,1) (pending_bonus_multiplier_boost) .get(field) вернет None, что нормально.
            return data
        return None # Запись не найдена
    except Exception as e:
        logger.error(f"DB: Ошибка получения roulette_status для user {user_id} chat {chat_id}: {e}", exc_info=True)
        return None
    finally:
        if not conn_ext and conn_to_use and not conn_to_use.is_closed():
            await conn_to_use.close()

async def update_roulette_status(user_id: int, chat_id: int, fields_to_update: Dict[str, Any], conn_ext: Optional[asyncpg.Connection] = None):
    conn_to_use = conn_ext if conn_ext else await get_connection()
    try:
        insert_cols_list = ["user_id", "chat_id"]
        insert_values_placeholders_list = ["$1", "$2"]
        values_for_query = [user_id, chat_id]
        
        update_set_clauses_list = []
        current_param_idx = 3 # Начинаем с $3, так как $1 и $2 уже заняты

        # ИЗМЕНЕНО: Добавлено 'extra_roulette_spins'
        allowed_fields = [
            'last_roulette_spin_timestamp', 
            'extra_bonus_attempts', 
            'extra_oneui_attempts', 
            'pending_bonus_multiplier_boost', 
            'negative_change_protection_charges',
            'extra_roulette_spins' # <<<< НОВОЕ ПОЛЕ
        ]

        for field, value in fields_to_update.items():
            if field not in allowed_fields:
                logger.warning(f"DB: Попытка обновить/вставить неизвестное поле '{field}' в roulette_status. Пропущено.")
                continue

            insert_cols_list.append(field)
            insert_values_placeholders_list.append(f"${current_param_idx}")
            update_set_clauses_list.append(f"{field} = EXCLUDED.{field}")

            val_to_add = value
            if field == 'last_roulette_spin_timestamp' and isinstance(value, datetime):
                 val_to_add = value.astimezone(dt_timezone.utc) if value.tzinfo is None else value.astimezone(dt_timezone.utc)
            
            values_for_query.append(val_to_add)
            current_param_idx += 1
        
        insert_columns_str = ", ".join(insert_cols_list)
        insert_values_placeholders_str = ", ".join(insert_values_placeholders_list)
        
        if not update_set_clauses_list: # fields_to_update был пуст или содержал только невалидные поля
            # Просто гарантируем создание записи, если её нет.
            # INSERT INTO roulette_status (user_id, chat_id) VALUES ($1, $2) ON CONFLICT DO NOTHING
            # Такой запрос создаст запись со значениями DEFAULT для всех остальных полей.
            await conn_to_use.execute(
                 f"INSERT INTO roulette_status (user_id, chat_id) VALUES ($1, $2) ON CONFLICT (user_id, chat_id) DO NOTHING;",
                 user_id, chat_id
            )
        else:
            update_set_str = ", ".join(update_set_clauses_list)
            # INSERT INTO roulette_status (user_id, chat_id, field1, field2) VALUES ($1, $2, $3, $4)
            # ON CONFLICT (user_id, chat_id) DO UPDATE SET field1 = EXCLUDED.field1, field2 = EXCLUDED.field2;
            query = f"""
                INSERT INTO roulette_status ({insert_columns_str})
                VALUES ({insert_values_placeholders_str})
                ON CONFLICT (user_id, chat_id) DO UPDATE SET
                {update_set_str};
            """
            await conn_to_use.execute(query, *values_for_query)

    except asyncpg.exceptions.ForeignKeyViolationError as e_fk:
        logger.error(f"DB: ForeignKeyViolationError при обновлении/создании roulette_status для user {user_id} chat {chat_id}. "
                     f"Вероятно, отсутствует запись в user_oneui. Ошибка: {e_fk}", exc_info=False)
        raise
    except Exception as e:
        logger.error(f"DB: Ошибка обновления/создания roulette_status для user {user_id} chat {chat_id}: {e}", exc_info=True)
        raise
    finally:
        if not conn_ext and conn_to_use and not conn_to_use.is_closed():
            await conn_to_use.close()
            
async def get_setting_float(key: str, default_value: Optional[float] = None, conn_ext: Optional[asyncpg.Connection] = None) -> Optional[float]:
    """
    Получает числовое значение (float) из system_settings (хранимое в setting_value_text).
    """
    conn_to_use = conn_ext if conn_ext else await get_connection()
    try:
        value_str = await conn_to_use.fetchval(
            "SELECT setting_value_text FROM system_settings WHERE setting_key = $1", key
        )
        if value_str is not None:
            try:
                return float(value_str)
            except ValueError:
                logger.error(f"DB: Не удалось конвертировать текстовое значение '{value_str}' для ключа '{key}' во float. Возвращается default_value.")
                return default_value
        # Если ключ не найден, возвращаем default_value
        return default_value
    except Exception as e:
        logger.error(f"DB: Ошибка при получении числовой настройки '{key}': {e}", exc_info=True)
        return default_value # Возвращаем default_value и при других ошибках БД
    finally:
        if not conn_ext and conn_to_use and not conn_to_use.is_closed():
            await conn_to_use.close()

async def set_setting_float(key: str, value: float, conn_ext: Optional[asyncpg.Connection] = None):
    """
    Устанавливает числовое значение (float) в system_settings (сохраняя как текст).
    Округляет значение до 4 знаков после запятой перед сохранением.
    """
    conn_to_use = conn_ext if conn_ext else await get_connection()
    try:
        # Округляем до разумного количества знаков после запятой
        value_to_save_str = f"{value:.4f}" 

        # Если вы хотите использовать Decimal для более точного округления (например, ROUND_HALF_UP):
        # from decimal import Decimal, ROUND_HALF_UP # Убедитесь, что импорт есть в начале файла
        # value_decimal = Decimal(str(value)) 
        # rounded_value_decimal = value_decimal.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
        # value_to_save_str = str(rounded_value_decimal)

        await conn_to_use.execute(
            """
            INSERT INTO system_settings (setting_key, setting_value_text)
            VALUES ($1, $2)
            ON CONFLICT (setting_key) DO UPDATE SET
                setting_value_text = EXCLUDED.setting_value_text,
                -- Обнуляем другие типы значений, если они были установлены для этого ключа ранее
                setting_value_timestamp = NULL,
                setting_value_int = NULL,
                setting_value_bool = NULL
            """,
            key, value_to_save_str
        )
        logger.info(f"DB: Установлена/обновлена настройка '{key}' со значением '{value_to_save_str}' (исходное float: {value}).")
    except Exception as e:
        logger.error(f"DB: Ошибка при установке числовой настройки '{key}' со значением {value}: {e}", exc_info=True)
    finally:
        if not conn_ext and conn_to_use and not conn_to_use.is_closed():
            await conn_to_use.close()            

async def get_user_data_for_update(user_id: int, chat_id: int, conn_ext: Optional[asyncpg.Connection] = None) -> Dict[str, Any]:
    conn_to_use = conn_ext if conn_ext else await get_connection()
    try:
        row = await conn_to_use.fetchrow(
            "SELECT username, full_name, chat_title FROM user_oneui WHERE user_id = $1 AND chat_id = $2 ORDER BY last_used DESC NULLS LAST LIMIT 1",
            user_id, chat_id
        )
        if row:
            return dict(row)
        # Если запись не найдена, возвращаем словарь с None, чтобы .get() не вызывал ошибку
        return {'username': None, 'full_name': None, 'chat_title': None}
    except Exception as e:
        logger.warning(f"DB: Не удалось получить user_data_for_update (user {user_id}, chat {chat_id}): {e}")
        return {'username': None, 'full_name': None, 'chat_title': None} # Возврат словаря при ошибке
    finally:
        if not conn_ext and conn_to_use and not conn_to_use.is_closed():
            await conn_to_use.close()



# --- Функции для user_phones ---

async def add_phone_to_user_inventory(
    user_id: int,
    chat_id_acquired_in: int,
    phone_model_key: str,
    color: str,
    purchase_price: int,
    purchase_date_utc: datetime,
    initial_memory_gb: int, 
    is_contraband: bool = False,
    custom_phone_data_json: Optional[Dict] = None, # <--- НОВЫЙ ПАРАМЕТР
    conn_ext: Optional[asyncpg.Connection] = None
) -> Optional[int]:
    conn = conn_ext if conn_ext else await get_connection()
    try:
        if purchase_date_utc.tzinfo is None:
            purchase_date_utc = purchase_date_utc.replace(tzinfo=dt_timezone.utc)
        else:
            purchase_date_utc = purchase_date_utc.astimezone(dt_timezone.utc)

        last_charged = purchase_date_utc 

        battery_life_factor = 1.0 # Стандартный фактор
        # Проверяем, есть ли в custom_phone_data_json информация о модификаторе жизни батареи
        # Это может быть от "краденого" телефона или от "эксклюзива"
        if custom_phone_data_json:
            # Пробуем несколько возможных ключей, так как мы могли их по-разному назвать в wear_data и special_properties
            factor_from_custom = custom_phone_data_json.get("battery_life_factor") # Из special_properties эксклюзива
            if factor_from_custom is None and custom_phone_data_json.get("effect_type") == "reduced_battery_factor":
                factor_from_custom = custom_phone_data_json.get("value") # Из wear_data краденого

            if isinstance(factor_from_custom, (int, float)) and factor_from_custom > 0:
                battery_life_factor = factor_from_custom
                logger.info(f"DB: Для телефона {phone_model_key} (user {user_id}) применен battery_life_factor: {battery_life_factor} из custom_data.")

        # Используем Config.PHONE_BASE_BATTERY_DAYS, если есть, иначе дефолт
        base_battery_duration_days = getattr(Config, "PHONE_BASE_BATTERY_DAYS", 2)
        actual_battery_life_days = base_battery_duration_days * battery_life_factor

        battery_dead_after = last_charged + timedelta(days=actual_battery_life_days)
        # Используем Config.PHONE_CHARGE_WINDOW_DAYS, если есть, иначе дефолт
        charge_window_duration_days = getattr(Config, "PHONE_CHARGE_WINDOW_DAYS", 2)
        battery_break_after = battery_dead_after + timedelta(days=charge_window_duration_days)

        phone_inventory_id = await conn.fetchval(
            """
            INSERT INTO user_phones
                (user_id, chat_id_acquired_in, phone_model_key, color,
                 purchase_price_onecoins, purchase_date_utc, is_sold,
                 current_memory_gb, is_contraband,
                 last_charged_utc, battery_dead_after_utc, battery_break_after_utc, data) 
            VALUES ($1, $2, $3, $4, $5, $6, FALSE, $7, $8, $9, $10, $11, $12)
            RETURNING phone_inventory_id
            """, # Добавили data и $12
            user_id, chat_id_acquired_in, phone_model_key, color,
            purchase_price, purchase_date_utc,
            initial_memory_gb, is_contraband,
            last_charged, battery_dead_after, battery_break_after,
            custom_phone_data_json # <--- ПЕРЕДАЕМ СЮДА
        )
        return phone_inventory_id
    except Exception as e:
        logger.error(f"DB: Ошибка при добавлении телефона в инвентарь для user {user_id}, модель {phone_model_key}: {e}", exc_info=True)
        return None # Возвращаем None в случае ошибки
    finally:
        if not conn_ext and conn and not conn.is_closed():
            await conn.close()

async def get_user_phones(user_id: int, active_only: bool = True) -> List[Dict[str, Any]]:
    """
    Извлекает список телефонов пользователя из таблицы user_phones.
    :param user_id: ID пользователя.
    :param active_only: Если True, возвращает только не проданные телефоны.
                        Если False, возвращает ВСЕ телефоны (включая проданные).
    :return: Список словарей, где каждый словарь представляет телефон.
    """
    conn = await get_connection()
    try:
        query = "SELECT * FROM user_phones WHERE user_id = $1"
        params = [user_id]
        if active_only:
            query += " AND is_sold = FALSE"
        query += " ORDER BY purchase_date_utc DESC" # Сначала новые
        
        rows = await conn.fetch(query, *params)
        # Преобразуем JSONB поля обратно в dict, если они были сохранены как строки
        result_phones = []
        for row_dict in (dict(r) for r in rows):
            if row_dict.get('data') and isinstance(row_dict['data'], str):
                try:
                    row_dict['data'] = json.loads(row_dict['data'])
                except json.JSONDecodeError:
                    logger.warning(f"DB (get_user_phones): Failed to decode JSON for 'data' for phone {row_dict.get('phone_inventory_id')}")
                    row_dict['data'] = None
            result_phones.append(row_dict)
        return result_phones
    except Exception as e:
        logger.error(f"DB: Ошибка при получении телефонов для пользователя {user_id}: {e}", exc_info=True)
        return []
    finally:
        if conn and not conn.is_closed():
            await conn.close()

async def get_phone_by_inventory_id(
    phone_inventory_id: int,
    conn_ext: Optional[asyncpg.Connection] = None  # <--- 1. Добавляем новый опциональный параметр
) -> Optional[Dict[str, Any]]:
    """
    Получает информацию о конкретном телефоне из инвентаря по его ID.
    Может использовать существующее соединение conn_ext.
    """
    # <--- 2. Логика выбора соединения
    conn_to_use = conn_ext  # По умолчанию используем переданное соединение
    if not conn_to_use:  # Если соединение не было передано (conn_ext is None)
        conn_to_use = await get_connection() # Создаем новое

    try:
        # <--- 3. Используем выбранное соединение (conn_to_use)
        row = await conn_to_use.fetchrow(
            "SELECT * FROM user_phones WHERE phone_inventory_id = $1",
            phone_inventory_id
        )
        # Преобразование данных в UTC, если необходимо (пример для sold_date_utc)
        # Это важно, если вы хотите консистентно работать с aware datetime объектами
        if row:
            data = dict(row)
            # Пример для полей типа TIMESTAMP WITH TIME ZONE, которые могли прийти как naive
            for key, value in data.items():
                if isinstance(value, datetime) and value.tzinfo is None:
                    # Предполагаем, что время в БД хранится в UTC, если оно naive
                    data[key] = value.replace(tzinfo=dt_timezone.utc)
                # Если они уже aware (с таймзоной), можно их привести к UTC для единообразия:
                # elif isinstance(value, datetime) and value.tzinfo is not None:
                #     data[key] = value.astimezone(dt_timezone.utc)
            return data
        return None
    except Exception as e:
        logger.error(f"DB: Ошибка при получении телефона по ID {phone_inventory_id} (conn_ext: {'да' if conn_ext else 'нет'}): {e}", exc_info=True)
        return None
    finally:
        # <--- 4. Закрываем соединение только если оно было создано ВНУТРИ этой функции
        if not conn_ext and conn_to_use and not conn_to_use.is_closed():
            await conn_to_use.close()

async def count_user_active_phones(
    user_id: int,
    conn_ext: Optional[asyncpg.Connection] = None # <--- ДОБАВЛЕН ПАРАМЕТР
) -> int:
    """
    Подсчитывает количество активных (не проданных) телефонов у пользователя.
    Может использовать существующее соединение conn_ext.
    """
    # <--- ЛОГИКА ВЫБОРА СОЕДИНЕНИЯ --->
    conn_to_use = conn_ext
    if not conn_to_use:
        conn_to_use = await get_connection()

    try:
        # <--- ИСПОЛЬЗУЕМ conn_to_use --->
        count = await conn_to_use.fetchval(
            "SELECT COUNT(*) FROM user_phones WHERE user_id = $1 AND is_sold = FALSE",
            user_id
        )
        return count if count is not None else 0
    except Exception as e:
        logger.error(f"DB: Ошибка при подсчете активных телефонов для пользователя {user_id} (conn_ext: {'да' if conn_ext else 'нет'}): {e}", exc_info=True)
        return 0
    finally:
        # <--- ЗАКРЫВАЕМ СОЕДИНЕНИЕ, ТОЛЬКО ЕСЛИ СОЗДАЛИ ЕГО ВНУТРИ ФУНКЦИИ --->
        if not conn_ext and conn_to_use and not conn_to_use.is_closed():
            await conn_to_use.close()

async def get_user_bm_monthly_purchases(user_id: int, year_month: str, conn_ext: Optional[asyncpg.Connection] = None) -> int:
    """Возвращает количество телефонов, купленных пользователем на ЧР в указанный месяц."""
    conn = conn_ext if conn_ext else await get_connection()
    try:
        count = await conn.fetchval(
            "SELECT phones_purchased_count FROM user_black_market_monthly_stats WHERE user_id = $1 AND year_month = $2",
            user_id, year_month
        )
        return count if count is not None else 0
    except Exception as e:
        logger.error(f"DB: Ошибка получения месячных покупок ЧР для user {user_id}, месяц {year_month}: {e}", exc_info=True)
        return 0 
    finally:
        if not conn_ext and conn and not conn.is_closed():
            await conn.close()

async def increment_user_bm_monthly_purchase(user_id: int, year_month: str, conn_ext: Optional[asyncpg.Connection] = None):
    """Увеличивает счетчик купленных на ЧР телефонов для пользователя в текущем месяце."""
    conn = conn_ext if conn_ext else await get_connection()
    try:
        await conn.execute("""
            INSERT INTO user_black_market_monthly_stats (user_id, year_month, phones_purchased_count)
            VALUES ($1, $2, 1)
            ON CONFLICT (user_id, year_month) DO UPDATE SET
                phones_purchased_count = user_black_market_monthly_stats.phones_purchased_count + 1
        """, user_id, year_month)
    except Exception as e:
        logger.error(f"DB: Ошибка инкремента месячных покупок ЧР для user {user_id}, месяц {year_month}: {e}", exc_info=True)
    finally:
        if not conn_ext and conn and not conn.is_closed():
            await conn.close()

async def clear_black_market_offers(conn_ext: Optional[asyncpg.Connection] = None):
    """Очищает все текущие предложения на Черном Рынке."""
    conn = conn_ext if conn_ext else await get_connection()
    try:
        await conn.execute("DELETE FROM black_market_offers")
        logger.info("DB: Офферы Черного Рынка очищены.")
    except Exception as e:
        logger.error(f"DB: Ошибка при очистке офферов Черного Рынка: {e}", exc_info=True)
    finally:
        if not conn_ext and conn and not conn.is_closed():
            await conn.close()

async def add_black_market_offer(
    slot_number: int, item_key: str, item_type: str,
    current_price: int, original_price_before_bm: int,
    is_stolen: bool, is_exclusive: bool, quantity_available: int,
    display_name_override: Optional[str] = None,
    wear_data: Optional[Dict] = None, 
    custom_data: Optional[Dict] = None,
    conn_ext: Optional[asyncpg.Connection] = None
):
    """Добавляет новое предложение на Черный Рынок."""
    conn = conn_ext if conn_ext else await get_connection()
    try:
        wear_data_to_db = json.dumps(wear_data) if wear_data is not None else None
        custom_data_to_db = json.dumps(custom_data) if custom_data is not None else None
        
        await conn.execute("""
            INSERT INTO black_market_offers 
                (slot_number, item_key, item_type, display_name_override, current_price, original_price_before_bm, 
                 is_stolen, is_exclusive, quantity_available, wear_data, custom_data, added_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        """, slot_number, item_key, item_type, display_name_override, current_price, original_price_before_bm,
             is_stolen, is_exclusive, quantity_available, 
             wear_data_to_db, 
             custom_data_to_db, 
             datetime.now(dt_timezone.utc)) # Убедись, что dt_timezone импортирован как from datetime import timezone as dt_timezone
    except Exception as e:
        logger.error(f"DB: Ошибка добавления предложения ЧР в слот {slot_number}, ключ {item_key}: {e}", exc_info=True) 
    finally:
        if not conn_ext and conn and not conn.is_closed():
            await conn.close()

async def get_current_black_market_offers(conn_ext: Optional[asyncpg.Connection] = None) -> List[Dict]:
    """Получает все текущие предложения с Черного Рынка, отсортированные по номеру слота."""
    conn = conn_ext if conn_ext else await get_connection()
    try:
        rows = await conn.fetch("SELECT * FROM black_market_offers ORDER BY slot_number ASC")
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"DB: Ошибка при получении текущих офферов ЧР: {e}", exc_info=True)
        return []
    finally:
        if not conn_ext and conn and not conn.is_closed():
            await conn.close()

async def get_black_market_offer_by_slot(slot_number: int, conn_ext: Optional[asyncpg.Connection] = None) -> Optional[Dict]:
    """Получает оффер Черного Рынка по номеру слота."""
    conn = conn_ext if conn_ext else await get_connection()
    try:
        row = await conn.fetchrow("SELECT * FROM black_market_offers WHERE slot_number = $1", slot_number)
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"DB: Ошибка при получении оффера ЧР по слоту {slot_number}: {e}", exc_info=True)
        return None
    finally:
        if not conn_ext and conn and not conn.is_closed():
            await conn.close()

async def decrease_bm_offer_quantity(offer_id: int, conn_ext: Optional[asyncpg.Connection] = None) -> bool:
    """Уменьшает количество доступного товара на ЧР на 1. Возвращает True в случае успеха."""
    conn = conn_ext if conn_ext else await get_connection()
    try:
        if conn_ext: 
            current_offer = await conn.fetchrow(
                "SELECT quantity_available FROM black_market_offers WHERE offer_id = $1 FOR UPDATE",
                offer_id
            )
            if current_offer is None or current_offer['quantity_available'] <= 0:
                logger.warning(f"DB: Попытка уменьшить количество для оффера ID {offer_id}, который уже закончился или не существует (внутри транзакции).")
                return False
            result = await conn.execute(
                "UPDATE black_market_offers SET quantity_available = quantity_available - 1 WHERE offer_id = $1",
                offer_id
            )
            return result == "UPDATE 1"
        else: 
            async with conn.transaction():
                current_offer = await conn.fetchrow(
                    "SELECT quantity_available FROM black_market_offers WHERE offer_id = $1 FOR UPDATE",
                    offer_id
                )
                if current_offer is None or current_offer['quantity_available'] <= 0:
                    logger.warning(f"DB: Попытка уменьшить количество для оффера ID {offer_id}, который уже закончился или не существует.")
                    return False 
                result = await conn.execute(
                    "UPDATE black_market_offers SET quantity_available = quantity_available - 1 WHERE offer_id = $1",
                    offer_id
                )
                return result == "UPDATE 1"
    except Exception as e:
        logger.error(f"DB: Ошибка при уменьшении количества оффера ЧР ID {offer_id}: {e}", exc_info=True)
        return False
    finally:
        if not conn_ext and conn and not conn.is_closed():
            await conn.close()
            
async def get_item_custom_data(user_item_id: int, conn_ext: Optional[asyncpg.Connection] = None) -> Optional[Dict]:
    conn = conn_ext if conn_ext else await get_connection()
    try:
        data_json = await conn.fetchval("SELECT data FROM user_items WHERE user_item_id = $1", user_item_id)
        return data_json # Может быть None или словарем
    except Exception as e:
        logger.error(f"DB: Ошибка получения data для user_item_id {user_item_id}: {e}", exc_info=True)
        return None
    finally:
        if not conn_ext and conn and not conn.is_closed():
            await conn.close()

async def get_user_items_by_key_and_type(user_id: int, item_key: str, item_type: str, conn_ext: Optional[asyncpg.Connection] = None) -> List[Dict]:
    """Получает все экземпляры конкретного предмета (по ключу и типу) для пользователя."""
    conn = conn_ext if conn_ext else await get_connection()
    try:
        rows = await conn.fetch("SELECT * FROM user_items WHERE user_id = $1 AND item_key = $2 AND item_type = $3 ORDER BY user_item_id", 
                                user_id, item_key, item_type)
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"DB: Ошибка в get_user_items_by_key_and_type для user {user_id}, key {item_key}: {e}", exc_info=True)
        return []
    finally:
        if not conn_ext and conn and not conn.is_closed():
            await conn.close()            
            

async def update_phone_as_sold(
    phone_inventory_id: int,
    sold_date_utc: datetime,
    sold_price_onecoins: int,
    conn_ext: Optional[asyncpg.Connection] = None
) -> bool:
    """
    Отмечает телефон как проданный и записывает детали продажи.
    """
    conn = conn_ext if conn_ext else await get_connection()
    try:
        if sold_date_utc.tzinfo is None:
            sold_date_utc = sold_date_utc.replace(tzinfo=dt_timezone.utc)
        else:
            sold_date_utc = sold_date_utc.astimezone(dt_timezone.utc)

        result = await conn.execute(
            """
            UPDATE user_phones
            SET is_sold = TRUE,
                sold_date_utc = $2,
                sold_price_onecoins = $3
            WHERE phone_inventory_id = $1 AND is_sold = FALSE
            """,
            phone_inventory_id, sold_date_utc, sold_price_onecoins
        )
        return result == "UPDATE 1"
    except Exception as e:
        logger.error(f"DB: Ошибка при обновлении телефона {phone_inventory_id} как проданного: {e}", exc_info=True)
        return False
    finally:
        if not conn_ext and conn and not conn.is_closed():
            await conn.close()

async def update_phone_status_fields(
    phone_inventory_id: int,
    fields_to_update: Dict[str, Any],
    conn_ext: Optional[asyncpg.Connection] = None
) -> bool:
    """
    Обновляет указанные поля для конкретного телефона в инвентаре.
    Используется для обновления памяти, состояния поломки, чехла, страховки, зарядки.
    """
    conn = conn_ext if conn_ext else await get_connection()
    if not fields_to_update:
        return False
    
    set_clauses = []
    values = []
    param_idx = 1

    allowed_fields = [
        "current_memory_gb", "is_broken", "broken_component_key",
        "insurance_active_until", "equipped_case_key", "is_contraband",
        "last_charged_utc", "battery_dead_after_utc", "battery_break_after_utc"
    ]

    for key, value in fields_to_update.items():
        if key not in allowed_fields:
            logger.warning(f"DB: Попытка обновить неизвестное поле '{key}' в user_phones. Пропущено.")
            continue
        
        set_clauses.append(f"{key} = ${param_idx}")
        # Приведение TIMESTAMP к UTC, если необходимо
        if "utc" in key and isinstance(value, datetime):
            if value.tzinfo is None:
                values.append(value.replace(tzinfo=dt_timezone.utc))
            else:
                values.append(value.astimezone(dt_timezone.utc))
        else:
            values.append(value)
        param_idx += 1

    if not set_clauses:
        return False # Нет валидных полей для обновления

    values.append(phone_inventory_id) # Для WHERE phone_inventory_id = $N
    query = f"UPDATE user_phones SET {', '.join(set_clauses)} WHERE phone_inventory_id = ${param_idx}"

    try:
        result = await conn.execute(query, *values)
        return result == "UPDATE 1"
    except Exception as e:
        logger.error(f"DB: Ошибка при обновлении полей телефона ID {phone_inventory_id}: {e}", exc_info=True)
        return False
    finally:
        if not conn_ext and conn and not conn.is_closed():
            await conn.close()
 # --- Функции для user_items (инвентарь компонентов, чехлов, модулей) ---

async def add_item_to_user_inventory(
    user_id: int,
    item_key: str,
    item_type: str, 
    quantity_to_add: int = 1,
    item_data_json: Optional[Dict] = None, 
    conn_ext: Optional[asyncpg.Connection] = None
) -> bool:
    conn = conn_ext if conn_ext else await get_connection()
    try:
        # ЯВНОЕ ПРЕОБРАЗОВАНИЕ item_data_json В JSON-СТРОКУ
        data_to_db_as_string = json.dumps(item_data_json) if item_data_json is not None else None

        if item_type == 'case':
            for _ in range(quantity_to_add):
                await conn.execute(
                    """
                    INSERT INTO user_items (user_id, item_key, item_type, quantity, data) 
                    VALUES ($1, $2, $3, 1, $4)
                    """, 
                    user_id, item_key, item_type, data_to_db_as_string # <--- Используем строку
                )
            return True
        elif item_type in ['component', 'memory_module', 'battery']:
            existing_item = await conn.fetchrow(
                "SELECT user_item_id, quantity, data FROM user_items WHERE user_id = $1 AND item_key = $2 AND item_type = $3",
                user_id, item_key, item_type
            )
            if existing_item:
                new_quantity = existing_item['quantity'] + quantity_to_add
                data_for_update_str = data_to_db_as_string 
                if data_for_update_str is None and existing_item['data'] is not None:
                    data_for_update_str = json.dumps(existing_item['data']) 
                
                await conn.execute(
                    "UPDATE user_items SET quantity = $1, data = $2 WHERE user_item_id = $3",
                    new_quantity, data_for_update_str, existing_item['user_item_id'] # <--- Используем строку
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO user_items (user_id, item_key, item_type, quantity, data)
                    VALUES ($1, $2, $3, $4, $5)
                    """, 
                    user_id, item_key, item_type, quantity_to_add, data_to_db_as_string # <--- Используем строку
                )
            return True
        else:
            logger.warning(f"DB: Попытка добавить предмет неизвестного типа '{item_type}' для user_id {user_id}")
            return False
    except Exception as e:
        logger.error(f"DB: Ошибка при добавлении/обновлении предмета '{item_key}' (тип: {item_type}, data: {item_data_json}) для user {user_id}: {e}", exc_info=True)
        return False 
    finally:
        if not conn_ext and conn and not conn.is_closed():
            await conn.close()

async def get_user_items(user_id: int, item_type_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Получает список всех предметов пользователя или предметов определенного типа.
    Каждая запись чехла - отдельный чехол.
    Для компонентов/модулей - запись с указанием quantity.
    """
    conn = await get_connection()
    try:
        query = "SELECT user_item_id, item_key, item_type, quantity FROM user_items WHERE user_id = $1"
        params: List[Any] = [user_id]
        if item_type_filter:
            query += " AND item_type = $2"
            params.append(item_type_filter)
        query += " ORDER BY item_type, item_key, user_item_id" # Для консистентного вывода
        
        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"DB: Ошибка при получении предметов для пользователя {user_id}: {e}", exc_info=True)
        return []
    finally:
        if conn and not conn.is_closed():
            await conn.close()

async def get_user_specific_item_count(
    user_id: int, 
    item_key: str, 
    item_type: str, 
    conn_ext: Optional[asyncpg.Connection] = None  # <--- 1. ДОБАВЛЕН ПАРАМЕТР
) -> int:
    conn_to_use = conn_ext if conn_ext else await get_connection() # <--- 2. ЛОГИКА ВЫБОРА СОЕДИНЕНИЯ
    try:
        if item_type == 'case':
            count = await conn_to_use.fetchval( # <--- 3. ИСПОЛЬЗУЕМ conn_to_use
                "SELECT COUNT(*) FROM user_items WHERE user_id = $1 AND item_key = $2 AND item_type = $3",
                user_id, item_key, item_type
            )
        else: 
            record = await conn_to_use.fetchrow( # <--- 3. ИСПОЛЬЗУЕМ conn_to_use
                "SELECT quantity FROM user_items WHERE user_id = $1 AND item_key = $2 AND item_type = $3",
                user_id, item_key, item_type
            )
            count = record['quantity'] if record else 0
        return count if count is not None else 0
    except Exception as e:
        logger.error(f"DB: Ошибка при получении количества предмета '{item_key}' (тип: {item_type}) для user {user_id} (conn_ext: {'да' if conn_ext else 'нет'}): {e}", exc_info=True)
        return 0
    finally:
        if not conn_ext and conn_to_use and not conn_to_use.is_closed(): # <--- 4. ЗАКРЫВАЕМ, ТОЛЬКО ЕСЛИ СОЗДАЛИ ВНУТРИ
            await conn_to_use.close()
            

async def remove_item_from_user_inventory(
    user_id: int,
    item_key: str,
    item_type: str,
    quantity_to_remove: int = 1,
    user_item_id_to_remove: Optional[int] = None, # Для удаления конкретного экземпляра чехла
    conn_ext: Optional[asyncpg.Connection] = None
) -> bool:
    """
    Удаляет предмет (или уменьшает количество) из инвентаря пользователя.
    Если указан user_item_id_to_remove (ОБЯЗАТЕЛЬНО для чехлов типа 'case'), удаляется конкретная запись.
    Иначе (для компонентов/модулей) уменьшается quantity.
    """
    conn = conn_ext if conn_ext else await get_connection()
    try:
        if item_type == 'case':
            if user_item_id_to_remove is None:
                logger.error(f"DB: Для удаления чехла (item_key: {item_key}) не указан user_item_id_to_remove для user {user_id}.")
                return False # Для чехлов всегда нужен ID конкретного экземпляра
            
            result = await conn.execute(
                "DELETE FROM user_items WHERE user_item_id = $1 AND user_id = $2 AND item_key = $3 AND item_type = 'case'",
                user_item_id_to_remove, user_id, item_key
            )
            return result == "DELETE 1"

        elif item_type in ['component', 'memory_module']:
            # Для компонентов и модулей памяти - уменьшаем quantity или удаляем запись
            # Найдем запись (должна быть одна из-за нашей логики добавления)
            item_record = await conn.fetchrow(
                "SELECT user_item_id, quantity FROM user_items WHERE user_id = $1 AND item_key = $2 AND item_type = $3",
                user_id, item_key, item_type
            )
            if not item_record or item_record['quantity'] < quantity_to_remove:
                logger.warning(f"DB: Недостаточно предметов '{item_key}' ({item_type}) у user {user_id} для удаления {quantity_to_remove} шт.")
                return False 

            if item_record['quantity'] == quantity_to_remove:
                # Удаляем запись, если количество совпадает
                result = await conn.execute(
                    "DELETE FROM user_items WHERE user_item_id = $1",
                    item_record['user_item_id']
                )
                return result == "DELETE 1"
            else:
                # Уменьшаем количество
                new_quantity = item_record['quantity'] - quantity_to_remove
                result = await conn.execute(
                    "UPDATE user_items SET quantity = $1 WHERE user_item_id = $2",
                    new_quantity, item_record['user_item_id']
                )
                return result == "UPDATE 1"
        else:
            logger.warning(f"DB: Попытка удалить предмет неизвестного типа '{item_type}' для user_id {user_id}")
            return False
            
    except Exception as e:
        logger.error(f"DB: Ошибка при удалении/уменьшении предмета '{item_key}' (тип: {item_type}) для user {user_id}: {e}", exc_info=True)
        return False
    finally:
        if not conn_ext and conn and not conn.is_closed():
            await conn.close()  


async def get_user_item_by_id(user_item_id: int, user_id: Optional[int] = None, conn_ext: Optional[asyncpg.Connection] = None) -> Optional[Dict[str, Any]]:
    """
    Получает конкретный экземпляр предмета пользователя по его user_item_id.
    Если указан user_id, проверяет принадлежность предмета пользователю.
    """
    conn = await get_connection()
    try:
        query = "SELECT user_item_id, user_id, item_key, item_type, quantity FROM user_items WHERE user_item_id = $1"
        params: List[Any] = [user_item_id]
        if user_id is not None:
            query += " AND user_id = $2"
            params.append(user_id)
            
        row = await conn.fetchrow(query, *params)
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"DB: Ошибка при получении предмета по user_item_id {user_item_id} (user: {user_id}): {e}", exc_info=True)
        return None
    finally:
        if conn and not conn.is_closed():
            await conn.close() 
async def get_all_operational_phones(conn_ext: Optional[asyncpg.Connection] = None) -> List[Dict[str, Any]]:
    """
    Получает все активные (не проданные) и не сломанные телефоны всех пользователей.
    """
    conn = conn_ext if conn_ext else await get_connection()
    try:
        # Выбираем все поля, чтобы иметь полную информацию, включая user_id, phone_model_key, equipped_case_key
        rows = await conn.fetch(
            """
            SELECT * FROM user_phones
            WHERE is_sold = FALSE AND is_broken = FALSE
            ORDER BY user_id, purchase_date_utc
            """
        )
        # Преобразуем даты в aware datetime UTC, если они naive
        result_phones = []
        for row_dict in (dict(r) for r in rows):
            for key, value in row_dict.items():
                if isinstance(value, datetime) and value.tzinfo is None:
                    row_dict[key] = value.replace(tzinfo=dt_timezone.utc)
            result_phones.append(row_dict)
        return result_phones
    except Exception as e:
        logger.error(f"DB: Ошибка при получении всех операционных телефонов: {e}", exc_info=True)
        return []
    finally:
        if not conn_ext and conn and not conn.is_closed():
            await conn.close()      
            
async def get_phones_for_battery_check(conn_ext: Optional[asyncpg.Connection] = None) -> List[Dict[str, Any]]:
    """
    Получает все активные, не проданные телефоны, у которых аккумулятор еще не помечен как сломанный
    из-за истечения battery_break_after_utc (т.е. is_broken = FALSE ИЛИ (is_broken = TRUE, но broken_component_key НЕ батарея)).
    Также проверяем, что battery_break_after_utc не NULL.
    """
    conn = conn_ext if conn_ext else await get_connection()
    try:
        # Нам нужны телефоны, которые:
        # 1. Не проданы (is_sold = FALSE)
        # 2. Либо вообще не сломаны (is_broken = FALSE)
        # 3. Либо сломаны, но сломанный компонент НЕ является батареей (чтобы не проверять батарею, которая уже помечена как сломанная по другой причине)
        # 4. И у которых есть дата окончательной поломки батареи (battery_break_after_utc IS NOT NULL)
        
        # Получаем все ключи компонентов, которые являются батареями
        battery_component_keys = [
            key for key, data in PHONE_COMPONENTS.items() 
            if data.get("component_type") == "battery"
        ]

        # Если список ключей батарей пуст, это ошибка конфигурации, но запрос все равно выполним без этого условия
        if not battery_component_keys:
            logger.warning("DB (get_phones_for_battery_check): Список ключей батарей (PHONE_COMPONENTS с type='battery') пуст. Проверка на тип сломанного компонента будет неполной.")
            condition_broken_not_battery = "is_broken = FALSE" # Если нет ключей батарей, считаем только несломанные
        else:
            # Формируем строку для условия IN ($1, $2, ...)
            placeholders = ", ".join([f"${i+1}" for i in range(len(battery_component_keys))])
            condition_broken_not_battery = f"(is_broken = FALSE OR (is_broken = TRUE AND broken_component_key NOT IN ({placeholders})))"
            params_for_query = battery_component_keys
        
        query_string = f"""
            SELECT * FROM user_phones
            WHERE is_sold = FALSE
            AND {condition_broken_not_battery}
            AND battery_break_after_utc IS NOT NULL 
            ORDER BY user_id, battery_break_after_utc ASC
        """

        rows = await conn.fetch(query_string, *params_for_query if battery_component_keys else [])
        
        result_phones = []
        for row_dict in (dict(r) for r in rows):
            for key, value in row_dict.items():
                if isinstance(value, datetime) and value.tzinfo is None:
                    row_dict[key] = value.replace(tzinfo=dt_timezone.utc)
            result_phones.append(row_dict)
        return result_phones
    except Exception as e:
        logger.error(f"DB: Ошибка при получении телефонов для проверки батареи: {e}", exc_info=True)
        return []
    finally:
        if not conn_ext and conn and not conn.is_closed():
            await conn.close()   
            
async def add_user_business(
    user_id: int,
    chat_id: int,
    username: Optional[str],
    full_name: Optional[str],
    chat_title: Optional[str],
    business_key: str,
    purchase_price: int, # Добавляем для логов/истории, хотя не хранится в таблице user_businesses напрямую
    conn_ext: Optional[asyncpg.Connection] = None
) -> Optional[int]:
    """
    Добавляет новый бизнес для пользователя в указанном чате.
    Возвращает business_id нового бизнеса или None в случае ошибки.
    """
    conn_to_use = conn_ext if conn_ext else await get_connection()
    try:
        now_utc = datetime.now(dt_timezone.utc)
        business_id = await conn_to_use.fetchval(
            """
            INSERT INTO user_businesses (
                user_id, chat_id, username, full_name, chat_title,
                business_key, current_level, staff_hired_slots,
                last_income_calculation_utc, time_purchased_utc, is_active
            )
            VALUES ($1, $2, $3, $4, $5, $6, 0, 0, $7, $7, TRUE)
            RETURNING business_id;
            """,
            user_id, chat_id, username, full_name, chat_title,
            business_key, now_utc
        )
        return business_id
    except asyncpg.exceptions.UniqueViolationError:
        logger.warning(f"DB: User {user_id} already has business {business_key} in chat {chat_id}. Cannot add duplicate.")
        return None
    except Exception as e:
        logger.error(f"DB: Error adding business {business_key} for user {user_id} in chat {chat_id}: {e}", exc_info=True)
        return None
    finally:
        if not conn_ext and conn_to_use and not conn_to_use.is_closed():
            await conn_to_use.close()

async def get_user_businesses(user_id: int, chat_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Получает список всех бизнесов пользователя. Если указан chat_id, то только из этого чата.
    """
    conn = await get_connection()
    try:
        query = "SELECT * FROM user_businesses WHERE user_id = $1"
        params = [user_id]
        if chat_id is not None:
            query += " AND chat_id = $2"
            params.append(chat_id)
        
        rows = await conn.fetch(query, *params)
        # Убедимся, что timestamp'ы aware
        result = []
        for row_dict in (dict(r) for r in rows):
            if row_dict.get('last_income_calculation_utc') and isinstance(row_dict['last_income_calculation_utc'], datetime):
                ts = row_dict['last_income_calculation_utc']
                row_dict['last_income_calculation_utc'] = ts.replace(tzinfo=dt_timezone.utc) if ts.tzinfo is None else ts.astimezone(dt_timezone.utc)
            if row_dict.get('time_purchased_utc') and isinstance(row_dict['time_purchased_utc'], datetime):
                ts = row_dict['time_purchased_utc']
                row_dict['time_purchased_utc'] = ts.replace(tzinfo=dt_timezone.utc) if ts.tzinfo is None else ts.astimezone(dt_timezone.utc)
            result.append(row_dict)
        return result
    except Exception as e:
        logger.error(f"DB: Error getting businesses for user {user_id} (chat: {chat_id}): {e}", exc_info=True)
        return []
    finally:
        if conn and not conn.is_closed():
            await conn.close()
            
async def update_user_item_fields(
    user_item_id: int,
    user_id: int,
    fields_to_update: Dict[str, Any],
    conn_ext: Optional[asyncpg.Connection] = None
) -> bool:
    """
    Обновляет указанные поля для конкретного предмета пользователя в инвентаре.
    Используется для обновления поля 'data' или 'equipped_phone_id' для чехлов.
    """
    conn = conn_ext if conn_ext else await get_connection()
    if not fields_to_update:
        return False
    
    set_clauses = []
    values = []
    param_idx = 1

    # Разрешенные поля для обновления в таблице user_items
    allowed_fields = [
        "quantity", "data", "equipped_phone_id" 
    ]

    for key, value in fields_to_update.items():
        if key not in allowed_fields:
            logger.warning(f"DB: Attempted to update disallowed field '{key}' in user_items for user_item_id {user_item_id}. Skipped.")
            continue
        
        set_clauses.append(f"{key} = ${param_idx}")
        
        # Обработка JSONB полей
        if key == "data" and isinstance(value, dict):
            values.append(json.dumps(value))
        elif key == "data" and value is None:
            values.append(None)
        else:
            values.append(value)
        param_idx += 1

    if not set_clauses:
        return False # Нет действительных полей для обновления

    values.append(user_item_id) # Для WHERE user_item_id = $N
    values.append(user_id)      # Для WHERE user_id = $M (проверка безопасности, что предмет принадлежит пользователю)
    query = f"UPDATE user_items SET {', '.join(set_clauses)} WHERE user_item_id = ${param_idx} AND user_id = ${param_idx + 1}"

    try:
        result = await conn.execute(query, *values)
        return result == "UPDATE 1"
    except Exception as e:
        logger.error(f"DB: Error updating fields for user_item_id {user_item_id} (user {user_id}): {e}", exc_info=True)
        return False
    finally:
        if not conn_ext and conn and not conn.is_closed():
            await conn.close()            
            

async def get_user_business_by_id(business_id: int, user_id: int, conn_ext: Optional[asyncpg.Connection] = None) -> Optional[Dict[str, Any]]:
    """
    Получает конкретный бизнес пользователя по его business_id.
    Дополнительно проверяет user_id для безопасности.
    """
    conn_to_use = conn_ext if conn_ext else await get_connection()
    try:
        row = await conn_to_use.fetchrow(
            "SELECT * FROM user_businesses WHERE business_id = $1 AND user_id = $2",
            business_id, user_id
        )
        if row:
            data = dict(row)
            if data.get('last_income_calculation_utc') and isinstance(data['last_income_calculation_utc'], datetime):
                ts = data['last_income_calculation_utc']
                data['last_income_calculation_utc'] = ts.replace(tzinfo=dt_timezone.utc) if ts.tzinfo is None else ts.astimezone(dt_timezone.utc)
            if data.get('time_purchased_utc') and isinstance(data['time_purchased_utc'], datetime):
                ts = data['time_purchased_utc']
                data['time_purchased_utc'] = ts.replace(tzinfo=dt_timezone.utc) if ts.tzinfo is None else ts.astimezone(dt_timezone.utc)
            return data
        return None
    except Exception as e:
        logger.error(f"DB: Error getting business {business_id} for user {user_id}: {e}", exc_info=True)
        return None
    finally:
        if not conn_ext and conn_to_use and not conn_to_use.is_closed():
            await conn_to_use.close()

async def update_user_business(
    business_id: int,
    user_id: int, # Для безопасности, чтобы пользователь мог менять только свои бизнесы
    fields_to_update: Dict[str, Any],
    conn_ext: Optional[asyncpg.Connection] = None
) -> bool:
    """
    Обновляет указанные поля для конкретного бизнеса пользователя.
    Принимает словарь полей для обновления.
    """
    conn_to_use = conn_ext if conn_ext else await get_connection()
    if not fields_to_update:
        return False
    
    set_clauses = []
    values = []
    param_idx = 1 # Индекс для параметров SQL-запроса

    allowed_fields = [
        "current_level", "staff_hired_slots", "last_income_calculation_utc",
        "is_active", "name_override", "username", "full_name", "chat_title" # Разрешаем обновление инфо о юзере/чате
    ]

    for key, value in fields_to_update.items():
        if key not in allowed_fields:
            logger.warning(f"DB: Attempted to update disallowed field '{key}' in user_businesses for business ID {business_id}. Skipped.")
            continue
        
        set_clauses.append(f"{key} = ${param_idx}")
        # Приведение TIMESTAMP к UTC, если необходимо
        if "utc" in key and isinstance(value, datetime):
            if value.tzinfo is None:
                values.append(value.replace(tzinfo=dt_timezone.utc))
            else:
                values.append(value.astimezone(dt_timezone.utc))
        else:
            values.append(value)
        param_idx += 1

    if not set_clauses:
        return False # Нет валидных полей для обновления

    values.append(business_id) # Для WHERE business_id = $N
    values.append(user_id) # Для WHERE user_id = $M (безопасность)
    query = f"UPDATE user_businesses SET {', '.join(set_clauses)} WHERE business_id = ${param_idx} AND user_id = ${param_idx + 1}"

    try:
        result = await conn_to_use.execute(query, *values)
        return result == "UPDATE 1"
    except Exception as e:
        logger.error(f"DB: Error updating user business {business_id} for user {user_id}: {e}", exc_info=True)
        return False
    finally:
        if not conn_ext and conn_to_use and not conn_to_use.is_closed():
            await conn_to_use.close()

async def delete_user_business(business_id: int, user_id: int, conn_ext: Optional[asyncpg.Connection] = None) -> bool:
    """
    Удаляет бизнес пользователя.
    """
    conn_to_use = conn_ext if conn_ext else await get_connection()
    try:
        result = await conn_to_use.execute(
            "DELETE FROM user_businesses WHERE business_id = $1 AND user_id = $2",
            business_id, user_id
        )
        return result == "DELETE 1"
    except Exception as e:
        logger.error(f"DB: Error deleting business {business_id} for user {user_id}: {e}", exc_info=True)
        return False
    finally:
        if not conn_ext and conn_to_use and not conn_to_use.is_closed():
            await conn_to_use.close()

# --- Функции для user_business_upgrades ---

async def add_business_upgrade(
    user_id: int,
    business_internal_id: int,
    upgrade_key: str,
    conn_ext: Optional[asyncpg.Connection] = None
) -> Optional[int]:
    """
    Добавляет апгрейд к конкретному бизнесу пользователя.
    Возвращает upgrade_id или None.
    """
    conn_to_use = conn_ext if conn_ext else await get_connection()
    try:
        now_utc = datetime.now(dt_timezone.utc)
        upgrade_id = await conn_to_use.fetchval(
            """
            INSERT INTO user_business_upgrades (user_id, business_internal_id, upgrade_key, time_installed_utc)
            VALUES ($1, $2, $3, $4)
            RETURNING upgrade_id;
            """,
            user_id, business_internal_id, upgrade_key, now_utc
        )
        return upgrade_id
    except asyncpg.exceptions.UniqueViolationError:
        logger.warning(f"DB: User {user_id} already has upgrade {upgrade_key} for business {business_internal_id}. Cannot add duplicate.")
        return None
    except Exception as e:
        logger.error(f"DB: Error adding upgrade {upgrade_key} to business {business_internal_id} for user {user_id}: {e}", exc_info=True)
        return None
    finally:
        if not conn_ext and conn_to_use and not conn_to_use.is_closed():
            await conn_to_use.close()

async def get_business_upgrades(business_internal_id: int, user_id: Optional[int] = None, conn_ext: Optional[asyncpg.Connection] = None) -> List[Dict[str, Any]]:
    """
    Получает список всех апгрейдов для конкретного бизнеса.
    Если указан user_id, проверяет принадлежность.
    """
    conn_to_use = conn_ext if conn_ext else await get_connection()
    try:
        query = "SELECT * FROM user_business_upgrades WHERE business_internal_id = $1"
        params = [business_internal_id]
        if user_id is not None:
            query += " AND user_id = $2"
            params.append(user_id)
        
        rows = await conn_to_use.fetch(query, *params)
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"DB: Error getting upgrades for business {business_internal_id} (user: {user_id}): {e}", exc_info=True)
        return []
    finally:
        if not conn_ext and conn_to_use and not conn_to_use.is_closed():
            await conn_to_use.close()

# --- Функции для user_bank ---

async def get_user_bank(user_id: int, chat_id: int, conn_ext: Optional[asyncpg.Connection] = None) -> Optional[Dict[str, Any]]:
    """
    Получает информацию о банке пользователя в конкретном чате.
    Если банка нет, возвращает None (или можно создать начальный здесь).
    """
    conn_to_use = conn_ext if conn_ext else await get_connection()
    try:
        row = await conn_to_use.fetchrow(
            "SELECT * FROM user_bank WHERE user_id = $1 AND chat_id = $2",
            user_id, chat_id
        )
        if row:
            data = dict(row)
            if data.get('last_deposit_utc') and isinstance(data['last_deposit_utc'], datetime):
                ts = data['last_deposit_utc']
                data['last_deposit_utc'] = ts.replace(tzinfo=dt_timezone.utc) if ts.tzinfo is None else ts.astimezone(dt_timezone.utc)
            return data
        return None
    except Exception as e:
        logger.error(f"DB: Error getting bank for user {user_id} chat {chat_id}: {e}", exc_info=True)
        return None
    finally:
        if not conn_ext and conn_to_use and not conn_to_use.is_closed():
            await conn_to_use.close()

async def create_or_update_user_bank(
    user_id: int,
    chat_id: int,
    username: Optional[str],
    full_name: Optional[str],
    chat_title: Optional[str],
    current_balance_change: int = 0, # Изменение баланса (может быть отрицательным)
    new_bank_level: Optional[int] = None, # Для повышения уровня
    conn_ext: Optional[asyncpg.Connection] = None
) -> Optional[Dict[str, Any]]:
    """
    Создает или обновляет запись о банке пользователя в указанном чате.
    Используется для пополнения, снятия и повышения уровня.
    Возвращает актуальную информацию о банке.
    """
    conn_to_use = conn_ext if conn_ext else await get_connection()
    try:
        now_utc = datetime.now(dt_timezone.utc)
        
        # Если пытаемся обновить уровень, и он не None
        level_update_sql = ""
        if new_bank_level is not None:
            level_update_sql = f", bank_level = GREATEST(user_bank.bank_level, {new_bank_level})" # GREATEST чтобы не понизить уровень случайно

        # Используем RETURNING *, чтобы получить все данные обновленной/вставленной строки
        result_row = await conn_to_use.fetchrow(
            f"""
            INSERT INTO user_bank (user_id, chat_id, username, full_name, chat_title, current_balance, bank_level, last_deposit_utc)
            VALUES ($1, $2, $3, $4, $5, $6, COALESCE((SELECT bank_level FROM user_bank WHERE user_id = $1 AND chat_id = $2), 0), $7)
            ON CONFLICT (user_id, chat_id) DO UPDATE SET
                current_balance = user_bank.current_balance + $6,
                last_deposit_utc = EXCLUDED.last_deposit_utc
                {level_update_sql}
            RETURNING *;
            """,
            user_id, chat_id, username, full_name, chat_title,
            current_balance_change, now_utc
        )
        if result_row:
            data = dict(result_row)
            if data.get('last_deposit_utc') and isinstance(data['last_deposit_utc'], datetime):
                ts = data['last_deposit_utc']
                data['last_deposit_utc'] = ts.replace(tzinfo=dt_timezone.utc) if ts.tzinfo is None else ts.astimezone(dt_timezone.utc)
            return data
        return None
    except Exception as e:
        logger.error(f"DB: Error creating/updating bank for user {user_id} chat {chat_id}: {e}", exc_info=True)
        return None
    finally:
        if not conn_ext and conn_to_use and not conn_to_use.is_closed():
            await conn_to_use.close()

async def update_user_bank_level(
    user_id: int,
    chat_id: int,
    new_level: int,
    conn_ext: Optional[asyncpg.Connection] = None
) -> bool:
    """
    Обновляет уровень банка пользователя в конкретном чате.
    """
    conn_to_use = conn_ext if conn_ext else await get_connection()
    try:
        result = await conn_to_use.execute(
            """
            UPDATE user_bank
            SET bank_level = $3
            WHERE user_id = $1 AND chat_id = $2 AND bank_level < $3
            """, # Проверяем, чтобы новый уровень был выше текущего
            user_id, chat_id, new_level
        )
        return result == "UPDATE 1"
    except Exception as e:
        logger.error(f"DB: Error updating bank level for user {user_id} chat {chat_id} to {new_level}: {e}", exc_info=True)
        return False
    finally:
        if not conn_ext and conn_to_use and not conn_to_use.is_closed():
            await conn_to_use.close()            
            
async def get_user_max_version_global_with_chat_info(user_id: int, conn_ext: Optional[asyncpg.Connection] = None) -> Optional[Dict[str, Any]]:
    """
    Получает максимальную глобальную версию OneUI пользователя и информацию о чате, где она была достигнута.
    """
    conn_to_use = conn_ext if conn_ext else await get_connection()
    try:
        # Сначала находим максимальное значение версии
        max_version_val = await conn_to_use.fetchval(
            "SELECT MAX(version) FROM user_oneui WHERE user_id = $1 AND version IS NOT NULL",
            user_id
        )
        if max_version_val is None:
            return None # У пользователя нет версий

        # Затем находим запись в user_oneui, соответствующую этой максимальной версии,
        # предпочитая ту, что была использована последней, если версий несколько одинаковых.
        row = await conn_to_use.fetchrow(
            """
            SELECT version, chat_id, chat_title, telegram_chat_link
            FROM user_oneui
            WHERE user_id = $1 AND version = $2 AND version IS NOT NULL
            ORDER BY last_used DESC NULLS LAST
            LIMIT 1;
            """,
            user_id, max_version_val
        )
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"DB: Ошибка в get_user_max_version_global_with_chat_info для user {user_id}: {e}", exc_info=True)
        return None
    finally:
        if not conn_ext and conn_to_use and not conn_to_use.is_closed():
            await conn_to_use.close()            

async def get_phones_with_expiring_insurance(days_before_expiry: int, conn_ext: Optional[asyncpg.Connection] = None) -> List[Dict[str, Any]]:
    """
    Получает все телефоны с активной страховкой, которая истекает в ближайшие 'days_before_expiry' дней
    или уже истекла, но не более чем на несколько дней (например, 1-2 дня для последнего напоминания).
    """
    conn = conn_ext if conn_ext else await get_connection()
    try:
        now_utc = datetime.now(dt_timezone.utc)
        # Дата, до которой мы ищем истекающие страховки (сегодня + days_before_expiry)
        upper_expiry_limit_utc = now_utc + timedelta(days=days_before_expiry)
        # Дата, от которой мы ищем уже истекшие страховки (например, сегодня - 2 дня, чтобы поймать недавно истекшие)
        lower_already_expired_limit_utc = now_utc - timedelta(days=2) # Напоминаем, если истекла в последние 2 дня

        # Выбираем телефоны, которые не проданы, не сломаны, и у которых страховка либо скоро истекает,
        # либо уже истекла, но не слишком давно.
        rows = await conn.fetch(
            """
            SELECT * FROM user_phones
            WHERE is_sold = FALSE 
              AND is_broken = FALSE 
              AND insurance_active_until IS NOT NULL
              AND insurance_active_until <= $1 
              AND insurance_active_until >= $2 
            ORDER BY user_id, insurance_active_until ASC
            """,
            upper_expiry_limit_utc,
            lower_already_expired_limit_utc 
        )
        
        result_phones = []
        for row_dict in (dict(r) for r in rows):
            for key, value in row_dict.items():
                if isinstance(value, datetime) and value.tzinfo is None:
                    row_dict[key] = value.replace(tzinfo=dt_timezone.utc)
            result_phones.append(row_dict)
        return result_phones
    except Exception as e:
        logger.error(f"DB: Ошибка при получении телефонов с истекающей страховкой: {e}", exc_info=True)
        return []
    finally:
        if not conn_ext and conn and not conn.is_closed():
            await conn.close()

            
            
async def add_achievement(user_id: int, achievement_key: str, progress_data: Optional[Dict] = None, conn_ext: Optional[asyncpg.Connection] = None) -> bool:
    """
    Добавляет достижение пользователю. Возвращает True, если достижение было добавлено (т.е. его не было), иначе False.
    """
    conn = conn_ext if conn_ext else await get_connection()
    try:
        existing = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM user_achievements WHERE user_id = $1 AND achievement_key = $2)",
            user_id, achievement_key
        )
        if existing:
            logger.debug(f"Achievement '{achievement_key}' already unlocked by user {user_id}.")
            return False

        progress_data_to_db = json.dumps(progress_data) if progress_data is not None else None

        await conn.execute(
            "INSERT INTO user_achievements (user_id, achievement_key, achieved_at, progress_data) VALUES ($1, $2, $3, $4)",
            user_id, achievement_key, datetime.now(dt_timezone.utc), progress_data_to_db
        )
        logger.info(f"Achievement '{achievement_key}' unlocked by user {user_id}.")
        return True
    except Exception as e:
        logger.error(f"DB: Error adding achievement '{achievement_key}' for user {user_id}: {e}", exc_info=True)
        return False
    finally:
        if not conn_ext and conn and not conn.is_closed():
            await conn.close()

async def get_user_achievements(user_id: int, conn_ext: Optional[asyncpg.Connection] = None) -> List[Dict[str, Any]]:
    """
    Получает список всех достижений пользователя.
    """
    conn = conn_ext if conn_ext else await get_connection()
    try:
        rows = await conn.fetch(
            "SELECT achievement_key, achieved_at, progress_data FROM user_achievements WHERE user_id = $1 ORDER BY achieved_at ASC",
            user_id
        )
        results = []
        for row_dict in (dict(r) for r in rows):
            if row_dict.get('progress_data') and isinstance(row_dict['progress_data'], str):
                try:
                    row_dict['progress_data'] = json.loads(row_dict['progress_data'])
                except json.JSONDecodeError:
                    logger.warning(f"DB (get_user_achievements): Failed to decode JSON for progress_data for user {user_id}, achievement {row_dict.get('achievement_key')}")
                    row_dict['progress_data'] = None
            results.append(row_dict)
        return results
    except Exception as e:
        logger.error(f"DB: Error getting achievements for user {user_id}: {e}", exc_info=True)
        return []
    finally:
        if not conn_ext and conn and not conn.is_closed():
            await conn.close()

# --- КОНЕЦ НОВЫХ ФУНКЦИЙ ДЛЯ ДОСТИЖЕНИЙ ---   
async def create_event_queue_table():
    """
    Создает таблицу event_queue, если она не существует.
    """
    query = """
    CREATE TABLE IF NOT EXISTS event_queue (
        event_id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        event_type VARCHAR(50) NOT NULL,
        event_data JSONB,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        processed BOOLEAN DEFAULT FALSE,
        processed_at TIMESTAMP WITH TIME ZONE
    );
    """
    conn = None
    try:
        conn = await asyncpg.connect(Config.DATABASE_URL)
        await conn.execute(query)
        logger.info("Таблица 'event_queue' проверена/создана успешно.")
        return True
    except Exception as e:
        logger.error(f"Ошибка при создании/проверке таблицы 'event_queue': {e}", exc_info=True)
        return False
    finally:
        if conn:
            await conn.close()

# Теперь добавьте функции для работы с очередью событий (если вы их ещё не добавили)
async def add_event_to_queue(user_id: int, event_type: str, event_data: Dict[str, Any], conn_ext: Optional[asyncpg.Connection] = None) -> bool:
    """
    Добавляет событие в очередь для последующей обработки.
    event_data будет сохранено как JSONB.
    """
    query = """
        INSERT INTO event_queue (user_id, event_type, event_data, created_at)
        VALUES ($1, $2, $3, NOW());
    """
    try:
        if conn_ext:
            await conn_ext.execute(query, user_id, event_type, json.dumps(event_data))
        else:
            # Используем пул соединений, если conn_ext не передан
            async with asyncpg.create_pool(Config.DATABASE_URL) as pool:
                async with pool.acquire() as conn:
                    await conn.execute(query, user_id, event_type, json.dumps(event_data))
        return True
    except Exception as e:
        logger.error(f"Failed to add event to queue for user {user_id}, type {event_type}: {e}", exc_info=True)
        return False

async def get_pending_events(limit: int = 100, conn_ext: Optional[asyncpg.Connection] = None) -> List[Dict[str, Any]]:
    """
    Получает необработанные события из очереди.
    """
    query = """
        SELECT event_id, user_id, event_type, event_data, created_at, processed
        FROM event_queue
        WHERE processed = FALSE
        ORDER BY created_at ASC
        LIMIT $1;
    """
    records = []
    try:
        if conn_ext:
            rows = await conn_ext.fetch(query, limit)
        else:
            async with asyncpg.create_pool(Config.DATABASE_URL) as pool:
                async with pool.acquire() as conn:
                    rows = await conn.fetch(query, limit)
        for row in rows:
            # asyncpg возвращает Record, преобразуем в dict для удобства
            record_dict = dict(row)
            # JSONB данные нужно распарсить, если asyncpg их не сделал автоматически (обычно делает)
            if isinstance(record_dict.get('event_data'), str):
                try:
                    record_dict['event_data'] = json.loads(record_dict['event_data'])
                except json.JSONDecodeError:
                    logger.warning(f"Failed to decode JSON for event_data in event {record_dict.get('event_id')}")
                    record_dict['event_data'] = {} # Fallback
            records.append(record_dict)
    except Exception as e:
        logger.error(f"Failed to get pending events: {e}", exc_info=True)
    return records

async def mark_event_as_processed(event_id: int, conn_ext: Optional[asyncpg.Connection] = None) -> bool:
    """
    Помечает событие как обработанное.
    """
    query = """
        UPDATE event_queue
        SET processed = TRUE, processed_at = NOW()
        WHERE event_id = $1;
    """
    try:
        if conn_ext:
            status = await conn_ext.execute(query, event_id)
        else:
            async with asyncpg.create_pool(Config.DATABASE_URL) as pool:
                async with pool.acquire() as conn:
                    status = await conn.execute(query, event_id)
        return status == 'UPDATE 1' # Проверяем, что обновилась одна строка
    except Exception as e:
        logger.error(f"Failed to mark event {event_id} as processed: {e}", exc_info=True)
        return False         
