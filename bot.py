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
ADULT_CHANNEL_ID = -1003826563552

COOLDOWN_SECONDS = 15
DELETE_AFTER_SECONDS = 15

ADMIN_IDS = [8678262416]
DATA_FILE = "videos.json"
ADULT_DATA_FILE = "adult_videos.json"
USERS_FILE = "users.json"

user_cooldowns = {}
user_last_video = {}
user_states = {}
anon_msg_senders = {}  # key -> {"user_id": int, "admin_msg_id": int, "admin_chat_id": int}

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

def load_adult_videos():
    if os.path.exists(ADULT_DATA_FILE):
        with open(ADULT_DATA_FILE, "r") as f:
            return json.load(f)
    return []

def save_adult_videos(videos):
    with open(ADULT_DATA_FILE, "w") as f:
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
        [
            InlineKeyboardButton("😈 آزاردهنده", callback_data="get_video"),
            InlineKeyboardButton("🔞 بزرگسالان", callback_data="get_adult_video")
        ],
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
    await query.edit_message_text("😈 در حال ارسال...")
    await send_video(None, context, user_id, adult=False)

async def get_adult_video_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    remaining = get_remaining(user_id)
    if remaining > 0:
        await query.edit_message_text(f"⏳ {remaining} ثانیه دیگه صبر کن")
        return
    await query.edit_message_text("🔞 در حال ارسال...")
    await send_video(None, context, user_id, adult=True)

async def anon_msg_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_states[user_id] = "waiting_anon_msg"
    await query.edit_message_text("✉️ پیامت رو بنویس، ناشناس برای ادمین میفرستم 👇")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = update.effective_user
    msg = update.message.text

    if user_states.get(user_id) == "waiting_anon_msg":
        user_states[user_id] = None
        msg_key = f"anon_{user_id}_{int(time.time())}"
        username = f"@{user.username}" if user.username else "بدون یوزرنیم"

        for admin_id in ADMIN_IDS:
            try:
                sent = await context.bot.send_message(
                    chat_id=admin_id,
                    text=(
                        f"✉️ پیام ناشناس:\n\n"
                        f"{msg}\n\n"
                        f"━━━━━━━━━━\n"
                        f"👤 اسم: {user.first_name}\n"
                        f"🆔 یوزرنیم: {username}\n"
                        f"🔢 آیدی عددی: {user_id}\n"
                        f"━━━━━━━━━━\n"
                        f"📩 برای جواب، روی این پیام ریپلای بزن"
                    )
                )
                # Store the admin message info so reply handler can find the sender
                anon_msg_senders[msg_key] = {
                    "user_id": user_id,
                    "admin_msg_id": sent.message_id,
                    "admin_chat_id": admin_id
                }
                # Map admin_msg_id to msg_key for quick reply lookup
                reply_map_key = f"{admin_id}_{sent.message_id}"
                anon_msg_senders[reply_map_key] = msg_key
            except TelegramError as e:
                logger.error(f"Failed to send anon msg to admin {admin_id}: {e}")

        await update.message.reply_text("✅ پیامت ناشناس فرستاده شد!")

    elif user_states.get(user_id) == "waiting_broadcast":
        user_states[user_id] = None
        users = load_users()
        sent_count = 0
        failed = 0
        for uid in users:
            try:
                await context.bot.send_message(chat_id=uid, text=msg)
                sent_count += 1
            except:
                failed += 1
        await update.message.reply_text(f"✅ فرستاده شد به {sent_count} نفر\n❌ {failed} نفر نشد")

    elif user_id in ADMIN_IDS and update.message.reply_to_message:
        # Admin replied to an anon message directly in Telegram
        replied_msg_id = update.message.reply_to_message.message_id
        reply_map_key = f"{user_id}_{replied_msg_id}"
        msg_key = anon_msg_senders.get(reply_map_key)

        if msg_key and isinstance(anon_msg_senders.get(msg_key), dict):
            sender_user_id = anon_msg_senders[msg_key]["user_id"]
            try:
                await context.bot.send_message(
                    chat_id=sender_user_id,
                    text=f"📩 جواب ادمین:\n\n{msg}"
                )
                await update.message.reply_text("✅ جواب فرستاده شد!")
            except TelegramError as e:
                await update.message.reply_text(f"❌ ارسال نشد: {e}")

async def reply_anon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return await update.message.reply_text("❌ فقط ادمین")
    if len(context.args) < 2:
        return await update.message.reply_text("استفاده: /reply key جواب شما")
    key = context.args[0]
    reply_text = " ".join(context.args[1:])
    entry = anon_msg_senders.get(key)
    user_id = entry["user_id"] if isinstance(entry, dict) else entry
    if not user_id:
        return await update.message.reply_text("❌ پیام پیدا نشد!")
    await context.bot.send_message(chat_id=user_id, text=f"📩 جواب ادمین:\n\n{reply_text}")
    await update.message.reply_text("✅ جواب فرستاده شد!")

