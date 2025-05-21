# business_data.py

# ==============================================================================
# --- Данные о БИЗНЕСАХ ---
# ==============================================================================

BUSINESS_DATA = {
    "business_1_home_samsung_region_change": {
        "name": "Домашний Сервис \"Смена Региона Samsung\"",
        "description": "Смена региональной прошивки на смартфонах Samsung для доступа к региональным функциям.",
        "levels": {
            0: {
                "display_name": "Домашний Сервис \"Смена Региона Samsung\"",
                "description_level": "Стартовый сервис на дому.",
                "base_income_per_hour": 6,
                "price": 2000,
                "max_staff_slots": 5 # Максимум 5 сотрудников
            },
            1: {
                "display_name": "Выездной Центр \"Регион-Мастер\"",
                "description_level": "Выездной сервис с профессиональным оборудованием.",
                "base_income_per_hour": 8,
                "upgrade_cost": 4000,
                "max_staff_slots": 10
            },
            2: {
                "display_name": "Онлайн-Хаб \"Глобальная Прошивка OneUI\"",
                "description_level": "Удалённая смена региона через облако.",
                "base_income_per_hour": 10,
                "upgrade_cost": 8000,
                "max_staff_slots": 20
            },
            3: {
                "display_name": "Нейросеть \"Абсолютный Адаптер Samsung\"",
                "description_level": "Автоматизированная платформа для мгновенной смены региона.",
                "base_income_per_hour": 13,
                "upgrade_cost": 16000,
                "max_staff_slots": 30
            }
        }
    },
    "business_2_mobile_galaxy_repair": {
        "name": "Мобильный Ремонт \"Galaxy на Колесах\"",
        "description": "Фургон для ремонта телефонов Samsung на выезде.",
        "levels": {
            0: {
                "display_name": "Мобильный Ремонт \"Galaxy на Колесах\"",
                "description_level": "Фургон для ремонта телефонов Samsung на выезде.",
                "base_income_per_hour": 10,
                "price": 3500,
                "max_staff_slots": 8
            },
            1: {
                "display_name": "Передвижная Клиника \"Техно-Скорая\"",
                "description_level": "Брендированный фургон с рекламой.",
                "base_income_per_hour": 13,
                "upgrade_cost": 7000,
                "max_staff_slots": 15
            },
            2: {
                "display_name": "Диагностический Фургон \"ИИ-Ремонт Galaxy\"",
                "description_level": "Мобильная диагностика с ИИ.",
                "base_income_per_hour": 16,
                "upgrade_cost": 14000,
                "max_staff_slots": 25
            },
            3: {
                "display_name": "Флот \"Спасатели Цифрового Пространства\"",
                "description_level": "Франшиза мобильных ремонтных станций.",
                "base_income_per_hour": 20,
                "upgrade_cost": 28000,
                "max_staff_slots": 40
            }
        }
    },
    "business_3_galaxy_premium_accessories_boutique": {
        "name": "Бутик \"Аксессуары Galaxy Премиум\"",
        "description": "Продажа чехлов, зарядок и аксессуаров для устройств Samsung.",
        "levels": {
            0: {
                "display_name": "Бутик \"Аксессуары Galaxy Премиум\"",
                "description_level": "Продажа чехлов, зарядок и аксессуаров для устройств Samsung.",
                "base_income_per_hour": 14,
                "price": 5000,
                "max_staff_slots": 12
            },
            1: {
                "display_name": "Галерея \"Стиль OneUI\"",
                "description_level": "Собственный бренд аксессуаров.",
                "base_income_per_hour": 17,
                "upgrade_cost": 10000,
                "max_staff_slots": 20
            },
            2: {
                "display_name": "Дизайн-Студия \"Эксклюзив для Samsung\"",
                "description_level": "Эксклюзивные дизайнерские аксессуары.",
                "base_income_per_hour": 21,
                "upgrade_cost": 20000,
                "max_staff_slots": 35
            },
            3: {
                "display_name": "Модный Дом \"Цифровая Элегантность Samsung\"",
                "description_level": "Лакшери-линейка аксессуаров.",
                "base_income_per_hour": 26,
                "upgrade_cost": 40000,
                "max_staff_slots": 50
            }
        }
    },
    "business_4_eco_recycling_samsung": {
        "name": "Пункт Утилизации \"Эко-Рециклинг Samsung\"",
        "description": "Утилизация и переработка электроники Samsung.",
        "levels": {
            0: {
                "display_name": "Пункт Утилизации \"Эко-Рециклинг Samsung\"",
                "description_level": "Утилизация и переработка электроники Samsung.",
                "base_income_per_hour": 18,
                "price": 7000,
                "max_staff_slots": 15
            },
            1: {
                "display_name": "Центр Регенерации Компонентов",
                "description_level": "Переработка компонентов для повторного использования.",
                "base_income_per_hour": 22,
                "upgrade_cost": 14000,
                "max_staff_slots": 25
            },
            2: {
                "display_name": "Завод \"Вторая Жизнь Электроники Galaxy\"",
                "description_level": "Полный цикл переработки.",
                "base_income_per_hour": 28,
                "upgrade_cost": 28000,
                "max_staff_slots": 40
            },
            3: {
                "display_name": "Глобальная Корпорация \"Вечный Ресурс Samsung\"",
                "description_level": "Мировая сеть эко-переработки.",
                "base_income_per_hour": 35,
                "upgrade_cost": 56000,
                "max_staff_slots": 60
            }
        }
    },
    "business_5_galaxy_trade_in_center": {
        "name": "Магазин \"Galaxy Trade-In Центр\"",
        "description": "Обмен старых устройств Samsung на новые.",
        "levels": {
            0: {
                "display_name": "Магазин \"Galaxy Trade-In Центр\"",
                "description_level": "Обмен старых устройств Samsung на новые.",
                "base_income_per_hour": 23,
                "price": 9500,
                "max_staff_slots": 20
            },
            1: {
                "display_name": "Пункт Апгрейда Samsung",
                "description_level": "Программа обмена с бонусами.",
                "base_income_per_hour": 29,
                "upgrade_cost": 19000,
                "max_staff_slots": 35
            },
            2: {
                "display_name": "Биржа Редких Моделей Galaxy",
                "description_level": "Торговля коллекционными устройствами.",
                "base_income_per_hour": 36,
                "upgrade_cost": 38000,
                "max_staff_slots": 50
            },
            3: {
                "display_name": "Международный Маркетплейс \"Наследие Samsung\"",
                "description_level": "Глобальная платформа для трейд-ин.",
                "base_income_per_hour": 45,
                "upgrade_cost": 76000,
                "max_staff_slots": 80
            }
        }
    },
    "business_6_official_samsung_service_center": {
        "name": "Официальный Сервисный Центр \"Гарант Samsung\"",
        "description": "Профессиональный ремонт смартфонов, планшетов и часов Samsung.",
        "levels": {
            0: {
                "display_name": "Официальный Сервисный Центр \"Гарант Samsung\"",
                "description_level": "Профессиональный ремонт смартфонов, планшетов и часов Samsung.",
                "base_income_per_hour": 30,
                "price": 13000,
                "max_staff_slots": 25
            },
            1: {
                "display_name": "Элитный Сервис \"Galaxy Pro\"",
                "description_level": "Ремонт премиум-устройств.",
                "base_income_per_hour": 38,
                "upgrade_cost": 26000,
                "max_staff_slots": 40
            },
            2: {
                "display_name": "Главный Диагностический Комплекс Galaxy",
                "description_level": "Центр с ИИ-диагностикой.",
                "base_income_per_hour": 47,
                "upgrade_cost": 52000,
                "max_staff_slots": 60
            },
            3: {
                "display_name": "Авторизованный Технопарк \"Гарант Будущего Samsung\"",
                "description_level": "Сеть сервисных центров.",
                "base_income_per_hour": 59,
                "upgrade_cost": 104000,
                "max_staff_slots": 100
            }
        }
    },
    "business_7_it_oneui_solutions_ai": {
        "name": "IT-Концерн \"OneUI Solutions & AI\"",
        "description": "Разработка приложений для экосистемы Samsung (Galaxy Store, Smart TV).",
        "levels": {
            0: {
                "display_name": "IT-Концерн \"OneUI Solutions & AI\"",
                "description_level": "Разработка приложений для экосистемы Samsung (Galaxy Store, Smart TV).",
                "base_income_per_hour": 104,
                "price": 50000,
                "max_staff_slots": 50 # С 7-го бизнеса начинается увеличение налога при полной занятости слотов
            },
            1: {
                "display_name": "Студия \"Флагманских Приложений Galaxy\"",
                "description_level": "Эксклюзивные приложения для Galaxy Store.",
                "base_income_per_hour": 130,
                "upgrade_cost": 100000,
                "max_staff_slots": 80
            },
            2: {
                "display_name": "Лаборатория \"ИИ-Интеграции Bixby\"",
                "description_level": "Интеграция с ИИ Bixby.",
                "base_income_per_hour": 163,
                "upgrade_cost": 200000,
                "max_staff_slots": 120
            },
            3: {
                "display_name": "Глобальный Софт-Гигант \"Цифровой Интеллект Samsung\"",
                "description_level": "Мировая софт-платформа.",
                "base_income_per_hour": 204,
                "upgrade_cost": 400000,
                "max_staff_slots": 200
            }
        }
    },
    "business_8_black_market_onecoin_exclusive": {
        "name": "\"Теневой Рынок OneCoin: Эксклюзив\"",
        "description": "Торговля редкими прототипами и эксклюзивными технологиями Samsung.",
        "levels": {
            0: {
                "display_name": "\"Теневой Рынок OneCoin: Эксклюзив\"",
                "description_level": "Торговля редкими прототипами и эксклюзивными технологиями Samsung.",
                "base_income_per_hour": 284,
                "price": 150000,
                "max_staff_slots": 80
            },
            1: {
                "display_name": "Подпольный Ангар \"Редчайшие Прототипы Galaxy\"",
                "description_level": "Секретная торговля прототипами.",
                "base_income_per_hour": 355,
                "upgrade_cost": 300000,
                "max_staff_slots": 150
            },
            2: {
                "display_name": "Аукционный Дом \"Запрещенные Технологии Samsung\"",
                "description_level": "Эксклюзивные аукционы.",
                "base_income_per_hour": 444,
                "upgrade_cost": 600000,
                "max_staff_slots": 250
            },
            3: {
                "display_name": "Синдикат \"Теневые Магнаты OneCoin\"",
                "description_level": "Глобальная сеть подпольной торговли.",
                "base_income_per_hour": 555,
                "upgrade_cost": 1200000,
                "max_staff_slots": 400
            }
        }
    },
    "business_9_samsung_electronics_manufacturing_plant": {
        "name": "Завод по Производству Электроники Samsung",
        "description": "Производство смартфонов, телевизоров и компонентов под лицензией Samsung.",
        "levels": {
            0: {
                "display_name": "Завод по Производству Электроники Samsung",
                "description_level": "Производство смартфонов, телевизоров и компонентов под лицензией Samsung.",
                "base_income_per_hour": 667,
                "price": 400000,
                "max_staff_slots": 200
            },
            1: {
                "display_name": "R&D Завод \"Инновации в Сборке\"",
                "description_level": "Центр исследований и разработок.",
                "base_income_per_hour": 834,
                "upgrade_cost": 800000,
                "max_staff_slots": 350
            },
            2: {
                "display_name": "Флагманский Завод \"Galaxy S-Серия\"",
                "description_level": "Производство флагманских моделей.",
                "base_income_per_hour": 1043,
                "upgrade_cost": 1600000,
                "max_staff_slots": 600
            },
            3: {
                "display_name": "Зеленый Завод Samsung: Эра Эко-Производства",
                "description_level": "Экологичное производство.",
                "base_income_per_hour": 1304,
                "upgrade_cost": 3200000,
                "max_staff_slots": 1000
            }
        }
    },
    "business_10_samsung_ai_drone_factory": {
        "name": "\"Завод по Дронам с ИИ Samsung\"",
        "description": "Производство военных и гражданских дронов с ИИ.",
        "levels": {
            0: {
                "display_name": "\"Завод по Дронам с ИИ Samsung\"",
                "description_level": "Производство военных и гражданских дронов с ИИ.",
                "base_income_per_hour": 1488,
                "price": 1000000,
                "max_staff_slots": 300
            },
            1: {
                "display_name": "Фабрика \"Бронированных Дронов Galaxy\"",
                "description_level": "Военные беспилотники.",
                "base_income_per_hour": 1860,
                "upgrade_cost": 2000000,
                "max_staff_slots": 500
            },
            2: {
                "display_name": "Производство \"Автономных Систем Управления\"",
                "description_level": "Полностью автономные дроны.",
                "base_income_per_hour": 2325,
                "upgrade_cost": 4000000,
                "max_staff_slots": 800
            },
            3: {
                "display_name": "Оборонный Концерн Samsung: Властелины Неба",
                "description_level": "Глобальное производство дронов.",
                "base_income_per_hour": 2906,
                "upgrade_cost": 8000000,
                "max_staff_slots": 1500
            }
        }
    },
    "business_11_samsung_main_tank_factory": {
        "name": "\"Главный Завод Танков Samsung\"",
        "description": "Производство тяжелой бронетехники, включая танки.",
        "levels": {
            0: {
                "display_name": "\"Главный Завод Танков Samsung\"",
                "description_level": "Производство тяжелой бронетехники, включая танки.",
                "base_income_per_hour": 3255,
                "price": 2500000,
                "max_staff_slots": 500
            },
            1: {
                "display_name": "Производство \"Бронированных Машин Galaxy\"",
                "description_level": "Легкая и средняя бронетехника.",
                "base_income_per_hour": 4069,
                "upgrade_cost": 5000000,
                "max_staff_slots": 900
            },
            2: {
                "display_name": "Фабрика \"Тяжелой Бронетехники Samsung AI\"",
                "description_level": "Танки с ИИ-управлением.",
                "base_income_per_hour": 5086,
                "upgrade_cost": 10000000,
                "max_staff_slots": 1500
            },
            3: {
                "display_name": "Военно-Промышленная Монополия Samsung: Щит Планеты",
                "description_level": "Глобальное производство.",
                "base_income_per_hour": 6358,
                "upgrade_cost": 20000000,
                "max_staff_slots": 2500
            }
        }
    },
    "business_12_global_samsung_innovation_hub": {
        "name": "Глобальный Инновационный Хаб Samsung",
        "description": "Международный центр управления инновациями Samsung: от смартфонов до космоса.",
        "levels": {
            0: {
                "display_name": "Глобальный Инновационный Хаб Samsung",
                "description_level": "Международный центр управления инновациями Samsung: от смартфонов до космоса.",
                "base_income_per_hour": 6579,
                "price": 6000000,
                "max_staff_slots": 800
            },
            1: {
                "display_name": "ИИ-Хаб \"Нейросеть Samsung\"",
                "description_level": "Центр искусственного интеллекта.",
                "base_income_per_hour": 8224,
                "upgrade_cost": 12000000,
                "max_staff_slots": 1400
            },
            2: {
                "display_name": "Всемирная Сеть Лабораторий Samsung \"Прорыв\"",
                "description_level": "Глобальная сеть исследований.",
                "base_income_per_hour": 10280,
                "upgrade_cost": 24000000,
                "max_staff_slots": 2500
            },
            3: {
                "display_name": "Космическая Экосистема Samsung: Матрица Будущего",
                "description_level": "Интеграция всех технологий.",
                "base_income_per_hour": 12850,
                "upgrade_cost": 48000000,
                "max_staff_slots": 4000
            }
        }
    },
    "business_13_samsung_commercial_space_agency": {
        "name": "Космическое Агентство Samsung (Коммерческое)",
        "description": "Услуги запуска спутников и космических технологий под брендом Samsung.",
        "levels": {
            0: {
                "display_name": "Космическое Агентство Samsung (Коммерческое)",
                "description_level": "Услуги запуска спутников и космических технологий под брендом Samsung.",
                "base_income_per_hour": 13889,
                "price": 15000000,
                "max_staff_slots": 1000
            },
            1: {
                "display_name": "Ракетное Агентство \"Восход Galaxy\"",
                "description_level": "Собственные ракеты-носители.",
                "base_income_per_hour": 17361,
                "upgrade_cost": 30000000,
                "max_staff_slots": 1800
            },
            2: {
                "display_name": "Центр \"Космический Туризм Samsung\"",
                "description_level": "Космический туризм.",
                "base_income_per_hour": 21701,
                "upgrade_cost": 60000000,
                "max_staff_slots": 3000
            },
            3: {
                "display_name": "Межгалактический Консорциум \"Звездный Путь Samsung\"",
                "description_level": "Услуги по межгалактическим перелетам и колонизации.",
                "base_income_per_hour": 27126,
                "upgrade_cost": 120000000,
                "max_staff_slots": 5000
            }
        }
    },
    "business_14_samsung_nuclear_reactor": {
        "name": "\"Ядерный Реактор Samsung\"",
        "description": "Разработка и эксплуатация термоядерного реактора для энергоснабжения производств Samsung.",
        "levels": {
            0: {
                "display_name": "\"Ядерный Реактор Samsung\"",
                "description_level": "Разработка и эксплуатация термоядерного реактора для энергоснабжения производств Samsung.",
                "base_income_per_hour": 32051,
                "price": 40000000,
                "max_staff_slots": 2000
            },
            1: {
                "display_name": "Четырехблочный Реактор Samsung",
                "description_level": "Реактор с четырьмя энергоблоками для повышенной мощности.",
                "base_income_per_hour": 40064,
                "upgrade_cost": 80000000,
                "max_staff_slots": 3500
            },
            2: {
                "display_name": "Термоядерный Комплекс \"Альфа-Энергия Samsung\"",
                "description_level": "Полностью термоядерный реактор с нулевыми выбросами.",
                "base_income_per_hour": 50080,
                "upgrade_cost": 160000000,
                "max_staff_slots": 6000
            },
            3: {
                "display_name": "Космоэнергетическая Империя \"Вечный Источник Samsung\"",
                "description_level": "Глобальная сеть термоядерных реакторов, питающих планетарные и космические проекты Samsung.",
                "base_income_per_hour": 62600,
                "upgrade_cost": 320000000,
                "max_staff_slots": 10000
            }
        }
    },
    "business_15_samsung_singularity_center": {
        "name": "\"Центр Сингулярности Samsung\"",
        "description": "Передовой исследовательский центр, занимающийся развитием искусственного сверхразума и его интеграцией в экосистему Samsung для управления всеми глобальными и космическими операциями.",
        "levels": {
            0: {
                "display_name": "\"Центр Сингулярности Samsung\"",
                "description_level": "Передовой исследовательский центр, занимающийся развитием искусственного сверхразума и его интеграцией в экосистему Samsung.",
                "base_income_per_hour": 71839,
                "price": 100000000,
                "max_staff_slots": 5000 # Для 15-го бизнеса, начальный лимит сотрудников
            },
            1: {
                "display_name": "Ядро \"Цифрового Разума Galaxy\"",
                "description_level": "Начальная фаза создания ИИ.",
                "base_income_per_hour": 89799,
                "upgrade_cost": 200000000,
                "max_staff_slots": 8000
            },
            2: {
                "display_name": "Проект \"Коллективный Разум OneUI\"",
                "description_level": "Интеграция ИИ с глобальными данными.",
                "base_income_per_hour": 112249,
                "upgrade_cost": 400000000,
                "max_staff_slots": 15000
            },
            3: {
                "display_name": "Сверхсознание Samsung: Эпоха Интеллектуальной Доминации",
                "description_level": "ИИ достигает уровня сверхразума и управляет всеми аспектами империи Samsung.",
                "base_income_per_hour": 140311,
                "upgrade_cost": 800000000,
                "max_staff_slots": 25000
            }
        }
    },
    "business_16_interstellar_resource_extraction": {
        "name": "\"Межзвездная Добыча Ресурсов Samsung\"",
        "description": "Экспедиции и платформы для добычи редких и ценных ресурсов (таких как OneElement) из астероидов и планет Солнечной системы.",
        "levels": {
            0: {
                "display_name": "\"Межзвездная Добыча Ресурсов Samsung\"",
                "description_level": "Экспедиции и платформы для добычи редких и ценных ресурсов из астероидов и планет Солнечной системы.",
                "base_income_per_hour": 148810,
                "price": 250000000,
                "max_staff_slots": 10000
            },
            1: {
                "display_name": "Астероидный Рудник \"OneCore\"",
                "description_level": "Добыча на ближайших астероидах.",
                "base_income_per_hour": 186013,
                "upgrade_cost": 500000000,
                "max_staff_slots": 18000
            },
            2: {
                "display_name": "Планетарный Коллектор \"Галактические Богатства\"",
                "description_level": "Разработка месторождений на планетах.",
                "base_income_per_hour": 232516,
                "upgrade_cost": 1000000000,
                "max_staff_slots": 30000
            },
            3: {
                "display_name": "Космическая Магнат-Корпорация \"Звездные Империи OneMatter\"",
                "description_level": "Монополия на межзвездную добычу ресурсов и контроль над экономикой OneCoin в космосе.",
                "base_income_per_hour": 290645,
                "upgrade_cost": 2000000000,
                "max_staff_slots": 50000
            }
        }
    },
    "business_17_samsung_space_station_research": {
        "name": "Космическая Станция Samsung (Исследовательская)",
        "description": "Исследовательская станция для тестирования технологий Samsung в космосе (например, Квантовая Коммуникация).",
        "levels": {
            0: {
                "display_name": "Космическая Станция Samsung (Исследовательская)",
                "description_level": "Исследовательская станция для тестирования технологий Samsung в космосе (например, Квантовая Коммуникация).",
                "base_income_per_hour": 312500,
                "price": 600000000,
                "max_staff_slots": 20000
            },
            1: {
                "display_name": "Межпланетная Космическая Станция Samsung \"Горизонт\"",
                "description_level": "Собственные спутники и межпланетные тесты.",
                "base_income_per_hour": 390625,
                "upgrade_cost": 1200000000,
                "max_staff_slots": 35000
            },
            2: {
                "display_name": "Межгалактическая Космическая Станция Samsung \"Первооткрыватель\"",
                "description_level": "Лаборатория дальнего космоса.",
                "base_income_per_hour": 488281,
                "upgrade_cost": 2400000000,
                "max_staff_slots": 60000
            },
            3: {
                "display_name": "Обитель \"Вселенский Разум Samsung\"",
                "description_level": "Кульминация космических инноваций и партнёрств.",
                "base_income_per_hour": 610352,
                "upgrade_cost": 4800000000,
                "max_staff_slots": 100000
            }
        }
    },
    "business_18_samsung_multiverse_masters": {
        "name": "\"Властелины Мультивселенной Samsung\"",
        "description": "Финальная стадия развития империи Samsung. Контроль над межпространственными технологиями, позволяющими исследовать, влиять и извлекать ресурсы из параллельных реальностей и мультивселенной.",
        "levels": {
            0: {
                "display_name": "\"Властелины Мультивселенной Samsung\"",
                "description_level": "Начало освоения межпространственных технологий.",
                "base_income_per_hour": 700000,
                "price": 1500000000,
                "max_staff_slots": 50000 # Для 18-го бизнеса, максимальный лимит сотрудников
            },
            1: {
                "display_name": "Проект \"Нексус Реальностей\"",
                "description_level": "Начало освоения смежных измерений.",
                "base_income_per_hour": 1562500,
                "upgrade_cost": 3000000000,
                "max_staff_slots": 80000
            },
            2: {
                "display_name": "Архитекторы \"Ткани Мироздания Samsung\"",
                "description_level": "Создание технологий для изменения реальности.",
                "base_income_per_hour": 2272727,
                "upgrade_cost": 6000000000,
                "max_staff_slots": 150000
            },
            3: {
                "display_name": "Суверенная Доминация \"Абсолют Samsung\" - Повелители Мультивселенной",
                "description_level": "Полный контроль над всеми известными и неизвестными измерениями.",
                "base_income_per_hour": 3571429,
                "upgrade_cost": 12000000000,
                "max_staff_slots": 250000
            }
        }
    }
}

