# commands_data.py

# Этот словарь будет содержать все категории команд и их команды.
# Ключи словаря (например, "семья", "бизнес") будут использоваться в команде /help <ключ>
# Значения - это словари с "title" (отображаемое название категории),
# "description" (короткое описание категории) и "commands" (сам список команд).

COMMAND_CATEGORIES = {
    "основные": {
        "title": "✨ Основные команды",
        "description": "Общие команды для взаимодействия с ботом и просмотра базовой информации.",
        "commands": {
            "🚀 /start": "Начать взаимодействие с ботом.",
            "ℹ️ /help": "Показать справку по командам. Используйте /help <категория> для подробностей.",
            "📲 /oneui": "Улучшить/понизить версию.",
            "👤 /profile": "Показать ваш игровой профиль.",
            "💰 /myonecoins": "Показать ваш текущий баланс OneCoin.",
            "📱 /myphones": "Показать информацию о телефоне/ах.",
            "🏆 /achievements": "Показать достижения."
        }
    },
    "семья": {
        "title": "👨‍👩‍👧‍👦 Команды для семьи",
        "description": "Управление вашей семьей, взаимодействие с другими игроками и семейные активности.",
        "commands": {
            "➕ /familycreate <имя>": "Создать новую семью с указанным названием.",
            "➡️ /familyjoin <имя>": "Вступить в существующую семью по её названию.",
            "🚪 /familyleave": "Покинуть текущую семью.",
            "👢 /familykick [ID или ответ]": "Выгнать пользователя из семьи (для лидера).",
            "✏️ /familyrename <новое имя>": "Переименовать вашу семью (для лидера).",
            "📊 /familystats [имя семьи]": "Показать информацию о вашей семье или о конкретной семье.",
            "🏆 /topfamilies": "Показать глобальный рейтинг семей.",
            "📜 /familylog": "Показать лог активности вашей семьи."
        }
    },
    "бизнес": {
        "title": "📈 Команды для бизнеса",
        "description": "Покупка, управление и развитие бизнесов для получения дохода.",
        "commands": {
            "🛍️ /buybusiness <ключ>": "Купить выбранный бизнес.",
            "🏪 /businessshop": "Показать список всех доступных бизнесов для покупки.",
            "💼 /mybusinesses": "Показать информацию о ваших бизнесах.",
            "🏦 /mybank": "Показать информацию о банке.",
            "⬆️ /upgradebank": "Улучшить ваш банк.",
            "🏧 /withdrawbank <сумма или all>": "Вывести OneCoin с вашего банковского счета на основной баланс.",
            "👥 /hirestaff <ID бизнеса> <кол-во>": "Нанять сотрудников для бизнеса.",
            "🔥 /firestaff <ID бизнеса> <кол-во>": "Уволить сотрудников из выбранного бизнеса.",
            "⚙️ /buyupgrade <ID бизнеса> [ключ]": "Показать/купить апгрейды для бизнеса.",
            "🚀 /upgradebusiness <ID бизнеса>": "Улучшить бизнес.",
            "💸 /sellbusiness <ID бизнеса>": "Продать бизнес."
        }
    },
    "телефон": {
        "title": "📱 Команды для телефона",
        "description": "Управление вашим смартфоном OneUI, покупка и улучшение его компонентов.",
        "commands": {
            "🛍️ /phoneshop [серия]": "Каталог телефонов.",
            "💳 /buyphone <ключ_модели> <цвет>": "Купить телефон.",
            "💸 /sellphone <ID телефона>": "Продать телефон.",
            "🔩 /itemshop [категория] [серия]": "Каталог предметов (компоненты, чехлы, память).",
            "🛒 /buyitem <ключ_предмета> [кол-во]": "Купить предмет.",
            "📱 /myphones": "Ваши телефоны.",
            "🎒 /myitems": "Ваш инвентарь предметов.",
            "🛡️ /equipcase <ID телефона> <ID чехла>": "Надеть чехол.",
            "💨 /removecase <ID телефона>": "Снять чехол.",
            "🔋 /chargephone <ID телефона>": "Зарядить телефон.",
            "💾 /upgradememory <ID телефона>": "Улучшить память.",
            "🛠️ /craftphone <серия>": "Собрать телефон из компонентов.",
            "📄 /insurephone <ID телеф.> [срок]": "Застраховать/продлить страховку телефона.",
            "🔧 /repairphone <ID телефона>": "Починить телефон.",
            "💰 /sellitem <ID предмета> [кол-во]": "Продать предмет из инвентаря.",
            "💰 /sellcase <ID чехла>": "Продать чехол из инвентаря.",
            "🔄 /keepwonphone <ID старого тел.>": "Обменять выигранный телефон на старый.",
            "💲 /sellwonphone": "Продать выигранный телефон."
        }
    },
    "маркет": {
        "title": "🏪 Команды для рынка",
        "description": "Покупка и продажа предметов на общедоступном рынке.",
        "commands": {
            "📊 /market": "Показать текущие предложения на рынке.",
            "💳 /buyitem <ключ_товара>": "Купить товар с рынка."
        }
    },
    "рулетка": {
        "title": "🎰 Команды для рулетки",
        "description": "Испытайте удачу и выигрывайте OneCoin или редкие телефоны.",
        "commands": {
            "🎲 /roulette": "Сделать бесплатный спин в рулетке.",
            "🎟️ /buyitem roulette_spin": "Купить дополнительный спин для рулетки."
        }
    },
    "черный_рынок": {
        "title": "🥷 Команды для Черного Рынка",
        "description": "Тайные сделки, редкие и эксклюзивные телефоны и компоненты.",
        "commands": {
            "🕶️ /bm": "Показать текущие предложения на Черном Рынке.",
            "🛒 /bmbuy <номер_слота>": "Купить предмет из указанного слота на Черном Рынке."
        }
    },
    "бонусы": {
        "title": "🌟 Бонусные команды",
        "description": "Просмотр информации о ежедневных бонусах и стрик-системе.",
        "commands": {
            "✨ /bonus": "Показать информацию о вашем текущем бонусном множителе.",
            "🔥 /mystreak": "Показать информацию о вашей ежедневной серии входа (стрике).",
            "🎟️ /buyitem bonus_attempt": "Купить дополнительную попытку /bonus."
        }
    },
}
