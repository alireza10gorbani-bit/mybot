import os
import json
import logging
import random
import asyncio
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError

BOT_TOKEN = os.environ.get("BOT_TOKEN")

REQUIRED_CHANNELS = ["@LoLo_LoLo_Lo_Lo", "@LoLo_funny2"]
REQUIRED_GROUPS = ["@LoLo_funny"]

PRIVATE_CHANNEL_ID = -1004299938337

COOLDOWN_SECONDS = 15
DELETE_AFTER_SECONDS = 15

ADMIN_IDS = [8678262416]
DATA_FILE = "videos.json"
USERS_FILE = "users.json"

user_cooldowns = {}
user_last_video = {}
user_states = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_videos():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return []

def save_videos(videos):
    with open(DATA_FILE, "w") as f:
        json.dump(videos, f)

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return []

def save_user(user_id):
    users = load_users()
    if user_id not in users:
        users.append(user_id)
        with open(USERS_FILE, "w") as f:
            json.dump(users, f)

def get_remaining(user_id):
    return max(0, int(user_cooldowns.get(user_id, 0) - time.time()))

def set_cooldown(user_id):
    user_cooldowns[user_id] = time.time() + COOLDOWN_SECONDS

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

def build_join_keyboard(not_joined):
    keyboard = [
        [InlineKeyboardButton(f"📢 عضویت در {c}", url=f"https://t.me/{c.replace('@','')}")]
        for c in not_joined
    ]
    keyboard.append([InlineKeyboardButton("✅ عضو شدم", callback_data="check_join")])
    return InlineKeyboardMarkup(keyboard)

def build_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("🎬 دریافت فیلم", callback_data="get_video")],
        [InlineKeyboardButton("✉️ پیام ناشناس به ادمین", callback_data="anon_msg")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user.id)
    not_joined = await check_membership(user.id, context)
    if not_joined:
        await update.message.reply_text(
            "🔒 اول عضو کانال‌ها شو 👇",
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
    not_joined = await check_membership(user_id, context)
    if not_joined:
        await query.edit_message_text(
            "❌ هنوز عضو همه کانال‌ها نشدی 👇",
            reply_markup=build_join_keyboard(not_joined)
        )
        return
    await query.edit_message_text(
        f"👋 سلام {query.from_user.first_name} عزیز!\n\nیه گزینه انتخاب کن 👇",
        reply_markup=build_main_keyboard()
    )

async def get_video_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    remaining = get_remaining(user_id)
    if remaining > 0:
        await query.edit_message_text(f"⏳ {remaining} ثانیه دیگه صبر کن")
        return
    await query.edit_message_text("🎬 در حال ارسال فیلم...")
    await send_video(None, context, user_id)

async def anon_msg_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_states[user_id] = "waiting_anon_msg"
    await query.edit_message_text("✉️ پیامت رو بنویس، ناشناس برای ادمین میفرستم 👇")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_states.get(user_id) == "waiting_anon_msg":
        user_states[user_id] = None
        msg = update.message.text
        for admin_id in ADMIN_IDS:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"✉️ پیام ناشناس:\n\n{msg}"
            )
        await update.message.reply_text("✅ پیامت ناشناس فرستاده شد!")

async def send_video(message, context, user_id):
    videos = load_videos()
    if not videos:
        text = "😔 فعلاً فیلمی موجود نیست!"
        if message:
            await message.reply_text(text)
        else:
            await context.bot.send_message(chat_id=user_id, text=text)
        return
    last = user_last_video.get(user_id)
    choices = [v for v in videos if v != last] or videos
    msg_id = random.choice(choices)
    user_last_video[user_id] = msg_id
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
                await context.bot.delete_message(chat_id=user_id, message_id=sent.message_id)
                await context.bot.send_message(chat_id=user_id, text="🗑 فیلم حذف شد.\n\n🔄 برای فیلم بعدی /start بزن!")
            except:
                pass
        asyncio.create_task(delete_later())
    except TelegramError as e:
        logger.error(e)
        await context.bot.send_message(chat_id=user_id, text="❌ خطا دوباره /start")

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

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return await update.message.reply_text("❌ فقط ادمین")
    if not context.args:
        return await update.message.reply_text("استفاده: /broadcast پیام شما")
    msg = " ".join(context.args)
    users = load_users()
    sent = 0
    failed = 0
    for user_id in users:
        try:
            await context.bot.send_message(chat_id=user_id, text=msg)
            sent += 1
        except:
            failed += 1
    await update.message.reply_text(f"✅ فرستاده شد به {sent} نفر\n❌ {failed} نفر نشد")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addvideo", add_video))
    app.add_handler(CommandHandler("removevideo", remove_video))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CallbackQueryHandler(check_join_callback, pattern="check_join"))
    app.add_handler(CallbackQueryHandler(get_video_callback, pattern="get_video"))
    app.add_handler(CallbackQueryHandler(anon_msg_callback, pattern="anon_msg"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
