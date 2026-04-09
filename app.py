import os
import threading
from flask import Flask
from bot.bot_main import main as run_bot  # Импортируем запуск бота

# Создаем фиктивное веб-приложение
web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    return "Telegram bot is running!"

if __name__ == '__main__':
    # Запускаем бота в фоновом потоке
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()
    # Запускаем веб-сервер, который будет слушать порт
    port = int(os.environ.get("PORT", 5000))
    web_app.run(host='0.0.0.0', port=port)