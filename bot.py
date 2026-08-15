import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ============================================================
# ВСТАВ СЮДИ ТОКЕН БОТА
# ============================================================

BOT_TOKEN = "8883290115:AAHY0DoUM0Pt_XBoQiDFe-FoLSN_t4SEM0o"


# ============================================================
# НАЛАШТУВАННЯ
# ============================================================

# Скільки подарунків показувати на одній сторінці
GIFTS_PER_PAGE = 8


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# ============================================================
# ОТРИМАННЯ ПОДАРУНКІВ
# ============================================================

async def get_gifts(bot):
    """
    Отримує всі подарунки, які Telegram дозволяє цьому боту
    відправляти.
    """

    result = await bot.get_available_gifts()

    return result.gifts


# ============================================================
# /start
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton(
                "🎁 Показати подарунки",
                callback_data="gifts_0",
            )
        ]
    ]

    await update.message.reply_text(
        "🎁 <b>Telegram Gifts</b>\n\n"
        "Тут можна переглянути подарунки, які доступні "
        "для відправлення через бота.\n\n"
        "Натисни кнопку нижче.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ============================================================
# ПОКАЗ ПОДАРУНКІВ
# ============================================================

async def show_gifts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        gifts = await get_gifts(context.bot)

        if not gifts:
            await query.edit_message_text(
                "❌ Telegram не повернув жодного доступного подарунка."
            )
            return

        page = int(query.data.split("_")[1])

        start_index = page * GIFTS_PER_PAGE
        end_index = start_index + GIFTS_PER_PAGE

        page_gifts = gifts[start_index:end_index]

        if not page_gifts:
            await query.answer(
                "Це остання сторінка.",
                show_alert=True,
            )
            return

        buttons = []

        for gift in page_gifts:
            price = gift.star_count

            # Назва подарунка у Bot API напряму не передається.
            # Використовуємо ID, ціну та emoji/стікер.
            sticker = gift.sticker

            emoji = "🎁"

            if sticker and getattr(sticker, "emoji", None):
                emoji = sticker.emoji

            text = f"{emoji} {price} ⭐"

            buttons.append(
                [
                    InlineKeyboardButton(
                        text,
                        callback_data=f"gift:{gift.id}",
                    )
                ]
            )

        # Навігація
        navigation = []

        if page > 0:
            navigation.append(
                InlineKeyboardButton(
                    "⬅️ Назад",
                    callback_data=f"gifts_{page - 1}",
                )
            )

        if end_index < len(gifts):
            navigation.append(
                InlineKeyboardButton(
                    "➡️ Далі",
                    callback_data=f"gifts_{page + 1}",
                )
            )

        if navigation:
            buttons.append(navigation)

        buttons.append(
            [
                InlineKeyboardButton(
                    "🔄 Оновити",
                    callback_data=f"gifts_{page}",
                )
            ]
        )

        text = (
            f"🎁 <b>Доступні подарунки</b>\n\n"
            f"Сторінка: {page + 1}\n"
            f"Усього подарунків: {len(gifts)}\n\n"
            f"Натисни на подарунок:"
        )

        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    except Exception as e:
        logger.exception("Помилка отримання подарунків")

        await query.edit_message_text(
            f"❌ Помилка:\n<code>{e}</code>",
            parse_mode="HTML",
        )


# ============================================================
# ІНФОРМАЦІЯ ПРО КОНКРЕТНИЙ ПОДАРУНОК
# ============================================================

async def gift_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    gift_id = query.data.split(":", 1)[1]

    try:
        gifts = await get_gifts(context.bot)

        gift = next(
            (g for g in gifts if g.id == gift_id),
            None,
        )

        if gift is None:
            await query.edit_message_text(
                "❌ Цей подарунок більше недоступний."
            )
            return

        price = gift.star_count

        emoji = "🎁"

        if gift.sticker and getattr(gift.sticker, "emoji", None):
            emoji = gift.sticker.emoji

        text = (
            f"{emoji} <b>Подарунок</b>\n\n"
            f"🆔 ID: <code>{gift.id}</code>\n"
            f"⭐ Ціна: <b>{price}</b>\n"
        )

        if gift.total_count is not None:
            text += (
                f"📦 Загальна кількість: {gift.total_count}\n"
                f"📦 Залишилось: {gift.remaining_count}\n"
            )

        if gift.upgrade_star_count is not None:
            text += (
                f"⬆️ Апгрейд: {gift.upgrade_star_count} ⭐\n"
            )

        keyboard = [
            [
                InlineKeyboardButton(
                    f"🎁 Купити за {price} ⭐",
                    callback_data=f"buy:{gift.id}",
                )
            ],
            [
                InlineKeyboardButton(
                    "⬅️ Назад",
                    callback_data="gifts_0",
                )
            ],
        ]

        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    except Exception as e:
        logger.exception("Помилка інформації про подарунок")

        await query.edit_message_text(
            f"❌ Помилка:\n<code>{e}</code>",
            parse_mode="HTML",
        )


# ============================================================
# ПОКУПКА / ВІДПРАВКА ПОДАРУНКА
# ============================================================

async def buy_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    gift_id = query.data.split(":", 1)[1]

    try:
        gifts = await get_gifts(context.bot)

        gift = next(
            (g for g in gifts if g.id == gift_id),
            None,
        )

        if gift is None:
            await query.edit_message_text(
                "❌ Подарунок більше недоступний."
            )
            return

        price = gift.star_count

        # ====================================================
        # ВАЖЛИВО
        #
        # Telegram сам проводить оплату такого подарунка.
        # Бот не повинен сам створювати invoice для Gift.
        # ====================================================

        await context.bot.send_gift(
            user_id=query.from_user.id,
            gift_id=gift.id,
        )

        await query.edit_message_text(
            "🎉 <b>Подарунок відправлено!</b>\n\n"
            f"🎁 Подарунок: <code>{gift.id}</code>\n"
            f"⭐ Ціна: {price} Stars",
            parse_mode="HTML",
        )

    except Exception as e:
        logger.exception("Помилка відправлення подарунка")

        error = str(e)

        await query.edit_message_text(
            "❌ <b>Не вдалося відправити подарунок.</b>\n\n"
            f"<code>{error}</code>",
            parse_mode="HTML",
        )


# ============================================================
# /gifts
# ============================================================

async def gifts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton(
                "🎁 Відкрити подарунки",
                callback_data="gifts_0",
            )
        ]
    ]

    await update.message.reply_text(
        "🎁 Натисни кнопку, щоб переглянути подарунки.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ============================================================
# MAIN
# ============================================================

def main():
    if BOT_TOKEN == "ВСТАВ_СЮДИ_ТОКЕН_ВІД_BOTFATHER":
        raise RuntimeError(
            "Ти не вставив BOT_TOKEN у код!"
        )

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("gifts", gifts_command)
    )

    application.add_handler(
        CallbackQueryHandler(
            show_gifts,
            pattern=r"^gifts_\d+$",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            gift_info,
            pattern=r"^gift:",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            buy_gift,
            pattern=r"^buy:",
        )
    )

    print("🤖 Бот запущений!")

    application.run_polling()


if __name__ == "__main__":
    main()