# ==============================================================================
# --- Данные об АПГРЕЙДАХ (Системах Защиты) для Бизнесов ---
# ==============================================================================
BUSINESS_UPGRADES = {
    # Общие апгрейды (для разных типов бизнесов)
    "UPGRADE_FIRE_EXTINGUISHER": {
        "name": "Огнетушитель",
        "description": "Базовая защита от возгораний. Снижает риск урона от пожара.",
        "price": 200,
        "type": "safety",
        "prevents_event_keys": ["EVENT_FIRE_SMALL", "EVENT_FIRE_MEDIUM"],
        "applicable_business_keys": [f"business_{i}_" for i in range(1, 19)] # Все бизнесы
    },
    "UPGRADE_MOTION_SENSOR": {
        "name": "Датчик движения",
        "description": "Повышает безопасность от несанкционированного проникновения.",
        "price": 350,
        "type": "security",
        "prevents_event_keys": ["EVENT_THEFT_MINOR"],
        "applicable_business_keys": [
            "business_1_home_samsung_region_change",
            "business_3_galaxy_premium_accessories_boutique",
            "business_5_galaxy_trade_in_center",
            "business_6_official_samsung_service_center",
            "business_7_it_oneui_solutions_ai",
            "business_8_black_market_onecoin_exclusive"
        ]
    },
    "UPGRADE_ALARM_SYSTEM": {
        "name": "Сигнализация",
        "description": "Предупреждает о взломе и призывает полицию/охрану.",
        "price": 1200,
        "type": "security",
        "prevents_event_keys": ["EVENT_THEFT_MEDIUM", "EVENT_VANDALISM"],
        "applicable_business_keys": [
            "business_3_galaxy_premium_accessories_boutique",
            "business_5_galaxy_trade_in_center",
            "business_6_official_samsung_service_center",
            "business_7_it_oneui_solutions_ai",
            "business_8_black_market_onecoin_exclusive",
            "business_9_samsung_electronics_manufacturing_plant",
            "business_12_global_samsung_innovation_hub"
        ]
    },
    "UPGRADE_CCTV_NETWORK": {
        "name": "Сеть видеонаблюдения",
        "description": "Постоянный мониторинг и запись происходящего.",
        "price": 2500,
        "type": "security",
        "prevents_event_keys": ["EVENT_VANDALISM", "EVENT_THEFT_MINOR", "EVENT_THEFT_MEDIUM"],
        "applicable_business_keys": [
            "business_3_galaxy_premium_accessories_boutique",
            "business_4_eco_recycling_samsung",
            "business_5_galaxy_trade_in_center",
            "business_6_official_samsung_service_center",
            "business_7_it_oneui_solutions_ai",
            "business_8_black_market_onecoin_exclusive",
            "business_9_samsung_electronics_manufacturing_plant",
            "business_12_global_samsung_innovation_hub"
        ]
    },
    "UPGRADE_EMERGENCY_GENERATOR": {
        "name": "Аварийный генератор",
        "description": "Обеспечивает бесперебойное электропитание во время сбоев.",
        "price": 5000,
        "type": "utility",
        "prevents_event_keys": ["EVENT_POWER_OUTAGE"],
        "applicable_business_keys": [f"business_{i}_" for i in range(1, 19) if i not in [2]] # Все кроме мобильного
    },
    "UPGRADE_FIRST_AID_POST": {
        "name": "Медпункт",
        "description": "Базовая медицинская помощь на месте, снижает риски для персонала.",
        "price": 1000,
        "type": "safety",
        "prevents_event_keys": ["EVENT_MINOR_INJURY"],
        "applicable_business_keys": [f"business_{i}_" for i in range(1, 19) if i not in [2]] # Все кроме мобильного
    },

    # Апгрейды для "Мобильный Ремонт 'Galaxy на Колесах'" (business_2)
    "UPGRADE_SPARE_TIRE": {
        "name": "Запасное колесо",
        "description": "Позволяет быстро устранить проблемы с колесами фургона.",
        "price": 150,
        "type": "vehicle_maintenance",
        "prevents_event_keys": ["EVENT_VEHICLE_BREAKDOWN_TIRE"],
        "applicable_business_keys": ["business_2_mobile_galaxy_repair"]
    },
    "UPGRADE_FUEL_CANISTER": {
        "name": "Канистра с бензином",
        "description": "Гарантия продолжения работы фургона даже при пустом баке.",
        "price": 100,
        "type": "vehicle_maintenance",
        "prevents_event_keys": ["EVENT_VEHICLE_NO_FUEL"],
        "applicable_business_keys": ["business_2_mobile_galaxy_repair"]
    },
    "UPGRADE_ADVANCED_DIAGNOSTICS": {
        "name": "Продвинутая диагностика",
        "description": "Ускоряет поиск и устранение неисправностей в фургоне.",
        "price": 1000,
        "type": "vehicle_maintenance",
        "prevents_event_keys": ["EVENT_VEHICLE_MAJOR_BREAKDOWN"],
        "applicable_business_keys": ["business_2_mobile_galaxy_repair"]
    },
    "UPGRADE_GPS_TRACKER": {
        "name": "GPS-трекер",
        "description": "Помогает найти угнанный или потерянный фургон.",
        "price": 800,
        "type": "security",
        "prevents_event_keys": ["EVENT_VEHICLE_THEFT"],
        "applicable_business_keys": ["business_2_mobile_galaxy_repair"]
    },

    # Апгрейды для "Пункт Утилизации 'Эко-Рециклинг Samsung'" (business_4)
    "UPGRADE_WASTE_COMPACTOR": {
        "name": "Компактор отходов",
        "description": "Эффективная утилизация и уменьшение объема мусора.",
        "price": 800,
        "type": "efficiency",
        "prevents_event_keys": ["EVENT_OVERLOAD_WASTE"],
        "applicable_business_keys": ["business_4_eco_recycling_samsung"]
    },
    "UPGRADE_HAZARDOUS_WASTE_DISPOSAL": {
        "name": "Утилизация опасных отходов",
        "description": "Безопасное обращение с токсичными компонентами.",
        "price": 1500,
        "type": "safety",
        "prevents_event_keys": ["EVENT_TOXIC_SPILL"],
        "applicable_business_keys": ["business_4_eco_recycling_samsung"]
    },
    "UPGRADE_AIR_FILTRATION": {
        "name": "Система фильтрации воздуха",
        "description": "Улучшает качество воздуха на объекте, предотвращает заболевания.",
        "price": 1000,
        "type": "safety",
        "prevents_event_keys": ["EVENT_HEALTH_HAZARD"],
        "applicable_business_keys": ["business_4_eco_recycling_samsung"]
    },

    # Апгрейды для Заводов (business_9, 10, 11)
    "UPGRADE_ROBOTIC_ARM_CALIBRATION": {
        "name": "Роботизированная калибровка",
        "description": "Повышает точность сборки, снижая брак.",
        "price": 50000,
        "type": "efficiency",
        "prevents_event_keys": ["EVENT_PRODUCTION_DEFECTS_MINOR"],
        "applicable_business_keys": [
            "business_9_samsung_electronics_manufacturing_plant",
            "business_10_samsung_ai_drone_factory",
            "business_11_samsung_main_tank_factory"
        ]
    },
    "UPGRADE_AUTOMATED_QUALITY_CONTROL": {
        "name": "Автоматизированный контроль качества",
        "description": "Минимизирует вероятность выпуска дефектной продукции.",
        "price": 150000,
        "type": "efficiency",
        "prevents_event_keys": ["EVENT_PRODUCTION_DEFECTS_MAJOR"],
        "applicable_business_keys": [
            "business_9_samsung_electronics_manufacturing_plant",
            "business_10_samsung_ai_drone_factory",
            "business_11_samsung_main_tank_factory"
        ]
    },
    "UPGRADE_HEAVY_SECURITY_PERIMETER": {
        "name": "Усиленный периметр безопасности",
        "description": "Отпугивает диверсантов и промышленных шпионов.",
        "price": 250000,
        "type": "security",
        "prevents_event_keys": ["EVENT_SABOTAGE"],
        "applicable_business_keys": [
            "business_9_samsung_electronics_manufacturing_plant",
            "business_10_samsung_ai_drone_factory",
            "business_11_samsung_main_tank_factory",
            "business_14_samsung_nuclear_reactor"
        ]
    },
    "UPGRADE_ADVANCED_CAMOFLAGE": {
        "name": "Продвинутая маскировка",
        "description": "Уменьшает заметность производств для вражеских систем разведки.",
        "price": 300000,
        "type": "defense",
        "prevents_event_keys": ["EVENT_SPY_DISCOVERY"],
        "applicable_business_keys": [
            "business_10_samsung_ai_drone_factory",
            "business_11_samsung_main_tank_factory"
        ]
    },

    # Апгрейды для "Ядерный Реактор Samsung" (business_14)
    "UPGRADE_RADIATION_SHIELDING": {
        "name": "Радиационная защита",
        "description": "Повышает безопасность реактора и защищает персонал.",
        "price": 500000,
        "type": "safety",
        "prevents_event_keys": ["EVENT_RADIATION_LEAK"],
        "applicable_business_keys": ["business_14_samsung_nuclear_reactor"]
    },
    "UPGRADE_COOLING_SYSTEM_OVERHAUL": {
        "name": "Переработка системы охлаждения",
        "description": "Предотвращает перегрев и критические ситуации.",
        "price": 750000,
        "type": "maintenance",
        "prevents_event_keys": ["EVENT_REACTOR_OVERHEAT"],
        "applicable_business_keys": ["business_14_samsung_nuclear_reactor"]
    },

    # Апгрейды для "Центра Сингулярности Samsung" (business_15)
    "UPGRADE_AI_FIREWALL_QUANTUM": {
        "name": "Квантовый Межсетевой Экран ИИ",
        "description": "Защищает от кибератак и попыток саботажа нейросетей.",
        "price": 1500000, # Увеличена цена
        "type": "cyber_security",
        "prevents_event_keys": ["EVENT_AI_CYBER_ATTACK", "EVENT_MALWARE_INFECTION"],
        "applicable_business_keys": ["business_15_samsung_singularity_center"]
    },
    "UPGRADE_DATA_ENCRYPTION_INTERSTELLAR": {
        "name": "Межзвездное Шифрование Данных",
        "description": "Обеспечивает безопасность передаваемых данных в космическом масштабе.",
        "price": 2000000, # Увеличена цена
        "type": "data_security",
        "prevents_event_keys": ["EVENT_QUANTUM_DATA_LEAK", "EVENT_DATA_CORRUPTION"],
        "applicable_business_keys": ["business_15_samsung_singularity_center", "business_17_samsung_space_station_research"]
    },
    "UPGRADE_COGNITIVE_SHIELD": {
        "name": "Когнитивный Щит Сверхразума",
        "description": "Защищает развивающийся ИИ от несанкционированного ментального или программного вмешательства.",
        "price": 3000000, # Увеличена цена
        "type": "ai_integrity",
        "prevents_event_keys": ["EVENT_AI_ETHICS_PROTEST", "EVENT_AI_MALFUNCTION"],
        "applicable_business_keys": ["business_15_samsung_singularity_center"]
    },

    # Апгрейды для Космических бизнесов (business_13, 16, 17, 18)
    "UPGRADE_ASTEROID_DEFLECTOR": {
        "name": "Астероидный дефлектор",
        "description": "Защищает космические станции и корабли от столкновений с астероидами.",
        "price": 5000000,
        "type": "space_defense",
        "prevents_event_keys": ["EVENT_ASTEROID_IMPACT"],
        "applicable_business_keys": [
            "business_13_samsung_commercial_space_agency",
            "business_16_interstellar_resource_extraction",
            "business_17_samsung_space_station_research"
        ]
    },
    "UPGRADE_GRAVITY_STABILIZER": {
        "name": "Гравитационный стабилизатор",
        "description": "Обеспечивает стабильность платформ в условиях переменной гравитации.",
        "price": 7500000,
        "type": "space_utility",
        "prevents_event_keys": ["EVENT_GRAVITY_FLUCTUATION"],
        "applicable_business_keys": [
            "business_13_samsung_commercial_space_agency",
            "business_16_interstellar_resource_extraction",
            "business_17_samsung_space_station_research",
            "business_18_samsung_multiverse_masters"
        ]
    },
    "UPGRADE_DIMENSIONAL_ANCHOR": {
        "name": "Пространственный Якорь",
        "description": "Стабилизирует межпространственные порталы, предотвращая неконтролируемые открытия.",
        "price": 10000000,
        "type": "multiverse_control",
        "prevents_event_keys": ["EVENT_DIMENSIONAL_DRIFT"],
        "applicable_business_keys": ["business_18_samsung_multiverse_masters"]
    }
}


