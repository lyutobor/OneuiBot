# families_logic.py
import asyncio
import html
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Optional, List # Убран Any, если не используется

from aiogram import Router, Bot, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, User as AiogramUser
# hlink УДАЛЕН ОТСЮДА, используется из utils
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from pytz import timezone as pytz_timezone
from achievements_logic import check_and_grant_achievements # <<< НОВЫЙ ИМПОРТ

import database
from config import Config
from utils import get_user_mention_html, send_telegram_log # Импорт из utils

families_router = Router()

class FamilyLeaveStates(StatesGroup):
    awaiting_text_confirmation = State()

CONFIRMATION_TIMEOUT_SECONDS = 60

# Локальные get_user_mention_link и get_user_mention_link_by_id_and_name УДАЛЕНЫ
# Вместо них используется get_user_mention_html из utils.py


@families_router.message(Command(
    "familycreate", "создатьсемью", "новаясемья", "основатьсемью", "createfamily", "newfamily", "семьясоздать",
    ignore_case=True
))
async def family_create_command(message: Message, command: CommandObject, bot: Bot): # bot добавлен для send_telegram_log
    user = message.from_user
    if not user: return await message.reply("Не удалось определить пользователя.")
    user_link = get_user_mention_html(user.id, user.full_name, user.username)

    if command.args is None:
        return await message.reply("Укажите название для новой семьи. Пример: <code>/familycreate Моя Семья</code>")
    family_name = command.args.strip()
    if not family_name or len(family_name) < 3 or len(family_name) > 30:
        return await message.reply("Название семьи должно быть от 3 до 30 символов.")

    try:
        user_max_global_version = await database.get_user_max_version_global(user.id)
        if user_max_global_version < database.FAMILY_CREATION_MIN_VERSION:
            return await message.reply(
                f"Для создания семьи ваша максимальная версия OneUI (где-либо) должна быть не менее {database.FAMILY_CREATION_MIN_VERSION:.1f}. "
                f"Ваша текущая максимальная версия: {user_max_global_version:.1f}."
            )

        success, result = await database.create_family(
            family_name, user.id, user.full_name,
            message.chat.id, message.chat.title or f"Chat {message.chat.id}"
        )
        if success:
            family_id = result
            await message.reply(f"Семья '<b>{html.escape(family_name)}</b>' успешно создана! Её лидер: {user_link}.\nID Семьи: {family_id}")
            await send_telegram_log(bot, f"👪 Семья '<b>{html.escape(family_name)}</b>' (ID: {family_id}) создана лидером {user_link}.")
            
    # --- ВЫЗОВ ПРОВЕРКИ ДОСТИЖЕНИЙ ---
            await check_and_grant_achievements(
                  user.id,
                  message.chat.id,
                  bot,
                  family_created_just_now=True # Для "Зародыш Клана"
            )
                # --- КОНЕЦ ВЫЗОВА ПРОВЕРКИ ДОСТИЖЕНИЙ ---        
        else:
            await message.reply(f"Не удалось создать семью: {html.escape(str(result))}")
            if "уже существует" not in str(result): # Не логируем как ошибку, если просто имя занято
                await send_telegram_log(bot, f"⚠️ Не удалось создать семью '{html.escape(family_name)}' для {user_link}. Причина: {html.escape(str(result))}")
    except Exception as e:
        await message.reply("Произошла ошибка при создании семьи. Попробуйте позже.")
        await send_telegram_log(bot, f"🔴 Ошибка при создании семьи '{html.escape(family_name)}' для {user_link}: <pre>{html.escape(str(e))}</pre>")


