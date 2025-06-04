# reminders_logic.py

from datetime import datetime
from .database import get_user_data, get_user_last_activity_in_chat, update_user_last_activity_in_chat
from . import utils
from . import config
from . import onecoin_logic
from . import bonus_logic
from . import roulette_logic
from . import phone_logic # Добавлен импорт для доступа к логике телефона (если потребуется для кулдаунов)

async def get_reminders_for_chat(user_id, chat_id, user_data=None):
    """
    Собирает напоминания для конкретного чата.
    """
    if user_data is None:
        user_data = get_user_data(user_id)

    now = utils.get_moscow_time()
    now_ts = now.timestamp()
    
    reminder_lines = []

    # 1. Напоминание для /oneui
    oneui_status_line = None
    oneui_phantom_lock_until_ts = user_data.get('oneui_phantom_lock_until_ts')

    if oneui_phantom_lock_until_ts and now_ts < oneui_phantom_lock_until_ts:
        phantom_lock_end_dt = datetime.fromtimestamp(oneui_phantom_lock_until_ts, tz=config.MOSCOW_TZ)
        time_left_str = utils.format_time_left_till_datetime(phantom_lock_end_dt, now)
        oneui_status_line = (f"❌ /oneui (фантомная блокировка) будет доступен после "
                             f"{utils.format_datetime_msk(phantom_lock_end_dt)} ({time_left_str}).")
    else:
        # Используем существующую логику phone_logic для определения доступности /oneui
        # Предполагается, что phone_logic.get_oneui_command_status или подобная функция
        # может вернуть время следующей доступности или None/0 если доступно.
        # В user_data может храниться 'last_oneui_change_time'
        
        last_oneui_change_time = user_data.get('last_oneui_change_time', 0)
        
        # Логика определения кулдауна для /oneui.
        # Она может быть сложной и зависеть от стрейка, как в phone_logic.py
        # Для примера, возьмем базовый кулдаун, но в идеале эту логику нужно синхронизировать
        # или вызывать из phone_logic.
        
        # Попытка получить next_oneui_eligible_ts, если phone_logic его устанавливает.
        # Это предпочтительный вариант.
        next_oneui_eligible_ts = user_data.get('next_oneui_eligible_ts') 

        if next_oneui_eligible_ts is None:
            # Если phone_logic не устанавливает 'next_oneui_eligible_ts',
            # пытаемся рассчитать на основе 'last_oneui_change_time' и базового кулдауна.
            # ВАЖНО: Это упрощение. Реальный кулдаун /oneui в phone_logic.py сложнее
            # и зависит от стрейка (ONEUI_COOLDOWN_BASE, ONEUI_COOLDOWN_STREAK_BONUS).
            # Чтобы напоминание было точным, эта логика должна точно соответствовать phone_logic.py
            # или phone_logic.py должен сохранять точное время следующей доступности.
            
            # Примерный расчет (может быть неточным без полной логики из phone_logic.py):
            current_streak = user_data.get('streak_days_oneui', 0)
            cooldown_hours = config.ONEUI_COOLDOWN_BASE
            if current_streak >= 7: # Пример упрощенного бонуса от стрейка
                cooldown_hours -= config.ONEUI_COOLDOWN_STREAK_BONUS.get(7, 0) # Уменьшаем на бонус за 7 дней, если есть
            
            actual_cooldown_seconds = cooldown_hours * 3600
            next_oneui_eligible_ts = last_oneui_change_time + actual_cooldown_seconds

        if now_ts >= next_oneui_eligible_ts:
            oneui_status_line = "✅ /oneui доступен для изменения версии."
        else:
            next_oneui_avail_dt = datetime.fromtimestamp(next_oneui_eligible_ts, tz=config.MOSCOW_TZ)
            time_left_str = utils.format_time_left_till_datetime(next_oneui_avail_dt, now)
            oneui_status_line = (f"❌ /oneui будет доступен после "
                                 f"{utils.format_datetime_msk(next_oneui_avail_dt)} ({time_left_str}).")
    
    if oneui_status_line:
        reminder_lines.append(oneui_status_line)

    # 2. Напоминание для /onecoin
    next_onecoin_time = onecoin_logic.get_next_onecoin_time(user_data)
    if now_ts >= next_onecoin_time:
        reminder_lines.append("✅ /onecoin доступен для получения.")
    else:
        dt_next_onecoin = datetime.fromtimestamp(next_onecoin_time, tz=config.MOSCOW_TZ)
        time_left_str = utils.format_time_left_till_datetime(dt_next_onecoin, now)
        reminder_lines.append(f"❌ /onecoin будет доступен после {utils.format_datetime_msk(dt_next_onecoin)} ({time_left_str}).")

    # 3. Напоминание для /bonus
    next_bonus_time = bonus_logic.get_next_bonus_time(user_data)
    if now_ts >= next_bonus_time:
        reminder_lines.append("✅ /bonus доступен для получения.")
    else:
        dt_next_bonus = datetime.fromtimestamp(next_bonus_time, tz=config.MOSCOW_TZ)
        time_left_str = utils.format_time_left_till_datetime(dt_next_bonus, now)
        reminder_lines.append(f"❌ /bonus будет доступен после {utils.format_datetime_msk(dt_next_bonus)} ({time_left_str}).")

    # 4. Напоминание для /roulette
    next_roulette_time = roulette_logic.get_next_roulette_time(user_data, chat_id) # roulette зависит от chat_id
    if now_ts >= next_roulette_time:
        reminder_lines.append("✅ /roulette доступна для игры.")
    else:
        dt_next_roulette = datetime.fromtimestamp(next_roulette_time, tz=config.MOSCOW_TZ)
        time_left_str = utils.format_time_left_till_datetime(dt_next_roulette, now)
        reminder_lines.append(f"❌ /roulette будет доступна после {utils.format_datetime_msk(dt_next_roulette)} ({time_left_str}).")
    
    return reminder_lines


