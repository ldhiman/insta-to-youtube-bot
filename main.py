import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
from metadata_gemini import generate_metadata, build_stats_context
# Import our custom modules
import downloader
import uploader
from telegram.request import HTTPXRequest


load_dotenv()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_url = update.message.text
    chat_id = update.effective_chat.id

    # 1. Validation
    if "instagram.com" not in user_url:
        await context.bot.send_message(chat_id=chat_id, text="Please send a valid Instagram link.")
        return

    await context.bot.send_message(chat_id=chat_id, text="⬇️ Downloading Reel...")

    # 2. Download Phase
    file_path, caption = downloader.download_instagram_reel(user_url)

    if not file_path:
        await context.bot.send_message(chat_id=chat_id, text="❌ Download failed.")
        return

    await context.bot.send_message(chat_id=chat_id, text="⬆️ Uploading to YouTube...")

    # 3. Upload Phase
    try:
        stats_context = build_stats_context()
        print("Stats Context:", stats_context)
        metadata = generate_metadata(caption=caption, url=user_url,stats_context=stats_context)
        print("Generated Metadata:", metadata)
        video_id = uploader.upload_video(file_path, title=(metadata["title"] or caption), description=(metadata["description"] or f"Original: {user_url}"), tags=metadata.get("tags", []))
        youtube_link = f"https://youtube.com/shorts/{video_id}"
        await context.bot.send_message(chat_id=chat_id, text=f"✅ Success! View here: {youtube_link}")
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Upload failed: {str(e)}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

if __name__ == '__main__':
    # Start the bot
    request = HTTPXRequest(
    connect_timeout=10.0,
    read_timeout=20.0,
    write_timeout=20.0,
    pool_timeout=5.0,
)
    app = ApplicationBuilder().token(os.getenv("TELEGRAM_BOT_TOKEN")).request(request).build()
    
    # Listen for text messages
    msg_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
    app.add_handler(msg_handler)

    print("Bot is polling...")
    app.run_polling()