@families_router.message(Command(
    "familyjoin", "вступитьвсемью", "присоединитьсяксемье", "joinfamily", "семьявступить", "войтивсемью",
    ignore_case=True
))
async def family_join_command(message: Message, command: CommandObject, bot: Bot): # bot добавлен
    user = message.from_user
    if not user: return await message.reply("Не удалось определить пользователя.")
    user_link = get_user_mention_html(user.id, user.full_name, user.username)

    if command.args is None:
        return await message.reply("Укажите название семьи, в которую хотите вступить. Пример: <code>/familyjoin ИмяСемьи</code>")
    family_name_arg = command.args.strip()

    try:
        family_info = await database.get_family_by_name(family_name_arg, chat_id=None)
        if not family_info:
            return await message.reply(f"Семья с названием '{html.escape(family_name_arg)}' не найдена.")

        success, result_message = await database.add_user_to_family(
            user.id, user.full_name, family_info['family_id'],
            message.chat.id, message.chat.title or f"Chat {message.chat.id}"
        )
        processed_message = html.escape(result_message)
        if user.full_name and html.escape(user.full_name) in processed_message: # Заменяем имя на ссылку
            processed_message = processed_message.replace(html.escape(user.full_name), user_link)

        await message.reply(processed_message)
        if success:
            await send_telegram_log(bot, f"➕ Пользователь {user_link} вступил в семью '{html.escape(family_info['name'])}'.")
        # --- ВЫЗОВ ПРОВЕРКИ ДОСТИЖЕНИЙ ---
        await check_and_grant_achievements(
              user.id,
              message.chat.id,
              bot,
              family_joined_just_now=True, # Для "Верный Послушник"
                # Дополнительно: для "Архитектор Альянсов" - проверка, что семья участвует в соревновании
              family_joined_active_competition_just_now=(await database.get_active_family_competition() is not None)
        )
            # --- КОНЕЦ ВЫЗОВА ПРОВЕРКИ ДОСТИЖЕНИЙ ---    
    
    except Exception as e:
        await message.reply("Произошла ошибка при вступлении в семью. Попробуйте позже.")
        await send_telegram_log(bot, f"🔴 Ошибка при вступлении {user_link} в семью '{html.escape(family_name_arg)}': <pre>{html.escape(str(e))}</pre>")


@families_router.message(Command(
    "familyleave", "покинутьсемью", "выйтиизсемьи", "leavefamily", "семьяуйти", "уйтиизсемьи",
    ignore_case=True
))
async def family_leave_command(message: Message, state: FSMContext): # bot здесь не нужен напрямую, но может понадобиться в confirm
    user = message.from_user
    if not user: return await message.reply("Не удалось определить пользователя.")

    membership = await database.get_user_family_membership(user.id)
    if not membership: return await message.reply("Вы не состоите ни в какой семье.")

    family_id = membership['family_id']
    family_name = membership.get('family_name', 'вашу семью')

    await state.set_state(FamilyLeaveStates.awaiting_text_confirmation)
    await state.update_data(
        family_id_to_leave=family_id,
        family_name_to_leave=family_name,
        confirmation_initiated_at=datetime.now(dt_timezone.utc).isoformat()
    )
    await message.reply(
        f"Вы уверены, что хотите покинуть семью '<b>{html.escape(family_name)}</b>'? "
        f"Ответьте 'Да' или 'Нет' в течение {CONFIRMATION_TIMEOUT_SECONDS} секунд."
    )

