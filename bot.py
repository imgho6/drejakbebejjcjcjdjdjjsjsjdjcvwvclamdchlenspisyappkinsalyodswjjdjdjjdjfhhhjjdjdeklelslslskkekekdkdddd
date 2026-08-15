import logging
import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from telethon import TelegramClient, functions, types


# ============================================================
# БОТ
# ============================================================

BOT_TOKEN = "8883290115:AAHY0DoUM0Pt_XBoQiDFe-FoLSN_t4SEM0o"


# ============================================================
# ОСОБИСТИЙ TELEGRAM-АКАУНТ
# ============================================================
# Саме цей акаунт платить Stars зі СВОГО балансу.
# Bot API не може витратити особисті Stars користувача.
#
# API_ID та API_HASH отримуються на my.telegram.org.
# SESSION_STRING треба один раз згенерувати для свого акаунта.
# Не передавай SESSION_STRING нікому: він фактично дає доступ
# до авторизованої сесії Telegram.

# API_ID та API_HASH можна НЕ вписувати в код.
# Команда /setup попросить їх у приватному чаті.
API_ID = 0
API_HASH = ""

# SESSION_STRING НЕ вводимо через чат бота.
# Його треба один раз безпечно згенерувати локально.
SESSION_STRING = "ВСТАВ_SESSION_STRING"


# ID твого Telegram-користувача.
# Якщо залишити 0, бот використовуватиме ID того, хто натиснув
# кнопку. Для безпеки краще вписати свій ID.
OWNER_ID = 0


GIFTS_PER_PAGE = 8


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

client = TelegramClient("gift_buyer", API_ID, API_HASH)

setup_state = {}


async def get_all_gifts():
    """
    Отримує StarGift через MTProto від особистого акаунта.

    Це принципово відрізняється від Bot API getAvailableGifts:
    Bot API показує лише подарунки, які Telegram дозволяє боту
    надсилати, а тут використовується payments.getStarGifts.
    """
    result = await client(functions.payments.GetStarGiftsRequest(hash=0))

    if isinstance(result, types.payments.StarGifts):
        return result.gifts

    return []


def gift_name(gift):
    """Намагається отримати зрозумілу назву подарунка."""
    # У StarGift назва може бути відсутня на рівні самого об'єкта.
    # У такому випадку показуємо ID, щоб його можна було знайти.
    return f"Gift {gift.id}"


def is_limited(gift):
    return bool(getattr(gift, "limited", False))


def is_sold_out(gift):
    return bool(getattr(gift, "sold_out", False))


def is_hidden_candidate(gift):
    """
    Старі подарунки можуть не мати обмеженої кількості.
    Ми НЕ викидаємо їх тільки тому, що вони відсутні в магазині.
    """
    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if OWNER_ID and update.effective_user.id != OWNER_ID:
        await update.message.reply_text("⛔ Цей бот приватний.")
        return

    keyboard = [[InlineKeyboardButton("🎁 Показати подарунки", callback_data="gifts_0")]]

    await update.message.reply_text(
        "🎁 <b>Hidden Telegram Gifts</b>\n\n"
        "Каталог отримується через MTProto від твого особистого Telegram-акаунта.\n"
        "Покупка списує Stars саме з його балансу.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def setup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Починає безпечне налаштування API_ID/API_HASH через чат."""
    if OWNER_ID and update.effective_user.id != OWNER_ID:
        await update.message.reply_text("⛔ Цей бот приватний.")
        return

    setup_state[update.effective_user.id] = "api_id"
    await update.message.reply_text(
        "Налаштування. Надішли API_ID з my.telegram.org.\n\n"
        "⚠️ Не надсилай сюди номер телефону, код входу, пароль 2FA "
        "або SESSION_STRING."
    )


async def setup_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приймає API_ID та API_HASH через приватний чат бота."""
    user_id = update.effective_user.id
    state = setup_state.get(user_id)

    if not state or not update.message or not update.message.text:
        return

    value = update.message.text.strip()

    if state == "api_id":
        try:
            api_id = int(value)
            if api_id <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❌ API_ID має бути додатним числом. Спробуй ще раз.")
            return

        setup_state[user_id] = "api_hash"
        context.user_data["setup_api_id"] = api_id
        await update.message.reply_text(
            "Добре. Тепер надішли API_HASH з my.telegram.org.\n\n"
            "Не надсилай SESSION_STRING, номер телефону або код входу."
        )
        return

    if state == "api_hash":
        if len(value) < 20:
            await update.message.reply_text("❌ Схоже, API_HASH некоректний. Спробуй ще раз.")
            return

        context.user_data["setup_api_hash"] = value
        setup_state.pop(user_id, None)

        global client
        global API_ID, API_HASH

        API_ID = context.user_data["setup_api_id"]
        API_HASH = context.user_data["setup_api_hash"]

        # Перепідключаємо MTProto з отриманими даними.
        await client.disconnect()
        client = TelegramClient("gift_buyer", API_ID, API_HASH)

        try:
            await client.connect()
        except Exception as e:
            logger.exception("Не вдалося підключити MTProto")
            await update.message.reply_text(
                f"❌ Не вдалося підключити Telegram API:\n<code>{e}</code>",
                parse_mode="HTML",
            )
            return

        await update.message.reply_text(
            "✅ API_ID та API_HASH отримано.\n\n"
            "Для входу особистого Telegram-акаунта потрібен SESSION_STRING. "
            "Я навмисно не приймаю його через чат бота, бо це секрет авторизованої сесії.\n\n"
            "Згенеруй SESSION_STRING локально та встав його в код/секрет Render. "
            "Після цього перезапусти бота."
        )


async def show_gifts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if OWNER_ID and query.from_user.id != OWNER_ID:
        await query.answer("⛔ Доступ заборонено.", show_alert=True)
        return

    try:
        gifts = await get_all_gifts()
        gifts = [g for g in gifts if is_hidden_candidate(g)]

        if not gifts:
            await query.edit_message_text("❌ Telegram не повернув Star Gifts через MTProto.")
            return

        page = int(query.data.split("_")[1])
        start_index = page * GIFTS_PER_PAGE
        end_index = start_index + GIFTS_PER_PAGE
        page_gifts = gifts[start_index:end_index]

        if not page_gifts:
            await query.answer("Це остання сторінка.", show_alert=True)
            return

        buttons = []

        for gift in page_gifts:
            price = gift.stars
            flags = []

            if is_sold_out(gift):
                flags.append("SOLD OUT")
            if is_limited(gift):
                flags.append("limited")

            suffix = f" [{', '.join(flags)}]" if flags else ""

            buttons.append([
                InlineKeyboardButton(
                    f"🎁 {gift_name(gift)} — {price} ⭐{suffix}",
                    callback_data=f"gift:{gift.id}",
                )
            ])

        navigation = []

        if page > 0:
            navigation.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"gifts_{page - 1}"))

        if end_index < len(gifts):
            navigation.append(InlineKeyboardButton("➡️ Далі", callback_data=f"gifts_{page + 1}"))

        if navigation:
            buttons.append(navigation)

        buttons.append([InlineKeyboardButton("🔄 Оновити", callback_data=f"gifts_{page}")])

        await query.edit_message_text(
            f"🎁 <b>Star Gifts через MTProto</b>\n\n"
            f"Сторінка: {page + 1}\n"
            f"Усього отримано: {len(gifts)}\n\n"
            "Натисни на подарунок.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    except Exception as e:
        logger.exception("Помилка отримання Star Gifts")
        await query.edit_message_text(f"❌ Помилка:\n<code>{e}</code>", parse_mode="HTML")


async def gift_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if OWNER_ID and query.from_user.id != OWNER_ID:
        await query.answer("⛔ Доступ заборонено.", show_alert=True)
        return

    gift_id = int(query.data.split(":", 1)[1])

    try:
        gifts = await get_all_gifts()
        gift = next((g for g in gifts if g.id == gift_id), None)

        if gift is None:
            await query.edit_message_text(
                "❌ Цей подарунок не повертається Telegram через payments.getStarGifts."
            )
            return

        text = (
            f"🎁 <b>{gift_name(gift)}</b>\n\n"
            f"🆔 ID: <code>{gift.id}</code>\n"
            f"⭐ Ціна: <b>{gift.stars}</b>\n"
            f"📦 Limited: {is_limited(gift)}\n"
            f"📦 Sold out: {is_sold_out(gift)}\n"
        )

        if getattr(gift, "availability_remains", None) is not None:
            text += f"📦 Залишилось: {gift.availability_remains}\n"

        if is_sold_out(gift):
            keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="gifts_0")]]
        else:
            keyboard = [
                [InlineKeyboardButton(
                    f"🎁 Купити за {gift.stars} ⭐",
                    callback_data=f"buy:{gift.id}",
                )],
                [InlineKeyboardButton("⬅️ Назад", callback_data="gifts_0")],
            ]

        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    except Exception as e:
        logger.exception("Помилка інформації про подарунок")
        await query.edit_message_text(f"❌ Помилка:\n<code>{e}</code>", parse_mode="HTML")


async def buy_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Реальна покупка через особистий MTProto-акаунт.

    Telegram офіційно описує для Star Gifts такий flow:
    getPaymentForm(inputInvoiceStarGift) -> sendStarsForm.
    sendStarsForm списує Stars із балансу поточного користувача.
    """
    query = update.callback_query
    await query.answer()

    if OWNER_ID and query.from_user.id != OWNER_ID:
        await query.answer("⛔ Доступ заборонено.", show_alert=True)
        return

    gift_id = int(query.data.split(":", 1)[1])

    try:
        gifts = await get_all_gifts()
        gift = next((g for g in gifts if g.id == gift_id), None)

        if gift is None:
            await query.edit_message_text("❌ Подарунок більше не доступний у Telegram API.")
            return

        if is_sold_out(gift):
            await query.edit_message_text("❌ Цей подарунок sold out і його не можна купити звичайним способом.")
            return

        # Подарунок надсилається тому самому користувачу, який керує ботом.
        # За потреби це можна замінити на вибір отримувача.
        receiver = await client.get_input_entity(query.from_user.id)

        invoice = types.InputInvoiceStarGift(
            peer=receiver,
            gift_id=gift.id,
        )

        form = await client(functions.payments.GetPaymentFormRequest(invoice=invoice))

        if not isinstance(form, types.payments.PaymentFormStarGift):
            await query.edit_message_text(
                "❌ Telegram повернув не форму оплати Star Gift."
            )
            return

        # Це саме списання Stars з особистого балансу акаунта.
        result = await client(functions.payments.SendStarsFormRequest(
            form_id=form.form_id,
            invoice=invoice,
        ))

        await query.edit_message_text(
            "🎉 <b>Подарунок успішно куплено!</b>\n\n"
            f"🎁 Gift ID: <code>{gift.id}</code>\n"
            f"⭐ Списано: <b>{gift.stars}</b> Stars",
            parse_mode="HTML",
        )

    except Exception as e:
        logger.exception("Помилка покупки подарунка")
        await query.edit_message_text(
            "❌ <b>Не вдалося купити подарунок.</b>\n\n"
            f"<code>{e}</code>",
            parse_mode="HTML",
        )


async def gifts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🎁 Відкрити подарунки", callback_data="gifts_0")]]
    await update.message.reply_text(
        "🎁 Натисни кнопку, щоб переглянути Star Gifts.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def post_init(application):
    global client

    # Якщо API_ID/API_HASH були введені через setup,
    # використовуємо їх для поточної сесії.
    # Після перезапуску Render ці значення треба зберегти в коді
    # або в секретах/Environment Variables.
    if API_ID and API_HASH:
        client = TelegramClient("gift_buyer", API_ID, API_HASH)

    await client.start()
    logger.info("MTProto user session connected")


async def post_shutdown(application):
    await client.disconnect()


def main():
    if BOT_TOKEN == "ВСТАВ_СЮДИ_ТОКЕН_ВІД_BOTFATHER":
        raise RuntimeError("Встав BOT_TOKEN у код")

    if SESSION_STRING == "ВСТАВ_SESSION_STRING":
        raise RuntimeError("Встав SESSION_STRING особистого Telegram-акаунта у код")

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setup", setup_command))
    application.add_handler(CallbackQueryHandler(show_gifts, pattern=r"^gifts_\d+$"))
    application.add_handler(CallbackQueryHandler(gift_info, pattern=r"^gift:"))
    application.add_handler(CallbackQueryHandler(buy_gift, pattern=r"^buy:"))
    # Текстові повідомлення для /setup повинні оброблятися до інших текстових handler'ів.
    from telegram.ext import MessageHandler, filters
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, setup_message))

    print("🤖 Бот запущений!")
    application.run_polling()


if __name__ == "__main__":
    main()
