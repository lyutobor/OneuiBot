import html
import logging
from typing import Optional, Tuple

from aiogram import F, Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from aiogram.utils.markdown import hlink
from pytz import timezone as pytz_timezone

import database
from config import Config #
from utils import get_user_mention_html, send_telegram_log, fetch_user_display_data, resolve_target_user
from business_data import BANK_DATA, BUSINESS_DATA #
from phone_data import PHONE_MODELS as PHONE_MODELS_STANDARD_LIST #
from exclusive_phone_data import EXCLUSIVE_PHONE_MODELS as EXCLUSIVE_PHONE_MODELS_LIST #
from datetime import datetime, timedelta
import pytz #

logger = logging.getLogger(__name__)
stats_router = Router()
PHONE_MODELS_STD_DICT_STATS = {p["key"]: p for p in PHONE_MODELS_STANDARD_LIST} #
EXCLUSIVE_PHONE_MODELS_DICT_STATS = {p["key"]: p for p in EXCLUSIVE_PHONE_MODELS_LIST} #

async def _get_formatted_stats(target_user_id: int, target_chat_id: int, bot_instance: Bot, for_self: bool = True) -> str:
    target_full_name, target_username = await fetch_user_display_data(bot_instance, target_user_id)
    target_user_link = get_user_mention_html(target_user_id, target_full_name, target_username)

    response_lines = [f"<b>📊 Статистика для {target_user_link}</b>"]
    if not for_self:
        try:
            chat_info = await bot_instance.get_chat(target_chat_id)
            chat_title_display = html.escape(chat_info.title or f"чате ID {target_chat_id}")
            response_lines.append(f"<i>(в текущем чате: {chat_title_display})</i>")
        except Exception:
            response_lines.append(f"<i>(в чате ID: {target_chat_id})</i>")

    response_lines.append("--------------------")
    
    # --- НОВЫЙ КОД: Отображение выбранного достижения ---
    selected_achievement_key = await database.get_user_selected_achievement(target_user_id)
    if selected_achievement_key:
        ach_info = Config.ACHIEVEMENTS_DATA.get(selected_achievement_key)
        if ach_info:
            response_lines.append(f"🌟 Избранное достижение: {ach_info['icon']} <b>«{ach_info['name']}»</b>")
            response_lines.append(f"  <i>{ach_info['description']}</i>")
        else:
            response_lines.append("🌟 Избранное достижение: Неизвестное (ключ не найден)")
    else:
        response_lines.append("🌟 Избранное достижение: Нет (используйте /selectachievement)")
    response_lines.append("--------------------")
    # --- КОНЕЦ НОВОГО КОДА ---

    # 1. Версия OneUI в текущем чате
    current_version_chat = await database.get_user_version(target_user_id, target_chat_id)
    response_lines.append(f"💻 Версия OneUI (этот чат): {current_version_chat:.1f}")

    # 2. Максимальная версия OneUI глобально
    max_version_data = await database.get_user_max_version_global_with_chat_info(target_user_id)
    if max_version_data and max_version_data.get('version') is not None:
        max_v = max_version_data['version']
        chat_title = max_version_data.get('chat_title')
        chat_link = max_version_data.get('telegram_chat_link')
        chat_id_max_v = max_version_data.get('chat_id')

        chat_info_str = ""
        # ИЗМЕНЕНИЕ ЗДЕСЬ:
        # Если ID чата с максимальной версией совпадает с ID целевого пользователя,
        # значит, это его личный чат.
        if chat_id_max_v and chat_id_max_v == target_user_id:
            chat_info_str = " (В личном чате)"
        elif chat_title: # Иначе, используем существующую логику
            escaped_chat_title = html.escape(chat_title)
            if chat_link:
                chat_info_str = f" (в чате {hlink(escaped_chat_title, chat_link)})"
            else:
                chat_info_str = f" (в чате '{escaped_chat_title}')"
        elif chat_id_max_v: # Если нет названия, но есть ID (и это не личный чат пользователя)
            chat_info_str = f" (в чате ID <code>{chat_id_max_v}</code>)"
        # Если chat_info_str остался пустым, значит, информации о чате нет

        response_lines.append(f"🏆 Макс. версия OneUI: <code>{float(max_v):.1f}</code>{chat_info_str}")
    else:
        response_lines.append(f"🏆 Макс. версия OneUI: 0.0 (нет данных)")


    # 3. OneCoin в текущем чате
    onecoins_chat = await database.get_user_onecoins(target_user_id, target_chat_id)
    response_lines.append(f"©️ OneCoin (этот чат): {onecoins_chat:}")

    # 4. Текущий стрик
    streak_data = await database.get_user_daily_streak(target_user_id, target_chat_id)
    current_streak = 0
    if streak_data:
        today_local_date = datetime.now(pytz_timezone(Config.TIMEZONE)).date()
        last_check_date_db = streak_data.get('last_streak_check_date')
        if last_check_date_db and (last_check_date_db == today_local_date or last_check_date_db == (today_local_date - timedelta(days=1))):
            current_streak = streak_data.get('current_streak', 0)
    response_lines.append(f"🔥 Ежедневный стрик: {current_streak}")

    # 5. Информация о семье
    family_membership = await database.get_user_family_membership(target_user_id)
    if family_membership:
        family_name = html.escape(family_membership.get('family_name', 'Неизвестная семья'))
        role = "👑 Лидер" if family_membership.get('leader_id') == target_user_id else "Участник"
        response_lines.append(f"👪 Семья: <b>{family_name}</b> ({role})")
    else:
        response_lines.append("👪 Семья: Не состоит")

    # 6. Активные телефоны (с деталями, БЕЗ ID)
    user_active_phones = await database.get_user_phones(target_user_id, active_only=True)
    active_phones_count = len(user_active_phones)
    response_lines.append(f"📱 Активные телефоны ({active_phones_count}/{Config.MAX_PHONES_PER_USER}):")
    if user_active_phones:
        for phone_db in user_active_phones:
            phone_key = phone_db['phone_model_key']
            # phone_id_inv = phone_db['phone_inventory_id'] # ID больше не нужен для вывода

            phone_name_display = f"Неизвестный телефон (<code>{html.escape(phone_key)}</code>)"
            phone_data_from_db = phone_db.get('data', {}) or {}

            # Поиск имени в стандартных, потом в эксклюзивных, потом в data из ЧР
            if phone_key in PHONE_MODELS_STD_DICT_STATS:
                phone_name_display = html.escape(PHONE_MODELS_STD_DICT_STATS[phone_key].get('display_name', PHONE_MODELS_STD_DICT_STATS[phone_key]['name']))
            elif phone_key in EXCLUSIVE_PHONE_MODELS_DICT_STATS:
                phone_name_display = html.escape(EXCLUSIVE_PHONE_MODELS_DICT_STATS[phone_key].get('display_name', EXCLUSIVE_PHONE_MODELS_DICT_STATS[phone_key]['name']))
            elif phone_data_from_db.get('display_name_override'): # Из ЧР слота
                phone_name_display = html.escape(phone_data_from_db['display_name_override'])

            # ИЗМЕНЕНО: Убрали отображение ID телефона
            response_lines.append(f"  - <b>{phone_name_display}</b>")
    else:
        response_lines.append("  <i>Нет активных телефонов.</i>")


    # 7. Уровень банка и баланс в текущем чате
    user_bank_data = await database.get_user_bank(target_user_id, target_chat_id)
    bank_level = user_bank_data['bank_level'] if user_bank_data else 0
    bank_balance = user_bank_data['current_balance'] if user_bank_data else 0
    bank_info_static = BANK_DATA.get(bank_level)
    bank_name_display = html.escape(bank_info_static['name']) if bank_info_static else "Мини-копилка"
    response_lines.append(f"🏦 Банк ({bank_name_display}, Ур. {bank_level}): {bank_balance:,} OC")

    # 8. Бизнесы в текущем чате (с деталями)
    user_businesses_chat = await database.get_user_businesses(target_user_id, target_chat_id)
    businesses_count_chat = len(user_businesses_chat)
    response_lines.append(f"🏢 Бизнесы ({businesses_count_chat}/{Config.BUSINESS_MAX_PER_USER_PER_CHAT}, этот чат):")
    if user_businesses_chat:
        for biz_db in user_businesses_chat:
            biz_key = biz_db['business_key']
            biz_level = biz_db['current_level']
            biz_id_db = biz_db['business_id']

            biz_name_override = biz_db.get('name_override')
            biz_static_data = BUSINESS_DATA.get(biz_key)

            biz_name_display = f"Неизвестный бизнес (<code>{html.escape(biz_key)}</code>)"
            if biz_name_override:
                biz_name_display = html.escape(biz_name_override)
            elif biz_static_data and biz_static_data.get('levels', {}).get(biz_level):
                biz_name_display = html.escape(biz_static_data['levels'][biz_level].get('display_name', biz_static_data['name']))
            elif biz_static_data:
                biz_name_display = html.escape(biz_static_data.get('name', biz_key))

            response_lines.append(f"  - <b>{biz_name_display}</b> (Ур. {biz_level})")
    else:
        response_lines.append("  <i>Нет бизнесов в этом чате.</i>")

    return "\n".join(response_lines)


