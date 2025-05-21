# competition_logic.py
import asyncio
import html
from datetime import datetime, date as DDate
from typing import Optional

from aiogram import Router, Bot, F
from aiogram.filters import Command, CommandObject, Filter
from aiogram.types import Message
from pytz import timezone as pytz_timezone

import database
from config import Config
from utils import get_user_mention_html, send_telegram_log

competition_router = Router()

class AdminFilter(Filter):
    async def __call__(self, message: Message) -> bool:
        if not message.from_user:
            return False
        return message.from_user.id == Config.ADMIN_ID


@competition_router.message(Command("start_family_competition", ignore_case=True), AdminFilter())
async def cmd_start_family_competition(message: Message, bot: Bot):
    if not message.from_user:
        return await message.reply("Не удалось определить администратора.")
    admin_link = get_user_mention_html(message.from_user.id, message.from_user.full_name, message.from_user.username)

    try:
        active_comp = await database.get_active_family_competition()
        if active_comp:
            end_ts_value = active_comp.get('end_ts')
            comp_end_local_str = "дата неизвестна"
            if end_ts_value:
                comp_end_local_str = end_ts_value.astimezone(pytz_timezone(Config.TIMEZONE)).strftime('%Y-%m-%d %H:%M:%S %Z')
            return await message.reply(
                f"Активное соревнование уже идет! ID: {active_comp['competition_id']}.\n"
                f"Завершится: {comp_end_local_str}"
            )

        competition_id = await database.create_family_competition(message.from_user.id, Config.COMPETITION_DURATION_DAYS)
        if competition_id:
            comp_details = None
            conn = None
            try:
                conn = await database.get_connection()
                comp_details_row = await conn.fetchrow("SELECT start_ts, end_ts FROM family_competitions WHERE competition_id = $1", competition_id)
                if comp_details_row: comp_details = dict(comp_details_row)
            except Exception as e_db:
                print(f"Error fetching new competition details by ID {competition_id}: {e_db}")
                await send_telegram_log(bot, f"⚠️ Ошибка получения деталей соревнования {competition_id} после создания: <pre>{html.escape(str(e_db))}</pre>")
            finally:
                if conn and not conn.is_closed(): await conn.close()

            if comp_details and comp_details.get('start_ts') and comp_details.get('end_ts'):
                start_local = comp_details['start_ts'].astimezone(pytz_timezone(Config.TIMEZONE))
                end_local = comp_details['end_ts'].astimezone(pytz_timezone(Config.TIMEZONE))
                reply_text = (
                    f"🏆 Новое соревнование семей запущенно!\n"
                    f"ID Соревнования: <code>{competition_id}</code>\n"
                    f"Начало: {start_local.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
                    f"Окончание: {end_local.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
                    f"Длительность: {Config.COMPETITION_DURATION_DAYS} дня(дней).\n"
                    f"Ежедневный подсчет очков после {Config.RESET_HOUR}:00 по времени {Config.TIMEZONE}."
                )
                await message.reply(reply_text)
                await send_telegram_log(bot, f"🚀 Админ {admin_link} запустил соревнование семей ID: {competition_id}.")
            else:
                await message.reply(f"Соревнование создано (ID: {competition_id}), но не удалось получить его полные детали. Проверьте статус позже.")
                await send_telegram_log(bot, f"⚠️ Админ {admin_link} запустил соревнование ID: {competition_id}, но детали для анонса не получены.")
        else:
            await message.reply("Не удалось запустить новое соревнование. Возможно, одно уже активно, или произошла ошибка БД.")
            await send_telegram_log(bot, f"🔴 Админ {admin_link} не смог запустить соревнование. Возможна активная сессия или ошибка БД.")
    except Exception as e:
        await message.reply("Произошла критическая ошибка при запуске соревнования.")
        await send_telegram_log(bot, f"🔴 Критическая ошибка в /start_family_competition (админ {admin_link}): <pre>{html.escape(str(e))}</pre>")


