# item_data.py


# Телефонные компоненты (детали)
# Цены рассчитаны так, чтобы сумма 5 компонентов серии составляла ~80%
# от базовой цены серии (A: 250, S: 700, Z: 1420).
PHONE_COMPONENTS = {
    # A-серия (сумма = 200)
    "SCREEN_A":  {"name": "Экран A-серии", "price": 68, "series": "A", "component_type": "component"},
    "BATTERY_A": {"name": "Батарея A-серии", "price": 51, "series": "A", "component_type": "component"},
    "CPU_A":     {"name": "Процессор A-серии", "price": 34, "series": "A", "component_type": "component"},
    "BOARD_A":   {"name": "Плата A-серии", "price": 30, "series": "A", "component_type": "component"},
    "BODY_A":    {"name": "Корпус A-серии", "price": 17, "series": "A", "component_type": "component"},

    # S-серия (сумма = 560)
    "SCREEN_S":  {"name": "Экран S-серии", "price": 190, "series": "S", "component_type": "component"},
    "BATTERY_S": {"name": "Батарея S-серии", "price": 142, "series": "S", "component_type": "component"},
    "CPU_S":     {"name": "Процессор S-серии", "price": 95, "series": "S", "component_type": "component"},
    "BOARD_S":   {"name": "Плата S-серии", "price": 85, "series": "S", "component_type": "component"},
    "BODY_S":    {"name": "Корпус S-серии", "price": 48, "series": "S", "component_type": "component"},

    # Z-серия (сумма = 1136)
    "SCREEN_Z":  {"name": "Экран Z-серии", "price": 385, "series": "Z", "component_type": "component"},
    "BATTERY_Z": {"name": "Батарея Z-серии", "price": 289, "series": "Z", "component_type": "component"},
    "CPU_Z":     {"name": "Процессор Z-серии", "price": 192, "series": "Z", "component_type": "component"},
    "BOARD_Z":   {"name": "Плата Z-серии", "price": 174, "series": "Z", "component_type": "component"},
    "BODY_Z":    {"name": "Корпус Z-серии", "price": 96, "series": "Z", "component_type": "component"},

    # Модуль памяти (универсальный)
    "MEMORY_MODULE_50GB": {"name": "Модуль памяти +50GB", "price": 70, "series": None, "component_type": "memory_module", "memory_gb": 50}
}

# Ключи типов компонентов, которые нужны для сборки телефона
# и могут сломаться
CORE_PHONE_COMPONENT_TYPES = ["screen", "cpu", "battery", "board", "body"]


