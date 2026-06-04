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

# ✅ فقط همینجا تغییر کرد
REQUIRED_CHANNELS = ["@LoLo_LoLo_Lo_Lo", "@LoLo_funny2"]
REQUIRED_GROUPS = ["@LoLo_funny"]

PRIVATE_CHANNEL_ID = -1004299938337

COOLDOWN_SECONDS = 15
DELETE_AFTER_SECONDS = 15

ADMIN_IDS = [8678262416]
DATA_FILE = "videos.json"

# user state
user_cooldowns = {}
user_last_video = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================= DATA =================
def load_videos():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return []

def save_videos(videos):
    with open(DATA_FILE, "w") as f:
        json.dump(videos, f)

# ================= COOLDOWN =================
def get_remaining(user_id):
    return max(0, int(user_cooldowns.get(user_id, 0) - time.time()))

def set_cooldown(user_id):
    user_cooldowns[user_id] = time.time() + COOLDOWN_SECONDS

# ================= CHECK =================
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

def build_keyboard(not_joined):
    keyboard = [
        [InlineKeyboardButton(f"📢 عضویت در {c}", url=f"https://t.me/{c.replace('@','')}")]
        for c in not_joined
    ]
    keyboard.append([InlineKeyboardButton("✅ عضو شدم", callback_data="check_join")])
    return InlineKeyboardMarkup(keyboard)

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    remaining = get_remaining(user.id)
    if remaining > 0:
        await update.message.reply_text(f"⏳ {remaining} ثانیه دیگه صبر کن")
        return

    not_joined = await check_membership(user.id, context)
    if not_joined:
        await update.message.reply_text(
            "🔒 اول عضو کانال‌ها شو 👇",
            reply_markup=build_keyboard(not_joined)
        )
        return

    await send_video(update.message, context, user.id)

# ================= CALLBACK =================
async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    remaining = get_remaining(user_id)
    if remaining > 0:
        await query.edit_message_text(f"⏳ {remaining} ثانیه دیگه صبر کن")
        return

    not_joined = await check_membership(user_id, context)
    if not_joined:
        await query.edit_message_text(
            "❌ هنوز عضو همه کانال‌ها نشدی 👇",
            reply_markup=build_keyboard(not_joined)
        )
        return

    await query.edit_message_text("🎬 در حال ارسال فیلم...")
    await send_video(None, context, user_id)

# ================= SEND VIDEO =================
async def send_video(message, context, user_id):
    videos = load_videos()

    if not videos:
        text = "😔 فعلاً فیلمی موجود نیست!"
        if message:
            await message.reply_text(text)
        else:
            await context.bot.send_message(chat_id=user_id, text=text)
        return

    # جلوگیری از تکرار پشت سر هم
    last = user_last_video.get(user_id)
    choices = [v for v in videos if v != last] or videos

    msg_id = random.choice(choices)
    user_last_video[user_id] = msg_id

    # کول‌داون
    set_cooldown(user_id)

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

        async def delete_later():
            await asyncio.sleep(DELETE_AFTER_SECONDS)
            try:
                await context.bot.delete_message(
                    chat_id=user_id,
                    message_id=sent.message_id
                )
            except:
                pass

        asyncio.create_task(delete_later())

    except TelegramError as e:
        logger.error(e)
        await context.bot.send_message(chat_id=user_id, text="❌ خطا دوباره /start")

# ================= ADMIN =================
async def add_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return await update.message.reply_text("❌ فقط ادمین")

    videos = load_videos()

    if not context.args:
        return await update.message.reply_text("استفاده: /addvideo 123")

    try:
        vid = int(context.args[0])
        if vid not in videos:
            videos.append(vid)
            save_videos(videos)
            await update.message.reply_text("✅ اضافه شد")
        else:
            await update.message.reply_text("⚠️ قبلاً هست")
    except:
        await update.message.reply_text("❌ فقط عدد")

async def remove_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return await update.message.reply_text("❌ فقط ادمین")

    videos = load_videos()

    if not context.args:
        return await update.message.reply_text("استفاده: /removevideo 123")

    try:
        vid = int(context.args[0])
        if vid in videos:
            videos.remove(vid)
            save_videos(videos)
            await update.message.reply_text("🗑 حذف شد")
        else:
            await update.message.reply_text("⚠️ پیدا نشد")
    except:
        await update.message.reply_text("❌ فقط عدد")

# ================= MAIN =================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addvideo", add_video))
    app.add_handler(CommandHandler("removevideo", remove_video))
    app.add_handler(CallbackQueryHandler(check_join_callback, pattern="check_join"))

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
