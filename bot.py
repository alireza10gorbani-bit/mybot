import os
import json
import logging
import random
import asyncio
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.error import TelegramError

BOT_TOKEN = os.environ.get("BOT_TOKEN")

REQUIRED_CHANNELS = ["@MaSih_BeNy", "@LoLo_funny2"]
REQUIRED_GROUPS = ["@LoLo_funny"]
PRIVATE_CHANNEL_ID = -1004299938337

DELETE_AFTER_SECONDS = 15
COOLDOWN_SECONDS = 15

ADMIN_IDS = [8678262416]
DATA_FILE = "videos.json"

user_cooldowns = {}

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

def load_videos():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return []

def save_videos(videos):
    with open(DATA_FILE, "w") as f:
        json.dump(videos, f)

def get_remaining(user_id):
    return max(0, int(user_cooldowns.get(user_id, 0) - time.time()))

async def check_membership(user_id, context):
    not_joined = []
    for channel in REQUIRED_CHANNELS + REQUIRED_GROUPS:
        try:
            member = await context.bot.get_chat_member(channel, user_id)
            if member.status in ["left", "kicked", "banned"]:
                not_joined.append(channel)
        except TelegramError:
            not_joined.append(channel)
    return not_joined

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    remaining = get_remaining(user.id)
    if remaining > 0:
        await update.message.reply_text(f"⏳ {remaining} ثانیه دیگه می‌تونی فیلم بعدی رو بگیری!")
        return

    not_joined = await check_membership(user.id, context)
    if not_joined:
        keyboard = []
        for channel in not_joined:
            name = channel.replace("@", "")
            keyboard.append([InlineKeyboardButton(f"📢 عضویت در {channel}", url=f"https://t.me/{name}")])
        keyboard.append([InlineKeyboardButton("✅ عضو شدم، بررسی کن", callback_data="check_join")])

        await update.message.reply_text(
            "👋 سلام!\n🔒 اول عضو کانال‌ها شو بعد فیلم بگیر 👇",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    await send_video(update.message, context, user.id)

async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    remaining = get_remaining(query.from_user.id)
    if remaining > 0:
        await query.edit_message_text(f"⏳ {remaining} ثانیه دیگه می‌تونی فیلم بعدی رو بگیری!")
        return

    not_joined = await check_membership(query.from_user.id, context)
    if not_joined:
        keyboard = []
        for channel in not_joined:
            name = channel.replace("@", "")
            keyboard.append([InlineKeyboardButton(f"📢 عضویت در {channel}", url=f"https://t.me/{name}")])
        keyboard.append([InlineKeyboardButton("✅ عضو شدم، بررسی کن", callback_data="check_join")])

        await query.edit_message_text("❌ هنوز عضو همه کانال‌ها نشدی 👇", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    await query.edit_message_text("⏳ ۱۵ ثانیه صبر کن...")

    await send_video(None, context, query.from_user.id)

async def send_video(message, context, user_id):
    videos = load_videos()

    if not videos:
        text = "😔 فعلاً فیلمی موجود نیست!"
        if message:
            await message.reply_text(text)
        else:
            await context.bot.send_message(chat_id=user_id, text=text)
        return

    msg_id = random.choice(videos)

    user_cooldowns[user_id] = time.time() + COOLDOWN_SECONDS

    async def job():
        await asyncio.sleep(COOLDOWN_SECONDS)

        try:
            sent = await context.bot.forward_message(
                chat_id=user_id,
                from_chat_id=PRIVATE_CHANNEL_ID,
                message_id=msg_id
            )

            await context.bot.send_message(
                chat_id=user_id,
                text="🎬 فیلم ارسال شد!\n⏳ بعد از ۱۵ ثانیه حذف میشه"
            )

            await asyncio.sleep(DELETE_AFTER_SECONDS)

            try:
                await context.bot.delete_message(chat_id=user_id, message_id=sent.message_id)
            except:
                pass

            await context.bot.send_message(chat_id=user_id, text="🗑 فیلم حذف شد\n/start")

        except TelegramError as e:
            logger.error(e)
            await context.bot.send_message(chat_id=user_id, text="❌ خطا! دوباره /start")

    asyncio.create_task(job())

async def add_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ فقط ادمین!")
        return

    videos = load_videos()

    if not context.args:
        await update.message.reply_text(f"استفاده: /addvideo 123\nکل: {len(videos)}")
        return

    try:
        msg_id = int(context.args[0])
        if msg_id not in videos:
            videos.append(msg_id)
            save_videos(videos)
            await update.message.reply_text("✅ اضافه شد")
        else:
            await update.message.reply_text("⚠️ قبلاً اضافه شده")
    except:
        await update.message.reply_text("❌ فقط عدد!")

async def remove_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ فقط ادمین!")
        return

    videos = load_videos()

    if not context.args:
        await update.message.reply_text("استفاده: /removevideo 123")
        return

    try:
        msg_id = int(context.args[0])
        if msg_id in videos:
            videos.remove(msg_id)
            save_videos(videos)
            await update.message.reply_text("🗑 حذف شد")
        else:
            await update.message.reply_text("⚠️ پیدا نشد")
    except:
        await update.message.reply_text("❌ فقط عدد!")

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addvideo", add_video))
    app.add_handler(CommandHandler("removevideo", remove_video))
    app.add_handler(CallbackQueryHandler(check_join_callback, pattern="check_join"))

    print("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()