# ==============================================================================
# --- Данные о БАНКЕ ---
# ==============================================================================
BANK_DATA = {
    0: {"name": "Мини-копилка", "price": 0, "max_capacity": 1000}, # Начальный уровень (для тех, у кого нет банка)
    1: {"name": "Обычный Сейф", "price": 500, "max_capacity": 5000},
    2: {"name": "Улучшенный Сейф", "price": 1000, "max_capacity": 10000},
    3: {"name": "Банковская Ячейка", "price": 2500, "max_capacity": 25000},
    4: {"name": "Крипто-кошелек Базовый", "price": 5000, "max_capacity": 50000},
    5: {"name": "Электронный Сейф Samsung", "price": 10000, "max_capacity": 100000},
    6: {"name": "Защищенное Хранилище Galaxy", "price": 25000, "max_capacity": 250000},
    7: {"name": "Частное Хранилище OneCoin", "price": 50000, "max_capacity": 500000},
    8: {"name": "Виртуальный Трезор Samsung", "price": 100000, "max_capacity": 1000000},
    9: {"name": "Дата-Центр Безопасности", "price": 200000, "max_capacity": 2000000},
    10: {"name": "Облачное Хранилище 'Гермес'", "price": 400000, "max_capacity": 4000000},
    11: {"name": "Блокчейн-Хранилище 'OneChain'", "price": 800000, "max_capacity": 8000000},
    12: {"name": "Глобальный Репозиторий Данных", "price": 1500000, "max_capacity": 15000000},
    13: {"name": "Межпланетный Депозитарий", "price": 3000000, "max_capacity": 30000000},
    14: {"name": "Фонд 'Галактический Капитал'", "price": 6000000, "max_capacity": 60000000},
    15: {"name": "Астероидный Сейф 'Один-Плюс'", "price": 12000000, "max_capacity": 120000000},
    16: {"name": "Космический Резерв 'Титан'", "price": 24000000, "max_capacity": 240000000},
    17: {"name": "Ресурсная Станция 'Эврика'", "price": 48000000, "max_capacity": 480000000},
    18: {"name": "Межгалактический Банк 'Вечный'", "price": 90000000, "max_capacity": 900000000},
    19: {"name": "Хранилище Мультивселенной", "price": 150000000, "max_capacity": 1000000000}, # 1 миллиард
    # Добавление уровней с 20 по 30
    20: {"name": "Сингулярный Финансовый Хаб", "price": 250000000, "max_capacity": 2000000000}, # 2 миллиарда
    21: {"name": "Межпространственный Банк", "price": 400000000, "max_capacity": 4000000000}, # 4 миллиарда
    22: {"name": "Космическая Кредитная Лига", "price": 600000000, "max_capacity": 8000000000}, # 8 миллиардов
    23: {"name": "Галактическая Валютная Биржа", "price": 900000000, "max_capacity": 16000000000}, # 16 миллиардов
    24: {"name": "Ресурсный Фонд Ориона", "price": 1300000000, "max_capacity": 32000000000}, # 32 миллиарда
    25: {"name": "Банк 'Край Вселенной'", "price": 1800000000, "max_capacity": 64000000000}, # 64 миллиарда
    26: {"name": "Корона Империи Samsung", "price": 2500000000, "max_capacity": 128000000000}, # 128 миллиардов
    27: {"name": "Хранилище 'Омега'", "price": 3500000000, "max_capacity": 256000000000}, # 256 миллиардов
    28: {"name": "Нексус Финансовых Потоков", "price": 5000000000, "max_capacity": 512000000000}, # 512 миллиардов
    29: {"name": "Абсолютный Банк OneCoin", "price": 7500000000, "max_capacity": 1000000000000}, # 1 триллион
    30: {"name": "Квантовое Хранилище Сингулярности: Властелин OneCoin", "price": 10000000000, "max_capacity": 2000000000000} # 2 триллиона (или можно установить до 1 МЛРД, если 30 уровень не должен быть таким высоким)
    # Я сделал 30 уровень с 2 триллионами, так как "1МЛРД" для 30 уровня звучал немного скромно после уже 19-го уровня.
    # Если ты хочешь ровно 1 млрд на 30 уровне, то логику уровней можно пересчитать.
    # Сейчас это довольно агрессивный рост.
}


