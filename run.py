import os
import threading
import subprocess
import sys
import time

print("🚀 ЗАПУСК ПРИЛОЖЕНИЯ", flush=True)

# Функция для запуска бота
def run_bot():
    print("🔄 Запуск Telegram-бота...", flush=True)
    # Запускаем бота как отдельный процесс
    result = subprocess.run([sys.executable, "bot/bot_main.py"])
    print(f"❌ Бот завершил работу с кодом {result.returncode}", flush=True)

# Функция для запуска FastAPI (Mini App)
def run_fastapi():
    print("🔄 Запуск FastAPI (Mini App)...", flush=True)
    subprocess.run([sys.executable, "-m", "uvicorn", "webapp.main:app", "--host", "0.0.0.0", "--port", "8000"])

if __name__ == "__main__":
    # Запускаем бота в фоновом потоке
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()
    
    # Небольшая задержка, чтобы бот успел инициализироваться
    time.sleep(2)
    
    # Запускаем FastAPI (этот процесс будет главным)
    run_fastapi()