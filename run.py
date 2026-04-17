import os
import threading
import subprocess
import sys
import time

print("🚀 ЗАПУСК ПРИЛОЖЕНИЯ", flush=True)

def run_bot():
    print("🔄 Запуск Telegram-бота...", flush=True)
    time.sleep(5)
    result = subprocess.run([sys.executable, "bot/bot_main.py"])
    print(f"❌ Бот завершил работу с кодом {result.returncode}", flush=True)

def run_fastapi():
    print("🔄 Запуск FastAPI (Mini App)...", flush=True)
    # КРИТИЧНО: хост ДОЛЖЕН быть 0.0.0.0
    subprocess.run([sys.executable, "-m", "uvicorn", "webapp.main:app", "--host", "0.0.0.0", "--port", "8000"])

if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()
    time.sleep(2)
    run_fastapi()