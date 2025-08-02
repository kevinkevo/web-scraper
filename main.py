import os
import logging
import asyncio
import redis
from datetime import datetime
import concurrent.futures
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from dotenv import load_dotenv
from utils import extract_intent_from_text, format_filters
from scraper import scrape_casayes

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏡 *Bem-vindo ao Bot CasaYes!*\n\n"
        "Digite consultas como:\n"
        "- `T2 em Lisboa `\n"
        "- `T3 com 2 WC`\n\n"
        "✅ Filtros: localização, tipologia, preço, área, quartos, WC.\n\n"
        "Comandos:\n"
        "/test — Ver todos os imóveis\n"
        "/pause — Pausar o bot\n"
        "/resume — Retomar\n"
        "/status — Ver status\n",
        parse_mode="Markdown"
    )

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if REDIS.get("paused"):
        await update.message.reply_text("🔴 Bot está pausado.")
        return

    await update.message.reply_text("🔍 A procurar imóveis... aguarde ⏳", parse_mode="Markdown")
    loop = asyncio.get_event_loop()
    try:
        with concurrent.futures.ThreadPoolExecutor() as pool:
            results = await asyncio.wait_for(
                loop.run_in_executor(pool, scrape_casayes, None),
                timeout=60
            )
    except asyncio.TimeoutError:
        await update.message.reply_text("❌ Tempo limite esgotado durante a pesquisa.")
        return
    except Exception as e:
        await update.message.reply_text(f"❌ Erro: {str(e)}")
        return

    if not results:
        await update.message.reply_text("❌ Nenhum imóvel encontrado.")
        return

    msg = "📊 *Todos os Imóveis*\n\n"
    for r in results:
        msg += f"🏠 *{r['title']}*\n"
        msg += f"📍 *Localização:* {r['location']}\n"
        msg += f"💶 *Preço:* {r['price']}\n"
        if r.get("area"):
            msg += f"📐 *Área:* {r['area']} m²\n"
        if r.get("bedrooms") is not None:
            msg += f"🛏 *Quartos:* {r['bedrooms']}\n"
        if r.get("bathrooms") is not None:
            msg += f"🛁 *WC:* {r['bathrooms']}\n"
        if r.get("link"):
            msg += f"🔗 [Ver imóvel]({r['link']})\n"
        msg += "\n"

        if len(msg) > 3500:
            await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)
            msg = ""

    if msg:
        await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)

    REDIS.set("last_scrape_time", datetime.now().isoformat())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if REDIS.get("paused"):
        await update.message.reply_text("🔴 Bot está pausado.")
        return

    text = update.message.text
    filters = extract_intent_from_text(text)
    logger.info(f"Parsed filters: {filters}")

    await update.message.reply_text(f"🔍 A procurar por: {format_filters(filters)}...", parse_mode="Markdown")

    loop = asyncio.get_event_loop()
    try:
        with concurrent.futures.ThreadPoolExecutor() as pool:
            results = await asyncio.wait_for(
                loop.run_in_executor(pool, scrape_casayes, filters),
                timeout=60
            )
    except Exception as e:
        await update.message.reply_text(f"❌ A pesquisa falhou: {e}")
        return

    if not results:
        await update.message.reply_text(f"❌ Nenhum imóvel encontrado para: {format_filters(filters)}.")
        return

    msg = f"🏘 *Resultados ({format_filters(filters)})*\n\n"
    for r in results:
        msg += f"🏠 *{r['title']}*\n"
        msg += f"📍 *Localização:* {r['location']}\n"
        msg += f"💶 *Preço:* {r['price']}\n"
        if r.get("area"):
            msg += f"📐 *Área:* {r['area']} m²\n"
        if r.get("bedrooms") is not None:
            msg += f"🛏 *Quartos:* {r['bedrooms']}\n"
        if r.get("bathrooms") is not None:
            msg += f"🛁 *WC:* {r['bathrooms']}\n"
        if r.get("link"):
            msg += f"🔗 [Ver imóvel]({r['link']})\n"
        msg += "\n"

        if len(msg) > 3500:
            await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)
            msg = ""

    if msg:
        await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)

    REDIS.set("last_scrape_time", datetime.now().isoformat())

async def pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    REDIS.set("paused", 1)
    await update.message.reply_text("⏸ Bot pausado.")

async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    REDIS.delete("paused")
    await update.message.reply_text("▶ Bot retomado.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    paused = REDIS.get("paused")
    last = REDIS.get("last_scrape_time")
    msg = f"⚙️ *Status*\nPausado: {'Sim' if paused else 'Não'}\nÚltima Pesquisa: {last if last else 'Nunca'}"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❓ Comando desconhecido.")

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
