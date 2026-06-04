import os
import json
import logging
import random
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.error import TelegramError

BOT_TOKEN = os.environ.get("BOT_TOKEN")

REQUIRED_CHANNELS = ["@MaSih_BeNy", "@LoLo_funny2"]
REQUIRED_GROUPS = ["@LoLo_funny"]
PRIVATE_CHANNEL_ID = -1004299938337
DELETE_AFTER_SECONDS = 30
ADMIN_IDS = [8678262416]
DATA_FILE = "videos.json"

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
    not_joined = await check_membership(user.id, context)
    if not_joined:
        keyboard = []
        for channel in not_joined:
            name = channel.replace("@", "")
            keyboard.append([InlineKeyboardButton(f"📢 عضویت در {channel}", url=f"https://t.me/{name}")])
        keyboard.append([InlineKeyboardButton("✅ عضو شدم، بررسی کن", callback_data="check_join")])
        await update.message.reply_text(
            f"👋 سلام {user.first_name} عزیز!\n\n🔒 برای دسترسی به محتوای ویژه، ابتدا در کانال‌های زیر عضو شو:\n\nبعد از عضویت دکمه ✅ رو بزن 👇",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    await send_video(update.message, context, user.id)

async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    not_joined = await check_membership(query.from_user.id, context)
    if not_joined:
        keyboard = []
        for channel in not_joined:
            name = channel.replace("@", "")
            keyboard.append([InlineKeyboardButton(f"📢 عضویت در {channel}", url=f"https://t.me/{name}")])
        keyboard.append([InlineKeyboardButton("✅ عضو شدم، بررسی کن", callback_data="check_join")])
        await query.edit_message_text("❌ هنوز عضو همه کانال‌ها نشدی!\n\nلطفاً اول عضو بشو 👇", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    await query.edit_message_text("✅ عضویت تأیید شد! داری فیلمت رو میفرستم... 🎬")
    await send_video(None, context, query.from_user.id)

async def send_video(message, context, user_id):
    videos = load_videos()
    if not videos:
        text = "😔 فعلاً فیلمی موجود نیست.\nبعداً دوباره امتحان کن!"
        if message:
            await message.reply_text(text)
        else:
            await context.bot.send_message(chat_id=user_id, text=text)
        return
    random_msg_id = random.choice(videos)
    try:
        sent = await context.bot.forward_message(chat_id=user_id, from_chat_id=PRIVATE_CHANNEL_ID, message_id=random_msg_id)
        await context.bot.send_message(
            chat_id=user_id,
            text="🎬 فیلم با موفقیت ارسال شد!\n\n⚠️ توجه: این فیلم پس از ۳۰ ثانیه به صورت خودکار حذف می‌شود.\n\n⏳ همین الان ببین!"
        )
        await asyncio.sleep(DELETE_AFTER_SECONDS)
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=sent.message_id)
            await context.bot.send_message(chat_id=user_id, text="🗑 فیلم حذف شد.\n\n🔄 برای دریافت فیلم جدید /start بزن!")
        except:
            pass
    except TelegramError as e:
        logger.error(f"خطا: {e}")
        await context.bot.send_message(chat_id=user_id, text="❌ خطایی رخ داد!\nدوباره /start بزن.")

async def add_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ فقط ادمین!")
        return
    videos = load_videos()
    if not context.args:
        await update.message.reply_text(f"📝 استفاده: /addvideo 123\n\n🎬 الان {len(videos)} فیلم داری")
        return
    try:
        msg_id = int(context.args[0])
        if msg_id not in videos:
            videos.append(msg_id)
            save_videos(videos)
            await update.message.reply_text(f"✅ فیلم اضافه شد!\n🎬 مجموع: {len(videos)} فیلم")
        else:
            await update.message.reply_text("⚠️ این فیلم قبلاً اضافه شده!")
    except:
        await update.message.reply_text("❌ آی‌دی باید عدد باشه!")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addvideo", add_video))
    app.add_handler(CallbackQueryHandler(check_join_callback, pattern="check_join"))
    print("✅ ربات شروع کرد!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
