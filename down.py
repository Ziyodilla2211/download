import os                  # FIXED: was missing, needed for file operations
import urllib.request
import glob
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

# Load .env file (works locally)
# On Railway, token comes from dashboard Variables automatically
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")  # FIXED: reads from environment, works both locally and Railway


# ============================================================
# HELPER: Check if a string looks like a URL
# ============================================================
def is_url(text: str) -> bool:
    return text.startswith("http://") or text.startswith("https://")


# ============================================================
# HELPER: Download video using yt-dlp
# ============================================================
def download_video(url: str) -> str | None:
    options = {
        'outtmpl': 'video.%(ext)s',
        'format': 'best[filesize<50M]/worst',
        'quiet': True,
        'no_warnings': True,
    }

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

def download_instagram_photos(url: str) -> list[str]:
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            entries = info.get('entries', [info])
            downloaded = []
            for i, entry in enumerate(entries):
                if entry.get('duration') and entry['duration'] > 1:
                    return []
                thumbnails = entry.get('thumbnails', [])
                if not thumbnails:
                    continue
                best = sorted(thumbnails, key=lambda t: t.get('width', 0) or 0, reverse=True)
                photo_url = best[0].get('url')
                if not photo_url:
                    continue
                filename = f"photo_{i+1}.jpg"
                urllib.request.urlretrieve(photo_url, filename)
                downloaded.append(filename)
            return downloaded
    except Exception as e:
        print(f"Error: {e}")
        return []


# ============================================================
# HELPER: Clean up video files after sending
# ============================================================
def cleanup():
    for pattern in ["video.*", "photo_*.*"]:
        for f in glob.glob(pattern):
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
        "Max file size: 50MB (Telegram limit)\n\n"
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

    if not is_url(user_text):
        await update.message.reply_text(
            "Please send a valid video URL starting with http:// or https://"
        )
        return

    status_message = await update.message.reply_text(
        "Downloading your video, please wait..."
    )

    filename = download_video(user_text)

    if not filename or not os.path.exists(filename):
        await status_message.edit_text(
            "Could not download this video.\n\n"
            "Possible reasons:\n"
            "• Private account or post\n"
            "• Link is expired or broken\n"
            "• Site is not supported\n"
            "• File is too large (over 50MB)"
        )
        cleanup()
        return
    

    file_size_mb = os.path.getsize(filename) / (1024 * 1024)

    if file_size_mb > 50:
        await status_message.edit_text(
            f"File is {file_size_mb:.1f}MB — too large.\n"
            "Telegram bots can only send files up to 50MB."
        )
        cleanup()
        return

    await status_message.edit_text("Uploading to Telegram...")

    try:
        with open(filename, "rb") as video_file:
            await update.message.reply_video(
                video=video_file,
                caption=f"Downloaded successfully!\nSize: {file_size_mb:.1f}MB",
                read_timeout=120,
                write_timeout=120,
                connect_timeout=120
            )

        await status_message.delete()

    except Exception as e:
        await status_message.edit_text(f"Failed to send video: {e}")

    finally:
        cleanup()

    if "instagram.com" in user_text:
        photos = download_instagram_photos(user_text)
        if photos:
            await update.message.reply_text("📤 Uploading photo(s)...")
            for path in photos:
                with open(path, "rb") as img:
                    await update.message.reply_photo(photo=img)
            cleanup()
            return


# ============================================================
# ERROR HANDLER
# ============================================================
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"Error: {context.error}")
    if isinstance(update, Update) and update.message:
        await update.message.reply_text("Something went wrong. Please try again.")
    cleanup()


# ============================================================
# MAIN
# ============================================================
def main():
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN not found.")
        return

    print("Starting Video Downloader Bot...")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    print("Bot is running! Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