async def send_video(message, context, user_id, adult=False):
    videos = load_adult_videos() if adult else load_videos()
    channel_id = ADULT_CHANNEL_ID if adult else PRIVATE_CHANNEL_ID
    label = "🔞" if adult else "😈"

    if not videos:
        text = "😔 فعلاً محتوایی موجود نیست!"
        if message:
            await message.reply_text(text)
        else:
            await context.bot.send_message(chat_id=user_id, text=text)
        return

    last_key = f"{'adult_' if adult else ''}{user_id}"
    last = user_last_video.get(last_key)
    choices = [v for v in videos if v != last] or videos
    msg_id = random.choice(choices)
    user_last_video[last_key] = msg_id
    set_cooldown(user_id)

    try:
        sent = await context.bot.forward_message(
            chat_id=user_id,
            from_chat_id=channel_id,
            message_id=msg_id
        )
        await context.bot.send_message(
            chat_id=user_id,
            text=f"{label} ارسال شد!\n⏳ بعد از ۱۵ ثانیه حذف میشه"
        )

        async def delete_later():
            await asyncio.sleep(DELETE_AFTER_SECONDS)
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=sent.message_id)
                await context.bot.send_message(
                    chat_id=user_id,
                    text="🗑 حذف شد.\n\n🔄 برای محتوای بعدی /start بزن!"
                )
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

async def add_adult_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return await update.message.reply_text("❌ فقط ادمین")
    videos = load_adult_videos()
    if not context.args:
        return await update.message.reply_text("استفاده: /addadultvideo 123")
    try:
        vid = int(context.args[0])
        if vid not in videos:
            videos.append(vid)
            save_adult_videos(videos)
            await update.message.reply_text("✅ اضافه شد به بخش بزرگسالان")
        else:
            await update.message.reply_text("⚠️ قبلاً هست")
    except:
        await update.message.reply_text("❌ فقط عدد")

async def add_adult_videos_bulk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return await update.message.reply_text("❌ فقط ادمین")
    if not context.args:
        return await update.message.reply_text("استفاده: /addadultvideos 7 8 9 10")
    videos = load_adult_videos()
    added = []
    exists = []
    for arg in context.args:
        try:
            vid = int(arg)
            if vid not in videos:
                videos.append(vid)
                added.append(vid)
            else:
                exists.append(vid)
        except:
            pass
    save_adult_videos(videos)
    text = f"✅ اضافه شد به بزرگسالان: {added}\n🔞 مجموع: {len(videos)} محتوا"
    if exists:
        text += f"\n⚠️ قبلاً بود: {exists}"
    await update.message.reply_text(text)

async def add_videos_bulk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return await update.message.reply_text("❌ فقط ادمین")
    if not context.args:
        return await update.message.reply_text("استفاده: /addvideos 7 8 9 10")
    videos = load_videos()
    added = []
    exists = []
    for arg in context.args:
        try:
            vid = int(arg)
            if vid not in videos:
                videos.append(vid)
                added.append(vid)
            else:
                exists.append(vid)
        except:
            pass
    save_videos(videos)
    text = f"✅ اضافه شد: {added}\n😈 مجموع: {len(videos)} محتوا"
    if exists:
        text += f"\n⚠️ قبلاً بود: {exists}"
    await update.message.reply_text(text)

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

async def remove_adult_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return await update.message.reply_text("❌ فقط ادمین")
    videos = load_adult_videos()
    if not context.args:
        return await update.message.reply_text("استفاده: /removeadultvideo 123")
    try:
        vid = int(context.args[0])
        if vid in videos:
            videos.remove(vid)
            save_adult_videos(videos)
            await update.message.reply_text("🗑 حذف شد از بخش بزرگسالان")
        else:
            await update.message.reply_text("⚠️ پیدا نشد")
    except:
        await update.message.reply_text("❌ فقط عدد")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return await update.message.reply_text("❌ فقط ادمین")
    user_states[update.effective_user.id] = "waiting_broadcast"
    await update.message.reply_text("📢 پیامی که میخوای به همه بفرستی رو بنویس 👇")

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addvideo", add_video))
    app.add_handler(CommandHandler("addvideos", add_videos_bulk))
    app.add_handler(CommandHandler("removevideo", remove_video))
    app.add_handler(CommandHandler("addadultvideo", add_adult_video))
    app.add_handler(CommandHandler("addadultvideos", add_adult_videos_bulk))
    app.add_handler(CommandHandler("removeadultvideo", remove_adult_video))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("reply", reply_anon))

    app.add_handler(CallbackQueryHandler(check_join_callback, pattern="check_join"))
    app.add_handler(CallbackQueryHandler(get_video_callback, pattern="get_video"))
    app.add_handler(CallbackQueryHandler(get_adult_video_callback, pattern="get_adult_video"))
    app.add_handler(CallbackQueryHandler(anon_msg_callback, pattern="anon_msg"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
