import logging
import sqlite3
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

# --- КОНФИГУРАЦИЯ ---
TOKEN = os.getenv("BOT_TOKEN")

# ... остальной код ...
logging.basicConfig(level=logging.ERROR)

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('/data/students.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            wallet_address TEXT,
            wallet_verified INTEGER DEFAULT 0,
            fa_balance INTEGER DEFAULT 0,
            registered_at TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            action TEXT,
            details TEXT,
            created_at TEXT
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ База данных готова")

def add_user(telegram_id, username, first_name):
    conn = sqlite3.connect('/data/students.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute('''
            INSERT INTO users (telegram_id, username, first_name, fa_balance, registered_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (telegram_id, username, first_name, 100, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

def log_action(telegram_id, action, details=""):
    conn = sqlite3.connect('/data/students.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO logs (telegram_id, action, details, created_at)
        VALUES (?, ?, ?, ?)
    ''', (telegram_id, action, details, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_balance(telegram_id):
    conn = sqlite3.connect('/data/students.db')
    cursor = conn.cursor()
    cursor.execute('SELECT fa_balance FROM users WHERE telegram_id = ?', (telegram_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def get_wallet_status(telegram_id):
    conn = sqlite3.connect('/data/students.db')
    cursor = conn.cursor()
    cursor.execute('SELECT wallet_address, wallet_verified FROM users WHERE telegram_id = ?', (telegram_id,))
    result = cursor.fetchone()
    conn.close()
    return result if result else (None, 0)

# --- КОМАНДЫ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    telegram_id = user.id
    username = user.username
    first_name = user.first_name
    
    is_new = add_user(telegram_id, username, first_name)
    log_action(telegram_id, "start")
    balance = get_balance(telegram_id)
    
    if is_new:
        await update.message.reply_text(
            f"🎉 Привет, {first_name}! Добро пожаловать!\n\n"
            f"💰 Тебе начислено 100 FA токенов!\n"
            f"💎 Твой баланс: {balance} FA\n\n"
            f"📌 Команды:\n"
            f"/balance - баланс\n"
            f"/profile - профиль\n"
            f"/wallet - привязать кошелёк\n"
            f"/help - помощь"
        )
    else:
        await update.message.reply_text(
            f"👋 С возвращением, {first_name}!\n\n"
            f"💎 Твой баланс: {balance} FA\n\n"
            f"/balance - баланс\n"
            f"/profile - профиль\n"
            f"/wallet - привязать кошелёк"
        )

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    balance = get_balance(telegram_id)
    log_action(telegram_id, "check_balance")
    await update.message.reply_text(f"💰 Твой баланс: *{balance} FA*", parse_mode="Markdown")

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    conn = sqlite3.connect('/data/students.db')
    cursor = conn.cursor()
    cursor.execute('SELECT first_name, username, wallet_address, wallet_verified, fa_balance, registered_at FROM users WHERE telegram_id = ?', (telegram_id,))
    user = cursor.fetchone()
    
    # Получаем NFT бейджи
    cursor.execute('SELECT badge_name FROM nft_badges WHERE telegram_id = ?', (telegram_id,))
    badges = cursor.fetchall()
    conn.close()
    
    if user:
        first_name, username, wallet, wallet_verified, balance, registered_at = user
        
        if wallet_verified and wallet:
            wallet_status = f"✅ {wallet[:6]}...{wallet[-4:]}"
        else:
            wallet_status = "❌ Не привязан"
        
        badges_text = "\n".join([f"• {b[0]}" for b in badges]) if badges else "• Нет бейджей"
        
        await update.message.reply_text(
            f"📱 *Мой профиль*\n\n"
            f"👤 Имя: {first_name}\n"
            f"🆔 Username: @{username}\n"
            f"💰 Баланс: {balance} FA\n"
            f"🔗 Кошелёк: {wallet_status}\n"
            f"🏆 Бейджи:\n{badges_text}\n"
            f"📅 Регистрация: {registered_at[:10]}",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("❌ Профиль не найден. Напишите /start")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Команды бота:*\n\n"
        "/start - начать работу\n"
        "/balance - проверить баланс\n"
        "/profile - мой профиль\n"
        "/wallet - привязать криптокошелёк\n"
        "/help - помощь",
        parse_mode="Markdown"
    )

async def wallet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    log_action(telegram_id, "open_wallet_menu")
    
    # ВРЕМЕННЫЙ URL: замените на ваш ngrok URL позже
    # Сейчас для теста используем localhost (не будет работать в Telegram)
    web_app_url = "https://telegram-bot1.amvera.cloud"  
    
    keyboard = [[InlineKeyboardButton("🔗 Подключить кошелёк", web_app=WebAppInfo(url=web_app_url))]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🔗 *Привязка криптокошелька*\n\n"
        "Нажмите кнопку ниже, чтобы подключить ваш MetaMask кошелёк.\n\n"
        "⚠️ *После привязки вы получите:*\n"
        "• +100 FA токенов\n"
        "• NFT бейдж '🔗 Pioneer'\n\n"
        "📌 Убедитесь, что у вас установлен MetaMask!\n\n"
        "⚙️ *Как установить MetaMask:*\n"
        "• На компьютере: расширение для Chrome/Firefox\n"
        "• На телефоне: приложение MetaMask",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

# --- ЗАПУСК ---
def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("wallet", wallet_command))
    
    print("🤖 Бот запущен!")
    print("📁 База данных: students.db")
    print("\n📌 Доступные команды:")
    print("  /start   - начать")
    print("  /balance - баланс")
    print("  /profile - профиль")
    print("  /wallet  - привязать кошелёк")
    print("  /help    - помощь")
    app.run_polling()

if __name__ == "__main__":
    main()
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

async def wallet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    log_action(telegram_id, "open_wallet_menu")
    
    # Замените на ваш реальный URL при публикации
    # Для локального теста используйте ngrok
    WEB_APP_URL = "https://telegram-bot1.amvera.cloud"
    
    keyboard = [[InlineKeyboardButton("🏠 Открыть Mini App", web_app=WebAppInfo(url=WEB_APP_URL))]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🔗 *Привязка криптокошелька*\n\n"
        "Нажмите кнопку ниже, чтобы открыть Mini App и подключить кошелёк.\n\n"
        "После привязки вы получите:\n"
        "• +100 FA токенов\n"
        "• NFT бейдж 'Pioneer'",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )