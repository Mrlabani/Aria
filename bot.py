import os
import logging
import asyncio
import aria2p
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from telegram import Update, ChatAction
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext

# Load environment variables
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "7565594863:AAF2uTPZOdMA4__i8fvZbksCjgdp4XQ0_xU")
ARIA2_SECRET = os.getenv("ARIA2_SECRET", "3f2d1c7a5b6e9f8a4c3d7e2b1a8d6f5c")

# Start Aria2 automatically
os.system("aria2c --enable-rpc --rpc-listen-all=true --rpc-allow-origin-all --rpc-secret=" + ARIA2_SECRET + " &")

# Aria2 RPC Client
aria2 = aria2p.API(
    aria2p.Client(host="http://localhost", port=6800, secret=ARIA2_SECRET)
)

# Logging
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

# Active Downloads Tracker
active_downloads = {}

# Function to Upload File with Progress
async def upload_file(update: Update, context: CallbackContext, file_path: str):
    chat_id = update.message.chat_id
    file_size = os.path.getsize(file_path)
    filename = Path(file_path).name

    if file_size > 2 * 1024 * 1024 * 1024:  # 2GB limit
        await update.message.reply_text(f"File {filename} is >2GB. Splitting into parts...")
        part_size = 2 * 1024 * 1024 * 1024  # 2GB chunks
        part_num = 1
        with open(file_path, "rb") as f:
            while chunk := f.read(part_size):
                part_name = f"{file_path}.part{part_num}"
                with open(part_name, "wb") as part_file:
                    part_file.write(chunk)

                await send_with_progress(update, context, part_name, f"{filename}.part{part_num}")
                os.remove(part_name)  # Delete after sending
                part_num += 1
    else:
        await send_with_progress(update, context, file_path, filename)

    os.remove(file_path)  # Delete after uploading

# Function to Send File with Progress
async def send_with_progress(update: Update, context: CallbackContext, file_path: str, filename: str):
    chat_id = update.message.chat_id
    file_size = os.path.getsize(file_path)

    with open(file_path, "rb") as f:
        await update.message.reply_chat_action(action=ChatAction.UPLOAD_DOCUMENT)
        msg = await update.message.reply_text(f"Uploading {filename}...")

        await update.message.reply_document(document=open(file_path, "rb"), filename=filename)
        await msg.delete()

# Start Command
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Welcome! Send a direct link or magnet URL to start downloading.")

# Handle Download Links
async def download(update: Update, context: CallbackContext):
    url = update.message.text
    if url.startswith(("http", "ftp", "magnet:")):
        try:
            download = aria2.add_uris([url])
            active_downloads[download.gid] = {
                "chat_id": update.message.chat_id,
                "msg": await update.message.reply_text(f"Download started!\nGID: {download.gid}")
            }
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")
    else:
        await update.message.reply_text("Invalid URL. Send a valid direct or magnet link.")

# Check Download Status
async def status(update: Update, context: CallbackContext):
    downloads = aria2.get_downloads()
    if not downloads:
        await update.message.reply_text("No active downloads.")
        return

    status_text = "\n".join([f"{d.name} - {d.status} ({d.progress}%)" for d in downloads])
    await update.message.reply_text(status_text)

# Cancel Download
async def cancel(update: Update, context: CallbackContext):
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /cancel <GID>")
        return

    gid = args[0]
    try:
        download = aria2.get_download(gid)
        download.remove()
        await update.message.reply_text(f"Download {gid} cancelled.")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

# Monitor Downloads and Send Progress
async def monitor_downloads(context: CallbackContext):
    while True:
        downloads = aria2.get_downloads()
        for download in downloads:
            data = active_downloads.get(download.gid)
            if not data:
                continue

            chat_id, msg = data["chat_id"], data["msg"]

            if download.is_complete:
                file_path = download.files[0].path
                await msg.edit_text(f"✅ Download Complete: {download.name}")
                await upload_file(update, context, file_path)
                download.remove()
                active_downloads.pop(download.gid, None)

            elif download.is_active:
                progress_text = (
                    f"⬇️ Downloading {download.name}\n"
                    f"📂 {download.completed_length}/{download.total_length} ({download.progress}%)\n"
                    f"🚀 Speed: {download.download_speed} | ⏳ ETA: {download.eta}"
                )
                await msg.edit_text(progress_text)

        await asyncio.sleep(10)  # Update every 10 seconds

# Terabox Link Support (Fixed Parsing)
def get_terabox_link(url):
    session = requests.Session()
    response = session.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    download_button = soup.find("a", {"id": "downloadButton"})
    if download_button:
        return download_button["href"]
    return None

async def download_terabox(update: Update, context: CallbackContext):
    url = update.message.text
    direct_link = get_terabox_link(url)
    if direct_link:
        await download(update, context)
    else:
        await update.message.reply_text("Could not extract download link from Terabox.")

# Bot Main Function
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download))
    app.add_handler(MessageHandler(filters.Regex(r"terabox.com"), download_terabox))

    # Start monitoring downloads in the background
    app.job_queue.run_repeating(monitor_downloads, interval=10)

    app.run_polling()

if __name__ == "__main__":
    main()
