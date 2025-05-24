# config.py
import os
from dotenv import load_dotenv
from pytz import timezone as pytz_timezone # <<< Убедитесь, что этот импорт есть
from datetime import timezone as dt_timezone # <<< Убедитесь, что этот импорт есть

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    DATABASE_URL = os.getenv("DATABASE_URL")
    ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
    TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")
    RESET_HOUR = 21 # Используется для сброса кулдауна OneUI
    TIMEZONE_OBJ_UTC = dt_timezone.utc 

    # Константы для семей
    FAMILY_MAX_MEMBERS = 10

    # Константы для системы браков
    PROPOSAL_EXPIRY_HOURS = 24
    DIVORCE_FINALIZE_HOURS = 72
    MARRIAGE_EVENT_CHECK_INTERVAL_SECONDS = 300

    # Константы для семейных соревнований
    COMPETITION_DURATION_DAYS = 4
    COMPETITION_WINNER_VERSION_BONUS = 3.0
    COMPETITION_WINNER_ONECOIN_BONUS = 50
    COMPETITION_END_CHECK_INTERVAL_SECONDS = 3600
    COMPETITION_RESTART_DELAY_SECONDS = 3600 # 1 час
    
    # Шансы для категорий призов рулетки: (категория, вес)
    ROULETTE_PRIZE_CATEGORIES_CHANCES = [
        ("onecoin_reward", 50),            # 50% шанс на OneCoin
        ("extra_bonus_attempt", 10),       # 10% шанс на доп. попытку /bonus
        ("extra_oneui_attempt", 10),       # 10% шанс на доп. попытку /oneui
        ("bonus_multiplier_boost", 20),    # 20% шанс на усиление множителя
        ("negative_protection_charge", 10),# 10% шанс на заряд защиты
        ("phone_reward", 2)                # 2% шнас на телефон             
    ]
    # Диапазоны и веса для приза OneCoin: ((min_coins, max_coins), weight)
    ROULETTE_ONECOIN_PRIZES = [
        ((20, 50), 60),    # Например, 40% из 50% (т.е. 20% от общего шанса) на 20-50 монет
        ((51, 100), 30),   # 15% от общего шанса
        ((101, 150), 10),  # 10% от общего шанса
        ((151, 170), 5),  # 5% от общего шанса
        ((200, 300), 0.4),    # 🎉 джекпот! шанс 0.5% от 50%
    ]
    # Значения и веса для усиления бонус-множителя: (boost_factor, weight)
    ROULETTE_BONUS_MULTIPLIER_BOOSTS = [
        (1.2, 40), # Например, 40% из 20% (т.е. 8% от общего шанса) на буст x1.2
        (1.5, 30), # 6% от общего шанса
        (2.0, 20), # 4% от общего шанса
        (3.0, 10), # 2% от общего шанса
    ]
    # Команды рулетки (для регистрации обработчика)
    ROULETTE_COMMAND_ALIASES = ["roll", "spin", "roulette", "lucky", "крутить", "рулетка", "спин"]
    # <<< НОВАЯ ПЕРЕМЕННАЯ: Шансы выпадения серий телефонов (если выпал "phone_reward") >>>
    # (Серия, Вес)
    ROULETTE_PHONE_SERIES_CHANCES = [
        ("A", 70), # 70% шанс на A-серию
        ("S", 25), # 25% шанс на S-серию
        ("Z", 5)   # 5% шанс на Z-серию (Fold/Flip и др. из этой категории)
    ]
    # <<< КОНЕЦ НОВОЙ ПЕРЕМЕННОЙ >>>

    # ID для отправки логов ботом
    _log_telegram_user_id_str = os.getenv("LOG_TELEGRAM_USER_ID")
    LOG_TELEGRAM_USER_ID = int(_log_telegram_user_id_str) if _log_telegram_user_id_str and _log_telegram_user_id_str.lstrip('-').isdigit() else None
    if _log_telegram_user_id_str and LOG_TELEGRAM_USER_ID is None: # Если строка была, но не распарсилась
        print(f"Предупреждение: LOG_TELEGRAM_USER_ID ('{_log_telegram_user_id_str}') не является корректным числом и будет проигнорирован.")


    _log_telegram_chat_id_str = os.getenv("LOG_TELEGRAM_CHAT_ID")
    LOG_TELEGRAM_CHAT_ID = int(_log_telegram_chat_id_str) if _log_telegram_chat_id_str and _log_telegram_chat_id_str.lstrip('-').isdigit() else None
    if _log_telegram_chat_id_str and LOG_TELEGRAM_CHAT_ID is None: # Если строка была, но не распарсилась
        print(f"Предупреждение: LOG_TELEGRAM_CHAT_ID ('{_log_telegram_chat_id_str}') не является корректным числом и будет проигнорирован.")

    # Загружаем ID темы для логов
    _log_telegram_topic_id_str = os.getenv("LOG_TELEGRAM_TOPIC_ID")
    LOG_TELEGRAM_TOPIC_ID = int(_log_telegram_topic_id_str) if _log_telegram_topic_id_str and _log_telegram_topic_id_str.isdigit() else None
    if _log_telegram_topic_id_str and LOG_TELEGRAM_TOPIC_ID is None: # Если строка была, но не распарсилась
        print(f"Предупреждение: LOG_TELEGRAM_TOPIC_ID ('{_log_telegram_topic_id_str}') не является корректным числом. Отправка в тему для логов будет отключена.")
        
    _status_notification_chat_id_str = os.getenv("STATUS_NOTIFICATION_CHAT_ID")
    NOTIFICATION_CHAT_ID = int(_status_notification_chat_id_str) if _status_notification_chat_id_str and _status_notification_chat_id_str.lstrip('-').isdigit() else None
    if _status_notification_chat_id_str and NOTIFICATION_CHAT_ID is None:
        print(f"Предупреждение: STATUS_NOTIFICATION_CHAT_ID ('{_status_notification_chat_id_str}') из .env не является корректным числом и будет проигнорирован для статусных уведомлений.")    

    ROULETTE_GLOBAL_COOLDOWN_DAYS = 2
    # === Настройки для системы бонусных множителей (команда /bonus) ===
    BONUS_MULTIPLIER_COOLDOWN_DAYS = 3
    BONUS_MULTIPLIER_RESET_HOUR = 21
    # Обновленные шансы: "экстремальные" значения реже, "мягкие" и "нейтральные" чаще
    BONUS_MULTIPLIER_CHANCES = [
    # Отрицательные значения (общий шанс 20%)
    # Шанс сильно уменьшается к -3.0
    (-3.0, 1), (-2.9, 1), (-2.8, 1), (-2.7, 1), (-2.6, 1),
    (-2.5, 1), (-2.4, 1), (-2.3, 1), (-2.2, 1), (-2.1, 1),
    (-2.0, 1),
    (-1.9, 2), (-1.8, 2),
    (-1.7, 3), (-1.6, 3),
    (-1.5, 4), (-1.4, 4),
    (-1.3, 5),
    (-1.2, 6),
    (-1.1, 7),
    (-1.0, 8),
    (-0.9, 15),
    (-0.8, 17),
    (-0.7, 18),
    (-0.6, 20),
    (-0.5, 30),
    (-0.4, 40),
    (-0.3, 44),
    (-0.2, 48),
    (-0.1, 50),

    # Нейтральное значение (шанс 40%)
    (1.0, 400),

    # Положительные значения (общий шанс 40%)
    # Шанс сильно уменьшается к 3.0
    (1.1, 44),
    (1.2, 42),
    (1.3, 37),
    (1.4, 34),
    (1.5, 32),
    (1.6, 30),
    (1.7, 27),
    (1.8, 24),
    (1.9, 22),
    (2.0, 20),
    (2.1, 17),
    (2.2, 14),
    (2.3, 12),
    (2.4, 10),
    (2.5, 8),
    (2.6, 7),
    (2.7, 5),
    (2.8, 5), (2.9, 5), (3.0, 5)
    ]

    # === Настройки для системы ежедневного стрик-бонуса (команда /oneui) ===
    DAILY_STREAKS_CONFIG = [
        {'target_days': 3,   'version_reward': 5.0,   'onecoin_reward': 0,     'progress_show_within_days': 2, 'name': "🚀 Взлёт Ракеты"},
        {'target_days': 7,   'version_reward': 7.0,  'onecoin_reward': 10,    'progress_show_within_days': 3, 'name': "✨ Звёздная Неделя"},
        {'target_days': 14,  'version_reward': 9.0,  'onecoin_reward': 20,    'progress_show_within_days': 4, 'name': "🌟 Сияние Полумесяца"},
        {'target_days': 21,  'version_reward': 13.0,  'onecoin_reward': 30,    'progress_show_within_days': 5, 'name': "🛠️ Стальной Характер"},
        {'target_days': 30,  'version_reward': 20.0,  'onecoin_reward': 40,    'progress_show_within_days': 7, 'name': "🗓️ Лунный Страж"},
        {'target_days': 45,  'version_reward': 28.0,  'onecoin_reward': 50,    'progress_show_within_days': 10, 'name': "🧭 Навигатор Преданности"},
        {'target_days': 60,  'version_reward': 33.0,  'onecoin_reward': 60,    'progress_show_within_days': 10, 'name': "💼 Мастер Двух Путей"},
        {'target_days': 90,  'version_reward': 45.0,  'onecoin_reward': 90,    'progress_show_within_days': 15, 'name': "🍂 Хранитель Трёх Сезонов"},
        {'target_days': 120, 'version_reward': 60.0,  'onecoin_reward': 120,   'progress_show_within_days': 20, 'name': "❄️ Ледяной Бастион"},
        {'target_days': 150, 'version_reward': 70.0,  'onecoin_reward': 150,   'progress_show_within_days': 25, 'name': "🌱 Росток Вечности"},
        {'target_days': 180, 'version_reward': 75.0,  'onecoin_reward': 180,   'progress_show_within_days': 30, 'name': "☀️ Экваториальное Сияние"},
        {'target_days': 240, 'version_reward': 85.0,  'onecoin_reward': 250,   'progress_show_within_days': 30, 'name': "💪 Мощь Континента"},
        {'target_days': 300, 'version_reward': 100.0, 'onecoin_reward': 300,   'progress_show_within_days': 45, 'name': "🏆 Чемпион Десятилетия (Циклов)"},
        {'target_days': 330, 'version_reward': 120.0, 'onecoin_reward': 300,   'progress_show_within_days': 30, 'name': "🏁 Предвестник Величия"},
        {'target_days': 365, 'version_reward': 150.0, 'onecoin_reward': 500,   'progress_show_within_days': 60, 'name': "👑 Император OneUi"}
    ]

    PROGRESSIVE_STREAK_BREAK_COMPENSATION = [
        {'min_streak_days_before_break': 330, 'version_bonus': 30.0, 'onecoin_bonus': 150},
        {'min_streak_days_before_break': 300, 'version_bonus': 25.0, 'onecoin_bonus': 120},
        {'min_streak_days_before_break': 240, 'version_bonus': 20.0, 'onecoin_bonus': 100},
        {'min_streak_days_before_break': 180, 'version_bonus': 15.0, 'onecoin_bonus': 75},
        {'min_streak_days_before_break': 120, 'version_bonus': 10.0, 'onecoin_bonus': 50},
        {'min_streak_days_before_break': 90,  'version_bonus': 7.0,  'onecoin_bonus': 35},
        {'min_streak_days_before_break': 60,  'version_bonus': 5.0,  'onecoin_bonus': 25},
        {'min_streak_days_before_break': 30,  'version_bonus': 3.0,  'onecoin_bonus': 15},
        {'min_streak_days_before_break': 14,  'version_bonus': 1.5,  'onecoin_bonus': 7},
        {'min_streak_days_before_break': 7,   'version_bonus': 0.7,  'onecoin_bonus': 3},
        {'min_streak_days_before_break': 3,   'version_bonus': 0.3,  'onecoin_bonus': 1},
        {'min_streak_days_before_break': 1,   'version_bonus': 0.1,  'onecoin_bonus': 0}
    ]
    DEFAULT_STREAK_BREAK_COMPENSATION_VERSION = 0.1
    DEFAULT_STREAK_BREAK_COMPENSATION_ONECOIN = 0

    PROGRESS_BAR_FILLED_CHAR = '🟨'
    PROGRESS_BAR_FULL_STREAK_CHAR = '🟩'
    PROGRESS_BAR_EMPTY_CHAR = '⬜️'

    # === Настройки Рынка ===
    MARKET_ITEMS = {
        "oneui_attempt": {
            "name": "Дополнительная попытка /oneui",
            "price": 100,
            "description": "Позволяет использовать /oneui еще раз, игнорируя обычный кулдаун.",
            "target_command": "/oneui",
            "db_field": "extra_oneui_attempts" # Поле в roulette_status
        },
        "bonus_attempt": {
            "name": "Дополнительная попытка /bonus",
            "price": 50,
            "description": "Позволяет использовать /bonus еще раз, игнорируя обычный кулдаун.",
            "target_command": "/bonus",
            "db_field": "extra_bonus_attempts" # Поле в roulette_status
        },
        "roulette_spin": {
            "name": "Дополнительный спин /roulette",
            "price": 70,
            "description": "Позволяет использовать /roulette еще раз, игнорируя обычный кулдаун.",
            "target_command": "/roulette",
            "db_field": "extra_roulette_spins" # НОВОЕ ПОЛЕ в roulette_status
        }
    }
    MARKET_COMMAND_ALIASES = ["market", "shop", "buy", "рынок", "магазин", "купить", "лавка", "товары"] # Добавил алиасы
    MARKET_PURCHASE_CONFIRMATION_TIMEOUT_SECONDS = 30
    MARKET_PHONE_CONFIRMATION_TIMEOUT_SECONDS = 60 # Таймаут для подтверждения покупки/продажи телефона (и ремонта)
    MARKET_BUY_COMMAND_ALIASES = ["buyitem", "purchase", "купитьтовар", "приобрести"] # Добавил алиасы
    
    # === Настройки Телефонов и Предметов ===
    MAX_PHONES_PER_USER = 2 # Максимальное количество активных телефонов у пользователя
    PHONE_CHARGE_COST = 20 # Стоимость зарядки телефона в OneCoin
    PHONE_BASE_BATTERY_DAYS = 2 # Базовое время работы телефона в днях без бонусов чехла
    PHONE_CHARGE_WINDOW_DAYS = 2 # Сколько дней есть на зарядку после того, как села батарея, до поломки аккумулятора
    PHONE_UPGRADE_MEMORY_COST = 50 # Стоимость работы по улучшению памяти (сам модуль памяти покупается отдельно)
    MEMORY_UPGRADE_ITEM_KEY = "MEMORY_MODULE_50GB" # Ключ модуля памяти, используемого для апгрейда
    
    # Проценты продажи от оригинальной цены PHONE_COMPONENTS или PHONE_CASES
    COMPONENT_SELL_PERCENTAGE = 0.50  # 50% для деталей (экраны, платы и т.д.)
    MEMORY_MODULE_SELL_PERCENTAGE = 0.40  # 40% для модулей памяти
    CASE_SELL_PERCENTAGE = 0.20      # 20% для чехлов
    # Минимальная цена продажи, если расчетная цена < 1 (чтобы не продавать за 0 OC)
    MIN_SELL_PRICE_IF_ORIGINAL_GT_ZERO = 1

    # Настройки ремонта телефонов
    PHONE_REPAIR_WORK_PERCENTAGE = 0.30  # 30% от "идеальной" текущей стоимости телефона за работу
    PHONE_MIN_REPAIR_WORK_COST = 10      # Минимальная стоимость работы мастера в OneCoin
    # Минимальная цена продажи, если расчетная цена < 1 (чтобы не продавать за 0 OC)
    MIN_SELL_PRICE_IF_ORIGINAL_GT_ZERO = 1
    PHONE_INSURANCE_COST = 50 # Стоимость страховки на месяц
    PHONE_INSURANCE_EARLY_RENEWAL_DAYS = 5 # За сколько дней до окончания можно продлить со скидкой
    PHONE_INSURANCE_EARLY_RENEWAL_COST = 40 # Стоимость продления со скидкой
    PHONE_INSURANCE_COST_6_MONTHS = 240 # Стоимость страховки на 6 месяцев (180 дней)
    PHONE_INSURANCE_DURATION_6_MONTHS_DAYS = 180 # Длительность полугодовой страховки в днях
    PHONE_INSURANCE_EARLY_RENEWAL_COST_6_MONTHS = 220 # Стоимость раннего продления на 6 месяцев (если хотите)
    # PHONE_INSURANCE_MIN_DAYS_LEFT_FOR_6_MONTH_RENEWAL = 30 # Например, если есть <30 дней, можно продлить на 6 мес (опционально)
    
    # === Инфляция ===
    INFLATION_SETTING_KEY = "current_inflation_multiplier"
    DEFAULT_INFLATION_MULTIPLIER = 1.0
    INFLATION_INCREASE_RATE = 0.09 # +5%
    INFLATION_PERIOD_MONTHS = 2 # Каждые 3 месяца
    MARKET_PHONE_CONFIRMATION_TIMEOUT_SECONDS = 3600 # 1 час
    ROULETTE_WON_PHONE_SELL_PERCENTAGE = 0.80 # 80%

    # === Настройки Черного Рынка (Динамический) ===
    BLACKMARKET_ACCESS_STREAK_REQUIREMENT = 30 # Мин. стрик для доступа ("Лунный Страж")
    BLACKMARKET_RESET_HOUR = 21 # Час обновления ассортимента ЧР (по TIMEZONE)
    # Команды ЧР (для регистрации и справки)
    BLACKMARKET_COMMAND_ALIASES = ["blackmarket", "bm", "чр", "черныйрынок"] 
    BLACKMARKET_BUY_SLOT_ALIASES = ["buybm", "купитьчрслот", "bmbuy"] 

    BLACKMARKET_NUM_REGULAR_ITEMS = 5  # Количество "обычных" контрабандных товаров (телефоны, компоненты, чехлы)
    BLACKMARKET_NUM_STOLEN_ITEMS = 1   # Количество "краденых" телефонов (только телефоны)
    BLACKMARKET_TOTAL_SLOTS = BLACKMARKET_NUM_REGULAR_ITEMS + BLACKMARKET_NUM_STOLEN_ITEMS # Всего 6 слотов

    # Скидки для обычных контрабандных товаров на ЧР (от цены после инфляции)
    BLACKMARKET_REGULAR_ITEM_DISCOUNT_MIN = 0.10  # Мин. скидка 10%
    BLACKMARKET_REGULAR_ITEM_DISCOUNT_MAX = 0.30  # Макс. скидка 25%

    # Дополнительная скидка для "краденых" телефонов (от цены *уже со скидкой ЧР*)
    BLACKMARKET_STOLEN_ITEM_ADDITIONAL_DISCOUNT_MIN = 0.15 # Мин. доп. скидка 15%
    BLACKMARKET_STOLEN_ITEM_ADDITIONAL_DISCOUNT_MAX = 0.30 # Макс. доп. скидка 30%
    
    # Возможные "износы" для краденых телефонов
    # Ключ эффекта будет сохранен в black_market_offers.wear_data и user_phones.data
    # Шаблоны описания помогут генерировать текст для игрока
    BLACKMARKET_STOLEN_ITEM_WEAR_EFFECTS = {
        "reduced_battery_factor": { # Множитель к базовому времени работы батареи
            "min_factor": 0.70, # Батарея будет работать на 70% от обычной
            "max_factor": 0.90, # Батарея будет работать на 90% от обычной
            "description_template": "Батарея этой модели немного 'устала' (эффективность ~{:.0f}%)."
        },
        "increased_break_chance_factor": { # Доп. множитель к шансу поломки (сверх контрабандного)
            "min_factor": 1.1, # +10% к итоговому шансу поломки
            "max_factor": 1.3, # +30% к итоговому шансу поломки
            "description_template": "Повышенная хрупкость (доп. риск поломки x{:.1f})."
        },
        "cosmetic_defect_descriptions": [ # Просто текстовые описания для bm_description и, возможно, для user_phones.data
            "небольшая трещина на углу экрана", "глубокая царапина на задней крышке",
            "слегка погнутый корпус", "выцветшие участки краски", "залипает кнопка громкости",
            "пыль под стеклом камеры", "потертости на гранях", "небольшой скол на рамке"
        ] 
    }

    # Шанс, что один из BLACKMARKET_NUM_REGULAR_ITEMS слотов ЧР будет заменен эксклюзивом из exclusive_phone_data.py
    BLACKMARKET_EXCLUSIVE_ITEM_CHANCE = 0.01  # 15% шанс на появление эксклюзива в одном из "обычных" слотов
 
    # Контрабандные компоненты
    BLACKMARKET_COMPONENT_DISCOUNT_PERCENT = 0.15 # Скидка 15% на компоненты с ЧР (от цены после инфляции)
    BLACKMARKET_COMPONENT_DEFECT_CHANCE = 0.20    # 20% шанс, что купленный на ЧР компонент окажется бракованным

    # Ненадежные продавцы (для телефонов, покупаемых на ЧР)
    BLACKMARKET_UNTRUSTED_SELLER_CHANCE = 0.08 # 8% шанс получить "не тот" цвет или косметический дефект

    # Повышенный шанс поломки для ЛЮБОГО контрабандного телефона (из ЧР или нет)
    # Этот параметр у тебя уже был, убедись, что он актуален. Если нет, добавь.
    CONTRABAND_BREAK_CHANCE_MULTIPLIER = 1.5 
    
    # Месячный лимит на покупку ТЕЛЕФОНОВ с ЧР
    BLACKMARKET_MAX_PHONES_PER_MONTH = 3
    # === Настройки для Бизнесов ===
    BUSINESS_MAX_PER_USER_PER_CHAT = 2 # Максимальное количество бизнесов на игрока в одном чате
    BUSINESS_DAILY_INCOME_COLLECTION_HOUR = 21 # Час сбора дохода бизнесов (по TIMEZONE)
    BUSINESS_TAX_BASE_PERCENT = 0.07 # Базовый налог 7%
    BUSINESS_TAX_FULL_STAFF_PERCENT = 0.15 # Налог 15% при полной занятости персонала
    BUSINESS_TAX_FULL_STAFF_START_BUSINESS_INDEX = 7 # Начинать увеличение налога с 7-го бизнеса (бизнес_7_it_oneui_solutions_ai)

    BUSINESS_STAFF_COST_MULTIPLIER = 0.10 # Стоимость найма 1 сотрудника = 10% от цены бизнеса
    BUSINESS_STAFF_INCOME_MAX_BOOST_PERCENT = 0.20 # Макс. 20% от базового дохода/час для 1-го бизнеса
    BUSINESS_STAFF_INCOME_MIN_BOOST_PERCENT = 0.01 # Мин. 1% от базового дохода/час для 18-го бизнеса

    BUSINESS_EVENT_CHANCE_PERCENT = 0.15 # 15% шанс, что произойдет событие (из 100% вероятности события)
    BUSINESS_EVENT_TYPE_CHANCE_POSITIVE = 0.50 # 50% шанс на позитивное событие (если событие произошло)
    BUSINESS_UPGRADE_PROTECTION_CHANCE_SUCCESS = 0.70 # 70% шанс, что апгрейд сработает (иначе 30% он не поможет)
    
    # Настройки для Банка
    BANK_MAX_LEVEL = 30 # Максимальный уровень банка
    
    # === Настройки Ограбления Банка (/robbank) ===
    ROBBANK_ALIASES = ["robbank", "ограбитьбанк", "налет", "ограбление", "bankrob"]
    ROBBANK_COOLDOWN_DAYS = 1 # Раз в игровой день
    ROBBANK_RESET_HOUR = 21 # Час сброса кулдауна (используем общий RESET_HOUR)
    ROBBANK_ONEUI_BLOCK_DURATION_DAYS = 2 
    ROBBANK_PREPARATION_COST_MIN = 50
    ROBBANK_PREPARATION_COST_MAX = 150
    ROBBANK_RESULT_DELAY_MIN_SECONDS = 300 # 1 минута
    ROBBANK_RESULT_DELAY_MAX_SECONDS = 800 # 2 минуты

    ROBBANK_BASE_SUCCESS_CHANCE = 0.60  # 60%
    ROBBANK_ONEUI_VERSION_BONUS_PER_X_VERSIONS = 0.01  # +1% к шансу
    ROBBANK_ONEUI_X_VERSIONS_FOR_BONUS = 15 # за каждые 15 версий
    ROBBANK_BANK_LEVEL_SUCCESS_BONUS_PER_LEVEL = 0.05  # +5% к шансу за уровень банка
    ROBBANK_MAX_SUCCESS_CHANCE = 0.95  # Максимальный шанс 95%
    ROBBANK_GUARANTEED_SUCCESS_BANK_LEVEL_MIN = 15 # Уровень банка для 100% шанса
    ROBBANK_GUARANTEED_SUCCESS_BANK_LEVEL_MAX = 18 # Верхняя граница для 100% шанса

    ROBBANK_REWARD_BASE_MIN = 100
    ROBBANK_REWARD_BASE_MAX = 1000
    ROBBANK_REWARD_MAX_CHANCE = 0.005  # 0.5% шанс на максимальную награду из диапазона

    # Мультипликаторы к награде (значение 1.0 означает отсутствие бонуса)
    ROBBANK_REWARD_ONEUI_MULTIPLIER_PER_X_VERSIONS = 0.05  # +5% к награде (т.е. множитель 1.05)
    ROBBANK_REWARD_ONEUI_X_VERSIONS_FOR_MULTIPLIER = 15     # за каждые 15 версий
    ROBBANK_REWARD_BANK_LEVEL_MULTIPLIER_PER_LEVEL = 0.20  # +20% к награде за уровень банка (т.е. множитель 1.20)

    # Бонусы от порядкового номера самого "старшего" бизнеса (1-18) в чате как МНОЖИТЕЛИ
    # Пример: 1.10 означает +10% к награде
    ROBBANK_REWARD_BIZ_TIER_1_6_MIN_BONUS_PERCENT_AS_MULTIPLIER = 1.10 # Для бизнеса №1
    ROBBANK_REWARD_BIZ_TIER_1_6_MAX_BONUS_PERCENT_AS_MULTIPLIER = 1.50 # Для бизнеса №6
    ROBBANK_REWARD_BIZ_TIER_7_14_BONUS_PERCENT_AS_MULTIPLIER = 2.00   # Для бизнесов №7-14 (100% бонус)
    ROBBANK_REWARD_BIZ_TIER_15_18_MIN_BONUS_PERCENT_AS_MULTIPLIER = 2.00 # Для бизнеса №15 (100% бонус)
    ROBBANK_REWARD_BIZ_TIER_15_18_MAX_BONUS_PERCENT_AS_MULTIPLIER = 5.00 # Для бизнеса №18 (400% бонус)
    ROBBANK_REWARD_BIZ_TIER_15_18_COUNT = 4 # Количество бизнесов в тире 15-18 (15, 16, 17, 18)
    
    
    # Настройки для команды /onecoin (ежедневная награда)
    DAILY_ONECOIN_ALIASES = ["onecoin", "монетка", "ежедневка", "собратьмонеты"] # Твои дерзкие алиасы
    DAILY_ONECOIN_COOLDOWN_DAYS = 1 # Кулдаун 1 "игровой день"
    # RESET_HOUR уже есть (21), будет использоваться тот же для сброса кулдауна

    # Шансы и диапазоны наград для /onecoin
    # Формат: ((min_coins, max_coins), вес_для_random.choices)
    DAILY_ONECOIN_REWARD_TIERS = [
        # Тир 1 (Частый): 30-50 OneCoin, общий шанс 80%
        ((30, 50), 80),

        # Тир 2 (Средний/Редкий): 51-199 OneCoin, общий шанс 19% (разбит на под-тиры)
        ((51, 80), 10),    # Абсолютный шанс: (10 / (80+10+5+3+2)) * 100% = 10%
        ((81, 120), 5),    # Абсолютный шанс: 5%
        ((121, 160), 3),   # Абсолютный шанс: 3%
        ((161, 200), 0.005),   # Абсолютный шанс: 1% (диапазон до 199)

        # Тир 3 (Джекпот): Ровно 200 OneCoin, общий шанс 1%
        ((500, 500), 1)    # Абсолютный шанс: 1%
    ]
    # Сумма весов: 80 + 10 + 5 + 3 + 1 + 1 = 100. Распределение корректно.
    
    # Блокировка /oneui после ареста (сброс в ROBBANK_RESET_HOUR)
    
    # --- Настройки Достижений ---
    ACHIEVEMENTS_DATA = {
        # OneUI-Мастерство
        "oneui_glitch_awakening": {
            "name": "Пробуждение Искажения", "description": "Достичь версии OneUI 10.0.",
            "type": "oneui_version", "target_value": 10.0, "icon": "🪞"
        },
        "oneui_echo_failure": {
            "name": "Эхо Сбоя", "description": "Достичь версии OneUI 15.0.",
            "type": "oneui_version", "target_value": 15.0, "icon": "👻"
        },
        "oneui_anomaly_vibration": {
            "name": "Вибрация Аномалии", "description": "Достичь версии OneUI 20.0.",
            "type": "oneui_version", "target_value": 20.0, "icon": "⚡️"
        },
        "oneui_reality_shift": {
            "name": "Сдвиг Реальности", "description": "Достичь версии OneUI 25.0.",
            "type": "oneui_version", "target_value": 25.0, "icon": "🌀"
        },
        "oneui_virus_harmony": {
            "name": "Гармония Вирусного Кода", "description": "Достичь версии OneUI 30.0.",
            "type": "oneui_version", "target_value": 30.0, "icon": "🦠"
        },
        "oneui_fragment_truth": {
            "name": "Фрагмент Истины (Лживой)", "description": "Достичь версии OneUI 35.0.",
            "type": "oneui_version", "target_value": 35.0, "icon": "🎭"
        },
        "oneui_protocol_breach": {
            "name": "Разрыв Протокола", "description": "Достичь версии OneUI 40.0.",
            "type": "oneui_version", "target_value": 40.0, "icon": "⛓️‍💥"
        },
        "oneui_shadow_collapse": {
            "name": "Тень Грядущего Коллапса", "description": "Достичь версии OneUI 45.0.",
            "type": "oneui_version", "target_value": 45.0, "icon": "🌑"
        },
        "oneui_web_distortion": {
            "name": "Искажение Веб-Паутины", "description": "Достичь версии OneUI 50.0.",
            "type": "oneui_version", "target_value": 50.0, "icon": "🕸️"
        },
        "oneui_system_architect": {
            "name": "Архитектор Обрушения Систем", "description": "Достичь версии OneUI 60.0.",
            "type": "oneui_version", "target_value": 60.0, "icon": "🏗️💥"
        },
        "oneui_fragmented_keeper": {
            "name": "Хранитель Разрозненных Схем", "description": "Достичь версии OneUI 70.0.",
            "type": "oneui_version", "target_value": 70.0, "icon": "🧩"
        },
        "oneui_foundation_breaker": {
            "name": "Взломщик Фундамента", "description": "Достичь версии OneUI 80.0.",
            "type": "oneui_version", "target_value": 80.0, "icon": "💣"
        },
        "oneui_digital_decay_maestro": {
            "name": "Маэстро Цифрового Разложения", "description": "Достичь версии OneUI 90.0.",
            "type": "oneui_version", "target_value": 90.0, "icon": "☢️"
        },
        "oneui_glitch_matrix_lord": {
            "name": "Повелитель Глючной Матрицы", "description": "Достичь версии OneUI 100.0.",
            "type": "oneui_version", "target_value": 100.0, "icon": "👑👾"
        },
        "oneui_virtual_distortion_weaver": {
            "name": "Ткач Виртуальных Искажений", "description": "Достичь версии OneUI 120.0.",
            "type": "oneui_version", "target_value": 120.0, "icon": "🌌"
        },
        "oneui_forgotten_firmware_necromancer": {
            "name": "Некромант Забытых Прошивок", "description": "Достичь версии OneUI 140.0.",
            "type": "oneui_version", "target_value": 140.0, "icon": "💀💾"
        },
        "oneui_quantum_chaos_conductor": {
            "name": "Проводник Квантового Хаоса", "description": "Достичь версии OneUI 160.0.",
            "type": "oneui_version", "target_value": 160.0, "icon": "⚛️"
        },
        "oneui_nowhere_signal_catcher": {
            "name": "Ловец Сигналов Из Ниоткуда", "description": "Достичь версии OneUI 180.0.",
            "type": "oneui_version", "target_value": 180.0, "icon": "📡👻"
        },
        "oneui_dead_networks_wanderer": {
            "name": "Бродяга По Мёртвым Сетям", "description": "Достичь версии OneUI 200.0.",
            "type": "oneui_version", "target_value": 200.0, "icon": "🚶‍♂️🕸️"
        },
        "oneui_destructive_code_emperor": {
            "name": "Император Деструктивного Кода", "description": "Достичь версии OneUI 250.0.",
            "type": "oneui_version", "target_value": 250.0, "icon": "皇帝💣"
        },
        "oneui_digital_void_absolute": {
            "name": "Абсолют Цифровой Пустоши", "description": "Достичь версии OneUI 300.0.",
            "type": "oneui_version", "target_value": 300.0, "icon": "🖤🌌"
        },
        "oneui_glitch_reality_titan": {
            "name": "Титан Глючной Реальности", "description": "Достичь версии OneUI 400.0.",
            "type": "oneui_version", "target_value": 400.0, "icon": "🗿👾"
        },
        "oneui_virtual_world_destroyer": {
            "name": "Разрушитель Виртуальных Миров", "description": "Достичь версии OneUI 500.0.",
            "type": "oneui_version", "target_value": 500.0, "icon": "🌍💥"
        },
        "oneui_digital_apocalypse_harbinger": {
            "name": "Предвестник Цифрового Апокалипсиса", "description": "Достичь версии OneUI 750.0.",
            "type": "oneui_version", "target_value": 750.0, "icon": "🐎💀"
        },
        "oneui_broken_protocol_king": {
            "name": "Король Сломанных Протоколов", "description": "Достичь версии OneUI 1000.0.",
            "type": "oneui_version", "target_value": 1000.0, "icon": "👑💔"
        },
        "oneui_information_collapse_absolute": {
            "name": "Абсолют Информационного Коллапса", "description": "Достичь версии OneUI 1250.0.",
            "type": "oneui_version", "target_value": 1250.0, "icon": "☢️🌪️"
        },
        "oneui_unified_glitch_consciousness": {
            "name": "Единое Сознание Глюков", "description": "Достичь версии OneUI 1500.0.",
            "type": "oneui_version", "target_value": 1500.0, "icon": "🧠👾"
        },
        "oneui_eternal_code_demon": {
            "name": "Вечный Демон Кода", "description": "Достичь версии OneUI 1750.0.",
            "type": "oneui_version", "target_value": 1750.0, "icon": "😈💻"
        },
        "oneui_anarchy_source": {
            "name": "Источник Анархии в OneUI", "description": "Достичь версии OneUI 2000.0.",
            "type": "oneui_version", "target_value": 2000.0, "icon": "Ⓐ🔥"
        },
        "oneui_destroyer_superconsciousness": {
            "name": "Сверхсознание Разрушителя", "description": "Достичь максимальной версии OneUI (например, 2500.0+).",
            "type": "oneui_version", "target_value": 2500.0, "icon": "🧠💥" # Предполагаем, что 2500.0 - это максимальное
        },

        # Финансовые Успехи
        "financial_first_hidden_cash": {
            "name": "Первый Скрытый Нал", "description": "Заработать свой первый OneCoin.",
            "type": "onecoin_balance", "target_value": 1, "icon": "💸"
        },
        "financial_dirty_tens_handful": {
            "name": "Горсть Грязных Десяток", "description": "Накопить 100 OneCoin на основном балансе.",
            "type": "onecoin_balance", "target_value": 100, "icon": "💰"
        },
        "financial_rusty_coins_stream": {
            "name": "Ручеёк Ржавых Монет", "description": "Накопить 500 OneCoin на основном балансе.",
            "type": "onecoin_balance", "target_value": 500, "icon": "💧🪙"
        },
        "financial_silver_waste_flow": {
            "name": "Поток Серебряных Отходов", "description": "Накопить 1,000 OneCoin на основном балансе.",
            "type": "onecoin_balance", "target_value": 1000, "icon": "🥈🌊"
        },
        "financial_outskirts_peddler": {
            "name": "Мелкий Барыга Окраин", "description": "Накопить 5,000 OneCoin на основном балансе.",
            "type": "onecoin_balance", "target_value": 5000, "icon": "🤫💵"
        },
        "financial_secret_accounts_holder": {
            "name": "Держатель Тайных Счетов", "description": "Накопить 10,000 OneCoin на основном балансе.",
            "type": "onecoin_balance", "target_value": 10000, "icon": "💼🔒"
        },
        "financial_forgotten_stashes_treasurer": {
            "name": "Казначей Забытых Схронов", "description": "Накопить 50,000 OneCoin на основном балансе.",
            "type": "onecoin_balance", "target_value": 50000, "icon": "🗝️💰"
        },
        "financial_black_turnover_controller": {
            "name": "Контролёр Чёрного Оборота", "description": "Накопить 100,000 OneCoin на основном балансе.",
            "type": "onecoin_balance", "target_value": 100000, "icon": "👁️‍🗨️"
        },
        "financial_crypto_million_thief": {
            "name": "Крипто-Вор Миллионов", "description": "Накопить 1,000,000 OneCoin на основном балансе.",
            "type": "onecoin_balance", "target_value": 1_000_000, "icon": "₿👻"
        },
        "financial_past_souls_trader": {
            "name": "Торговец Душами Прошлого", "description": "Накопить 10,000,000 OneCoin на основном балансе.",
            "type": "onecoin_balance", "target_value": 10_000_000, "icon": "⏳💲"
        },
        "financial_deep_market_kraken": {
            "name": "Спрут Глубинного Рынка", "description": "Накопить 100,000,000 OneCoin на основном балансе.",
            "type": "onecoin_balance", "target_value": 100_000_000, "icon": "🐙💰"
        },
        "financial_chaos_lord_absolute": {
            "name": "Абсолют Властелина Хаоса", "description": "Накопить 1,000,000,000 OneCoin.",
            "type": "onecoin_balance", "target_value": 1_000_000_000, "icon": "👑🌪️"
        },
        "financial_quantum_crypt_necromancer": {
            "name": "Квантовый Некромант Крипты", "description": "Накопить 100,000,000,000 OneCoin.",
            "type": "onecoin_balance", "target_value": 100_000_000_000, "icon": "⚛️💀"
        },
        "financial_cosmic_code_defiler_capital": {
            "name": "Осквернитель Космического Кода (Капитал)", "description": "Накопить 1,000,000,000,000 OneCoin.",
            "type": "onecoin_balance", "target_value": 1_000_000_000_000, "icon": "🌌💸"
        },

        # Достижения Стриков
        "streak_resistance_rhythm": {
            "name": "Ритм Сопротивления", "description": "Завершить ежедневный стрик в 3 дня.",
            "type": "daily_streak", "target_value": 3, "icon": "🥁✊"
        },
        "streak_disobedience_echo": {
            "name": "Эхо Непокорности", "description": "Завершить ежедневный стрик в 7 дней.",
            "type": "daily_streak", "target_value": 7, "icon": "🗣️🚫"
        },
        "streak_guerrilla_dance": {
            "name": "Танец Партизана", "description": "Завершить ежедневный стрик в 14 дней.",
            "type": "daily_streak", "target_value": 14, "icon": "💃🕺"
        },
        "streak_steel_rod": {
            "name": "Стальной Стержень", "description": "Завершить ежедневный стрик в 21 день.",
            "type": "daily_streak", "target_value": 21, "icon": "💪⚙️"
        },
        "streak_curfew_ignoring": {
            "name": "Комендантский Час Игнорирования", "description": "Завершить ежедневный стрик в 30 дней.",
            "type": "daily_streak", "target_value": 30, "icon": "🌃🚶"
        },
        "streak_forbidden_paths_navigator": {
            "name": "Навигатор По Запрещённым Тропам", "description": "Завершить ежедневный стрик в 45 дней.",
            "type": "daily_streak", "target_value": 45, "icon": "🧭🚫"
        },
        "streak_double_life_master": {
            "name": "Мастер Двойной Жизни", "description": "Завершить ежедневный стрик в 60 дней.",
            "type": "daily_streak", "target_value": 60, "icon": "🎭🤫"
        },
        "streak_unbending_chrono_rebel": {
            "name": "Несгибаемый Хроно-Бунтарь", "description": "Завершить ежедневный стрик в 90 дней.",
            "type": "daily_streak", "target_value": 90, "icon": "🕰️🔥"
        },
        "streak_chaos_bastion": {
            "name": "Бастион Хаоса", "description": "Завершить ежедневный стрик в 120 дней.",
            "type": "daily_streak", "target_value": 120, "icon": "🏰🌪️"
        },
        "streak_decay_seeds": {
            "name": "Семена Разложения", "description": "Завершить ежедневный стрик в 150 дней.",
            "type": "daily_streak", "target_value": 150, "icon": "🌱💀"
        },
        "streak_freedom_horizon": {
            "name": "Горизонт Свободы", "description": "Завершить ежедневный стрик в 180 дней.",
            "type": "daily_streak", "target_value": 180, "icon": "🌅🕊️"
        },
        "streak_rebellious_spirit_might": {
            "name": "Мощь Мятежного Духа", "description": "Завершить ежедневный стрик в 240 дней.",
            "type": "daily_streak", "target_value": 240, "icon": "💥👻"
        },
        "streak_shadow_account_champion": {
            "name": "Чемпион Теневого Счёта", "description": "Достичь 300 дней стрика.",
            "type": "daily_streak", "target_value": 300, "icon": "🏆🕵️"
        },
        "streak_impending_chaos_harbinger": {
            "name": "Предвестник Грядущего Хаоса", "description": "Достичь 330 дней стрика.",
            "type": "daily_streak", "target_value": 330, "icon": "🌪️" # Убрал "herald", т.к. нет эмодзи
        },
        "streak_eternal_system_defiler": {
            "name": "Вечный Осквернитель Систем", "description": "Достичь 365 дней стрика.",
            "type": "daily_streak", "target_value": 365, "icon": "♾️☢️"
        },

        # Телефонные Достижения
        "phone_first_trophy": {
            "name": "Твой Первый Трофей", "description": "Купить свой первый телефон.",
            "type": "phone_owned_total", "target_value": 1, "icon": "📱🎁"
        },
        "phone_chains_liberator": {
            "name": "Избавитель От Оков", "description": "Продать свой первый телефон.",
            "type": "phone_sold_total", "target_value": 1, "icon": "⛓️‍️➡️"
        },
        "phone_adapt_arsenal": {
            "name": "Арсенал Приспособленца", "description": "Владеть максимальным количеством телефонов (2).",
            "type": "phone_owned_max_current", "target_value": 2, "icon": "🛠️📱📱"
        },
        "phone_rusted_a_collector": {
            "name": "Коллекционер Ржавых А", "description": "Приобрести (когда-либо) 5 разных моделей A-серии.",
            "type": "phone_series_collected_A", "target_value": 5, "icon": "📱🗑️"
        },
        "phone_lost_s_keeper": {
            "name": "Хранитель Утерянных S-серий", "description": "Приобрести (когда-либо) 5 разных моделей S-серии.",
            "type": "phone_series_collected_S", "target_value": 5, "icon": "📱🗝️"
        },
        "phone_bend_reality_z_lord": {
            "name": "Властелин Сгибаемой Реальности Z", "description": "Приобрести (когда-либо) 5 разных моделей Z-серии.",
            "type": "phone_series_collected_Z", "target_value": 5, "icon": "📱🌀"
        },
        "phone_mind_expander_memory": {
            "name": "Расширитель Сознания (Памяти)", "description": "Улучшить память телефона до 1TB.",
            "type": "phone_memory_upgrade_target", "target_value": 1024, "icon": "🧠💾" # 1TB = 1024GB
        },
        "phone_boundless_intellect": {
            "name": "Безграничный Разум", "description": "Улучшить память телефона до 2TB (максимум).",
            "type": "phone_memory_upgrade_target", "target_value": 2048, "icon": "♾️💾" # 2TB = 2048GB
        },
        "phone_phoenix_engineering": {
            "name": "Феникс Из Пепла Инженерии", "description": "Успешно починить 5 сломанных телефонов.",
            "type": "phone_repaired_total", "target_value": 5, "icon": "🐦‍🔥🔧"
        },
        "phone_dead_mechanisms_healer": {
            "name": "Целитель Мёртвых Механизмов", "description": "Успешно починить 10 сломанных телефонов.",
            "type": "phone_repaired_total", "target_value": 10, "icon": "🩺⚙️"
        },
        "phone_energy_vampire": {
            "name": "Энергетический Вампир", "description": "Зарядить свой телефон 10 раз.",
            "type": "phone_charged_total", "target_value": 10, "icon": "🧛🔋"
        },
        "phone_black_energy_conductor": {
            "name": "Проводник Чёрной Энергии", "description": "Зарядить свой телефон 50 раз.",
            "type": "phone_charged_total", "target_value": 50, "icon": "🔌🌑"
        },
        "phone_shadow_pact": {
            "name": "Договор С Тенью", "description": "Впервые застраховать свой телефон.",
            "type": "phone_insured_first", "target_value": True, "icon": "🤝📜"
        },
        "phone_renegade_invincible_fleet": {
            "name": "Неуязвимый Флот Отступника", "description": "Застраховать оба своих телефона.",
            "type": "phone_insured_all_current", "target_value": 2, "icon": "🛡️📱📱"
        },
        "phone_underground_schemes_alchemist": {
            "name": "Алхимик Подпольных Схем", "description": "Починить телефон, используя компонент, купленный на Черном Рынке.",
            "type": "phone_repaired_with_bm_component", "target_value": True, "icon": "⚗️⚙️"
        },
        "phone_hell_blacksmith": {
            "name": "Кузнец Самодельного Ада", "description": "Впервые успешно собрать телефон с помощью команды `/craftphone`.",
            "type": "phone_crafted_first", "target_value": True, "icon": "🔨🔥"
        },
        "phone_artificial_life_creator": {
            "name": "Творец Искусственных Жизней", "description": "Собрать все типы телефонов (A, S, Z серии) с помощью команды `/craftphone`).",
            "type": "phone_crafted_all_series", "target_value": ["A", "S", "Z"], "icon": "🤖🧬"
        }, # target_value будет списком серий, для проверки понадобится Set.
        "phone_sabotage_master": {
            "name": "Мастер Саботажа", "description": "Собрать 3 телефона с помощью команды `/craftphone`.",
            "type": "phone_crafted_total", "target_value": 3, "icon": "😈🛠️"
        },
        "phone_rise_from_ashes": {
            "name": "Восставший из Пепла (Телефон)", "description": "Починить телефон после того, как он полностью сломался из-за разрядки батареи.",
            "type": "phone_repaired_battery_breakdown", "target_value": True, "icon": "🔋💀"
        },

        # Рыночные Достижения
        "market_first_step_in_dirt": {
            "name": "Первый Шаг В Грязь", "description": "Купить любой товар на рынке (/market).",
            "type": "market_buy_first", "target_value": True, "icon": "👣💸"
        },
        "market_outskirts_supplier": {
            "name": "Поставщик Окраин", "description": "Совершить 10 покупок на рынке.",
            "type": "market_buy_total", "target_value": 10, "icon": "📦🏘️"
        },
        "market_forgotten_souls_trader": {
            "name": "Торговец Забытыми Душами", "description": "Потратить 10,000 OneCoin на рынке.",
            "type": "market_spend_total", "target_value": 10000, "icon": "👻💰"
        },
        "market_cashing_master": {
            "name": "Мастер Обналичивания", "description": "Продать 10 предметов на рынке.",
            "type": "market_sell_total", "target_value": 10, "icon": "💵✨"
        },
        "market_whisper_from_darkness": {
            "name": "Шепот Из Тьмы", "description": "Впервые купить товар на Черном Рынке.",
            "type": "bm_buy_first", "target_value": True, "icon": "🤫🌑"
        },
        "market_forbidden_tech_hunter": {
            "name": "Охотник за Запрещенными Технологиями", "description": "Купить 3 'краденых' телефона на Черном Рынке.",
            "type": "bm_buy_stolen_phone", "target_value": 3, "icon": "🏹🚫"
        },
        "market_unexplored_artifacts_lord": {
            "name": "Властелин Неизведанных Артефактов", "description": "Купить 3 эксклюзивных телефона на Черном Рынке.",
            "type": "bm_buy_exclusive_phone", "target_value": 3, "icon": "👑✨"
        },
        "market_providence_agent": {
            "name": "Агент Провидения", "description": "Купить компонент на Черном Рынке, который оказался небракованным.",
            "type": "bm_buy_component_not_defective", "target_value": True, "icon": "🕵️‍♂️🔮"
        },
        "market_shadow_deals_master": {
            "name": "Мастер Теневых Сделок", "description": "Продать выигранный телефон боту за высокую цену (например, > 1000 OneCoin).",
            "type": "roulette_won_phone_sell_high", "target_value": 1000, "icon": "🤝💸"
        },
        "market_profitable_exchange_strategist": {
            "name": "Стратег Выгодного Обмена", "description": "Обменять выигранный телефон на старый, продав старый за максимальную цену.",
            "type": "roulette_won_phone_exchange_old", "target_value": True, "icon": "♻️🧠"
        },
        "market_lost_sanctuaries_seeker": {
            "name": "Искатель Потерянных Святынь", "description": "Впервые найти и купить редкий винтажный телефон на Черном Рынке.",
            "type": "bm_buy_vintage_phone", "target_value": True, "icon": "🔍 relic" # Эмодзи "relic" нет, оставил текст
        },
        "market_deep_defect_analyst": {
            "name": "Аналитик Глубинных Дефектов", "description": "Купить бракованный компонент на Черном Рынке.",
            "type": "bm_buy_component_defective", "target_value": True, "icon": "🔬💔"
        },
        "market_loyal_supplier": {
            "name": "Верный Поставщик", "description": "Купить 10 предметов на Черном Рынке.",
            "type": "bm_buy_total", "target_value": 10, "icon": "🤝📦"
        },
        "market_contraband_collector": {
            "name": "Сборщик Контрабанды", "description": "Купить 5 компонентов с Черного Рынка.",
            "type": "bm_buy_components_total", "target_value": 5, "icon": "📦🤫"
        },
        "market_dark_side_trader": {
            "name": "Торговец Темной Стороны", "description": "Купить чехол с Черного Рынка.",
            "type": "bm_buy_case_first", "target_value": True, "icon": "😈👜"
        },

        # Бонусные Достижения
        "bonus_impossibility_attraction": {
            "name": "Притяжение Невозможности", "description": "Впервые получить бонус-множитель x2.0 или выше.",
            "type": "bonus_multiplier_high", "target_value": 2.0, "icon": "✨🌌"
        },
        "bonus_chains_of_misfortune": {
            "name": "Оковы Неудачи", "description": "Впервые получить отрицательный бонус-множитель (например, x-0.5).",
            "type": "bonus_multiplier_negative", "target_value": -0.5, "icon": "⛓️‍️👎"
        },
        "bonus_chaos_wheel_tamer": {
            "name": "Укротитель Колеса Хаоса", "description": "Сыграть в рулетку 10 раз.",
            "type": "roulette_spins_total", "target_value": 10, "icon": "🎲🌀"
        },
        "bonus_gambler_hostage": {
            "name": "Заложник Азарта", "description": "Сыграть в рулетку 50 раз.",
            "type": "roulette_spins_total", "target_value": 50, "icon": "🎰😈"
        },
        "bonus_anarchy_heart_jackpot": {
            "name": "Сердце Анархии (Джекпот)", "description": "Впервые выиграть телефон в рулетке.",
            "type": "roulette_win_phone_first", "target_value": True, "icon": "💖Ⓐ"
        },
        "bonus_chaos_abundance_caller": {
            "name": "Призыватель Изобилия Хаоса", "description": "Выиграть 3 телефона в рулетке.",
            "type": "roulette_win_phone_total", "target_value": 3, "icon": "🔮💰"
        },
        "bonus_destruction_catalyst": {
            "name": "Катализатор Разрушения", "description": "Впервые использовать буст от рулетки на множитель OneUI.",
            "type": "roulette_use_multiplier_boost_first", "target_value": True, "icon": "💥🧪"
        },
        "bonus_distortion_shield": {
            "name": "Щит Искажения", "description": "Впервые использовать заряд защиты от отрицательного изменения OneUI.",
            "type": "roulette_use_negative_protection_first", "target_value": True, "icon": "🛡️🌀"
        },
        "bonus_loyal_servant_chance": {
            "name": "Верный Слуга Случая", "description": "Получить 5 дополнительных попыток /bonus.",
            "type": "bonus_extra_attempts_total", "target_value": 5, "icon": "🎲🤝"
        },
        "bonus_impending_changes_harbinger": {
            "name": "Предвестник Грядущих Перемен", "description": "Получить 5 дополнительных попыток /oneui.",
            "type": "oneui_extra_attempts_total", "target_value": 5, "icon": "🌬️🔮"
        },
        "bonus_wind_of_change": {
            "name": "Ветер Перемен", "description": "Достичь бонус-множителя х0.0.",
            "type": "bonus_multiplier_zero", "target_value": 0.0, "icon": "💨"
        },
        "bonus_fortune_curse": {
            "name": "Проклятие Фортуны", "description": "Достичь бонус-множителя ниже -1.0.",
            "type": "bonus_multiplier_very_negative", "target_value": -1.0, "icon": "💀🎲"
        },

        # Семейные Достижения
        "family_clan_embryo": {
            "name": "Зародыш Клана", "description": "Создать свою первую семью.",
            "type": "family_create_first", "target_value": True, "icon": "🌱👥"
        },
        "family_loyal_acolyte": {
            "name": "Верный Послушник", "description": "Вступить в семью.",
            "type": "family_join_first", "target_value": True, "icon": "🤝🤫"
        },
        "family_free_peoples_chieftain": {
            "name": "Вождь Свободных Народов", "description": "Быть лидером семьи, состоящей из 5 или более участников.",
            "type": "family_leader_members_count", "target_value": 5, "icon": "🏛️✊"
        },
        "family_clan_heritage": {
            "name": "Наследие Клана", "description": "Достичь 10 активных членов в семье.",
            "type": "family_total_members_count", "target_value": 10, "icon": "📜👪"
        },
        "family_renegade_caller": {
            "name": "Призыватель Отступников", "description": "Пригласить 5 уникальных пользователей в свою семью.",
            "type": "family_invite_total", "target_value": 5, "icon": "📣🚶‍♂️"
        },
        "family_rebellion_collective_mind": {
            "name": "Коллективный Разум Бунта", "description": "Сделать вклад в семейное соревнование.",
            "type": "family_competition_contribute_first", "target_value": True, "icon": "🧠💥"
        },
        "family_voice_of_chaos": {
            "name": "Голос Хаоса", "description": "Впервые переименовать семью.",
            "type": "family_rename_first", "target_value": True, "icon": "🗣️🌪️"
        },
        "family_alliance_architect": {
            "name": "Архитектор Альянсов", "description": "Вступить в семью, которая участвует в соревновании.",
            "type": "family_join_active_competition", "target_value": True, "icon": "🤝🌐"
        },
        "family_system_traitor": {
            "name": "Предатель Системы", "description": "Впервые покинуть семью.",
            "type": "family_leave_first", "target_value": True, "icon": "💔⛓️"
        },
        "family_exclusion_from_circle": {
            "name": "Исключение из Круга", "description": "Впервые быть изгнанным из семьи.",
            "type": "family_kicked_first", "target_value": True, "icon": "🚫🚪"
        },

        # Бизнес Достижения
        "business_empire_seed": {
            "name": "Зерно Империи", "description": "Купить свой первый бизнес.",
            "type": "business_buy_first", "target_value": True, "icon": "🌳💰"
        },
        "business_influence_builder": {
            "name": "Строитель Влияния", "description": "Владеть 2 бизнесами в одном чате.",
            "type": "business_owned_max_current", "target_value": 2, "icon": "🏗️👁️‍🗨️"
        },
        "business_progress_alchemist": {
            "name": "Алхимик Прогресса", "description": "Улучшить любой бизнес до максимального уровня (Уровень 3).",
            "type": "business_upgrade_to_max_level_first", "target_value": True, "icon": "⚗️📈"
        },
        "business_legion_master": {
            "name": "Мастер Легионов", "description": "Нанять максимальное количество сотрудников для одного бизнеса.",
            "type": "business_hire_max_staff_first", "target_value": True, "icon": "👥⚔️"
        },
        "business_underworld_seer": {
            "name": "Провидец Подпольного Мира", "description": "Нанять 50 сотрудников суммарно во всех бизнесах.",
            "type": "business_total_staff_hired", "target_value": 50, "icon": "🔮🌍"
        },
        "business_hidden_account_keeper": {
            "name": "Хранитель Скрытого Счёта", "description": "Улучшить свой банк до уровня 1.",
            "type": "bank_upgrade_level", "target_value": 1, "icon": "🤫🏦"
        },
        "business_wealth_stronghold": {
            "name": "Оплот Богатства", "description": "Улучшить свой банк до уровня 5.",
            "type": "bank_upgrade_level", "target_value": 5, "icon": "💪💰"
        },
        "business_secret_vault": {
            "name": "Тайное Хранилище", "description": "Улучшить свой банк до уровня 10.",
            "type": "bank_upgrade_level", "target_value": 10, "icon": "🔒💎"
        },
        "business_chaos_financial_flow_lord": {
            "name": "Властелин Финансовых Потоков Хаоса", "description": "Улучшить свой банк до максимального уровня (Уровень 30).",
            "type": "bank_upgrade_level", "target_value": 30, "icon": "👑💸"
        },
        "business_sabotage_engineer": {
            "name": "Инженер Саботажа", "description": "Купить 3 различных апгрейда для бизнесов.",
            "type": "business_buy_upgrades_total", "target_value": 3, "icon": "🔧😈"
        },
        "business_shadow_assets_absolute_defender": {
            "name": "Абсолютный Защитник Теневых Активов", "description": "Купить все доступные типы апгрейдов для одного бизнеса.",
            "type": "business_buy_all_upgrades_for_one", "target_value": True, "icon": "🛡️🖤"
        }, # Для этого нужно будет знать, сколько апгрейдов доступно для конкретного бизнеса.
        "business_apocalypse_seer": {
            "name": "Провидец Апокалипсиса", "description": "Успешно предотвратить 5 негативных событий благодаря апгрейдам.",
            "type": "business_prevent_negative_events", "target_value": 5, "icon": "🔮💥"
        },
        "business_economic_anarchist": {
            "name": "Экономический Анархист", "description": "Заработать 1,000,000 OneCoin с бизнесов (общий доход).",
            "type": "business_total_income_earned", "target_value": 1_000_000, "icon": "Ⓐ📈"
        },
        "business_waste_lord": {
            "name": "Повелитель Мусора", "description": "Владеть бизнесом 'Пункт Утилизации' и улучшить его до уровня 3.",
            "type": "business_specific_max_level", "target_key": "business_4_eco_recycling_samsung", "target_value": 3, "icon": "🗑️👑"
        },
        "business_interstellar_contraband_controller": {
            "name": "Межзвездный Контролёр Контрабанды", "description": "Владеть бизнесом 'Межзвездная Добыча Ресурсов' и улучшить его до уровня 3.",
            "type": "business_specific_max_level", "target_key": "business_16_interstellar_resource_extraction", "target_value": 3, "icon": "🌌📦"
        },
        "business_multiverse_chaos_absolute": {
            "name": "Абсолют Мультивселенной Хаоса", "description": "Владеть бизнесом 'Властелины Мультивселенной' и улучшить его до уровня 3.",
            "type": "business_specific_max_level", "target_key": "business_18_samsung_multiverse_masters", "target_value": 3, "icon": "🤯🌌"
        },
        "business_asset_collector": {
            "name": "Коллекционер Активов", "description": "Владеть всеми доступными бизнесами (все 18).",
            "type": "business_owned_all", "target_value": 18, "icon": "💎📦"
        },

        # Достижения Соревнований
        "competition_arena_gladiator": {
            "name": "Гладиатор Арены", "description": "Сделать вклад в семейное соревнование (впервые).",
            "type": "competition_contribute_first", "target_value": True, "icon": "⚔️🏟️"
        },
        "competition_freedom_warrior": {
            "name": "Воин Свободы", "description": "Сделать вклад в 3 семейных соревнования.",
            "type": "competition_contribute_total", "target_value": 3, "icon": "⛓️‍️✊"
        },
        "competition_madness_triumpher": {
            "name": "Триумфатор Безумия", "description": "Быть членом семьи, которая заняла 1-е место в соревновании.",
            "type": "competition_win_first", "target_value": True, "icon": "🏆🤪"
        },
        "competition_battlefield_legend": {
            "name": "Легенда Поля Битвы", "description": "Быть членом семьи, которая выиграла 3 соревнования.",
            "type": "competition_win_total", "target_value": 3, "icon": "⚔️🌟"
        },

        # Взаимодействие с Ботом (Особые Отметки) - "Секретные"
        "bot_observer": {
            "name": "Наблюдатель", "description": "Впервые отправить команду боту не из своего чата.",
            "type": "bot_command_foreign_chat", "target_value": True, "icon": "🕵️‍♀️"
        },
        "bot_negotiator": {
            "name": "Переговорщик", "description": "Впервые ответить на сообщение бота.",
            "type": "bot_reply_to_bot_first", "target_value": True, "icon": "💬"
        },
        "bot_quiet_one": {
            "name": "Тихоня", "description": "Использовать команду /help.",
            "type": "bot_use_help_first", "target_value": True, "icon": "🤫"
        },

        # "Секретные" и Исследовательские Достижения
        "secret_protocol_breaker": {
            "name": "Нарушитель Протоколов", "description": "Достичь отрицательной версии OneUI.",
            "type": "oneui_version_negative", "target_value": -0.1, "icon": "🚫"
        },
        "secret_degradation_adept": {
            "name": "Адепт Деградации", "description": "Достичь версии OneUI -10.0.",
            "type": "oneui_version_negative_threshold", "target_value": -10.0, "icon": "📉"
        },
        "secret_black_hole_oneui": {
            "name": "Чёрная Дыра (OneUI)", "description": "Достичь версии OneUI -15.0.",
            "type": "oneui_version_negative_threshold", "target_value": -15, "icon": "⚫"
        },
        "secret_echo_of_void": {
            "name": "Эхо Пустоты", "description": "Применить множитель x0.0 к OneUI.",
            "type": "bonus_multiplier_zero_applied", "target_value": True, "icon": "🕳️"
        },
        "secret_battery_curse": {
            "name": "Проклятие Батареи", "description": "Допустить поломку аккумулятора из-за полной разрядки.",
            "type": "phone_battery_breakdown_due_to_drain", "target_value": True, "icon": "⚡️💀"
        },
        "secret_master_defect": {
            "name": "Мастер Брак", "description": "Купить 3 бракованных компонента на ЧР.",
            "type": "bm_buy_defective_component_total", "target_value": 3, "icon": "💔🛠️"
        },
        "secret_defect_collector": {
            "name": "Коллекционер Дефектов", "description": "Купить телефон с косметическим дефектом на ЧР.",
            "type": "bm_buy_phone_cosmetic_defect", "target_value": True, "icon": "📱🩹"
        },
        "secret_unreliable_supplier": {
            "name": "Ненадежный Поставщик", "description": "Купить телефон с измененным цветом на ЧР (из-за 'сюрприза от продавца').",
            "type": "bm_buy_phone_wrong_color", "target_value": True, "icon": "🌈🤫"
        },
    }    