@competition_router.message(Command("family_competition_status", "fc_status", ignore_case=True))
async def cmd_family_competition_status(message: Message, bot: Bot):
    user_mention = ""
    if message.from_user:
        user_mention = get_user_mention_html(message.from_user.id, message.from_user.full_name, message.from_user.username)

    try:
        active_comp = await database.get_active_family_competition()
        status_message = ""
        comp_to_display_id = None
        header_leaderboard = ""

        if not active_comp:
            last_completed_unrewarded = await database.get_latest_completed_unrewarded_competition()
            if last_completed_unrewarded:
                comp_to_display = last_completed_unrewarded
                comp_to_display_id = comp_to_display.get('competition_id')
                end_ts_value = comp_to_display.get('end_ts')
                end_local_str = "дата неизвестна"
                if end_ts_value:
                     end_local_str = end_ts_value.astimezone(pytz_timezone(Config.TIMEZONE)).strftime('%Y-%m-%d %H:%M')
                status_message = (
                    f"🏁 Соревнование ID <code>{comp_to_display_id}</code> завершилось "
                    f"{end_local_str}, "
                    f"ожидается подведение итогов и награждение.\n"
                )
                header_leaderboard = "\n<b>Лидеры на момент завершения:</b>\n"
            else:
                return await message.reply("На данный момент активных или недавно завершенных соревнований семей нет.")
        else:
            comp_to_display = active_comp
            comp_to_display_id = comp_to_display.get('competition_id')
            start_ts_value = comp_to_display.get('start_ts')
            end_ts_value = comp_to_display.get('end_ts')

            start_local_str = "дата неизвестна"
            end_local_str = "дата неизвестна"
            time_left_str = "Время не определено."

            if start_ts_value:
                start_local_str = start_ts_value.astimezone(pytz_timezone(Config.TIMEZONE)).strftime('%Y-%m-%d %H:%M:%S %Z')
            if end_ts_value:
                end_local_obj = end_ts_value.astimezone(pytz_timezone(Config.TIMEZONE))
                end_local_str = end_local_obj.strftime('%Y-%m-%d %H:%M:%S %Z')
                now_local = datetime.now(pytz_timezone(Config.TIMEZONE))
                time_left = end_local_obj - now_local
                if time_left.total_seconds() > 0:
                    days = time_left.days
                    hours, remainder = divmod(time_left.seconds, 3600)
                    minutes, _ = divmod(remainder, 60)
                    time_left_str = f"Осталось времени: {days} д. {hours} ч. {minutes} мин.\n"
                else:
                    time_left_str = "Соревнование должно было уже завершиться, ожидайте результатов.\n"
            status_message = (
                f"🏆 Идет соревнование семей! ID: <code>{comp_to_display_id}</code>\n"
                f"Началось: {start_local_str}\n"
                f"Завершится: {end_local_str}\n"
                f"{time_left_str}"
            )
            header_leaderboard = "\n<b>Текущие лидеры (топ-10):</b>\n" # Уточнили, что это топ-10 по умолчанию

        if comp_to_display_id:
            leaderboard = await database.get_competition_leaderboard(comp_to_display_id, limit=10)
            if leaderboard:
                status_message += header_leaderboard
                for i, entry in enumerate(leaderboard):
                    status_message += f"{i+1}. <b>{html.escape(entry['family_name'])}</b> - {entry['total_score']:.1f} очков\n"
            else:
                status_message += "Данных о счете семей для этого соревнования пока нет."
        elif not active_comp and not last_completed_unrewarded:
            pass
        else:
            status_message += "Не удалось получить детали соревнования для отображения лидеров."

        await message.reply(status_message, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        await message.reply("Произошла ошибка при получении статуса соревнования.")
        requested_by = f" (запросил {user_mention})" if user_mention else ""
        await send_telegram_log(bot, f"🔴 Ошибка в /fc_status{requested_by}: <pre>{html.escape(str(e))}</pre>")


@competition_router.message(Command("top_competition", "топ_соревнования", ignore_case=True))
async def cmd_top_competition_families(message: Message, bot: Bot):
    user_mention = ""
    if message.from_user:
        user_mention = get_user_mention_html(message.from_user.id, message.from_user.full_name, message.from_user.username)

    try:
        active_comp = await database.get_active_family_competition()
        if not active_comp:
            return await message.reply("Сейчас нет активного соревнования семей, чтобы показать топ.")

        competition_id = active_comp['competition_id']
        comp_name_str = f"соревнования ID <code>{competition_id}</code>" # Для сообщения

        leaderboard = await database.get_competition_leaderboard(competition_id, limit=5)

        if not leaderboard:
            return await message.reply(f"В текущем {comp_name_str} пока нет данных о счете семей для отображения топа.")

        response_lines = [f"<b>🏆 Топ-5 семей в текущем {comp_name_str}:</b>"]
        for i, entry in enumerate(leaderboard):
            response_lines.append(f"{i+1}. <b>{html.escape(entry['family_name'])}</b> - {entry['total_score']:.1f} очков")

        await message.reply("\n".join(response_lines), parse_mode="HTML", disable_web_page_preview=True)

    except Exception as e:
        await message.reply("Произошла ошибка при получении топа семей соревнования.")
        requested_by = f" (запросил {user_mention})" if user_mention else ""
        await send_telegram_log(bot, f"🔴 Ошибка в /top_competition{requested_by}: <pre>{html.escape(str(e))}</pre>")


def setup_competition_handlers(dp):
    dp.include_router(competition_router)
    print("Обработчики команд соревнований зарегистрированы.")