@stats_router.message(Command("mystats", "моястата", "моястатистика", "stata", "профиль", "profile", ignore_case=True))
async def cmd_my_stats_explicit(message: Message, bot: Bot): # Переименовал для ясности
    if not message.from_user:
        await message.reply("Не удалось определить пользователя.", disable_web_page_preview=True)
        return

    user_id = message.from_user.id
    chat_id = message.chat.id

    try:
        stats_message = await _get_formatted_stats(user_id, chat_id, bot, for_self=True)
        await message.reply(stats_message, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Error in /mystats (explicit) for user {user_id} in chat {chat_id}: {e}", exc_info=True)
        await message.reply("Произошла ошибка при получении вашей статистики.", disable_web_page_preview=True)
        user_link_for_log = get_user_mention_html(user_id, message.from_user.full_name, message.from_user.username)
        await send_telegram_log(bot, f"🔴 Ошибка в /mystats (explicit) для {user_link_for_log}: <pre>{html.escape(str(e))}</pre>")

# Новый обработчик для /стата и /статистика
@stats_router.message(Command("стата", "статистика", ignore_case=True))
async def cmd_general_stats_handler(message: Message, command: CommandObject, bot: Bot):
    if not message.from_user:
        await message.reply("Не удалось определить пользователя.", disable_web_page_preview=True)
        return

    calling_user_id = message.from_user.id
    current_chat_id = message.chat.id

    # Определяем, есть ли цель (ответ на сообщение или аргументы)
    has_args = bool(command.args)
    is_reply = bool(message.reply_to_message and message.reply_to_message.from_user and not message.reply_to_message.from_user.is_bot) # Добавил проверку на не-бота в reply

    user_to_display_id: Optional[int] = None
    user_to_display_name: Optional[str] = None
    user_to_display_username: Optional[str] = None
    display_for_self = True

    if has_args or is_reply:
        # Попытка получить целевого пользователя
        target_user_data = await resolve_target_user(message, command, bot)
        if target_user_data:
            user_to_display_id, user_to_display_name, user_to_display_username = target_user_data
            if user_to_display_id == calling_user_id: # Если пользователь указал сам себя
                display_for_self = True
            else:
                display_for_self = False
                # Проверка, не является ли цель ботом (resolve_target_user может это делать, но дублируем)
                try:
                    target_chat_obj = await bot.get_chat(user_to_display_id)
                    if hasattr(target_chat_obj, 'is_bot') and target_chat_obj.is_bot: # Для User объектов
                        await message.reply("Нельзя посмотреть статистику бота.", disable_web_page_preview=True)
                        return
                    elif target_chat_obj.type != "private": # Если это группа/канал
                         # resolve_target_user должен был бы отфильтровать это, если он ищет только пользователей
                         pass # Предполагаем, что resolve_target_user вернул ID пользователя
                except Exception:
                    pass # Ошибки resolve_target_user обрабатывает сам
        else:
            # resolve_target_user уже отправил сообщение об ошибке, если аргументы были, но неверные.
            # Если это был ответ боту/системному сообщению, то target_user_data будет None.
            if is_reply and not has_args: # Явный ответ, но цель не определена
                await message.reply("Не удалось определить пользователя по вашему ответу. Возможно, вы ответили на сообщение бота или системное сообщение.", disable_web_page_preview=True)
            return
    else:
        # Нет аргументов и не ответ - показываем статистику вызвавшего
        user_to_display_id = calling_user_id
        user_to_display_name = message.from_user.full_name
        user_to_display_username = message.from_user.username
        display_for_self = True

    if user_to_display_id is None:
        # Этого не должно произойти, если логика выше верна
        await message.reply("Не удалось определить пользователя для отображения статистики.", disable_web_page_preview=True)
        return

    # Получаем и отправляем статистику
    try:
        stats_message_content = await _get_formatted_stats(user_to_display_id, current_chat_id, bot, for_self=display_for_self)
        await message.reply(stats_message_content, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Error in /стата (general_stats_handler) for target {user_to_display_id} by {calling_user_id}: {e}", exc_info=True)
        target_user_link_log = get_user_mention_html(user_to_display_id, user_to_display_name, user_to_display_username)
        await message.reply(f"Произошла ошибка при получении статистики для {target_user_link_log}.", parse_mode="HTML", disable_web_page_preview=True)
        # Логирование
        calling_user_link_log = get_user_mention_html(calling_user_id, message.from_user.full_name, message.from_user.username)
        await send_telegram_log(bot, f"🔴 Ошибка в /стата (general) для {target_user_link_log} (запросил {calling_user_link_log}): <pre>{html.escape(str(e))}</pre>")


@stats_router.message(Command("userstats", "статапользователя", ignore_case=True))
async def cmd_user_stats_explicit(message: Message, command: CommandObject, bot: Bot): # Переименовал для ясности
    if not message.from_user:
        await message.reply("Не удалось определить, кто вызвал команду.", disable_web_page_preview=True)
        return

    target_user_data = await resolve_target_user(message, command, bot)

    if not target_user_data:
        # resolve_target_user должен был отправить сообщение, если аргументы были неверными,
        # или если это был ответ на сообщение бота.
        # Если же команда вызвана без аргументов и не ответом - сообщаем.
        if not command.args and not message.reply_to_message:
            await message.reply("Укажите пользователя (ID, @username или ответом на сообщение), чью статистику вы хотите посмотреть.", disable_web_page_preview=True)
        return

    target_user_id, target_full_name, target_username = target_user_data
    current_chat_id = message.chat.id

    try:
        # Проверка на бота
        target_chat_obj = await bot.get_chat(target_user_id)
        if hasattr(target_chat_obj, 'is_bot') and target_chat_obj.is_bot:
            await message.reply("Нельзя посмотреть статистику бота.", disable_web_page_preview=True)
            return
        elif target_chat_obj.type != "private": # Убедимся, что это пользователь, а не группа/канал
            # Эта проверка может быть излишней, если resolve_target_user уже гарантирует пользователя
            pass

    except Exception as e_check_bot:
        logger.warning(f"Не удалось проверить, является ли цель {target_user_id} ботом (userstats_explicit): {e_check_bot}")
        # Продолжаем, но если это был бот, другие запросы к БД могут быть бессмысленны

    try:
        stats_message = await _get_formatted_stats(target_user_id, current_chat_id, bot, for_self=(target_user_id == message.from_user.id))
        await message.reply(stats_message, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Error in /userstats (explicit) for target {target_user_id} by {message.from_user.id}: {e}", exc_info=True)
        target_user_link_for_log = get_user_mention_html(target_user_id, target_full_name, target_username)
        await message.reply(f"Произошла ошибка при получении статистики для {target_user_link_for_log}.", parse_mode="HTML", disable_web_page_preview=True)
        calling_user_link_for_log = get_user_mention_html(message.from_user.id, message.from_user.full_name, message.from_user.username)
        await send_telegram_log(bot, f"🔴 Ошибка в /userstats (explicit) для {target_user_link_for_log} (запросил {calling_user_link_for_log}): <pre>{html.escape(str(e))}</pre>")


def setup_stats_handlers(dp: Router):
    dp.include_router(stats_router)
    logger.info("Обработчики команд статистики зарегистрированы.")
