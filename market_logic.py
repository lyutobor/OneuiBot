import asyncio
import html
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Optional

from aiogram import Router, Bot, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from achievements_logic import check_and_grant_achievements



# Убедитесь, что Config импортируется правильно
try:
    from config import Config
except ImportError:
    # Это может произойти, если структура проекта не позволяет прямой импорт.
    # В таком случае, возможно, понадобится from .config import Config или другая настройка.
    # Для простоты предполагаем, что Config доступен.
    # Если будут проблемы с импортом, сообщите.
    raise ImportError("Не удалось импортировать Config в market_logic.py")


# Убедитесь, что database и utils импортируются правильно
try:
    import database
    from utils import get_user_mention_html, send_telegram_log, get_current_price
    # >>> ВАЖНО: Добавьте этот импорт <<<
    from phone_logic import get_active_user_phone_bonuses
except ImportError:
    raise ImportError("Не удалось импортировать database, utils или phone_logic в market_logic.py")

import logging
# Импорт asyncpg для обработки исключения ForeignKeyViolationError
try:
    import asyncpg # Добавлен импорт
except ImportError:
    asyncpg = None # Установка в None, если asyncpg не используется или не установлен
    logger.warning("asyncpg не установлен. ForeignKeyViolationError не будет обрабатываться специфично.")


logger = logging.getLogger(__name__)
market_router = Router()

class MarketPurchaseStates(StatesGroup):
    awaiting_confirmation = State()

CONFIRMATION_TEXT_YES = "да" # Можно вынести в Config, если нужно менять
CONFIRMATION_TEXT_NO = "нет" # Аналогично