async def get_all_reminders_for_user(user_id, user_name):
    """
    Собирает напоминания по всем чатам для пользователя и формирует общее сообщение.
    Используется для ответа в ЛС.
    """
    user_data = get_user_data(user_id)
    now = utils.get_moscow_time()
    
    # Получаем все чаты, где пользователь был активен или есть данные
    # Это может потребовать дополнительной логики для отслеживания чатов пользователя
    # Для примера, будем использовать чаты, где есть last_roulette_time_{chat_id}
    
    # Простой способ - проверить чаты, где есть какая-либо активность рулетки
    # В идеале, нужно иметь список чатов, где бот и пользователь взаимодействуют.
    known_chat_ids = set()
    for key in user_data.keys():
        if key.startswith('last_roulette_time_'):
            try:
                chat_id_str = key.split('_')[-1]
                known_chat_ids.add(int(chat_id_str))
            except ValueError:
                continue
    
    # Добавляем текущий "личный чат" (если такой концепт есть, например, для /onecoin, /bonus)
    # Если /onecoin и /bonus не привязаны к чату, их можно обработать отдельно или с chat_id=None
    
    all_reminders_text = f"📌 {user_name}, вот твои актуальные напоминания:\n\n"
    found_any_reminders = False

    # Напоминания, не привязанные к чату (или обрабатываемые как "глобальные" для ЛС)
    # Команды /onecoin и /bonus обычно не зависят от чата, но /oneui и /roulette могут.
    # В вашем примере /oneui, /onecoin, /bonus, /roulette показаны для "Этого чата".
    # Значит, get_reminders_for_chat должен быть вызван для текущего чата команды /напомни.

    # Если команда /напомни дана в ЛС, а нам нужны напоминания "в этом чате" (ЛС),
    # то это может быть чат с самим ботом.
    # Для универсальности, get_reminders_for_chat может принимать chat_id=user_id для ЛС.
    
    # Для примера, если /напомни в ЛС показывает только "глобальные" или "ЛС-специфичные" таймеры:
    
    # --- Глобальные/ЛС напоминания (если есть) ---
    # Например, /onecoin и /bonus, если они не зависят от чата в get_next_..._time
    ls_reminder_lines = []
    
    # /onecoin
    next_onecoin_time = onecoin_logic.get_next_onecoin_time(user_data)
    if now.timestamp() >= next_onecoin_time:
        ls_reminder_lines.append("✅ /onecoin доступен для получения.")
    else:
        dt_next_onecoin = datetime.fromtimestamp(next_onecoin_time, tz=config.MOSCOW_TZ)
        time_left_str = utils.format_time_left_till_datetime(dt_next_onecoin, now)
        ls_reminder_lines.append(f"❌ /onecoin будет доступен после {utils.format_datetime_msk(dt_next_onecoin)} ({time_left_str}).")

    # /bonus
    next_bonus_time = bonus_logic.get_next_bonus_time(user_data)
    if now.timestamp() >= next_bonus_time:
        ls_reminder_lines.append("✅ /bonus доступен для получения.")
    else:
        dt_next_bonus = datetime.fromtimestamp(next_bonus_time, tz=config.MOSCOW_TZ)
        time_left_str = utils.format_time_left_till_datetime(dt_next_bonus, now)
        ls_reminder_lines.append(f"❌ /bonus будет доступен после {utils.format_datetime_msk(dt_next_bonus)} ({time_left_str}).")
    
    # /oneui (если у него есть глобальный аспект или он проверяется для ЛС отдельно)
    # В вашем примере /oneui был в "этом чате". Если /напомни в ЛС, то "этот чат" - это ЛС.
    # Предположим, что oneui_phantom_lock_until_ts и next_oneui_eligible_ts - глобальные.
    oneui_status_line_ls = None
    oneui_phantom_lock_until_ts = user_data.get('oneui_phantom_lock_until_ts')
    if oneui_phantom_lock_until_ts and now.timestamp() < oneui_phantom_lock_until_ts:
        phantom_lock_end_dt = datetime.fromtimestamp(oneui_phantom_lock_until_ts, tz=config.MOSCOW_TZ)
        time_left_str = utils.format_time_left_till_datetime(phantom_lock_end_dt, now)
        oneui_status_line_ls = (f"❌ /oneui (фантомная блокировка) будет доступен после "
                                f"{utils.format_datetime_msk(phantom_lock_end_dt)} ({time_left_str}).")
    else:
        next_oneui_eligible_ts_ls = user_data.get('next_oneui_eligible_ts') # или расчет как выше
        if next_oneui_eligible_ts_ls is None: # Резервный расчет
            last_oneui_change_time = user_data.get('last_oneui_change_time', 0)
            current_streak = user_data.get('streak_days_oneui', 0)
            cooldown_hours = config.ONEUI_COOLDOWN_BASE
            if current_streak >= 7:
                 cooldown_hours -= config.ONEUI_COOLDOWN_STREAK_BONUS.get(7, 0)
            actual_cooldown_seconds = cooldown_hours * 3600
            next_oneui_eligible_ts_ls = last_oneui_change_time + actual_cooldown_seconds
            
        if now.timestamp() >= next_oneui_eligible_ts_ls:
            oneui_status_line_ls = "✅ /oneui доступен для изменения версии."
        else:
            next_oneui_avail_dt_ls = datetime.fromtimestamp(next_oneui_eligible_ts_ls, tz=config.MOSCOW_TZ)
            time_left_str = utils.format_time_left_till_datetime(next_oneui_avail_dt_ls, now)
            oneui_status_line_ls = (f"❌ /oneui будет доступен после "
                                   f"{utils.format_datetime_msk(next_oneui_avail_dt_ls)} ({time_left_str}).")
    if oneui_status_line_ls:
        ls_reminder_lines.append(oneui_status_line_ls)


    if ls_reminder_lines:
        all_reminders_text += "🔔 Глобальные/ЛС:\n" # Или "В личных сообщениях"
        for line in ls_reminder_lines:
            all_reminders_text += f"  • {line}\n"
        all_reminders_text += "\n"
        found_any_reminders = True
        
    # Напоминания по конкретным чатам (особенно /roulette, которая зависит от chat_id)
    for chat_id_val in known_chat_ids:
        # Получаем название чата (если это возможно/нужно)
        # chat_title = await bot.get_chat(chat_id_val).title # Пример, если есть доступ к объекту bot
        chat_title_str = f"в чате ID {chat_id_val}" # Запасной вариант
        
        chat_specific_reminders = []
        
        # Только /roulette или другие чат-специфичные команды
        next_r_time = roulette_logic.get_next_roulette_time(user_data, chat_id_val)
        if now.timestamp() >= next_r_time:
            chat_specific_reminders.append("✅ /roulette доступна для игры.")
        else:
            dt_next_r = datetime.fromtimestamp(next_r_time, tz=config.MOSCOW_TZ)
            time_left_str = utils.format_time_left_till_datetime(dt_next_r, now)
            chat_specific_reminders.append(f"❌ /roulette будет доступна после {utils.format_datetime_msk(dt_next_r)} ({time_left_str}).")
            
        if chat_specific_reminders:
            all_reminders_text += f"🔔 Напоминания {chat_title_str}:\n"
            for line in chat_specific_reminders:
                all_reminders_text += f"  • {line}\n"
            all_reminders_text += "\n"
            found_any_reminders = True

    if not found_any_reminders:
        return f"{user_name}, у тебя пока нет активных напоминаний по чатам."
        
    return all_reminders_text.strip()

