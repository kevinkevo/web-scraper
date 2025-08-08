import os
import logging
import asyncio
import redis
from datetime import datetime
import concurrent.futures
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from dotenv import load_dotenv
from utils import extract_intent_from_text, format_filters, generate_pdf_report
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
        "- `T2 em Lisboa`\n"
        "- `T3 com 2 WC`\n\n"
        "✅ Filtros: localização, tipologia, preço, área, quartos, WC.\n\n"
        "Comandos:\n"
        "/test — Ver todos os imóveis\n"
        "/pause — Pausar o bot\n"
        "/resume — Retomar\n"
        "/status — Ver status\n",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if REDIS.get("paused"):
        await update.message.reply_text("🔴 Bot está pausado.")
        return

    text = update.message.text
    filters = extract_intent_from_text(text)
    logger.info(f"Parsed filters: {filters}")

    await update.message.reply_text(f"🔍 *A procurar imóveis...*\n{format_filters(filters)}", parse_mode="Markdown")

    loop = asyncio.get_event_loop()
    try:
        with concurrent.futures.ThreadPoolExecutor() as pool:
            results = await asyncio.wait_for(
                loop.run_in_executor(pool, scrape_casayes, filters),
                timeout=1800
            )
    except asyncio.TimeoutError:
        logger.error("Search timed out after 60 seconds", exc_info=True)
        await update.message.reply_text("❌ A pesquisa falhou: Tempo limite esgotado.")
        return
    except Exception as e:
        logger.error(f"Search failed: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ A pesquisa falhou: {str(e)}")
        return

    if not results:
        await update.message.reply_text(f"❌ *Nenhum imóvel encontrado:*\n{format_filters(filters)}")
        return

    # Send top 5 preview
    preview = f"🏘 *Top {min(5, len(results))} Imóveis Encontrados*\n\n"
    for i, r in enumerate(results[:5], 1):
        preview += f"🔹 *{r['title']}*\n"
        preview += f"   📍 {r['location']}\n"
        preview += f"   💶 {r['price']}\n"
        if r.get('area'):
            preview += f"   📐 {r['area']} m²\n"
        if r.get('bedrooms') is not None:
            preview += f"   🛏️ {r['bedrooms']} quartos\n"
        if r.get('bathrooms') is not None:
            preview += f"   🛁 {r['bathrooms']} WC\n"
        if r.get('link'):
            preview += f"   🔗 [Ver imóvel]({r['link']})\n"
        preview += "\n"

    await update.message.reply_text(preview, parse_mode="Markdown", disable_web_page_preview=True)

    # Generate PDF of full results
    filename = generate_pdf_report(results, filters)
    if os.path.exists(filename):
        with open(filename, "rb") as pdf_file:
            await update.message.reply_document(
                document=InputFile(pdf_file, filename="imoveis.pdf"),
                caption="📄 *Lista completa de imóveis*"
            )
        os.remove(filename)

    REDIS.set("last_scrape_time", datetime.now().isoformat())

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if REDIS.get("paused"):
        await update.message.reply_text("🔴 Bot está pausado.")
        return

    await update.message.reply_text("🔍 *A procurar imóveis... aguarde ⏳*", parse_mode="Markdown")
    loop = asyncio.get_event_loop()
    try:
        with concurrent.futures.ThreadPoolExecutor() as pool:
            results = await asyncio.wait_for(
                loop.run_in_executor(pool, scrape_casayes, None),
                timeout=1800
            )
    except asyncio.TimeoutError:
        await update.message.reply_text("❌ Tempo limite esgotado durante a pesquisa.")
        return
    except Exception as e:
        await update.message.reply_text(f"❌ Erro: {str(e)}")
        return

    if not results:
        await update.message.reply_text("❌ *Nenhum imóvel encontrado.*")
        return

    # Preview top 5
    msg = f"📊 *Top {min(5, len(results))} Imóveis Encontrados:*\n\n"
    for i, r in enumerate(results[:5], 1):
        msg += f"🔹 *{r['title']}*\n"
        msg += f"   📍 {r['location']}\n"
        msg += f"   💶 {r['price']}\n"
        if r.get('area'):
            msg += f"   📐 {r['area']} m²\n"
        if r.get('bedrooms') is not None:
            msg += f"   🛏️ {r['bedrooms']} quartos\n"
        if r.get('bathrooms') is not None:
            msg += f"   🛁 {r['bathrooms']} WC\n"
        if r.get('link'):
            msg += f"   🔗 [Ver imóvel]({r['link']})\n"
        msg += "\n"

    await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)

    # PDF
    filename = generate_pdf_report(results)
    if os.path.exists(filename):
        with open(filename, "rb") as pdf_file:
            await update.message.reply_document(
                document=InputFile(pdf_file, filename="imoveis.pdf"),
                caption="📄 *Lista completa de imóveis*"
            )
        os.remove(filename)

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
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.add_handler(MessageHandler(filters.COMMAND, unknown))
    asyncio.run(app.run_polling())