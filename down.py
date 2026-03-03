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

# ============================================================
# LOAD TOKEN FROM .env FILE
# Create a .env file in the same folder with:
#   BOT_TOKEN=your_token_here
# ============================================================
load_dotenv()
BOT_TOKEN =("8681192880:AAEf8Nt-sNXTLTTuLRJV2pwcse8pd_rPpMY")


# ============================================================
# HELPER: Check if a string looks like a URL
# ============================================================
def is_url(text: str) -> bool:
    return text.startswith("http://") or text.startswith("https://")


# ============================================================
# HELPER: Download video using yt-dlp
# Returns the filename if successful, None if failed
# ============================================================
def download_video(url: str) -> str | None:
    # yt-dlp options
    options = {
        # Save file as "video.mp4" (or whatever extension yt-dlp picks)
        'outtmpl': 'video.%(ext)s',

        # Download best quality that is under 50MB (Telegram limit)
        # If no format under 50MB exists, it tries the smallest available
        'format': 'best[filesize<50M]/worst',

        # Don't print progress to console
        'quiet': True,

        # Don't show warnings
        'no_warnings': True,

        # If the site needs cookies (helps with some Instagram content)
        # 'cookiefile': 'cookies.txt',  # uncomment if needed
    }

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            # extract_info downloads the video and returns info about it
            info = ydl.extract_info(url, download=True)

            # get the actual filename that was saved
            filename = ydl.prepare_filename(info)
            return filename

    except yt_dlp.utils.DownloadError as e:
        print(f"Download error: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None


# ============================================================
# HELPER: Clean up all video files after sending
# ============================================================
def cleanup():
    # delete any file starting with "video."
    for f in glob.glob("video.*"):
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
        "✅ Supported sites:\n"
        "• Instagram (reels, posts)\n"
        "• YouTube (videos, shorts)\n"
        "• TikTok\n"
        "• Twitter / X\n"
        "• Facebook\n"
        "• Reddit\n"
        "• Vimeo\n"
        "• 1000+ other sites\n\n"
        "⚠️ Max file size: 50MB (Telegram limit)\n\n"
        "Send /help for more info."
    )


# ============================================================
# /help COMMAND
# ============================================================
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 How to use:\n\n"
        "1. Copy a video link from Instagram, YouTube, TikTok, etc.\n"
        "2. Paste it here and send it\n"
        "3. Wait a few seconds\n"
        "4. Receive your video!\n\n"
        "Commands:\n"
        "/start - Welcome message\n"
        "/help  - This message\n\n"
        "❗ Note: Some private Instagram posts may not work "
        "unless the account is public."
    )


# ============================================================
# MAIN MESSAGE HANDLER
# Runs when user sends any text message
# ============================================================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()

    # Check if the message is a URL
    if not is_url(user_text):
        await update.message.reply_text(
            "Please send a valid video URL starting with http:// or https://"
        )
        return

    # Tell user we are working on it
    status_message = await update.message.reply_text(
        "⏳ Downloading your video, please wait..."
    )

    # Try to download the video
    filename = download_video(user_text)

    # If download failed
    if not filename or not os.path.exists(filename):
        await status_message.edit_text(
            "❌ Could not download this video.\n\n"
            "Possible reasons:\n"
            "• Private account or post\n"
            "• Link is expired or broken\n"
            "• Site is not supported\n"
            "• File is too large (over 50MB)"
        )
        cleanup()
        return

    # Check file size — Telegram bots max is 50MB
    file_size_mb = os.path.getsize(filename) / (1024 * 1024)

    if file_size_mb > 50:
        await status_message.edit_text(
            f"❌ File is {file_size_mb:.1f}MB — too large.\n"
            "Telegram bots can only send files up to 50MB."
        )
        cleanup()
        return

    # Update status message
    await status_message.edit_text("📤 Uploading to Telegram...")

    # Send the video to the user
    try:
        with open(filename, "rb") as video_file:
            await update.message.reply_video(
                video=video_file,
                caption=f"✅ Downloaded successfully!\nSize: {file_size_mb:.1f}MB",
                # show upload progress bar in Telegram
                read_timeout=120,
                write_timeout=120,
                connect_timeout=120
            )

        # Delete the "Uploading..." status message after sending
        await status_message.delete()

    except Exception as e:
        await status_message.edit_text(
            f"❌ Failed to send video: {e}"
        )

    finally:
        # Always clean up the downloaded file
        cleanup()


# ============================================================
# ERROR HANDLER
# Catches any unhandled errors so the bot doesn't crash
# ============================================================
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"Error: {context.error}")

    # If the error happened in a message, notify the user
    if isinstance(update, Update) and update.message:
        await update.message.reply_text(
            "❌ Something went wrong. Please try again."
        )
    cleanup()


# ============================================================
# MAIN — build and run the bot
# ============================================================
def main():
    # Make sure token is loaded
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN not found. Create a .env file with BOT_TOKEN=your_token")
        return

    print("Starting Video Downloader Bot...")

    # Build the application
    app = Application.builder().token(BOT_TOKEN).build()

    # Register command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))

    # Register message handler — handles any text message (URLs)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Register error handler
    app.add_error_handler(error_handler)

    print("Bot is running! Press Ctrl+C to stop.")

    # Start polling for messages
    app.run_polling()


if __name__ == "__main__":
    main()