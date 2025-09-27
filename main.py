import os
import threading
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from notion_client import Client
import re
from flask import Flask

# === Конфигурация ===
BOT_TOKEN = os.environ["BOT_TOKEN"]
NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DATABASE_ID = os.environ["DATABASE_ID"]
CHANNEL_ID = os.environ["CHANNEL_ID"]

notion = Client(auth=NOTION_TOKEN)

# === Telegram бот ===
def extract_tags(text: str):
    return list(set(re.findall(r"#(\w+)", text)))

async def handle_insight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text
    if raw.startswith("/insight "):
        content = raw[len("/insight "):].strip()
    elif raw.startswith("/insight"):
        content = raw[len("/insight"):].strip()
    else:
        return

    if not content:
        await update.message.reply_text("Пусто. Не позорься.")
        return

    tags = extract_tags(content)
    if len(tags) < 2:
        await update.message.reply_text("Минимум 2 тега. Иначе — шум.")
        return

    try:
        today = datetime.now().strftime("%Y-%m-%d")
        page = notion.pages.create(
            parent={"database_id": DATABASE_ID},
            properties={
                "Название": {"title": [{"text": {"content": f"Инсайт: {tags[0]}..."}}]},
                "Содержание": {"rich_text": [{"text": {"content": content}}]},
                "Теги": {"multi_select": [{"name": t} for t in tags]},
                "Дата": {"date": {"start": today}},
            },
        )
        page_id = page["id"].replace("-", "")
        url = f"https://www.notion.so/{page_id}"

        keyboard = [[InlineKeyboardButton("✅ Опубликовать", callback_data=f"pub|{content}")]]
        await update.message.reply_text(
            f"✅ Сохранено.\n{url}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def publish_to_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, content = query.data.split("|", 1)
    try:
        await context.bot.send_message(chat_id=CHANNEL_ID, text=content)
        await query.edit_message_text("🚀 В эфире.")
    except Exception as e:
        await query.edit_message_text(f"💥 Не вышло: {str(e)}")

# === Запуск Telegram бота в фоне ===
def run_telegram_bot():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("insight", handle_insight))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_insight))
    app.add_handler(CallbackQueryHandler(publish_to_channel))
    app.run_polling()

# === Минимальный HTTP-сервер для Render ===
app_flask = Flask(__name__)

@app_flask.route('/')
def health_check():
    return "Bot is alive", 200

# === Запуск ===
if __name__ == "__main__":
    # Запускаем Telegram бота в отдельном потоке
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    bot_thread.start()
    
    # Запускаем Flask на порту, который требует Render
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port)
