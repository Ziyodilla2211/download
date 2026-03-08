import os
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

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")


# ============================================================
# HELPER: Check if a string looks like a URL
# ============================================================
def is_url(text: str) -> bool:
    return text.startswith("http://") or text.startswith("https://")


# ============================================================
# HELPER: Check if URL is an Instagram link
# ============================================================
def is_instagram_url(url: str) -> bool:
    return "instagram.com" in url


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


# ============================================================
# HELPER: Download Instagram photo(s) using yt-dlp
# Returns a list of downloaded image file paths
# ============================================================
def download_instagram_photos(url: str) -> list[str]:
    options = {
        'outtmpl': 'photo_%(autonumber)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        # Tell yt-dlp to prefer images over video when available
        'format': 'bestvideo[ext=mp4]/best/bestaudio',
        'writethumbnail': False,
    }

    # Use a dedicated image-focused config
    image_options = {
        'outtmpl': 'photo_%(autonumber)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(image_options) as ydl:
            info = ydl.extract_info(url, download=False)

            # Check if this is a photo post (no duration or very short)
            # Instagram photos have no 'duration' or duration is None
            entries = info.get('entries', [info])  # handles carousels (multiple images)

            downloaded = []
            for i, entry in enumerate(entries):
                # If it has a video format, it's a video — skip photo logic
                if entry.get('duration') and entry['duration'] > 1:
                    return []  # It's a video, let the video handler deal with it

                # Get the thumbnail URL (Instagram photo URL)
                thumbnails = entry.get('thumbnails', [])
                if not thumbnails:
                    continue

                # Pick the highest resolution thumbnail
                best = sorted(thumbnails, key=lambda t: t.get('width', 0) or 0, reverse=True)
                photo_url = best[0].get('url')

                if not photo_url:
                    continue

                # Download the image using requests-style via yt-dlp's urlopen
                import urllib.request
                filename = f"photo_{i+1}.jpg"
                urllib.request.urlretrieve(photo_url, filename)
                downloaded.append(filename)

            return downloaded

    except Exception as e:
        print(f"Photo download error: {e}")
        return []


# ============================================================
# HELPER: Clean up downloaded files after sending
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
        "👋 Welcome to Video & Photo Downloader Bot!\n\n"
        "Just send me a link and I'll download it for you.\n\n"
        "Supported:\n"
        "• Instagram (reels, posts, photos 🖼️, carousels)\n"
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
        "1. Copy a link from Instagram, YouTube, TikTok, etc.\n"
        "2. Paste it here and send it\n"
        "3. Wait a few seconds\n"
        "4. Receive your video or photo!\n\n"
        "📸 Instagram photos & carousels are supported!\n\n"
        "Commands:\n"
        "/start - Welcome message\n"
        "/help  - This message\n\n"
        "Note: Private Instagram posts won't work "
        "unless the account is public."
    )


# ============================================================
# MAIN MESSAGE HANDLER
# ============================================================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()

    if not is_url(user_text):
        await update.message.reply_text(
            "Please send a valid URL starting with http:// or https://"
        )
        return

    status_message = await update.message.reply_text(
        "⏳ Fetching your content, please wait..."
    )

    # ── Instagram: try photos first ──────────────────────────
    if is_instagram_url(user_text):
        photos = download_instagram_photos(user_text)

        if photos:
            await status_message.edit_text("📤 Uploading photo(s) to Telegram...")
            try:
                if len(photos) == 1:
                    # Single photo
                    with open(photos[0], "rb") as img:
                        await update.message.reply_photo(
                            photo=img,
                            caption="📸 Downloaded from Instagram!",
                            read_timeout=60,
                            write_timeout=60,
                            connect_timeout=60
                        )
                else:
                    # Carousel — send as media group
                    from telegram import InputMediaPhoto
                    media = []
                    file_handles = []
                    for i, path in enumerate(photos):
                        fh = open(path, "rb")
                        file_handles.append(fh)
                        caption = f"📸 Photo {i+1}/{len(photos)} — Instagram" if i == 0 else None
                        media.append(InputMediaPhoto(media=fh, caption=caption))

                    await update.message.reply_media_group(
                        media=media,
                        read_timeout=120,
                        write_timeout=120,
                        connect_timeout=120
                    )
                    for fh in file_handles:
                        fh.close()

                await status_message.delete()
            except Exception as e:
                await status_message.edit_text(f"Failed to send photo(s): {e}")
            finally:
                cleanup()
            return  # Done — don't fall through to video handler

    # ── Video download (all sites including Instagram videos) ─
    await status_message.edit_text("⬇️ Downloading your video, please wait...")
    filename = download_video(user_text)

    if not filename or not os.path.exists(filename):
        await status_message.edit_text(
            "❌ Could not download this content.\n\n"
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
            f"❌ File is {file_size_mb:.1f}MB — too large.\n"
            "Telegram bots can only send files up to 50MB."
        )
        cleanup()
        return

    await status_message.edit_text("📤 Uploading to Telegram...")

    try:
        with open(filename, "rb") as video_file:
            await update.message.reply_video(
                video=video_file,
                caption=f"✅ Downloaded!\nSize: {file_size_mb:.1f}MB",
                read_timeout=120,
                write_timeout=120,
                connect_timeout=120
            )
        await status_message.delete()

    except Exception as e:
        await status_message.edit_text(f"Failed to send video: {e}")

    finally:
        cleanup()


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

    print("Starting Video & Photo Downloader Bot...")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    print("Bot is running! Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