# В main.py или где у вас хендлер команды /напомни

# async def remind_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     user = update.effective_user
#     chat = update.effective_chat
#     user_data = get_user_data(user.id) # Убедитесь, что user_data актуальна
    
#     # Записываем активность пользователя в чате
#     update_user_last_activity_in_chat(user.id, chat.id, utils.get_moscow_time().timestamp())

#     if chat.type == 'private':
#         # Пользователь запросил напоминания в ЛС - показываем по всем чатам
#         # (или только глобальные/ЛС, в зависимости от вашей логики get_all_reminders_for_user)
#         reminder_message_text = await reminders_logic.get_all_reminders_for_user(user.id, user.first_name)
#     else:
#         # Пользователь запросил напоминания в групповом чате - показываем для этого чата
#         user_name_in_chat = user.first_name # или user.full_name
#         # Заголовок с именем пользователя
#         header = f"📌 {user_name_in_chat}, вот твои актуальные напоминания:\n\n"
#         # Получаем строки напоминаний для чата
#         reminder_lines = await reminders_logic.get_reminders_for_chat(user.id, chat.id, user_data)
        
#         if not reminder_lines:
#             reminder_message_text = header + "🔔 В этом чате:\n  • Нет актуальных напоминаний."
#         else:
#             reminder_message_text = header + "🔔 В этом чате:\n"
#             for line in reminder_lines:
#                 reminder_message_text += f"  • {line}\n"
        
#         # Общая подсказка
#         reminder_message_text += "\n\n💡 Используй /напомни в личных сообщениях со мной, увидеть напоминания по всем чатам"

#     await update.message.reply_text(reminder_message_text, parse_mode='HTML', disable_web_page_preview=True)