@families_router.message(FamilyLeaveStates.awaiting_text_confirmation, F.text.lower() == 'да')
async def family_leave_confirm_yes(message: Message, state: FSMContext, bot: Bot):
    user = message.from_user
    if not user:
        await state.clear()
        return await message.reply("Не удалось определить пользователя.")
    user_link = get_user_mention_html(user.id, user.full_name, user.username)

    user_data = await state.get_data()
    family_id_to_leave = user_data.get('family_id_to_leave')
    family_name_to_leave = user_data.get('family_name_to_leave', 'вашу семью')
    confirmation_initiated_at_iso = user_data.get('confirmation_initiated_at')

    if not family_id_to_leave or not confirmation_initiated_at_iso:
        await state.clear()
        return await message.reply("Произошла ошибка или ваш запрос устарел. Пожалуйста, начните сначала с /familyleave.")

    try:
        confirmation_initiated_at = datetime.fromisoformat(confirmation_initiated_at_iso)
        current_time = datetime.now(dt_timezone.utc)
        if (current_time - confirmation_initiated_at) > timedelta(seconds=CONFIRMATION_TIMEOUT_SECONDS):
            await state.clear()
            return await message.reply(f"Время на подтверждение выхода из семьи '<b>{html.escape(family_name_to_leave)}</b>' истекло. Используйте /familyleave снова.")
    except ValueError:
         await state.clear()
         return await message.reply("Ошибка в формате времени. Начните заново.")

    try:
        current_membership = await database.get_user_family_membership(user.id)
        if not current_membership or current_membership['family_id'] != family_id_to_leave:
            await state.clear()
            return await message.reply(f"Вы больше не состоите в семье '{html.escape(family_name_to_leave)}' или произошла ошибка.")

        success, result_message_db = await database.remove_user_from_family(
            user.id, family_id_to_leave, user.id, user.full_name, "LEAVE",
            message.chat.id, message.chat.title or f"Chat {message.chat.id}"
        )
        processed_message = html.escape(result_message_db)
        if user.full_name and html.escape(user.full_name) in processed_message:
            processed_message = processed_message.replace(html.escape(user.full_name), user_link)

        await message.reply(processed_message)
        if success:
            await send_telegram_log(bot, f"➖ Пользователь {user_link} покинул семью '{html.escape(family_name_to_leave)}'.")
            # --- ВЫЗОВ ПРОВЕРКИ ДОСТИЖЕНИЙ ---
            await check_and_grant_achievements(
                user.id,
                message.chat.id,
                bot,
                family_left_just_now=True # Для "Предатель Системы"
            )
            # --- КОНЕЦ ВЫЗОВА ПРОВЕРКИ ДОСТИЖЕНИЙ ---
    except Exception as e:
        await message.reply("Произошла ошибка при выходе из семьи.")
        await send_telegram_log(bot, f"🔴 Ошибка при выходе {user_link} из семьи '{html.escape(family_name_to_leave)}': <pre>{html.escape(str(e))}</pre>")
    finally:
        await state.clear()


@families_router.message(FamilyLeaveStates.awaiting_text_confirmation, F.text.lower() == 'нет')
async def family_leave_confirm_no(message: Message, state: FSMContext):
    user_data = await state.get_data()
    family_name_to_leave = user_data.get('family_name_to_leave', 'вашу семью')
    await message.reply(f"Выход из семьи '<b>{html.escape(family_name_to_leave)}</b>' отменен.")
    await state.clear()

@families_router.message(FamilyLeaveStates.awaiting_text_confirmation)
async def family_leave_invalid_confirmation(message: Message, state: FSMContext):
    user_data = await state.get_data()
    confirmation_initiated_at_iso = user_data.get('confirmation_initiated_at')
    if confirmation_initiated_at_iso:
        try:
            confirmation_initiated_at = datetime.fromisoformat(confirmation_initiated_at_iso)
            current_time = datetime.now(dt_timezone.utc)
            if (current_time - confirmation_initiated_at) > timedelta(seconds=CONFIRMATION_TIMEOUT_SECONDS):
                family_name_to_leave = user_data.get('family_name_to_leave', 'вашу семью')
                await state.clear()
                return await message.reply(f"Время на подтверждение выхода из семьи '<b>{html.escape(family_name_to_leave)}</b>' истекло.")
        except ValueError: pass # Ошибка формата уже обработана в confirm_yes, здесь просто игнорируем для таймаута

    await message.reply("Пожалуйста, ответьте 'Да' или 'Нет'.")


