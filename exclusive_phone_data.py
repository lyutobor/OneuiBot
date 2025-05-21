# exclusive_phone_data.py

# Список эксклюзивных моделей телефонов для Черного Рынка (ЧР).
# Это либо уникальные, вымышленные версии телефонов известных брендов,
# либо полностью кастомные артефакты.
# Все телефоны здесь по умолчанию is_contraband=True при покупке на ЧР
# и должны иметь память от 512GB и базовую цену от 1200 до 6000.

EXCLUSIVE_PHONE_MODELS = [
    # --- Apple (Серия "I" - iPhone) ---
    {
        "key": "bm_apple_iphone_future_x1",
        "name": "Apple iPhone Future X1 'Провидец'",
        "brand_tag": "Apple", "series": "I", "display_name": "iPhone Future X1",
        "memory": "1TB Предвидения", "base_price": 4500, "release_year": 2030,
        "bm_description": "Прототип iPhone из лаборатории темпоральных исследований Apple. Его экран иногда показывает фрагменты ближайшего будущего... или альтернативных реальностей. Нестабилен.",
        "rarity": "legendary",
        "special_properties": {
            "fixed_color": "Жидкий Металл с Хроматическими Переливами",
            "custom_bonus_description": "Раз в день дает 50% шанс предсказать, будет ли следующее изменение OneUI положительным или отрицательным. Увеличивает шанс на 'системный сбой' на 2%.",
            "predictive_analytics_chance": 0.50,
            "system_glitch_increase_percent": 0.02,
        }, "is_true_exclusive": True,
    },
    {
        "key": "bm_apple_iphone_stealth_ops",
        "name": "Apple iPhone Stealth Ops 'Призрак'",
        "brand_tag": "Apple", "series": "I", "display_name": "iPhone Stealth Ops",
        "memory": "512GB Тишины", "base_price": 3200, "release_year": 2028,
        "bm_description": "Разработан для спецслужб, этот iPhone не оставляет следов и покрыт материалом, поглощающим радарные волны. Идеален для тайных операций... и очень дорог в ремонте.",
        "rarity": "epic",
        "special_properties": {
            "fixed_color": "Матовый Невидимый Черный",
            "custom_bonus_description": "Снижает шанс быть 'пойманным' при 'облавах' на 30% (если механика будет). Компоненты для ремонта этой модели стоят на 50% дороже.",
            "evasion_bonus_percent_if_raids": 0.30,
            "repair_cost_multiplier": 1.5,
        }, "is_true_exclusive": True,
    },
    {
        "key": "bm_apple_iphone_cyborg_custom",
        "name": "Apple iPhone 'Киборг' (Кастом ЧР)",
        "brand_tag": "Apple", "series": "I", "display_name": "iPhone 'Киборг'",
        "memory": "1.5TB Интегрированной Памяти", "base_price": 5800, "release_year": 2029,
        "bm_description": "Жестоко модифицированный iPhone, сросшийся с инопланетными технологиями. Частично органический, он адаптируется к владельцу, усиливая его... или поглощая.",
        "rarity": "mythic",
        "special_properties": {
            "fixed_color": "Биомеханический с Пульсирующими Венами",
            "custom_bonus_description": "Медленно улучшает случайную характеристику одного из других ваших телефонов раз в неделю. Требует ежедневного 'подношения' в 10 OneCoin, иначе начинает ухудшать ваши стрики.",
            "symbiotic_enhancement_ability": True,
            "daily_upkeep_cost_onecoin": 10,
        }, "is_true_exclusive": True,
    },

    # --- Google (Серия "P" - Pixel) ---
    {
        "key": "bm_google_pixel_singularity_net",
        "name": "Google Pixel Singularity 'Нейросеть Всего'",
        "brand_tag": "Google", "series": "P", "display_name": "Pixel Singularity",
        "memory": "Коллективный Разум (2TB)", "base_price": 4800, "release_year": 2031,
        "bm_description": "Этот Pixel подключен к экспериментальной нейросети Google, которая стремится к Сингулярности. Он знает ответы на многие вопросы... но иногда задает свои.",
        "rarity": "legendary",
        "special_properties": {
            "fixed_color": "Белый с Переливающейся Дата-Матрицей",
            "custom_bonus_description": "Раз в день дает +1 дополнительную попытку для любой команды (/oneui, /bonus, /roulette) на выбор. Слегка увеличивает шанс на 'не тот товар' от ЧР-продавцов.",
            "daily_extra_attempt_any_cmd": 1,
            "bad_merchant_chance_increase_percent": 0.05,
        }, "is_true_exclusive": True,
    },
    {
        "key": "bm_google_pixel_dreamscape_portal",
        "name": "Google Pixel Dreamscape 'Портал в Сны'",
        "brand_tag": "Google", "series": "P", "display_name": "Pixel Dreamscape",
        "memory": "512GB Эфирных Видений", "base_price": 3300, "release_year": 2027,
        "bm_description": "Экспериментальный Pixel, использующий технологию осознанных сновидений для... чего-то. Его экран показывает сюрреалистичные пейзажи. Не рекомендуется использовать перед сном.",
        "rarity": "epic",
        "special_properties": {
            "fixed_color": "Лавандовый Туман с Зыбкими Образами",
            "custom_bonus_description": "Увеличивает награды за завершение длительных стриков на 10%. Иногда показывает случайные 'пасхалки' или секреты игры.",
            "long_streak_reward_bonus_percent": 0.10,
            "reveals_game_secrets_chance": 0.02,
        }, "is_true_exclusive": True,
    },

    # --- Xiaomi (Серия "M") ---
    {
        "key": "bm_xiaomi_terraformer_core_x",
        "name": "Xiaomi Terraformer Core X 'Сердце Мира'",
        "brand_tag": "Xiaomi", "series": "M", "display_name": "Terraformer Core X",
        "memory": "Геоданные Планеты (1TB)", "base_price": 4200, "release_year": 2030,
        "bm_description": "Этот Xiaomi содержит ядро терраформирующей установки. Он может изменять 'окружающую среду' (шансы в рулетке) в небольшом радиусе, но очень энергоемок.",
        "rarity": "legendary",
        "special_properties": {
            "fixed_color": "Земляной с Жилами Изумруда",
            "custom_bonus_description": "Раз в 3 дня позволяет 'сдвинуть удачу' в рулетке: на 10% увеличивает шанс на категорию 'onecoin_reward' или 'phone_reward' на следующий спин. Батарея садится на 20% быстрее обычной.",
            "roulette_luck_shift_ability": True,
            "battery_life_factor": 0.8,
        }, "is_true_exclusive": True,
    },
    {
        "key": "bm_xiaomi_phantom_weave_7g",
        "name": "Xiaomi PhantomWeave 7G 'Призрачная Сеть'",
        "brand_tag": "Xiaomi", "series": "M", "display_name": "PhantomWeave 7G",
        "memory": "768GB Спектральных Данных", "base_price": 2800, "release_year": 2029,
        "bm_description": "Работает на несуществующих 7G частотах, этот Xiaomi ловит сигналы из параллельных измерений. Иногда вместо звонков принимает 'сообщения от духов'.",
        "rarity": "epic",
        "special_properties": {
            "fixed_color": "Полупрозрачный Дымчатый",
            "custom_bonus_description": "Позволяет владельцу раз в день получить +0.2 к версии OneUI без использования основной команды /oneui (пассивный бонус). Слегка увеличивает шанс 'косметического дефекта' при покупке других телефонов.",
            "passive_oneui_daily_bonus": 0.2,
        }, "is_true_exclusive": True,
    },

    # --- OnePlus (Серия "O") ---
    {
        "key": "bm_oneplus_timeweaver_pro",
        "name": "OnePlus TimeWeaver Pro 'Ткач Времени'",
        "brand_tag": "OnePlus", "series": "O", "display_name": "TimeWeaver Pro",
        "memory": "1TB Хроно-нитей", "base_price": 4600, "release_year": 2032,
        "bm_description": "Этот OnePlus не просто быстр, он может манипулировать локальным временем. 'Никогда не опаздывай' – девиз его создателей... или тех, кто его украл.",
        "rarity": "legendary",
        "special_properties": {
            "fixed_color": "Отполированный Обсидиан с Золотыми Часовыми Метками",
            "custom_bonus_description": "Позволяет раз в 3 дня 'заморозить' один из кулдаунов (OneUI, Bonus или Roulette) на 12 часов, или мгновенно завершить его. Высокая стоимость зарядки.",
            "time_manipulation_skill": "freeze_cooldown_12h_or_finish",
            "charge_cost_multiplier": 2.0, # Зарядка в 2 раза дороже
        }, "is_true_exclusive": True,
    },
    {
        "key": "bm_oneplus_zenith_ascendant",
        "name": "OnePlus Zenith Ascendant 'Восхождение'",
        "brand_tag": "OnePlus", "series": "O", "display_name": "Zenith Ascendant",
        "memory": "512GB Небесной Энергии", "base_price": 3100, "release_year": 2028,
        "bm_description": "Телефон, созданный для достижения 'пиковой производительности' во всем. Его владелец чувствует прилив сил... и постоянную жажду большего.",
        "rarity": "epic",
        "special_properties": {
            "fixed_color": "Лазурный с Золотыми Всполохами",
            "custom_bonus_description": "Увеличивает награды за достижение целей ежедневного стрика на 15%. Слегка увеличивает цену на товары в обычном магазине для владельца (+5%).",
            "streak_goal_reward_bonus_percent": 0.15,
            "regular_market_price_increase_self_percent": 0.05,
        }, "is_true_exclusive": True,
    },

    # --- Huawei (Серия "H") ---
    {
        "key": "bm_huawei_kunlun_dragonscale",
        "name": "Huawei Kunlun DragonScale 'Чешуя Дракона'",
        "brand_tag": "Huawei", "series": "H", "display_name": "Kunlun DragonScale",
        "memory": "1TB Древней Мудрости", "base_price": 5200, "release_year": 2030,
        "bm_description": "Корпус этого Huawei сделан из материала, напоминающего чешую дракона. Он невероятно прочен и, по слухам, хранит в себе частицу древней магии гор Куньлунь.",
        "rarity": "mythic",
        "special_properties": {
            "fixed_color": "Багрово-Золотой с Текстурой Чешуи",
            "custom_bonus_description": "Дает владельцу +1 к максимальному количеству активных телефонов. Компоненты этого телефона не ломаются от обычного износа (только если сам телефон будет уничтожен особым событием).",
            "max_phone_slot_bonus": 1,
            "components_are_indestructible_standard_wear": True,
        }, "is_true_exclusive": True,
    },
    {
        "key": "bm_huawei_astral_cartographer",
        "name": "Huawei Astral Cartographer 'Звездный Картограф'",
        "brand_tag": "Huawei", "series": "H", "display_name": "Astral Cartographer",
        "memory": "512GB Космических Карт", "base_price": 3400, "release_year": 2029,
        "bm_description": "Этот Huawei может прокладывать маршруты через неизведанные сектора космоса... или просто показывать очень точные карты Земли. Иногда ловит странные сигналы.",
        "rarity": "epic",
        "special_properties": {
            "fixed_color": "Глубокий Космос с Туманностями",
            "custom_bonus_description": "Увеличивает шанс нахождения редких 'координат' для доступа к временным событиям или локациям (если такая механика будет). Снижает шанс на 'Эксклюзив дня' на ЧР для владельца (конкуренция).",
            "rare_coordinate_find_chance_bonus": 0.10,
        }, "is_true_exclusive": True,
    },

    # --- Samsung (Кастомные ЧР версии) ---
    {
        "key": "bm_samsung_galaxy_zero_day_exploit",
        "name": "Samsung Galaxy Zero-Day 'Эксплойт'",
        "brand_tag": "Samsung", "series": "S", "display_name": "Galaxy Zero-Day",
        "memory": "512GB Уязвимостей", "base_price": 2200, "release_year": 2026,
        "bm_description": "Модифицированный Galaxy S-серии, напичканный эксплойтами нулевого дня. Может 'взломать' другие системы... или самого себя. Используйте с осторожностью.",
        "rarity": "epic",
        "special_properties": {
            "fixed_color": "Черный с Глючными Зелеными Линиями",
            "custom_bonus_description": "При использовании /bonus есть 10% шанс 'взломать' систему и получить x2 к выпавшему множителю. Но также 5% шанс, что /bonus уйдет в кулдаун на доп. 24 часа.",
            "bonus_hack_double_chance": 0.10,
            "bonus_hack_cooldown_penalty_chance": 0.05,
        }, "is_true_exclusive": True, # Кастомная версия
    },
    {
        "key": "bm_samsung_galaxy_a_rogue_ai",
        "name": "Samsung Galaxy A-series 'ИИ-Изгой'",
        "brand_tag": "Samsung", "series": "A", "display_name": "Galaxy A 'ИИ-Изгой'",
        "memory": "Саморазвивающийся (Начало 512GB)", "base_price": 1800, "release_year": 2027,
        "bm_description": "В этой A-шке поселился взбунтовавшийся ИИ. Он помогает владельцу, но его цели неизвестны. Иногда требует странные 'жертвы' (случайные предметы).",
        "rarity": "epic",
        "special_properties": {
            "fixed_color": "Металлик с Красным 'Глазом'",
            "custom_bonus_description": "Дает +0.1 к OneUI каждый день пассивно. Раз в неделю может потребовать случайный компонент (A/S/Z) для 'самоулучшения', иначе перестает давать бонус.",
            "rogue_ai_passive_oneui_bonus": 0.1,
            "rogue_ai_demands_component_weekly": True,
        }, "is_true_exclusive": True,
    },
    {
        "key": "bm_samsung_z_fold_origami_master",
        "name": "Samsung Z Fold 'Мастер Оригами' (Прототип ЧР)",
        "brand_tag": "Samsung", "series": "Z", "display_name": "Z Fold 'Оригами'",
        "memory": "1TB Бесконечных Складок", "base_price": 3800, "release_year": 2028,
        "bm_description": "Экспериментальный Z Fold, который может складываться не только пополам, но и в другие фигуры, меняя свои свойства. Очень хрупкий в сложенном виде.",
        "rarity": "legendary",
        "special_properties": {
            "fixed_color": "Бумажно-Белый с Тонкими Линиями Сгиба",
            "custom_bonus_description": "Может 'сложиться' в один из трех режимов раз в день: 'Щит' (+20% к шансу избежать поломки на 12ч), 'Сканер' (удваивает шанс на редкий предмет из рулетки на след. спин), 'Куб' (дает +100 OneCoin, но телефон нельзя использовать 6ч). В режиме 'Куб' очень уязвим.",
            "origami_mode_ability": ["shield", "scanner", "cube"],
        }, "is_true_exclusive": True,
    },

    # --- Полностью Кастомные Артефакты ЧР ---
    {
        "key": "bm_artifact_whispering_idol_v2", # v2
        "name": "Шепчущий Идол Возрожденный",
        "brand_tag": "Artifact", "series": "L", "display_name": "Идол Возрожденный",
        "memory": "Эманации Порядка (1TB)", "base_price": 5000, "release_year": "Новая Эра",
        "bm_description": "Идол был очищен и теперь шепчет не хаос, а формулы успеха. Дарует стабильность, но требует верности.",
        "rarity": "mythic",
        "special_properties": {
            "fixed_color": "Белый Мрамор с Золотыми Рунами",
            "custom_bonus_description": "Всегда предотвращает самый худший исход в рулетке (если их несколько, то один из). Увеличивает стоимость всех покупок на ЧР на 5% для владельца.",
            "roulette_worst_outcome_prevention": True,
            "black_market_purchase_cost_increase_self_percent": 0.05,
        }, "is_true_exclusive": True,
    },
    {
        "key": "bm_custom_nomad_wanderer_spirit",
        "name": "Дух Странника 'Кочевник'",
        "brand_tag": "CustomBM", "series": "X", "display_name": "Дух Странника",
        "memory": "Карты Дорог (512GB)", "base_price": 1750, "release_year": "Вечность",
        "bm_description": "Этот телефон принадлежал вечному страннику. Он не привязан к одному месту и всегда найдет 'обходной путь'.",
        "rarity": "rare",
        "special_properties": {
            "fixed_color": "Выцветшая Кожа с Компасом",
            "custom_bonus_description": "Снижает стоимость 'дополнительных попыток' любых команд на рынке на 15%. Не может быть застрахован.",
            "market_extra_attempt_cost_reduction_percent": 0.15,
            "cannot_be_insured": True,
        }, "is_true_exclusive": True,
    },
    {
        "key": "bm_artifact_luckstone_charm",
        "name": "Талисман Удачи 'Клевер'",
        "brand_tag": "Artifact", "series": "L", "display_name": "Талисман Удачи",
        "memory": "Чистая Фортуна (777GB)", "base_price": 3777, "release_year": "Удача",
        "bm_description": "Говорят, этот телефон сделан из четырехлистного клевера, найденного в конце радуги. Приносит удачу... но только если верить.",
        "rarity": "legendary",
        "special_properties": {
            "fixed_color": "Изумрудно-Зеленый с Золотым Клевером",
            "custom_bonus_description": "Увеличивает шанс на положительный исход во всех 'шансовых' событиях (OneUI, Bonus, Roulette) на небольшой процент (+3%).",
            "global_positive_luck_bonus_percent": 0.03,
        }, "is_true_exclusive": True,
    },
    {
        "key": "bm_tech_mimic_data_golem",
        "name": "Дата-Голем 'Подражатель'",
        "brand_tag": "CustomTech", "series": "X", "display_name": "Дата-Голем",
        "memory": "Адаптивная Матрица (до 2TB)", "base_price": 2400, "release_year": 2029,
        "bm_description": "Этот телефон может 'копировать' базовые характеристики (кроме уникальных свойств) другого вашего активного телефона на 24 часа. Сам по себе он слаб.",
        "rarity": "epic",
        "special_properties": {
            "fixed_color": "Серебристый, меняющий форму",
            "custom_bonus_description": "Раз в день может скопировать серию, память и базовый шанс поломки одного из ваших других не-эксклюзивных телефонов. Копирование длится 24ч.",
            "can_mimic_other_phone_daily": True,
        }, "is_true_exclusive": True,
    },
    {
        "key": "bm_cursed_hourglass_rewinder",
        "name": "Проклятые Песочные Часы 'Перемотка'",
        "brand_tag": "CursedItem", "series": "X", "display_name": "Песочные Часы",
        "memory": "Потерянное Время (512GB)", "base_price": 1999, "release_year": "Забытое Прошлое",
        "bm_description": "Эти 'часы' позволяют отмотать время назад... но каждая перемотка забирает частичку души (или OneCoin). Использовать не более раза в день!",
        "rarity": "epic",
        "special_properties": {
            "fixed_color": "Черный Песок в Стеклянном Корпусе",
            "custom_bonus_description": "Раз в день позволяет 'отменить' последний полученный результат /oneui или /bonus (если он был получен не более 10 минут назад). Стоимость отмены: 50 OneCoin и 10% шанс поломки этих 'часов'.",
            "can_rewind_last_action_daily": True,
            "rewind_cost_onecoin": 50,
            "rewind_self_break_chance": 0.10,
        }, "is_true_exclusive": True,
    },
    {
        "key": "bm_artifact_philosophers_echo",
        "name": "Эхо Философского Камня",
        "brand_tag": "Artifact", "series": "L", "display_name": "Эхо Камня",
        "memory": "Трансмутация (1TB)", "base_price": 5500, "release_year": "Великое Делание",
        "bm_description": "Не сам Камень, но его мощное эхо. Может превращать одни ресурсы в другие, но требует огромной концентрации и энергии.",
        "rarity": "mythic",
        "special_properties": {
            "fixed_color": "Рубиново-Красный, излучающий тепло",
            "custom_bonus_description": "Позволяет раз в неделю трансмутировать 3 любых одинаковых компонента (например, 3х SCREEN_A) в 1 случайный компонент той же серии, но более высокого 'уровня' (например, CPU_A или BATTERY_A). Требует 200 OneCoin за попытку.",
            "advanced_transmutation_ability": True,
            "transmutation_cost_onecoin": 200,
        }, "is_true_exclusive": True,
    },
    # Добавляем еще, чтобы точно было больше 20-ти
     {
        "key": "bm_custom_void_gazer_mk2",
        "name": "Void Gazer Mk.II 'Око Бездны'",
        "brand_tag": "CustomBM", "series": "X", "display_name": "Void Gazer II",
        "memory": "Зашифрованная Пустота (768GB)", "base_price": 3100, "release_year": 2029,
        "bm_description": "Улучшенная версия легендарного Void Gazer. Позволяет не только видеть в пустоту, но и извлекать оттуда 'данные'. Крайне опасно для психики.",
        "rarity": "legendary",
        "special_properties": {
            "fixed_color": "Фиолетовый с Черными Разломами",
            "custom_bonus_description": "Раз в 3 дня дает шанс получить 'Пакет данных из Пустоты' (содержит случайные ресурсы: OneCoin, компонент или временный бафф). Может вызвать 'ментальный откат' (временное снижение всех характеристик).",
            "void_data_packet_chance": 0.33,
            "mental_recoil_chance": 0.15,
        }, "is_true_exclusive": True,
    },
    {
        "key": "bm_sony_soundwave_cannon_mini",
        "name": "Sony SoundWave Cannon (Miniature) 'Шопот'",
        "brand_tag": "Sony", "series": "X", "display_name": "SoundWave Cannon Mini",
        "memory": "Акустический Резонатор (512GB)", "base_price": 2750, "release_year": 2026,
        "bm_description": "Портативная версия звуковой пушки Sony, маскирующаяся под телефон. Может издавать инфразвук, влияющий на электронику... и мозги.",
        "rarity": "epic",
        "special_properties": {
            "fixed_color": "Металлический Серый с Видимыми Динамиками",
            "custom_bonus_description": "При использовании /oneui, есть 5% шанс 'подавить' соседние телефоны в чате, снизив их следующее изменение OneUI на -0.1 (не стакается). Увеличивает награды за семейные соревнования на 5%.",
            "aoe_oneui_debuff_chance": 0.05,
            "family_competition_reward_bonus_percent": 0.05,
        }, "is_true_exclusive": True,
    },
    {
        "key": "bm_nokia_guardian_angel_777",
        "name": "Nokia Guardian Angel 777 'Хранитель'",
        "brand_tag": "Nokia", "series": "L", "display_name": "Nokia Guardian 777",
        "memory": "Благословенная (777GB)", "base_price": 4777, "release_year": "Небесная Кузница",
        "bm_description": "Этот Nokia, по слухам, был благословлен ангелами. Он защищает своего владельца от многих бед, но требует веры и добрых дел.",
        "rarity": "mythic",
        "special_properties": {
            "fixed_color": "Жемчужно-Белый с Золотым Нимбом",
            "custom_bonus_description": "Полностью защищает от 'Облав' и 'Ненадежных Продавцов'. Раз в неделю может предотвратить одну поломку (не от износа батареи). Требует, чтобы стрик /oneui был не ниже 7 дней для активации защитных свойств.",
            "angelic_protection_active_min_streak": 7,
            "prevents_one_breakdown_weekly": True,
        }, "is_true_exclusive": True,
    },
    {
        "key": "bm_vertu_tycoon_legacy_sealed",
        "name": "Vertu Tycoon's Legacy (Sealed Vault Edition)",
        "brand_tag": "Vertu", "series": "X", "display_name": "Vertu Tycoon's Legacy",
        "memory": "Запечатанный Актив (2TB)", "base_price": 6000, # Максимальная цена
        "release_year": "Наследие",
        "bm_description": "Последний телефон легендарного магната, запечатанный в мини-хранилище. Открыть его – уже достижение. Содержимое неизвестно, но слухи ходят о несметных богатствах... или проклятии.",
        "rarity": "mythic",
        "special_properties": {
            "fixed_color": "Платиновый Сейф с Рубиновой Печатью",
            "custom_bonus_description": "При покупке игрок получает не только телефон, но и 'Запечатанный Контейнер Магната' (специальный предмет, который нужно 'открыть' отдельной командой или квестом, может содержать много OneCoin, редкие компоненты или даже другой эксклюзивный телефон). Сам телефон имеет средние характеристики, но очень прочен.",
            "comes_with_sealed_container_item": True,
            "intrinsic_wear_resistance_factor": 0.5,
        }, "is_true_exclusive": True,
    }
]

VINTAGE_PHONE_KEYS_FOR_BM = [
    "samsung_galaxy_s2",  # Пример, замени на реальные ключи
            # Пример, замени на реальные ключи
    # Добавь сюда другие ключи "винтажных" моделей,
    # которые определены в твоем основном списке телефонов (phone_data.py)
    # и могут появляться на Черном Рынке.
]