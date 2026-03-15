import os
import glob
import asyncio
import yt_dlp
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
    filters,
    ContextTypes
)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

COOKIE_FILE = "instagram_cookies.txt"


# ============================================================
# HELPER: Check if a string looks like a URL
# ============================================================
def is_url(text: str) -> bool:
    return text.startswith("http://") or text.startswith("https://")


# ============================================================
# HELPER: Download video using yt-dlp (runs in thread)
# ============================================================
def download_video(url: str, user_id: int) -> str | None:
    filename_base = f"{user_id}_video"
    

    options = {
        'outtmpl': f'{filename_base}.%(ext)s',
        'format': 'best[filesize<100M]/worst',
        'quiet': True,
        'no_warnings': True,
        'no_color': True,
        'noprogress': True,
        'noplaylist': True,
        'concurrent_fragment_downloads': 4,
        'buffersize': 1024 * 16,
        'http_chunk_size': 10485760,  # 10MB chunks
    
    }
    if os.path.exists(COOKIE_FILE):
        options['cookiefile'] = COOKIE_FILE

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            return filename
    except yt_dlp.utils.DownloadError as e:
        print(f"Download error: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None


# ============================================================
# HELPER: Clean up video files after sending
# ============================================================
def cleanup(user_id: int):
    for f in glob.glob(f"{user_id}_video.*"):
        try:
            os.remove(f)
        except:
            pass


# ============================================================
# /start COMMAND
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to Video Downloader Bot!\n\n"
        "Just send me a video link and I'll download it for you.\n\n"
        "Supported sites:\n"
        "• Instagram (reels, posts)\n"
        "• YouTube (videos, shorts)\n"
        "• TikTok\n"
        "• Twitter / X\n"
        "• Facebook\n"
        "• Reddit\n"
        "• Vimeo\n"
        "• 1000+ other sites\n\n"
        "Max file size: 100MB (Telegram limit)\n\n"
        "Send /help for more info."
    )


# ============================================================
# /help COMMAND
# ============================================================
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "How to use:\n\n"
        "1. Copy a video link from Instagram, YouTube, TikTok, etc.\n"
        "2. Paste it here and send it\n"
        "3. Wait a few seconds\n"
        "4. Receive your video!\n\n"
        "Commands:\n"
        "/start - Welcome message\n"
        "/help  - This message\n\n"
        "Note: Some private Instagram posts may not work "
        "unless the account is public."
    )


# ============================================================
# MAIN MESSAGE HANDLER
# ============================================================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    user_id = update.effective_user.id

    if not is_url(user_text):
        await update.message.reply_text(
            "Please send a valid video URL starting with http:// or https://"
        )
        return

    status_message = await update.message.reply_text("Downloading the video...")

    # Run blocking download in a thread — bot stays responsive for other users
    filename = await asyncio.to_thread(download_video, user_text, user_id)

    if not filename or not os.path.exists(filename):
        await status_message.edit_text(
            "❌ Could not download this video.\n\n"
            "Possible reasons:\n"
            "• Private account or post\n"
            "• Link is expired or broken\n"
            "• Site is not supported\n"
            "• File is too large (over 100MB)"
        )
        cleanup(user_id)
        return

    file_size_mb = os.path.getsize(filename) / (1024 * 1024)

    if file_size_mb > 100:
        await status_message.edit_text(
            f"❌ File is {file_size_mb:.1f}MB — too large.\n"
            "Telegram bots can only send files up to 100MB."
        )
        cleanup(user_id)
        return

    await status_message.edit_text("Uploading to Telegram...")

    try:
        with open(filename, "rb") as video_file:
            await update.message.reply_video(
                video=video_file,
                caption="",
                read_timeout=120,
                write_timeout=120,
                connect_timeout=120
            )
        await status_message.delete()

    except Exception as e:
        await status_message.edit_text(f"❌ Failed to send video: {e}")

    finally:
        cleanup(user_id)


# ============================================================
# ERROR HANDLER
# ============================================================
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"Error: {context.error}")
    if isinstance(update, Update) and update.message:
        await update.message.reply_text("Something went wrong. Please try again.")
        cleanup(update.effective_user.id)


# ============================================================
# MAIN
# ============================================================
def main():
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN not found.")
        return

    print("Starting Video Downloader Bot...")

    if os.path.exists(COOKIE_FILE):
        print(f"✅ Cookie file found: {COOKIE_FILE}")
    else:
        print(f"⚠️  Warning: Cookie file not found: {COOKIE_FILE}")

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .concurrent_updates(True)   # handle multiple users simultaneously
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    print("Bot is running! Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
