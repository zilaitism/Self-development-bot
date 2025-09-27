import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from notion_client import Client
import re

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DATABASE_ID = os.environ["DATABASE_ID"]
CHANNEL_ID = os.environ["CHANNEL_ID"]

notion = Client(auth=NOTION_TOKEN)

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

if __name__ == "__main__":
    app = Application.builder().token(os.environ["BOT_TOKEN"]).build()
    app.add_handler(CommandHandler("insight", handle_insight))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_insight))
    app.add_handler(CallbackQueryHandler(publish_to_channel))
    app.run_polling()