@families_router.message(Command(
    "familykick", "кикнутьизсемьи", "выгнатьизсемьи", "исключитьизсемьи", "kickfamily", "семьякик",
    ignore_case=True
))
async def family_kick_command(message: Message, command: CommandObject, bot: Bot):
    leader = message.from_user
    if not leader: return await message.reply("Не удалось определить лидера.")
    leader_link = get_user_mention_html(leader.id, leader.full_name, leader.username)

    target_user_id: Optional[int] = None
    target_user_full_name_for_db: Optional[str] = None
    target_user_username_for_link: Optional[str] = None
    target_user_display_link: str = "N/A"

    if message.reply_to_message and message.reply_to_message.from_user:
        target_user_obj = message.reply_to_message.from_user
        target_user_id = target_user_obj.id
        target_user_full_name_for_db = target_user_obj.full_name
        target_user_username_for_link = target_user_obj.username
        target_user_display_link = get_user_mention_html(target_user_id, target_user_full_name_for_db, target_user_username_for_link)
    elif command.args:
        target_arg = command.args.strip()
        if target_arg.startswith('@'):
            # Попытка извлечь username без @
            username_to_check = target_arg[1:]
            # Здесь нужна логика поиска user_id по username, если это необходимо.
            # Это может потребовать дополнительного запроса к БД или хранения маппинга username:user_id.
            # Пока что оставим как "не поддерживается" для простоты.
            return await message.reply("Исключение по @username пока не поддерживается в полном объеме без поиска ID. Используйте ID или ответьте на сообщение.")
        else:
            try:
                target_user_id = int(target_arg)
                # Попытаемся получить данные о пользователе для более красивого отображения
                try:
                    # get_chat может не вернуть full_name для пользователя, если бот с ним не общался
                    # Более надежно было бы иметь функцию в БД для поиска пользователя по ID
                    target_user_chat_info = await bot.get_chat(target_user_id) # type: ignore
                    target_user_full_name_for_db = getattr(target_user_chat_info, 'full_name', None) or getattr(target_user_chat_info, 'first_name', None) # Добавил first_name
                    target_user_username_for_link = getattr(target_user_chat_info, 'username', None)
                    target_user_display_link = get_user_mention_html(target_user_id, target_user_full_name_for_db, target_user_username_for_link)
                except Exception: # Если не удалось получить информацию
                    target_user_full_name_for_db = f"User ID {target_user_id}" # Запасной вариант
                    target_user_display_link = get_user_mention_html(target_user_id, None, None) # Имя будет "User ID X"
            except ValueError:
                return await message.reply("Неверный формат ID. Укажите число или ответьте на сообщение.")
    else:
        return await message.reply("Укажите ID или ответьте на сообщение пользователя для исключения.")

    if not target_user_id: return await message.reply("Не удалось определить пользователя для исключения.")
    if target_user_id == leader.id: return await message.reply("Вы не можете исключить самого себя.")

    try:
        leader_membership = await database.get_user_family_membership(leader.id)
        if not leader_membership: return await message.reply("Вы не состоите в семье.")

        family_info = await database.get_family_by_id(leader_membership['family_id'])
        if not family_info or family_info['leader_id'] != leader.id:
            return await message.reply("Только лидер семьи может исключать участников.")

        target_membership = await database.get_user_family_membership(target_user_id)
        if not target_membership or target_membership['family_id'] != family_info['family_id']:
            return await message.reply(f"Пользователь {target_user_display_link} не состоит в вашей семье.")

        success, result_message_from_db = await database.remove_user_from_family(
            target_user_id, family_info['family_id'], leader.id, leader.full_name, "KICK",
            message.chat.id, message.chat.title or f"Chat {message.chat.id}",
            target_full_name_override = target_user_full_name_for_db # Передаем имя, которое удалось получить
        )
        final_message = html.escape(result_message_from_db)
        # Замена плейсхолдеров на ссылки
        placeholder_name_escaped = html.escape(target_user_full_name_for_db or f"User ID {target_user_id}")
        if placeholder_name_escaped in final_message:
             final_message = final_message.replace(placeholder_name_escaped, target_user_display_link)
        elif f"User ID {target_user_id}" in final_message: # Если в сообщении из БД использовался ID
             final_message = final_message.replace(f"User ID {target_user_id}", target_user_display_link)

        if leader.full_name and html.escape(leader.full_name) in final_message:
            final_message = final_message.replace(html.escape(leader.full_name), leader_link)

        await message.reply(final_message)
        if success:
            await send_telegram_log(bot, f"👢 Пользователь {target_user_display_link} был исключен из семьи '{html.escape(family_info['name'])}' лидером {leader_link}.")
        # --- ВЫЗОВ ПРОВЕРКИ ДОСТИЖЕНИЙ (для кикнутого пользователя) ---
            # Это достижение получает тот, кого кикнули, а не тот, кто кикнул
        await check_and_grant_achievements(
              target_user_id, # ID кикнутого пользователя
              message.chat.id,
              bot,
              family_kicked_just_now=True # Для "Исключение из Круга"
        )
            # --- КОНЕЦ ВЫЗОВА ПРОВЕРКИ ДОСТИЖЕНИЙ ---
        
    
    except Exception as e:
        await message.reply("Произошла ошибка при исключении пользователя.")
        await send_telegram_log(bot, f"🔴 Ошибка при исключении {target_user_display_link} лидером {leader_link} из семьи: <pre>{html.escape(str(e))}</pre>")


