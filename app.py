import os
import threading
import logging
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- 1. НАСТРОЙКИ ---
logging.basicConfig(level=logging.INFO)
TOKEN = os.environ.get("BOT_TOKEN")

# Убедимся, что токен найден
if not TOKEN:
    logging.error("❌ ОШИБКА: BOT_TOKEN не найден в переменных окружения!")
    exit(1)

# --- 2. КОМАНДЫ БОТА (ПРОВЕРКА) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Простая команда /start для проверки"""
    await update.message.reply_text(
        "✅ Бот успешно запущен на Render!\n\n"
        "Ваш проект работает. Можете пользоваться."
    )

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /balance для проверки"""
    await update.message.reply_text("💰 Ваш баланс: 100 FA (тестовый режим)")

# --- 3. ЗАПУСК БОТА В ОТДЕЛЬНОМ ПОТОКЕ ---
def run_bot():
    """Эта функция запускает вашего Telegram-бота"""
    print("🤖 Запускаем бота...")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance))
    
    # Сюда позже добавите все остальные ваши команды (profile, wallet...)
    
    print("✅ Бот запущен и слушает сообщения!")
    app.run_polling()

# --- 4. ВЕБ-СЕРВЕР ДЛЯ RENDER (НЕ ТРОГАТЬ) ---
flask_app = Flask(__name__)

@flask_app.route('/')
def health_check():
    return "Telegram bot is running!", 200

# --- 5. ТОЧКА ВХОДА ---
if __name__ == '__main__':
    # Запускаем бота в фоновом потоке
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()
    
    # Запускаем веб-сервер (то, что видит Render)
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)