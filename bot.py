import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError
import os

BOT_TOKEN = os.environ.get("BOT_TOKEN")

ADMIN_ID = 8678262416
REQUIRED_CHANNELS = ["@LoLo_LoLo_Lo_Lo", "@LoLo_funny2", "@LoLo_funny"]
CHANNEL_1 = -1004299938337
CHANNEL_2 = -1003826563552
PUBLIC_CHANNEL = "https://t.me/LoLo_funny2"
DELETE_AFTER_SECONDS = 8

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# نگه داشتن state ادمین
admin_state = {}  # ADMIN_ID -> {"step": ..., "channel": ...}

async def check_membership(user_id, context):
    not_joined = []
    for channel in REQUIRED_CHANNELS:
        try:
            member = await context.bot.get_chat_member(channel, user_id)
            if member.status in ["left", "kicked", "banned"]:
                not_joined.append(channel)
        except TelegramError:
            not_joined.append(channel)
    return not_joined

def build_join_keyboard(not_joined, msg_id=None):
    keyboard = [
        [InlineKeyboardButton(f"📢 عضویت در {c}", url=f"https://t.me/{c.replace('@', '')}")]
        for c in not_joined
    ]
    callback = f"checkjoin_{msg_id}" if msg_id else "checkjoin"
    keyboard.append([InlineKeyboardButton("✅ عضو شدم", callback_data=callback)])
    return InlineKeyboardMarkup(keyboard)