@families_router.message(Command(
    "familyrename", "переименоватьсемью", "сменитьимясемьи", "renamefamily", "семьяимя", "новоеимясемьи",
    ignore_case=True
))
async def family_rename_command(message: Message, command: CommandObject, bot: Bot):
    user = message.from_user
    if not user: return await message.reply("Не удалось определить пользователя.")
    user_link = get_user_mention_html(user.id, user.full_name, user.username)

    if command.args is None:
        return await message.reply("Укажите новое название для семьи. Пример: <code>/familyrename НовоеИмя</code>")
    new_name = command.args.strip()
    if not new_name or len(new_name) < 3 or len(new_name) > 30:
        return await message.reply("Новое название семьи должно быть от 3 до 30 символов.")

    try:
        membership = await database.get_user_family_membership(user.id)
        if not membership: return await message.reply("Вы не состоите в семье.")
        
        old_family_info = await database.get_family_by_id(membership['family_id'])
        old_name_for_log = old_family_info['name'] if old_family_info else "Неизвестное старое имя"


        success, result_message = await database.update_family_name(
            membership['family_id'], new_name, user.id, user.full_name,
            message.chat.id, message.chat.title or f"Chat {message.chat.id}"
        )
        await message.reply(html.escape(result_message))
        if success:
            await send_telegram_log(bot, f"✏️ Семья '{html.escape(old_name_for_log)}' (ID: {membership['family_id']}) переименована в '{html.escape(new_name)}' лидером {user_link}.")
        elif "уже существует" not in result_message:
             await send_telegram_log(bot, f"⚠️ Не удалось переименовать семью (ID: {membership['family_id']}) в '{html.escape(new_name)}' лидером {user_link}. Причина: {html.escape(result_message)}")
        
        # --- ВЫЗОВ ПРОВЕРКИ ДОСТИЖЕНИЙ ---
        await check_and_grant_achievements(
              user.id,
              message.chat.id,
              bot,
              family_renamed_just_now=True # Для "Голос Хаоса"
        )
            # --- КОНЕЦ ВЫЗОВА ПРОВЕРКИ ДОСТИЖЕНИЙ ---        
    
    except Exception as e:
        await message.reply("Произошла ошибка при переименовании семьи.")
        await send_telegram_log(bot, f"🔴 Ошибка при переименовании семьи (лидер {user_link}) в '{html.escape(new_name)}': <pre>{html.escape(str(e))}</pre>")


