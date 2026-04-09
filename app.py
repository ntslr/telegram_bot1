import os
import threading
import logging
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- НАСТРОЙКИ ---
logging.basicConfig(level=logging.INFO)
TOKEN = os.environ.get("BOT_TOKEN")

if not TOKEN:
    logging.error("❌ BOT_TOKEN не найден!")
    exit(1)

# --- ПРОСТЕЙШАЯ КОМАНДА БОТА ДЛЯ ТЕСТА ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Бот на Render работает!")

def run_bot():
    """Запуск бота"""
    print("🤖 Запускаем бота...")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    print("✅ Бот запущен и слушает!")
    app.run_polling()

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
flask_app = Flask(__name__)

@flask_app.route('/')
def health():
    return "Bot is running!", 200

# --- ТОЧКА ВХОДА ---
if __name__ == '__main__':
    # Запускаем бота в фоновом потоке
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()
    
    # Запускаем веб-сервер
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)