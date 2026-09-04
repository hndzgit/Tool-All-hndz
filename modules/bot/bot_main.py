import os
import re
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    filters,
)

import json

TOKEN = "8768218656:AAE4pKCxmSHxiY3ohbNIoEXz-vTfZiy-9cQ"

DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

def extract_url(text):
    match = re.search(r"(https?://[^\s]+)", text)
    return match.group(0) if match else None


def download_video(url):
    ydl_opts = {
        "outtmpl": f"{DOWNLOAD_FOLDER}/%(title)s.%(ext)s",
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "extractor_args": {
            "douyin": {"api_hostname": "api.amemv.com"}
        },
        "concurrent_fragment_downloads": 5,   # ⭐ tăng tốc
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)

    return filename


def download_mp3(url):
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": f"{DOWNLOAD_FOLDER}/%(title)s.%(ext)s",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = os.path.splitext(ydl.prepare_filename(info))[0] + ".mp3"

    return filename


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Gửi link TikTok / Douyin / YouTube\nChọn Video hoặc MP3"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    url = extract_url(text)

    if not url:
        await update.message.reply_text("❌ Không tìm thấy link")
        return

    context.user_data["url"] = url

    keyboard = [
        [
            InlineKeyboardButton("🎬 Video", callback_data="video"),
            InlineKeyboardButton("🎵 MP3", callback_data="mp3"),
        ]
    ]

    await update.message.reply_text(
        "Chọn định dạng:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    url = context.user_data.get("url")

    await query.message.reply_text("⏳ Đang tải...")

    try:
        if query.data == "video":
            file_path = download_video(url)
            await query.message.reply_video(video=open(file_path, "rb"))

        else:
            file_path = download_mp3(url)
            await query.message.reply_audio(audio=open(file_path, "rb"))

        os.remove(file_path)

    except Exception as e:
        await query.message.reply_text(f"❌ Lỗi: {e}")


app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.add_handler(CallbackQueryHandler(button_click))

if __name__ == "__main__":
    print("Bot đang chạy...")
    app.run_polling()