@families_router.message(Command(
    "familystats", "статасемьи", "статистикасемьи", "familyinfo", "инфосемьи", "инфасемья",
    "семьястат", "statfamily", "семьяинфо", "семья",
    ignore_case=True
))
async def family_stats_command(message: Message, command: CommandObject, bot: Bot):
    chat_id_context = message.chat.id
    family_to_show_data: Optional[dict] = None
    user_who_called = message.from_user

    try:
        if command.args:
            family_name_arg = command.args.strip()
            family_to_show_data = await database.get_family_by_name(family_name_arg, chat_id=None)
            if not family_to_show_data:
                return await message.reply(f"Семья с названием '{html.escape(family_name_arg)}' не найдена.")
        elif user_who_called:
            membership = await database.get_user_family_membership(user_who_called.id)
            if not membership:
                await top_families_command(message, bot)
                return
            family_to_show_data = await database.get_family_by_id(membership['family_id'])
        else:
            await top_families_command(message, bot)
            return

        if not family_to_show_data:
            return await message.reply("Не удалось найти информацию о семье. Возможно, она была удалена, или вы больше не ее участник.")

        family_id = family_to_show_data['family_id']
        family_name = html.escape(family_to_show_data['name'])
        leader_id = family_to_show_data['leader_id']

        leader_full_name_from_db: Optional[str] = None
        leader_username_from_db: Optional[str] = None
        conn = None
        try:
            conn = await database.get_connection()
            leader_info_row = await conn.fetchrow("SELECT full_name, username FROM user_oneui WHERE user_id = $1 ORDER BY last_used DESC NULLS LAST LIMIT 1", leader_id)
            if leader_info_row:
                leader_full_name_from_db = leader_info_row['full_name']
                leader_username_from_db = leader_info_row['username']
        except Exception as e_db: print(f"DB error fetching leader info for {leader_id}: {e_db}") # Оставим print для отладки БД
        finally:
            if conn and not conn.is_closed(): await conn.close()

        if not leader_full_name_from_db:
            try:
                leader_chat_info = await bot.get_chat(leader_id) # type: ignore
                leader_full_name_from_db = getattr(leader_chat_info, 'full_name', None) or getattr(leader_chat_info, 'first_name', None)
                leader_username_from_db = getattr(leader_chat_info, 'username', None)
            except Exception as e_api: print(f"API error fetching leader info for {leader_id}: {e_api}") # Оставим print для отладки API

        leader_link = get_user_mention_html(leader_id, leader_full_name_from_db, leader_username_from_db)
        members_data = await database.get_family_members(family_id)
        member_count = len(members_data)

        response_lines = [
            f"<b>📊 Статистика Семьи: {family_name}</b> (ID: {family_id})",
            f"👑 Лидер: {leader_link}",
            f"👥 Участников: {member_count}/{Config.FAMILY_MAX_MEMBERS}",
            "--------------------",
        ]
        if members_data:
            response_lines.append("<b>Участники (сортировка по дате вступления):</b>")
            for member in members_data:
                user_id_member = member['user_id']
                member_full_name = member.get('full_name_when_joined')
                member_username_db = member.get('username') # username теперь берется из get_family_members
                member_display_link = get_user_mention_html(user_id_member, member_full_name, member_username_db)
                user_personal_version_in_this_chat = await database.get_user_version(user_id_member, chat_id_context)
                response_lines.append(
                    f"👤 {member_display_link}: \n"
                    f"   ▫️ Личная версия: <code>{user_personal_version_in_this_chat:.1f}</code>"
                )
        else:
            response_lines.append("В семье пока нет участников.")
        await message.reply("\n".join(response_lines), parse_mode="HTML", disable_web_page_preview=True)

    except Exception as e:
        await message.reply("Произошла ошибка при отображении статистики семьи.")
        user_who_called_link = get_user_mention_html(user_who_called.id, user_who_called.full_name, user_who_called.username) if user_who_called else "Неизвестный пользователь"
        await send_telegram_log(bot, f"🔴 Ошибка в /familystats (запросил {user_who_called_link}): <pre>{html.escape(str(e))}</pre>")


