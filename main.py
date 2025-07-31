import os
import logging
import asyncio
import redis
from datetime import datetime
import concurrent.futures
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from dotenv import load_dotenv
from utils import extract_intent_from_text, generate_fallback_txt, format_filters
from scraper import scrape_casayes

# === LOAD CONFIG ===
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
REDIS_URL = os.getenv("REDIS_URL")
REDIS = redis.Redis.from_url(REDIS_URL, decode_responses=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# === COMMANDS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏡 *Welcome to CasaYes Real Estate Bot!*\n\n"
        "Find your perfect property by sending a text query, e.g.:\n"
        "- `T2 in Almada up to €250,000`\n"
        "- `T1 in Lisboa`\n"
        "- `T3 up to €500,000`\n\n"
        "🔎 *Supported Filters*: Typology (T1, T2, T3, etc.), location (e.g., Almada, Lisboa), and price range.\n"
        "📄 A text report will be generated for all matching listings.\n\n"
        "Commands:\n"
        "/test — View all available listings\n"
        "/pause — Pause the bot\n"
        "/resume — Resume the bot\n"
        "/status — Check bot status\n\n"
        "*Note*: Voice input and feature filters (e.g., balcony) are not supported in this version. Use text queries with typology, location, or price for best results.",
        parse_mode="Markdown"
    )

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if REDIS.get("paused"):
        await update.message.reply_text("🔴 Bot is paused.")
        return

    await update.message.reply_text("🔍 Scraping all listings... please wait ⏳", parse_mode="Markdown")

    loop = asyncio.get_event_loop()
    try:
        with concurrent.futures.ThreadPoolExecutor() as pool:
            results = await asyncio.wait_for(
                loop.run_in_executor(pool, scrape_casayes, None),
                timeout=60
            )
    except asyncio.TimeoutError:
        logger.error("Timeout during test scrape")
        await update.message.reply_text("❌ Timeout while scraping. Please try again later.")
        return
    except Exception as e:
        logger.error(f"Scraping failed in test: {e}")
        await update.message.reply_text(f"❌ Scraping failed: {str(e)}")
        return

    if not results:
        await update.message.reply_text("❌ No listings found. The website may be down or have no listings.")
        return

    message = f"📊 *All Listings from casayes.pt*\n\n"
    for i, r in enumerate(results):
        message += f"• *{r['title']}* — {r['price']}\n📍 {r['location']}\n\n"
        if len(message) > 3500 or i == len(results) - 1:
            await update.message.reply_text(message, parse_mode="Markdown")
            message = ""

    try:
        txt_path = generate_fallback_txt(results)
        await update.message.reply_document(document=InputFile(txt_path), filename="listings.txt")
        os.remove(txt_path)
    except Exception as e:
        logger.error(f"Failed to generate/send text report: {str(e)}")
        await update.message.reply_text("⚠️ Listings found, but failed to generate text report.")

    REDIS.set("last_scrape_time", datetime.now().isoformat())

async def pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    REDIS.set("paused", 1)
    await update.message.reply_text("⏸ Bot paused.")

async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    REDIS.delete("paused")
    await update.message.reply_text("▶ Bot resumed.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    paused = REDIS.get("paused")
    last = REDIS.get("last_scrape_time")
    msg = f"⚙️ *Bot Status*\nPaused: {'Yes' if paused else 'No'}\nLast scrape: {last if last else 'N/A'}"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❓ Unknown command.")

# === TEXT HANDLER ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if REDIS.get("paused"):
        await update.message.reply_text("🔴 Bot is paused.")
        return

    if update.message.voice:
        await update.message.reply_text("❌ Voice input is not supported in this version. Please use text queries.")
        return

    text = update.message.text
    filters = extract_intent_from_text(text)
    logger.info(f"Parsed filters: {filters}")
    await update.message.reply_text(
        f"🔍 Scraping listings with filters: {format_filters(filters)}...",
        parse_mode="Markdown"
    )

    loop = asyncio.get_event_loop()
    try:
        with concurrent.futures.ThreadPoolExecutor() as pool:
            results = await asyncio.wait_for(
                loop.run_in_executor(pool, scrape_casayes, filters),
                timeout=60
            )
    except asyncio.TimeoutError:
        logger.error("Timeout during message scrape")
        await update.message.reply_text("❌ Timeout while scraping. Please try again later.")
        return
    except Exception as e:
        logger.error(f"Scraping failed in handle_message: {e}")
        await update.message.reply_text(f"❌ Scraping failed: {str(e)}")
        return

    if not results:
        await update.message.reply_text(
            f"❌ No listings found matching: {format_filters(filters)}. Try a different location (e.g., Almada, Lisboa) or higher price."
        )
        return

    message = f"🏘 *Listings from casayes.pt (Filters: {format_filters(filters)})*\n\n"
    for i, r in enumerate(results):
        message += f"• *{r['title']}* — {r['price']}\n📍 {r['location']}\n\n"
        if len(message) > 3500 or i == len(results) - 1:
            await update.message.reply_text(message, parse_mode="Markdown")
            message = ""

    try:
        txt_path = generate_fallback_txt(results)
        await update.message.reply_document(document=InputFile(txt_path), filename="listings.txt")
        os.remove(txt_path)
    except Exception as e:
        logger.error(f"Failed to generate/send text report: {str(e)}")
        await update.message.reply_text("⚠️ Listings found, but failed to generate text report.")

    REDIS.set("last_scrape_time", datetime.now().isoformat())

# === MAIN ===
if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("test", test))
    app.add_handler(CommandHandler("pause", pause))
    app.add_handler(CommandHandler("resume", resume))
    app.add_handler(CommandHandler("status", status))

    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    app.add_handler(MessageHandler(filters.COMMAND, unknown))

    asyncio.run(app.run_polling())