# Чехлы для телефонов
PHONE_CASES = {
    # Ключ: {"name": "Название (Серия)", "price": Цена, "series": "A/S/Z", "break_chance_reduction_percent": %, "другие_бонусы": значение}
    
    "CASE_A_ULTRA_SLIM": {"name": "Ультра-тонкий чехол (A-серия)", "price": 10, "series": "A", "break_chance_reduction_percent": 1},
    "CASE_S_ULTRA_SLIM": {"name": "Ультра-тонкий чехол (S-серия)", "price": 20, "series": "S", "break_chance_reduction_percent": 1},
    "CASE_Z_ULTRA_SLIM": {"name": "Ультра-тонкий чехол (Z-серия)", "price": 30, "series": "Z", "break_chance_reduction_percent": 1},

    "CASE_A_LEATHER_ELEGANT": {"name": "Элегантный кожаный чехол (A-серия)", "price": 45, "series": "A", "break_chance_reduction_percent": 2, "bonus_roulette_luck_percent": 1.0},
    "CASE_S_LEATHER_ELEGANT": {"name": "Элегантный кожаный чехол (S-серия)", "price": 70, "series": "S", "break_chance_reduction_percent": 2, "bonus_roulette_luck_percent": 1.0},
    "CASE_Z_LEATHER_ELEGANT": {"name": "Элегантный кожаный чехол (Z-серия)", "price": 95, "series": "Z", "break_chance_reduction_percent": 2, "bonus_roulette_luck_percent": 1.0},

    "CASE_A_SIMPLE":  {"name": "Простой силиконовый чехол (A-серия)", "price": 15, "series": "A", "break_chance_reduction_percent": 3},
    "CASE_S_SIMPLE":  {"name": "Простой силиконовый чехол (S-серия)", "price": 25, "series": "S", "break_chance_reduction_percent": 3},
    "CASE_Z_SIMPLE":  {"name": "Простой силиконовый чехол (Z-серия)", "price": 35, "series": "Z", "break_chance_reduction_percent": 3},

    "CASE_A_ECO_NATURE": {"name": "Эко-чехол 'Природа' (A-серия)", "price": 25, "series": "A", "break_chance_reduction_percent": 4, "market_discount_percent": 1.0},
    "CASE_S_ECO_NATURE": {"name": "Эко-чехол 'Природа' (S-серия)", "price": 35, "series": "S", "break_chance_reduction_percent": 4, "market_discount_percent": 1.0},
    "CASE_Z_ECO_NATURE": {"name": "Эко-чехол 'Природа' (Z-серия)", "price": 50, "series": "Z", "break_chance_reduction_percent": 4, "market_discount_percent": 1.0},

    "CASE_A_KAWAII_3D": {"name": "Силиконовый 3D 'Кавай' (A-серия)", "price": 22, "series": "A", "break_chance_reduction_percent": 4},
    "CASE_S_KAWAII_3D": {"name": "Силиконовый 3D 'Кавай' (S-серия)", "price": 30, "series": "S", "break_chance_reduction_percent": 4},
    "CASE_Z_KAWAII_3D": {"name": "Силиконовый 3D 'Кавай' (Z-серия)", "price": 50, "series": "Z", "break_chance_reduction_percent": 4},

    "CASE_A_ART_COLLAGE": {"name": "Чехол 'Арт-коллаж' (A-серия)", "price": 28, "series": "A", "break_chance_reduction_percent": 5},
    "CASE_S_ART_COLLAGE": {"name": "Чехол 'Арт-коллаж' (S-серия)", "price": 45, "series": "S", "break_chance_reduction_percent": 5},
    "CASE_Z_ART_COLLAGE": {"name": "Чехол 'Арт-коллаж' (Z-серия)", "price": 65, "series": "Z", "break_chance_reduction_percent": 5},
    
    "CASE_A_BOOKLET": {"name": "Чехол-книжка (A-серия)", "price": 25, "series": "A", "break_chance_reduction_percent": 5},
    "CASE_S_BOOKLET": {"name": "Чехол-книжка (S-серия)", "price": 40, "series": "S", "break_chance_reduction_percent": 5},
    "CASE_Z_BOOKLET": {"name": "Чехол-книжка (Z-серия)", "price": 60, "series": "Z", "break_chance_reduction_percent": 5},

    "CASE_A_GAMER_PRO": {"name": "Чехол 'Геймерский PRO' (A-серия)", "price": 50, "series": "A", "break_chance_reduction_percent": 6, "oneui_version_bonus_percent": 5},
    "CASE_S_GAMER_PRO": {"name": "Чехол 'Геймерский PRO' (S-серия)", "price": 85, "series": "S", "break_chance_reduction_percent": 6, "oneui_version_bonus_percent": 5},
    "CASE_Z_GAMER_PRO": {"name": "Чехол 'Геймерский PRO' (Z-серия)", "price": 115, "series": "Z", "break_chance_reduction_percent": 6, "oneui_version_bonus_percent": 5},

    "CASE_A_NEON_GLOW": {"name": "Светящийся 'Неон' (A-серия)", "price": 33, "series": "A", "break_chance_reduction_percent": 6},
    "CASE_S_NEON_GLOW": {"name": "Светящийся 'Неон' (S-серия)", "price": 55, "series": "S", "break_chance_reduction_percent": 6},
    "CASE_Z_NEON_GLOW": {"name": "Светящийся 'Неон' (Z-серия)", "price": 75, "series": "Z", "break_chance_reduction_percent": 6},

    "CASE_A_CHAMELEON": {"name": "Чехол 'Хамелеон' (A-серия)", "price": 35, "series": "A", "break_chance_reduction_percent": 6},
    "CASE_S_CHAMELEON": {"name": "Чехол 'Хамелеон' (S-серия)", "price": 60, "series": "S", "break_chance_reduction_percent": 6},
    "CASE_Z_CHAMELEON": {"name": "Чехол 'Хамелеон' (Z-серия)", "price": 85, "series": "Z", "break_chance_reduction_percent": 6},

    "CASE_A_BUSINESS_WALLET": {"name": "Чехол-кошелек 'Бизнесмен' (A-серия)", "price": 55, "series": "A", "break_chance_reduction_percent": 7, "onecoin_bonus_percent": 5},
    "CASE_S_BUSINESS_WALLET": {"name": "Чехол-кошелек 'Бизнесмен' (S-серия)", "price": 90, "series": "S", "break_chance_reduction_percent": 7, "onecoin_bonus_percent": 5},
    "CASE_Z_BUSINESS_WALLET": {"name": "Чехол-кошелек 'Бизнесмен' (Z-серия)", "price": 125, "series": "Z", "break_chance_reduction_percent": 7, "onecoin_bonus_percent": 5},

    "CASE_A_STRONG":  {"name": "Усиленный чехол (A-серия)", "price": 30, "series": "A", "break_chance_reduction_percent": 7},
    "CASE_S_STRONG":  {"name": "Усиленный чехол (S-серия)", "price": 50, "series": "S", "break_chance_reduction_percent": 7},
    "CASE_Z_STRONG":  {"name": "Усиленный чехол (Z-серия)", "price": 70, "series": "Z", "break_chance_reduction_percent": 7},
    
    "CASE_A_BATTERY_BOOST_L1": {"name": "Чехол-аккумулятор 'Энерджайзер' (A-серия, +1 день)", "price": 80, "series": "A", "break_chance_reduction_percent": 9, "battery_days_increase": 1},
    "CASE_S_BATTERY_BOOST_L1": {"name": "Чехол-аккумулятор 'Энерджайзер' (S-серия, +1 день)", "price": 120, "series": "S", "break_chance_reduction_percent": 9, "battery_days_increase": 1},
    "CASE_Z_BATTERY_BOOST_L1": {"name": "Чехол-аккумулятор 'Энерджайзер' (Z-серия, +1 день)", "price": 160, "series": "Z", "break_chance_reduction_percent": 9, "battery_days_increase": 1},

    "CASE_A_BATTERY_BOOST_L2": {"name": "Чехол-аккумулятор 'Долгожитель' (A-серия, +2 дня)", "price": 110, "series": "A", "break_chance_reduction_percent": 10, "battery_days_increase": 2},
    "CASE_S_BATTERY_BOOST_L2": {"name": "Чехол-аккумулятор 'Долгожитель' (S-серия, +2 дня)", "price": 170, "series": "S", "break_chance_reduction_percent": 10, "battery_days_increase": 2},
    "CASE_Z_BATTERY_BOOST_L2": {"name": "Чехол-аккумулятор 'Долгожитель' (Z-серия, +2 дня)", "price": 220, "series": "Z", "break_chance_reduction_percent": 10, "battery_days_increase": 2},

    "CASE_A_CRYSTAL_SHOCKPROOF": {"name": "Прозрачный противоударный 'Кристалл' (A-серия)", "price": 40, "series": "A", "break_chance_reduction_percent": 10},
    "CASE_S_CRYSTAL_SHOCKPROOF": {"name": "Прозрачный противоударный 'Кристалл' (S-серия)", "price": 60, "series": "S", "break_chance_reduction_percent": 10},
    "CASE_Z_CRYSTAL_SHOCKPROOF": {"name": "Прозрачный противоударный 'Кристалл' (Z-серия)", "price": 80, "series": "Z", "break_chance_reduction_percent": 10},

    "CASE_A_CARBON_FORMULA": {"name": "Карбоновый чехол 'Формула' (A-серия)", "price": 60, "series": "A", "break_chance_reduction_percent": 14},
    "CASE_S_CARBON_FORMULA": {"name": "Карбоновый чехол 'Формула' (S-серия)", "price": 90, "series": "S", "break_chance_reduction_percent": 14},
    "CASE_Z_CARBON_FORMULA": {"name": "Карбоновый чехол 'Формула' (Z-серия)", "price": 125, "series": "Z", "break_chance_reduction_percent": 14},

    "CASE_A_ARMORED": {"name": "Бронированный чехол (A-серия)", "price": 50, "series": "A", "break_chance_reduction_percent": 12}, # Переместил, чтобы было по порядку защиты
    "CASE_S_ARMORED": {"name": "Бронированный чехол (S-серия)", "price": 80, "series": "S", "break_chance_reduction_percent": 12},
    "CASE_Z_ARMORED": {"name": "Бронированный чехол (Z-серия)", "price": 110, "series": "Z", "break_chance_reduction_percent": 12},
    
    "CASE_A_EXTREME_DEFENSE": {"name": "Экстремальная защита (A-серия)", "price": 70, "series": "A", "break_chance_reduction_percent": 15},
    "CASE_S_EXTREME_DEFENSE": {"name": "Экстремальная защита (S-серия)", "price": 100, "series": "S", "break_chance_reduction_percent": 15},
    "CASE_Z_EXTREME_DEFENSE": {"name": "Экстремальная защита (Z-серия)", "price": 140, "series": "Z", "break_chance_reduction_percent": 15},

    "CASE_A_TITAN_GUARD": {"name": "Военный стандарт 'Титан' (A-серия)", "price": 90, "series": "A", "break_chance_reduction_percent": 20},
    "CASE_S_TITAN_GUARD": {"name": "Военный стандарт 'Титан' (S-серия)", "price": 150, "series": "S", "break_chance_reduction_percent": 20},
    "CASE_Z_TITAN_GUARD": {"name": "Военный стандарт 'Титан' (Z-серия)", "price": 200, "series": "Z", "break_chance_reduction_percent": 20},
}

# Максимальный объем памяти, до которого можно апгрейдить телефон
MAX_PHONE_MEMORY_GB = 2048 # 2TB