@families_router.message(Command(
    "topfamilies", "топсемья", "топсемей", "topfamily", "семейныйтоп", "рейтингсемей",
    "familytop", "families_top", "лучшиесемьи", "семьятоп",
    ignore_case=True
))
async def top_families_command(message: Message, bot: Bot):
    try:
        top_fams = await database.get_top_families_by_total_contribution(limit=10)
        if not top_fams:
            return await message.reply("Пока нет семей для отображения в топе.")

        response_lines = ["<b>🏆 Топ Семей (сортировка по участникам):</b>"]
        conn_local = None # Используем локальное имя, чтобы не пересекаться с conn в других местах
        try:
            conn_local = await database.get_connection()
            for i, fam_data in enumerate(top_fams):
                leader_id = fam_data['leader_id']
                leader_full_name = fam_data.get('leader_full_name') # Это имя из user_oneui или при создании
                leader_username: Optional[str] = None

                # Дополнительный запрос для самого свежего username, если leader_full_name уже есть
                # leader_full_name из get_top_families_by_total_contribution уже должен быть актуальным из user_oneui
                if conn_local:
                    leader_info_row = await conn_local.fetchrow("SELECT username FROM user_oneui WHERE user_id = $1 ORDER BY last_used DESC NULLS LAST LIMIT 1", leader_id)
                    if leader_info_row:
                        leader_username = leader_info_row['username']
                
                # Если имя все еще не определено (маловероятно, если лидер есть в user_oneui)
                if not leader_full_name:
                    try:
                        leader_chat_info = await bot.get_chat(leader_id) # type: ignore
                        leader_full_name = getattr(leader_chat_info, 'full_name', None) or getattr(leader_chat_info, 'first_name', None)
                        if not leader_username: # Если username не был найден из БД
                           leader_username = getattr(leader_chat_info, 'username', None)
                    except Exception as e_gc: print(f"API error fetching leader info {leader_id} for topfamilies: {e_gc}")


                leader_link = get_user_mention_html(leader_id, leader_full_name, leader_username)
                response_lines.append(
                    f"{i + 1}. <b>{html.escape(fam_data['name'])}</b> - "
                    f"Участников: {fam_data['member_count']}/{Config.FAMILY_MAX_MEMBERS}, Лидер: {leader_link}"
                )
        finally:
            if conn_local and not conn_local.is_closed(): await conn_local.close()
        await message.reply("\n".join(response_lines), parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        await message.reply("Произошла ошибка при отображении топа семей.")
        await send_telegram_log(bot, f"🔴 Ошибка в /topfamilies: <pre>{html.escape(str(e))}</pre>")


@families_router.message(Command(
    "familylog", "логсемьи", "историясемьи", "familyhistory", "logfamily", "семьялог", "действиясемьи",
    ignore_case=True
))
async def family_log_command(message: Message, bot: Bot): # bot добавлен для send_telegram_log
    user = message.from_user
    if not user: return await message.reply("Не удалось определить пользователя.")
    user_link = get_user_mention_html(user.id, user.full_name, user.username)

    try:
        membership = await database.get_user_family_membership(user.id)
        if not membership:
            return await message.reply("Вы не состоите в семье, чтобы просматривать её лог.")

        family_id = membership['family_id']
        family_info = await database.get_family_by_id(family_id)
        if not family_info:
            return await message.reply("Не удалось найти информацию о вашей семье.")

        logs = await database.get_family_logs(family_id, limit=20)
        if not logs:
            return await message.reply(f"Лог для семьи '{html.escape(family_info['name'])}' пока пуст.")

        response_lines = [f"<b>📜 Лог событий семьи '{html.escape(family_info['name'])}' (последние {len(logs)}):</b>"]
        pytz_tz = pytz_timezone(Config.TIMEZONE if Config.TIMEZONE else "UTC")

        for log_entry in logs:
            ts_db = log_entry['timestamp']
            ts_local = ts_db.astimezone(pytz_tz)
            ts_formatted = ts_local.strftime('%Y-%m-%d %H:%M:%S %Z')

            actor_display_link = "Система"
            actor_name = log_entry['actor_full_name']
            actor_id = log_entry['actor_user_id']
            # Username для логов не будем запрашивать дополнительно, чтобы не нагружать
            if actor_id:
                 actor_display_link = get_user_mention_html(actor_id, actor_name, None) # username=None

            description_text = html.escape(log_entry['description'])
            if actor_id and actor_name and html.escape(actor_name) in description_text:
                description_text = description_text.replace(html.escape(actor_name), actor_display_link)

            target_id = log_entry['target_user_id']
            target_name = log_entry['target_full_name']
            if target_id and target_name and html.escape(target_name) in description_text:
                target_name_in_desc_link = get_user_mention_html(target_id, target_name, None) # username=None
                description_text = description_text.replace(html.escape(target_name), target_name_in_desc_link)

            action_type_display = html.escape(log_entry['action_type'].replace("_", " ").title())
            log_line_start = f"<pre>[{ts_formatted}]</pre> {action_type_display}"
            if log_entry['actor_user_id']:
                log_line_start += f" (иниц: {actor_display_link})"
            response_lines.append(f"{log_line_start}: {description_text}")

        await message.reply("\n".join(response_lines), parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        await message.reply("Произошла ошибка при отображении лога семьи.")
        await send_telegram_log(bot, f"🔴 Ошибка в /familylog (запросил {user_link}): <pre>{html.escape(str(e))}</pre>")


def setup_families_handlers(main_dp: Router):
    main_dp.include_router(families_router)
    print("Обработчики команд семей зарегистрированы.")