@market_router.message(Command(*Config.MARKET_COMMAND_ALIASES, ignore_case=True))
async def cmd_market_show(message: Message, bot: Bot):
    if not message.from_user:
        await message.reply("Не удалось определить пользователя.", disable_web_page_preview=True)
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    user_link = get_user_mention_html(user_id, message.from_user.full_name, message.from_user.username)

    conn_market_prices = None
    try:
        conn_market_prices = await database.get_connection()
        balance = await database.get_user_onecoins(user_id, chat_id, conn_ext=conn_market_prices)

        response_lines = [
            f"🏪 <b>Рынок Попыток</b>",
            f"{user_link}, ваш баланс в этом чате: <code>{balance}</code> OneCoin(s).",
            "--------------------",
            "<b>Доступные товары:</b>"
        ]

        if not Config.MARKET_ITEMS:
            response_lines.append("На данный момент товаров на рынке нет.")
        else:
            for item_key, item_details in Config.MARKET_ITEMS.items():
                item_price_display = 0
                if item_key == "oneui_attempt":
                    # ИЗМЕНЕНИЕ ЗДЕСЬ: Используем Config.MIN_MARKET_DYNAMIC_PRICE
                    item_price_display = int(max(Config.MIN_MARKET_DYNAMIC_PRICE, balance * Config.MARKET_ONEUI_ATTEMPT_PERCENT_OF_BALANCE))
                elif item_key == "roulette_spin":
                    # ИЗМЕНЕНИЕ ЗДЕСЬ: Используем Config.MIN_MARKET_DYNAMIC_PRICE
                    item_price_display = int(max(Config.MIN_MARKET_DYNAMIC_PRICE, balance * Config.MARKET_ROULETTE_SPIN_PERCENT_OF_BALANCE))
                elif item_key == "bonus_attempt":
                    # ИЗМЕНЕНИЕ ЗДЕСЬ: Используем Config.MIN_MARKET_DYNAMIC_PRICE
                    item_price_display = int(max(Config.MIN_MARKET_DYNAMIC_PRICE, balance * Config.MARKET_BONUS_ATTEMPT_PERCENT_OF_BALANCE))
                else:
                    # Для остальных товаров (если будут), используем старую логику с инфляцией
                    base_price = item_details['price']
                    item_price_display = await get_current_price(base_price, conn_ext=conn_market_prices)
                
                item_display_string = (
                    f"🔹 <b>{html.escape(item_details['name'])}</b>\n"
                    f"   Цена: <code>{item_price_display}</code> OneCoin(s)\n" # disable_web_page_preview=True здесь не нужен
                    f"   Описание: <i>{html.escape(item_details['description'])}</i>\n"
                    f"   Для покупки: <code>/{Config.MARKET_BUY_COMMAND_ALIASES[0]} {item_key}</code>"
                )
                response_lines.append(item_display_string)
                response_lines.append("---")

        await message.reply("\n".join(response_lines), parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Market: Ошибка в cmd_market_show для user {user_id} chat {chat_id}: {e}", exc_info=True)
        await message.reply("Произошла ошибка при отображении товаров рынка.", disable_web_page_preview=True)
        await send_telegram_log(bot, f"🔴 Ошибка в /market для {user_link} (<code>{user_id}@{chat_id}</code>): <pre>{html.escape(str(e))}</pre>")
    finally:
        if conn_market_prices and not conn_market_prices.is_closed():
            await conn_market_prices.close()


@market_router.message(Command(*Config.MARKET_BUY_COMMAND_ALIASES, ignore_case=True))
async def cmd_market_buy_item(message: Message, command: CommandObject, state: FSMContext, bot: Bot):
    if not message.from_user:
        await message.reply("Не удалось определить пользователя.", disable_web_page_preview=True)
        return

    user_id = message.from_user.id
    chat_id = message.chat.id # Используем chat_id из сообщения для контекста рынка
    user_full_name = message.from_user.full_name
    user_tg_username = message.from_user.username
    user_link = get_user_mention_html(user_id, user_full_name, user_tg_username)

    if command.args is None:
        await message.reply(
            "Пожалуйста, укажите идентификатор товара, который хотите купить.\n"
            f"Пример: `/{Config.MARKET_BUY_COMMAND_ALIASES[0]} oneui_attempt`\n"
            f"Список товаров можно посмотреть командой `/{Config.MARKET_COMMAND_ALIASES[0]}`.",
            disable_web_page_preview=True
        )
        return

    item_key_to_buy = command.args.strip().lower()

    if item_key_to_buy not in Config.MARKET_ITEMS:
        await message.reply(
            f"Товар с идентификатором '<code>{html.escape(item_key_to_buy)}</code>' не найден на рынке.\n"
            f"Используйте команду `/{Config.MARKET_COMMAND_ALIASES[0]}` , чтобы увидеть доступные товары и их идентификаторы.",
            disable_web_page_preview=True
        )
        return

    item_details = Config.MARKET_ITEMS[item_key_to_buy]
    
    conn_market_buy = None
    try:
        conn_market_buy = await database.get_connection()
        current_balance = await database.get_user_onecoins(user_id, chat_id, conn_ext=conn_market_buy)

        final_total_price_to_charge = 0
        original_price_display_if_discounted = 0 
        
        if item_key_to_buy == "oneui_attempt":
            final_total_price_to_charge = int(max(Config.MIN_MARKET_DYNAMIC_PRICE, current_balance * Config.MARKET_ONEUI_ATTEMPT_PERCENT_OF_BALANCE))
            original_price_display_if_discounted = final_total_price_to_charge 
        elif item_key_to_buy == "roulette_spin":
            final_total_price_to_charge = int(max(Config.MIN_MARKET_DYNAMIC_PRICE, current_balance * Config.MARKET_ROULETTE_SPIN_PERCENT_OF_BALANCE))
            original_price_display_if_discounted = final_total_price_to_charge
        elif item_key_to_buy == "bonus_attempt":
            final_total_price_to_charge = int(max(Config.MIN_MARKET_DYNAMIC_PRICE, current_balance * Config.MARKET_BONUS_ATTEMPT_PERCENT_OF_BALANCE))
            original_price_display_if_discounted = final_total_price_to_charge
        else:
            base_item_price_per_unit = item_details['price']
            actual_item_price_per_unit = await get_current_price(base_item_price_per_unit, conn_ext=conn_market_buy)
            final_total_price_to_charge = actual_item_price_per_unit
            original_price_display_if_discounted = final_total_price_to_charge
        
        # quantity_to_buy всегда 1 для этих товаров
        
        applied_discount_percent = 0.0
        
        if user_id:
            try:
                phone_bonuses = await get_active_user_phone_bonuses(user_id) #
                market_discount_p = phone_bonuses.get("market_discount_percent", 0.0)
                
                if market_discount_p > 0:
                    logger.info(f"MarketBuy: User {user_id} has phone discount {market_discount_p}%. Price before discount (dynamic/inflation): {final_total_price_to_charge}")
                    discount_amount = int(round(final_total_price_to_charge * (market_discount_p / 100.0)))
                    final_total_price_to_charge -= discount_amount
                    if final_total_price_to_charge < 0: final_total_price_to_charge = 0
                    applied_discount_percent = market_discount_p
                    logger.info(f"MarketBuy: User {user_id} after phone discount, final price to charge: {final_total_price_to_charge}")
            except Exception as e_market_discount:
                logger.error(f"MarketBuy: Error applying phone discount for user {user_id}: {e_market_discount}", exc_info=True)
        
        if current_balance < final_total_price_to_charge:
            price_message = f"<code>{final_total_price_to_charge}</code>"
            if applied_discount_percent > 0:
                price_message += f" (с учетом скидки {applied_discount_percent:.0f}%; обычная цена: {original_price_display_if_discounted})"
            
            await message.reply(
                f"{user_link}, у вас недостаточно средств для покупки товара "
                f"\"<b>{html.escape(item_details['name'])}</b>\" (нужно {price_message}, у вас <code>{current_balance}</code> OneCoin(s)).",
                disable_web_page_preview=True
            )
            if conn_market_buy and not conn_market_buy.is_closed(): await conn_market_buy.close()
            return

        await state.set_state(MarketPurchaseStates.awaiting_confirmation)
        state_data_for_fsm = {
            "item_key": item_key_to_buy,
            "item_name": item_details['name'],
            "item_price_final": final_total_price_to_charge,
            "item_db_field": item_details['db_field'],
            "confirmation_initiated_at": datetime.now(dt_timezone.utc).isoformat(),
            "original_chat_id": chat_id,
            "original_user_id": user_id
        }
        if applied_discount_percent > 0:
            state_data_for_fsm["original_market_price_before_discount"] = original_price_display_if_discounted
            state_data_for_fsm["applied_discount_percent"] = applied_discount_percent

        await state.update_data(**state_data_for_fsm)

        confirmation_message_str = f"{user_link}, вы хотите купить \"<b>{html.escape(item_details['name'])}</b>\" "
        if applied_discount_percent > 0:
            confirmation_message_str += (f"за <code>{final_total_price_to_charge}</code> OneCoin(s) "
                                         f"(обычная цена с инфляцией: <code>{original_price_display_if_discounted}</code>, ваша скидка {applied_discount_percent:.0f}%)?\n")
        else:
            confirmation_message_str += f"за <code>{final_total_price_to_charge}</code> OneCoin(s)?\n"

        confirmation_message_str += (f"У вас на балансе: <code>{current_balance}</code> OneCoin(s).\n"
                                     f"Ответьте '<b>{CONFIRMATION_TEXT_YES}</b>' или '<b>{CONFIRMATION_TEXT_NO}</b>' "
                                     f"в течение {Config.MARKET_PURCHASE_CONFIRMATION_TIMEOUT_SECONDS} секунд.")

        await message.reply(confirmation_message_str, parse_mode="HTML", disable_web_page_preview=True)

    except Exception as e_market_buy:
        logger.error(f"MarketBuy: Ошибка в cmd_market_buy_item (до FSM) для user {user_id} chat {chat_id}, item {item_key_to_buy}: {e_market_buy}", exc_info=True)
        await message.reply("Произошла ошибка при подготовке к покупке. Попробуйте позже.", disable_web_page_preview=True)
        await send_telegram_log(bot, f"🔴 Ошибка в /{Config.MARKET_BUY_COMMAND_ALIASES[0]} (до FSM) для {user_link}, товар {item_key_to_buy}: <pre>{html.escape(str(e_market_buy))}</pre>")
    finally:
        if conn_market_buy and not conn_market_buy.is_closed():
            await conn_market_buy.close()


@market_router.message(MarketPurchaseStates.awaiting_confirmation, F.text.lower() == CONFIRMATION_TEXT_YES)
async def market_purchase_confirm_yes(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id

    user_data_from_state = await state.get_data()
    state_user_id = user_data_from_state.get('original_user_id')
    item_key = user_data_from_state.get('item_key')
    item_name = user_data_from_state.get('item_name')
    # Используем final_total_price, сохраненную как item_price_final
    item_price_final = user_data_from_state.get('item_price_final')
    item_db_field = user_data_from_state.get('item_db_field')
    confirmation_initiated_at_iso = user_data_from_state.get('confirmation_initiated_at')
    original_chat_id = user_data_from_state.get('original_chat_id')
    original_market_price = user_data_from_state.get('original_market_price') # Может быть None
    applied_discount_percent = user_data_from_state.get('applied_discount_percent') # Может быть None


    if state_user_id != user_id:
        await message.reply("Подтверждать покупку должен тот же пользователь, который ее начал.")
        return

    user_full_name = message.from_user.full_name
    user_tg_username = message.from_user.username
    user_link = get_user_mention_html(user_id, user_full_name, user_tg_username)

    if not all([item_key, item_name, isinstance(item_price_final, int), item_db_field, confirmation_initiated_at_iso, original_chat_id is not None]):
        await state.clear()
        await message.reply("Произошла ошибка с данными покупки или ваш запрос устарел. Пожалуйста, начните сначала.")
        logger.warning(f"Market: Missing or invalid data in state for user {user_id} during purchase confirmation. State: {user_data_from_state}")
        return

    try:
        confirmation_initiated_at = datetime.fromisoformat(confirmation_initiated_at_iso)
        if (datetime.now(dt_timezone.utc) - confirmation_initiated_at) > timedelta(seconds=Config.MARKET_PURCHASE_CONFIRMATION_TIMEOUT_SECONDS):
            await state.clear()
            await message.reply(f"Время на подтверждение покупки товара \"<b>{html.escape(item_name)}</b>\" истекло. Попробуйте снова.")
            return
    except ValueError:
        await state.clear()
        await message.reply("Ошибка в формате времени подтверждения. Начните покупку заново.")
        logger.error(f"Market: ValueError parsing confirmation_initiated_at_iso for user {user_id}. ISO: {confirmation_initiated_at_iso}")
        return

    # Повторная проверка баланса с final_total_price (item_price_final)
    current_balance = await database.get_user_onecoins(user_id, original_chat_id)
    if current_balance < item_price_final:
        await state.clear()
        price_message = f"<code>{item_price_final}</code>"
        if applied_discount_percent and applied_discount_percent > 0:
             price_message += f" (с учетом скидки {applied_discount_percent}%)"
        await message.reply(
            f"{user_link}, к сожалению, у вас больше недостаточно средств (<code>{current_balance}</code> OneCoin(s)) "
            f"для покупки \"<b>{html.escape(item_name)}</b>\" (нужно {price_message} OneCoin(s))."
        )
        return

    try:
        # 1. Списать OneCoins (используем item_price_final)
        user_oneui_data_for_log = await database.get_user_data_for_update(user_id, original_chat_id)
        await database.update_user_onecoins(
            user_id, original_chat_id, -item_price_final,
            username=user_oneui_data_for_log.get('username'),
            full_name=user_oneui_data_for_log.get('full_name'),
            chat_title=user_oneui_data_for_log.get('chat_title')
        )

        # 2. Начислить попытку
        roulette_status = await database.get_roulette_status(user_id, original_chat_id)
        if roulette_status is None:
            await database.update_roulette_status(user_id, original_chat_id, {})
            roulette_status = await database.get_roulette_status(user_id, original_chat_id)
            if roulette_status is None:
                 logger.critical(f"Market: CRITICAL - Failed to create/get roulette_status for user {user_id} chat {original_chat_id} during purchase.")
                 raise Exception(f"Не удалось создать/получить данные для начисления попытки (user {user_id} chat {original_chat_id}).")

        current_attempts = roulette_status.get(item_db_field, 0)
        new_attempts_count = current_attempts + 1

        await database.update_roulette_status(user_id, original_chat_id, {item_db_field: new_attempts_count})

        new_balance = current_balance - item_price_final
        
        purchase_details_message = ""
        if original_market_price is not None and applied_discount_percent is not None and applied_discount_percent > 0:
            purchase_details_message = (f" (цена <code>{item_price_final}</code> OneCoin(s) "
                                        f"с учетом вашей скидки {applied_discount_percent}%, "
                                        f"вместо <code>{original_market_price}</code>)")
        else:
            purchase_details_message = f" за <code>{item_price_final}</code> OneCoin(s)"


        await message.reply(
            f"✅ {user_link}, вы успешно купили \"<b>{html.escape(item_name)}</b>\"{purchase_details_message}!\n"
            f"Теперь у вас <code>{new_attempts_count}</code> таких попыток (включая эту).\n"
            f"Ваш новый баланс: <code>{new_balance}</code> OneCoin(s)."
        )

        chat_title_for_log = html.escape(message.chat.title or f"ChatID {original_chat_id}")
        if message.chat.id != original_chat_id:
            logger.warning(f"Market: Purchase confirmation for user {user_id} for chat {original_chat_id} came from chat {message.chat.id}. Using original_chat_id for logging context.")
            try:
                chat_info_for_log = await bot.get_chat(original_chat_id)
                chat_title_for_log = html.escape(chat_info_for_log.title or f"ChatID {original_chat_id}")
            except Exception:
                pass

        log_message_price_part = f"Цена: <code>{item_price_final}</code> OneCoin(s)"
        if original_market_price is not None and applied_discount_percent is not None and applied_discount_percent > 0:
             log_message_price_part += (f" (Ориг. цена: <code>{original_market_price}</code>, "
                                        f"Скидка: {applied_discount_percent}%)")


        await send_telegram_log(
            bot,
            f"🛍️ <b>Покупка на Рынке</b>\n"
            f"Пользователь: {user_link} (ID: <code>{user_id}</code>)\n"
            f"Чат: {chat_title_for_log} (ID: <code>{original_chat_id}</code>)\n"
            f"Товар: \"{html.escape(item_name)}\" (ID: <code>{item_key}</code>)\n"
            f"{log_message_price_part}\n"
            f"Новый баланс: <code>{new_balance}</code> OneCoin(s)\n"
            f"Поле БД: <code>{item_db_field}</code>, новое значение: <code>{new_attempts_count}</code>"
        )
        logger.info(f"User {user_id} purchased '{item_key}' for {item_price_final} OneCoins (Original: {original_market_price if original_market_price else 'N/A'}, Discount: {applied_discount_percent if applied_discount_percent else '0'}%) in chat {original_chat_id}. Field {item_db_field} is now {new_attempts_count}.")


        # --- ВЫЗОВ ПРОВЕРКИ ДОСТИЖЕНИЙ ---
        await check_and_grant_achievements(
            user_id,
            original_chat_id,
            bot,
            market_buy_just_now=True, # Для "Первый Шаг В Грязь"
            market_buy_total_count=1, # Заглушка, нужно будет получать общий счетчик
            market_spend_total_amount=item_price_final # Для "Торговец Забытыми Душами"
        )
        # --- КОНЕЦ ВЫЗОВА ПРОВЕРКИ ДОСТИЖЕНИЙ ---

    except asyncpg.exceptions.ForeignKeyViolationError as fk_err: # Обработка конкретного исключения
        await message.reply(f"{user_link}, не удалось совершить покупку из-за системной ошибки (FKV). "
                            "Убедитесь, что вы хотя бы раз использовали `/oneui` в этом чате. "
                            "Если проблема повторяется, обратитесь к администратору.")
        logger.error(f"Market: ForeignKeyViolationError for user {user_id} in chat {original_chat_id} buying '{item_key}'. Details: {fk_err}", exc_info=False)
    except Exception as e:
        await message.reply(f"Произошла непредвиденная ошибка при совершении покупки \"<b>{html.escape(item_name)}</b>\". "
                            "Пожалуйста, проверьте свой баланс и количество попыток. Если что-то не так, обратитесь к администратору.")
        logger.error(f"Market: Error during purchase confirmation for user {user_id}, item '{item_key}': {e}", exc_info=True)
        await send_telegram_log(bot, f"🔴 КРИТИЧЕСКАЯ ОШИБКА при покупке товара '{item_key}' для {user_link} в чате {original_chat_id}: <pre>{html.escape(str(e))}</pre>")
    finally:
        await state.clear()

@market_router.message(MarketPurchaseStates.awaiting_confirmation, F.text.lower() == CONFIRMATION_TEXT_NO)
async def market_purchase_confirm_no(message: Message, state: FSMContext):
    user_data_from_state = await state.get_data()
    item_name = user_data_from_state.get('item_name', 'товар')
    await message.reply(f"Покупка товара \"<b>{html.escape(item_name)}</b>\" отменена.")
    await state.clear()

@market_router.message(MarketPurchaseStates.awaiting_confirmation)
async def market_purchase_invalid_confirmation(message: Message, state: FSMContext):
    user_data_from_state = await state.get_data()
    confirmation_initiated_at_iso = user_data_from_state.get('confirmation_initiated_at')
    item_name = user_data_from_state.get('item_name', 'товар')

    if confirmation_initiated_at_iso:
        try:
            confirmation_initiated_at = datetime.fromisoformat(confirmation_initiated_at_iso)
            if (datetime.now(dt_timezone.utc) - confirmation_initiated_at) > timedelta(seconds=Config.MARKET_PURCHASE_CONFIRMATION_TIMEOUT_SECONDS):
                await state.clear()
                await message.reply(f"Время на подтверждение покупки товара \"<b>{html.escape(item_name)}</b>\" истекло. Попробуйте снова.")
                return
        except ValueError:
            await state.clear()
            await message.reply("Ошибка состояния подтверждения. Пожалуйста, начните покупку заново.")
            return

    await message.reply(f"Пожалуйста, ответьте '<b>{CONFIRMATION_TEXT_YES}</b>' или '<b>{CONFIRMATION_TEXT_NO}</b>'.")

def setup_market_handlers(dp: Router):
    """Регистрирует обработчики команд Рынка."""
    dp.include_router(market_router)
    logger.info("Обработчики команд Рынка зарегистрированы.")