def build_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("📢 استارت", url=PUBLIC_CHANNEL)],
        [InlineKeyboardButton("🎧 پشتیبانی", callback_data="support")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args

    # اومده از دکمه مشاهده کانال
    if args and args[0].startswith("film_"):
        parts = args[0].split("_")
        channel_id = int(parts[1])
        msg_id = int(parts[2])
        not_joined = await check_membership(user.id, context)
        if not_joined:
            await update.message.reply_text(
                "🔒 برای دیدن محتوا اول عضو کانال‌ها شو 👇",
                reply_markup=build_join_keyboard(not_joined, f"{channel_id}_{msg_id}")
            )
            return
        await send_film(context, user.id, channel_id, msg_id)
        return

    # استارت معمولی
    not_joined = await check_membership(user.id, context)
    if not_joined:
        await update.message.reply_text(
            "🔒 برای استفاده از ربات اول عضو کانال‌ها شو 👇",
            reply_markup=build_join_keyboard(not_joined)
        )
        return

    await update.message.reply_text(
        f"👋 سلام {user.first_name} عزیز!\n\nیه گزینه انتخاب کن 👇",
        reply_markup=build_main_keyboard()
    )

async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data  # checkjoin یا checkjoin_CHANNELID_MSGID

    parts = data.split("_")
    film_info = f"{parts[1]}_{parts[2]}" if len(parts) > 2 else None

    not_joined = await check_membership(user_id, context)
    if not_joined:
        await query.edit_message_text(
            "❌ هنوز عضو همه کانال‌ها نشدی 👇",
            reply_markup=build_join_keyboard(not_joined, film_info)
        )
        return

    if film_info:
        await query.edit_message_text("✅ عضویت تایید شد! در حال ارسال...")
        channel_id = int(film_info.split("_")[0])
        msg_id = int(film_info.split("_")[1])
        await send_film(context, user_id, channel_id, msg_id)
    else:
        await query.edit_message_text(
            f"👋 سلام {query.from_user.first_name} عزیز!\n\nیه گزینه انتخاب کن 👇",
            reply_markup=build_main_keyboard()
        )

async def support_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # ذخیره state کاربر
    context.user_data["waiting_support"] = True

    await query.edit_message_text(
        "🎧 پیامت رو بنویس، به ادمین میفرستم 👇"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    msg = update.message.text

    # پیام پشتیبانی از کاربر
    if context.user_data.get("waiting_support"):
        context.user_data["waiting_support"] = False
        username = f"@{user.username}" if user.username else "ندارد"
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"🎧 پیام پشتیبانی:\n\n"
                    f"{msg}\n\n"
                    f"━━━━━━━━━━\n"
                    f"👤 اسم: {user.first_name}\n"
                    f"🆔 یوزرنیم: {username}\n"
                    f"🔢 آیدی: {user_id}\n"
                    f"━━━━━━━━━━\n"
                    f"📩 برای جواب روی این پیام ریپلای بزن"
                )
            )
            await update.message.reply_text("✅ پیامت فرستاده شد، به زودی جواب میگیری!")
        except TelegramError as e:
            logger.error(e)
        return

    # ادمین ریپلای زد به پیام پشتیبانی
    if user_id == ADMIN_ID and update.message.reply_to_message:
        replied_text = update.message.reply_to_message.text or ""
        target_id = None
        for line in replied_text.split("\n"):
            if "آیدی:" in line:
                try:
                    target_id = int(line.split(":")[1].strip())
                except:
                    pass
        if target_id:
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=f"📩 جواب پشتیبانی:\n\n{msg}"
                )
                await update.message.reply_text("✅ جواب فرستاده شد!")
            except TelegramError as e:
                await update.message.reply_text(f"❌ خطا: {e}")
        return

    # ادمین فیلم فوروارد کرد
    if user_id == ADMIN_ID:
        if update.message.video or update.message.photo or update.message.document or update.message.forward_origin:
            admin_state[ADMIN_ID] = {
                "step": "waiting_channel",
                "message_id": update.message.message_id,
                "chat_id": update.message.chat_id
            }
            keyboard = [
                [InlineKeyboardButton("📁 کانال اول", callback_data="adminchan_1")],
                [InlineKeyboardButton("📁 کانال دوم", callback_data="adminchan_2")]
            ]
            await update.message.reply_text(
                "از کدوم کانال خصوصی بفرسته؟",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

async def admin_channel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    channel_id = CHANNEL_1 if query.data == "adminchan_1" else CHANNEL_2
    stored = admin_state.get(ADMIN_ID)

    if not stored:
        await query.edit_message_text("❌ فیلم پیدا نشد، دوباره بفرست.")
        return

    admin_state[ADMIN_ID]["channel_id"] = channel_id
    admin_state[ADMIN_ID]["step"] = "waiting_caption"

    await query.edit_message_text(
        "✅ کانال انتخاب شد!\n\nحالا متن پست رو بنویس 👇"
    )

async def handle_admin_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return

    stored = admin_state.get(ADMIN_ID)
    if not stored or stored.get("step") != "waiting_caption":
        return

    caption_text = update.message.text

    try:
        # فوروارد به کانال خصوصی
        forwarded = await context.bot.forward_message(
            chat_id=stored["channel_id"],
            from_chat_id=stored["chat_id"],
            message_id=stored["message_id"]
        )
        film_msg_id = forwarded.message_id
        channel_num = 1 if stored["channel_id"] == CHANNEL_1 else 2

        bot_username = (await context.bot.get_me()).username
        view_url = f"https://t.me/{bot_username}?start=film_{stored['channel_id']}_{film_msg_id}"

        keyboard = [[InlineKeyboardButton("مشاهده 👁", url=view_url)]]

        await context.bot.send_message(
            chat_id="@LoLo_funny2",
            text=caption_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        del admin_state[ADMIN_ID]
        await update.message.reply_text("✅ پست با موفقیت توی کانال گذاشته شد!")

    except TelegramError as e:
        logger.error(f"خطا: {e}")
        await update.message.reply_text(f"❌ خطا: {e}")

async def send_film(context, user_id, channel_id, msg_id):
    try:
        sent = await context.bot.forward_message(
            chat_id=user_id,
            from_chat_id=channel_id,
            message_id=msg_id
        )
        notice = await context.bot.send_message(
            chat_id=user_id,
            text=f"⏳ این محتوا بعد از {DELETE_AFTER_SECONDS} ثانیه حذف میشه!"
        )

        async def delete_later():
            await asyncio.sleep(DELETE_AFTER_SECONDS)
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=sent.message_id)
                await context.bot.delete_message(chat_id=user_id, message_id=notice.message_id)
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🗑 حذف شد.\n\n📢 برای محتوای بیشتر:\n{PUBLIC_CHANNEL}"
                )
            except:
                pass

        asyncio.create_task(delete_later())

    except TelegramError as e:
        logger.error(f"خطا در ارسال: {e}")
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ خطا در ارسال. دوباره امتحان کن."
        )

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(check_join_callback, pattern="^checkjoin"))
    app.add_handler(CallbackQueryHandler(support_callback, pattern="^support$"))
    app.add_handler(CallbackQueryHandler(admin_channel_callback, pattern="^adminchan_"))
    app.add_handler(MessageHandler(
        filters.User(ADMIN_ID) & filters.TEXT & ~filters.COMMAND,
        lambda u, c: handle_admin_caption(u, c) if admin_state.get(ADMIN_ID, {}).get("step") == "waiting_caption" else handle_message(u, c)
    ))
    app.add_handler(MessageHandler(
        filters.User(ADMIN_ID) & (filters.VIDEO | filters.PHOTO | filters.Document.ALL | filters.FORWARDED),
        handle_message
    ))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.User(ADMIN_ID), handle_message))
    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