# ==============================================================================
# --- Данные о Случайных Событиях для Бизнесов ---
# ==============================================================================
# type: 'positive' или 'negative'
# effect_multiplier_min/max: Процент от base_income_per_hour
# affected_business_keys: Список ключей бизнесов, на которые может влиять это событие. "all" если для всех.
# protection_upgrade_key: Ключ апгрейда из BUSINESS_UPGRADES, который предотвращает это событие (с 70% шансом)
BUSINESS_EVENTS = [
    # --- НЕГАТИВНЫЕ СОБЫТИЯ ---
    {
        "key": "EVENT_FIRE_SMALL",
        "name": "Небольшое возгорание!",
        "description": "В вашем помещении произошло небольшое возгорание. Требуется срочное вмешательство!",
        "type": "negative",
        "effect_multiplier_min": -0.05, # -5% от базового дохода
        "effect_multiplier_max": -0.10, # -10%
        "affected_business_keys": [f"business_{i}_" for i in range(1, 19)], # Все бизнесы
        "protection_upgrade_key": "UPGRADE_FIRE_EXTINGUISHER"
    },
    {
        "key": "EVENT_FIRE_MEDIUM",
        "name": "Серьезный пожар!",
        "description": "Крупное возгорание нанесло значительный ущерб. Потребуется время на восстановление.",
        "type": "negative",
        "effect_multiplier_min": -0.10, # -10%
        "effect_multiplier_max": -0.15, # -15%
        "affected_business_keys": [f"business_{i}_" for i in range(1, 19)], # Все бизнесы
        "protection_upgrade_key": "UPGRADE_FIRE_EXTINGUISHER"
    },
    {
        "key": "EVENT_THEFT_MINOR",
        "name": "Мелкая кража!",
        "description": "Произошла мелкая кража оборудования или товара. Небольшие потери.",
        "type": "negative",
        "effect_multiplier_min": -0.03, # -3% от базового дохода
        "effect_multiplier_max": -0.07, # -7%
        "affected_business_keys": [
            "business_1_home_samsung_region_change", "business_3_galaxy_premium_accessories_boutique",
            "business_5_galaxy_trade_in_center", "business_6_official_samsung_service_center",
            "business_7_it_oneui_solutions_ai", "business_8_black_market_onecoin_exclusive"
        ],
        "protection_upgrade_key": "UPGRADE_MOTION_SENSOR"
    },
    {
        "key": "EVENT_THEFT_MEDIUM",
        "name": "Крупное ограбление!",
        "description": "Серьезное ограбление привело к значительным потерям.",
        "type": "negative",
        "effect_multiplier_min": -0.08,
        "effect_multiplier_max": -0.12,
        "affected_business_keys": [
            "business_3_galaxy_premium_accessories_boutique", "business_5_galaxy_trade_in_center",
            "business_6_official_samsung_service_center", "business_7_it_oneui_solutions_ai",
            "business_8_black_market_onecoin_exclusive", "business_9_samsung_electronics_manufacturing_plant"
        ],
        "protection_upgrade_key": "UPGRADE_ALARM_SYSTEM"
    },
    {
        "key": "EVENT_VANDALISM",
        "name": "Акт вандализма!",
        "description": "Ваш бизнес подвергся акту вандализма. Нужен ремонт.",
        "type": "negative",
        "effect_multiplier_min": -0.04,
        "effect_multiplier_max": -0.09,
        "affected_business_keys": [
            "business_1_home_samsung_region_change", "business_3_galaxy_premium_accessories_boutique",
            "business_4_eco_recycling_samsung", "business_5_galaxy_trade_in_center",
            "business_6_official_samsung_service_center"
        ],
        "protection_upgrade_key": "UPGRADE_CCTV_NETWORK" # Или ALARM_SYSTEM
    },
    {
        "key": "EVENT_POWER_OUTAGE",
        "name": "Отключение электричества!",
        "description": "В районе вашего бизнеса произошел сбой электроснабжения. Работа остановлена.",
        "type": "negative",
        "effect_multiplier_min": -0.06,
        "effect_multiplier_max": -0.11,
        "affected_business_keys": [f"business_{i}_" for i in range(1, 19) if i not in [2]],
        "protection_upgrade_key": "UPGRADE_EMERGENCY_GENERATOR"
    },
    {
        "key": "EVENT_MINOR_INJURY",
        "name": "Небольшая травма персонала!",
        "description": "Сотрудник получил легкую травму. Работа временно замедлилась.",
        "type": "negative",
        "effect_multiplier_min": -0.03,
        "effect_multiplier_max": -0.05,
        "affected_business_keys": [f"business_{i}_" for i in range(1, 19) if i not in [2]],
        "protection_upgrade_key": "UPGRADE_FIRST_AID_POST"
    },

    # Негативные события для мобильных бизнесов (business_2)
    {
        "key": "EVENT_VEHICLE_BREAKDOWN_TIRE",
        "name": "Прокол колеса фургона!",
        "description": "Мобильный фургон столкнулся с проколом колеса. Задержка в работе.",
        "type": "negative",
        "effect_multiplier_min": -0.05,
        "effect_multiplier_max": -0.08,
        "affected_business_keys": ["business_2_mobile_galaxy_repair"],
        "protection_upgrade_key": "UPGRADE_SPARE_TIRE"
    },
    {
        "key": "EVENT_VEHICLE_NO_FUEL",
        "name": "Закончился бензин!",
        "description": "Фургон остановился из-за отсутствия топлива. Потерянное время.",
        "type": "negative",
        "effect_multiplier_min": -0.03,
        "effect_multiplier_max": -0.06,
        "affected_business_keys": ["business_2_mobile_galaxy_repair"],
        "protection_upgrade_key": "UPGRADE_FUEL_CANISTER"
    },
    {
        "key": "EVENT_VEHICLE_MAJOR_BREAKDOWN",
        "name": "Серьезная поломка фургона!",
        "description": "Двигатель фургона вышел из строя. Дорогой ремонт и простой.",
        "type": "negative",
        "effect_multiplier_min": -0.10,
        "effect_multiplier_max": -0.15,
        "affected_business_keys": ["business_2_mobile_galaxy_repair"],
        "protection_upgrade_key": "UPGRADE_ADVANCED_DIAGNOSTICS"
    },
    {
        "key": "EVENT_VEHICLE_THEFT",
        "name": "Угон мобильного пункта!",
        "description": "Ваш фургон угнали! Огромные потери.",
        "type": "negative",
        "effect_multiplier_min": -0.15,
        "effect_multiplier_max": -0.20, # Самое болезненное событие
        "affected_business_keys": ["business_2_mobile_galaxy_repair"],
        "protection_upgrade_key": "UPGRADE_GPS_TRACKER"
    },

    # Негативные события для утилизации (business_4)
    {
        "key": "EVENT_OVERLOAD_WASTE",
        "name": "Переполнение отходами!",
        "description": "Пункт утилизации переполнен, замедление работы.",
        "type": "negative",
        "effect_multiplier_min": -0.08,
        "effect_multiplier_max": -0.12,
        "affected_business_keys": ["business_4_eco_recycling_samsung"],
        "protection_upgrade_key": "UPGRADE_WASTE_COMPACTOR"
    },
    {
        "key": "EVENT_TOXIC_SPILL",
        "name": "Утечка токсичных веществ!",
        "description": "На пункте утилизации произошла утечка опасных веществ. Требуется срочная дезинфекция.",
        "type": "negative",
        "effect_multiplier_min": -0.10,
        "effect_multiplier_max": -0.15,
        "affected_business_keys": ["business_4_eco_recycling_samsung"],
        "protection_upgrade_key": "UPGRADE_HAZARDOUS_WASTE_DISPOSAL"
    },
    {
        "key": "EVENT_HEALTH_HAZARD",
        "name": "Риск для здоровья персонала!",
        "description": "Обнаружены проблемы с качеством воздуха. Персонал временно отстранен.",
        "type": "negative",
        "effect_multiplier_min": -0.07,
        "effect_multiplier_max": -0.10,
        "affected_business_keys": ["business_4_eco_recycling_samsung"],
        "protection_upgrade_key": "UPGRADE_AIR_FILTRATION"
    },

    # Негативные события для Заводов (business_9, 10, 11)
    {
        "key": "EVENT_PRODUCTION_DEFECTS_MINOR",
        "name": "Незначительный брак производства!",
        "description": "Часть продукции не соответствует стандартам. Небольшие потери.",
        "type": "negative",
        "effect_multiplier_min": -0.03,
        "effect_multiplier_max": -0.07,
        "affected_business_keys": [
            "business_9_samsung_electronics_manufacturing_plant",
            "business_10_samsung_ai_drone_factory",
            "business_11_samsung_main_tank_factory"
        ],
        "protection_upgrade_key": "UPGRADE_ROBOTIC_ARM_CALIBRATION"
    },
    {
        "key": "EVENT_PRODUCTION_DEFECTS_MAJOR",
        "name": "Критический брак производства!",
        "description": "Крупная партия продукции оказалась бракованной. Большие убытки.",
        "type": "negative",
        "effect_multiplier_min": -0.10,
        "effect_multiplier_max": -0.15,
        "affected_business_keys": [
            "business_9_samsung_electronics_manufacturing_plant",
            "business_10_samsung_ai_drone_factory",
            "business_11_samsung_main_tank_factory"
        ],
        "protection_upgrade_key": "UPGRADE_AUTOMATED_QUALITY_CONTROL"
    },
    {
        "key": "EVENT_SABOTAGE",
        "name": "Акт саботажа!",
        "description": "Конкуренты или шпионы повредили оборудование. Долгий простой.",
        "type": "negative",
        "effect_multiplier_min": -0.12,
        "effect_multiplier_max": -0.17,
        "affected_business_keys": [
            "business_9_samsung_electronics_manufacturing_plant",
            "business_10_samsung_ai_drone_factory",
            "business_11_samsung_main_tank_factory",
            "business_14_samsung_nuclear_reactor" # Для реактора тоже актуально
        ],
        "protection_upgrade_key": "UPGRADE_HEAVY_SECURITY_PERIMETER"
    },
    {
        "key": "EVENT_SPY_DISCOVERY",
        "name": "Обнаружен шпион!",
        "description": "Внедренный шпион замечен. Операции приостановлены для контрразведки.",
        "type": "negative",
        "effect_multiplier_min": -0.07,
        "effect_multiplier_max": -0.10,
        "affected_business_keys": [
            "business_10_samsung_ai_drone_factory",
            "business_11_samsung_main_tank_factory",
            "business_12_global_samsung_innovation_hub"
        ],
        "protection_upgrade_key": "UPGRADE_ADVANCED_CAMOFLAGE"
    },

    # Негативные события для Ядерного Реактора (business_14)
    {
        "key": "EVENT_RADIATION_LEAK",
        "name": "Небольшая утечка радиации!",
        "description": "Обнаружена незначительная утечка радиации. Требуется срочная локализация.",
        "type": "negative",
        "effect_multiplier_min": -0.10,
        "effect_multiplier_max": -0.15,
        "affected_business_keys": ["business_14_samsung_nuclear_reactor"],
        "protection_upgrade_key": "UPGRADE_RADIATION_SHIELDING"
    },
    {
        "key": "EVENT_REACTOR_OVERHEAT",
        "name": "Перегрев реактора!",
        "description": "Системы охлаждения с трудом справляются. Есть риск критической ситуации.",
        "type": "negative",
        "effect_multiplier_min": -0.12,
        "effect_multiplier_max": -0.17,
        "affected_business_keys": ["business_14_samsung_nuclear_reactor"],
        "protection_upgrade_key": "UPGRADE_COOLING_SYSTEM_OVERHAUL"
    },

    # Негативные события для Центра Сингулярности (business_15)
    {
        "key": "EVENT_AI_CYBER_ATTACK",
        "name": "Кибератака на ИИ-ядро!",
        "description": "Ваши ИИ-системы подверглись массированной кибератаке. Требуется изоляция.",
        "type": "negative",
        "effect_multiplier_min": -0.10,
        "effect_multiplier_max": -0.17,
        "affected_business_keys": ["business_15_samsung_singularity_center"],
        "protection_upgrade_key": "UPGRADE_AI_FIREWALL_QUANTUM"
    },
    {
        "key": "EVENT_QUANTUM_DATA_LEAK",
        "name": "Квантовая утечка данных!",
        "description": "Произошла частичная утечка критических квантовых данных. Репутационные потери.",
        "type": "negative",
        "effect_multiplier_min": -0.12,
        "effect_multiplier_max": -0.15,
        "affected_business_keys": ["business_15_samsung_singularity_center", "business_17_samsung_space_station_research"],
        "protection_upgrade_key": "UPGRADE_DATA_ENCRYPTION_INTERSTELLAR"
    },
    {
        "key": "EVENT_AI_ETHICS_PROTEST",
        "name": "Протесты Этиков ИИ",
        "description": "Общественность возмущена последними разработками ИИ, требуется время на 'разъяснения'.",
        "type": "negative",
        "effect_multiplier_min": -0.10,
        "effect_multiplier_max": -0.15,
        "affected_business_keys": ["business_15_samsung_singularity_center"],
        "protection_upgrade_key": "UPGRADE_COGNITIVE_SHIELD"
    },
    {
        "key": "EVENT_AI_MALFUNCTION",
        "name": "Неисправность сверхразума!",
        "description": "В работе ИИ-ядра произошел сбой. Система требует перезагрузки.",
        "type": "negative",
        "effect_multiplier_min": -0.14,
        "effect_multiplier_max": -0.18,
        "affected_business_keys": ["business_15_samsung_singularity_center"],
        "protection_upgrade_key": "UPGRADE_COGNITIVE_SHIELD"
    },

    # Негативные события для Космических бизнесов (business_13, 16, 17, 18)
    {
        "key": "EVENT_ASTEROID_IMPACT",
        "name": "Удар астероида!",
        "description": "Ваша космическая станция или корабль получили повреждения от столкновения с астероидом.",
        "type": "negative",
        "effect_multiplier_min": -0.10,
        "effect_multiplier_max": -0.15,
        "affected_business_keys": [
            "business_13_samsung_commercial_space_agency",
            "business_16_interstellar_resource_extraction",
            "business_17_samsung_space_station_research"
        ],
        "protection_upgrade_key": "UPGRADE_ASTEROID_DEFLECTOR"
    },
    {
        "key": "EVENT_GRAVITY_FLUCTUATION",
        "name": "Гравитационная аномалия!",
        "description": "Нестабильность гравитации вызвала перебои в работе. Требуется стабилизация.",
        "type": "negative",
        "effect_multiplier_min": -0.08,
        "effect_multiplier_max": -0.12,
        "affected_business_keys": [
            "business_13_samsung_commercial_space_agency",
            "business_16_interstellar_resource_extraction",
            "business_17_samsung_space_station_research",
            "business_18_samsung_multiverse_masters"
        ],
        "protection_upgrade_key": "UPGRADE_GRAVITY_STABILIZER"
    },
    {
        "key": "EVENT_DIMENSIONAL_DRIFT",
        "name": "Пространственный дрейф!",
        "description": "Межпространственный портал вышел из-под контроля. Опасное смещение!",
        "type": "negative",
        "effect_multiplier_min": -0.15,
        "effect_multiplier_max": -0.20,
        "affected_business_keys": ["business_18_samsung_multiverse_masters"],
        "protection_upgrade_key": "UPGRADE_DIMENSIONAL_ANCHOR"
    },
    {
        "key": "EVENT_UNAUTHORIZED_ACCESS",
        "name": "Несанкционированный доступ!",
        "description": "Обнаружена попытка несанкционированного доступа к вашим космическим системам. Защита сработала, но есть временные сбои.",
        "type": "negative",
        "effect_multiplier_min": -0.07,
        "effect_multiplier_max": -0.11,
        "affected_business_keys": [
            "business_12_global_samsung_innovation_hub",
            "business_13_samsung_commercial_space_agency",
            "business_17_samsung_space_station_research",
            "business_18_samsung_multiverse_masters"
        ],
        "protection_upgrade_key": "UPGRADE_DATA_ENCRYPTION_INTERSTELLAR" # Или какой-то общий щит
    },

    # --- ПОЗИТИВНЫЕ СОБЫТИЯ ---
    {
        "key": "EVENT_BLOGGER_VISIT",
        "name": "К вам зашёл блогер!",
        "description": "Известный блогер посетил ваш бизнес и снял обзор. Большая реклама!",
        "type": "positive",
        "effect_multiplier_min": 0.05, # +5% к базовому доходу
        "effect_multiplier_max": 0.10, # +10%
        "affected_business_keys": [
            "business_1_home_samsung_region_change", "business_2_mobile_galaxy_repair",
            "business_3_galaxy_premium_accessories_boutique", "business_5_galaxy_trade_in_center",
            "business_6_official_samsung_service_center"
        ]
    },
    {
        "key": "EVENT_LOCAL_MEDIA_COVERAGE",
        "name": "Освещение в местных СМИ!",
        "description": "Позитивная статья о вашем бизнесе в местной газете или на ТВ.",
        "type": "positive",
        "effect_multiplier_min": 0.03,
        "effect_multiplier_max": 0.07,
        "affected_business_keys": [
            "business_1_home_samsung_region_change", "business_2_mobile_galaxy_repair",
            "business_3_galaxy_premium_accessories_boutique", "business_4_eco_recycling_samsung",
            "business_5_galaxy_trade_in_center", "business_6_official_samsung_service_center"
        ]
    },
    {
        "key": "EVENT_SAMSUNG_REPRESENTATIVE_VISIT",
        "name": "Приезд представителя Samsung!",
        "description": "Высокопоставленный представитель Samsung лично посетил ваш бизнес и остался доволен.",
        "type": "positive",
        "effect_multiplier_min": 0.10,
        "effect_multiplier_max": 0.15,
        "affected_business_keys": [
            "business_3_galaxy_premium_accessories_boutique", "business_6_official_samsung_service_center",
            "business_7_it_oneui_solutions_ai", "business_9_samsung_electronics_manufacturing_plant",
            "business_12_global_samsung_innovation_hub"
        ]
    },
    {
        "key": "EVENT_EC_ADMIN_CHECK",
        "name": "Проверка администрации EC!",
        "description": "Администрация Евразийского Содружества одобрила вашу деятельность и выдала грант.",
        "type": "positive",
        "effect_multiplier_min": 0.15,
        "effect_multiplier_max": 0.20,
        "affected_business_keys": ["business_4_eco_recycling_samsung"]
    },
    {
        "key": "EVENT_SINGULARITY_BREAKTHROUGH",
        "name": "Прорыв Сингулярности: Осознание!",
        "description": "Ваша нейросеть достигла нового уровня самосознания, открывая новые возможности!",
        "type": "positive",
        "effect_multiplier_min": 0.15, # +15%
        "effect_multiplier_max": 0.20, # +20%
        "affected_business_keys": ["business_15_samsung_singularity_center"]
    },
    {
        "key": "EVENT_GALACTIC_PARTNERSHIP",
        "name": "Заключено Галактическое Партнерство",
        "description": "Крупная межзвездная корпорация подписала контракт на использование ваших ИИ-решений.",
        "type": "positive",
        "effect_multiplier_min": 0.10,
        "effect_multiplier_max": 0.18,
        "affected_business_keys": ["business_13_samsung_commercial_space_agency", "business_15_samsung_singularity_center", "business_16_interstellar_resource_extraction", "business_17_samsung_space_station_research", "business_18_samsung_multiverse_masters"]
    },
    {
        "key": "EVENT_BLACKMARKET_BOOM",
        "name": "Бум на черном рынке!",
        "description": "Внезапный спрос на эксклюзивные технологии взвинтил цены на теневом рынке.",
        "type": "positive",
        "effect_multiplier_min": 0.10,
        "effect_multiplier_max": 0.16,
        "affected_business_keys": ["business_8_black_market_onecoin_exclusive"]
    },
    {
        "key": "EVENT_GOVERNMENT_CONTRACT",
        "name": "Выгодный госзаказ!",
        "description": "Ваш завод получил крупный и прибыльный государственный контракт.",
        "type": "positive",
        "effect_multiplier_min": 0.12,
        "effect_multiplier_max": 0.18,
        "affected_business_keys": [
            "business_9_samsung_electronics_manufacturing_plant",
            "business_10_samsung_ai_drone_factory",
            "business_11_samsung_main_tank_factory"
        ]
    },
    {
        "key": "EVENT_SCIENTIFIC_DISCOVERY",
        "name": "Научное открытие!",
        "description": "В вашей лаборатории совершено открытие, которое принесет огромную прибыль.",
        "type": "positive",
        "effect_multiplier_min": 0.10,
        "effect_multiplier_max": 0.20,
        "affected_business_keys": ["business_12_global_samsung_innovation_hub", "business_17_samsung_space_station_research"]
    },
    {
        "key": "EVENT_ENERGY_SURPLUS",
        "name": "Энергетический профицит!",
        "description": "Ваш ядерный реактор производит избыток энергии, которую можно выгодно продать.",
        "type": "positive",
        "effect_multiplier_min": 0.15,
        "effect_multiplier_max": 0.20,
        "affected_business_keys": ["business_14_samsung_nuclear_reactor"]
    },
    {
        "key": "EVENT_NEW_DIMENSION_DISCOVERY",
        "name": "Открытие нового измерения!",
        "description": "Вам удалось обнаружить новое, богатое ресурсами измерение. Неограниченные возможности!",
        "type": "positive",
        "effect_multiplier_min": 0.18,
        "effect_multiplier_max": 0.25, # Чуть больше для топового бизнеса
        "affected_business_keys": ["business_18_samsung_multiverse_masters"]
    }
]