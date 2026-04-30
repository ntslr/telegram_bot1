import logging
import sqlite3
import os
import json
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

# --- КОНФИГУРАЦИЯ ---
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [967932083]  # ЗАМЕНИТЕ НА ВАШ TELEGRAM ID

# Настройка БД
DB_PATH = '/data/students.db'

logging.basicConfig(level=logging.INFO)

# ==================== БАЗА ДАННЫХ ====================

def init_db():
    """Создаёт все таблицы"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Таблица пользователей
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
    
    # Таблица логов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            action TEXT,
            details TEXT,
            created_at TEXT
        )
    ''')
    
    # Таблица NFT бейджей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS nft_badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            badge_type TEXT,
            badge_name TEXT,
            issued_at TEXT
        )
    ''')
    
    # Таблица голосований
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS votings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            options TEXT NOT NULL,
            created_by INTEGER,
            created_at TEXT,
            end_at TEXT,
            status TEXT DEFAULT 'active'
        )
    ''')
    
    # Таблица голосов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            voting_id INTEGER,
            telegram_id INTEGER,
            option_index INTEGER,
            voted_at TEXT,
            UNIQUE(voting_id, telegram_id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ База данных готова")

def add_user(telegram_id, username, first_name):
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO logs (telegram_id, action, details, created_at)
        VALUES (?, ?, ?, ?)
    ''', (telegram_id, action, details, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_balance(telegram_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT fa_balance FROM users WHERE telegram_id = ?', (telegram_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def update_balance(telegram_id, amount):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET fa_balance = fa_balance + ? WHERE telegram_id = ?', (amount, telegram_id))
    conn.commit()
    conn.close()

# ==================== ГОЛОСОВАНИЯ ====================

def create_voting(title, description, options, admin_id, days_open=7):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    end_at = (datetime.now() + timedelta(days=days_open)).isoformat()
    cursor.execute('''
        INSERT INTO votings (title, description, options, created_by, created_at, end_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (title, description, json.dumps(options), admin_id, datetime.now().isoformat(), end_at, 'active'))
    voting_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return voting_id

def get_active_votings():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, title, description, options, end_at, 
               (SELECT COUNT(*) FROM votes WHERE voting_id = votings.id) as total_votes
        FROM votings 
        WHERE status = 'active' AND datetime(end_at) > datetime('now')
        ORDER BY created_at DESC
    ''')
    rows = cursor.fetchall()
    conn.close()
    
    votings = []
    for row in rows:
        votings.append({
            'id': row[0],
            'title': row[1],
            'description': row[2],
            'options': json.loads(row[3]),
            'end_at': row[4],
            'total_votes': row[5]
        })
    return votings

def get_voting_by_id(voting_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, title, description, options, end_at, status FROM votings WHERE id = ?', (voting_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            'id': row[0],
            'title': row[1],
            'description': row[2],
            'options': json.loads(row[3]),
            'end_at': row[4],
            'status': row[5]
        }
    return None

def user_has_voted(voting_id, telegram_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM votes WHERE voting_id = ? AND telegram_id = ?', (voting_id, telegram_id))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def cast_vote(voting_id, telegram_id, option_index):
    if user_has_voted(voting_id, telegram_id):
        return False
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO votes (voting_id, telegram_id, option_index, voted_at) VALUES (?, ?, ?, ?)',
                   (voting_id, telegram_id, option_index, datetime.now().isoformat()))
    cursor.execute('UPDATE users SET fa_balance = fa_balance + 10 WHERE telegram_id = ?', (telegram_id,))
    conn.commit()
    conn.close()
    return True

def get_voting_results(voting_id):
    voting = get_voting_by_id(voting_id)
    if not voting:
        return None
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    results = {i: 0 for i in range(len(voting['options']))}
    cursor.execute('SELECT option_index FROM votes WHERE voting_id = ?', (voting_id,))
    for row in cursor.fetchall():
        results[row[0]] += 1
    conn.close()
    return results

def close_voting(voting_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE votings SET status = "closed" WHERE id = ?', (voting_id,))
    conn.commit()
    conn.close()

# ==================== КОМАНДЫ ПОЛЬЗОВАТЕЛЕЙ ====================

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
            f"/list_votes - голосования\n"
            f"/help - помощь"
        )
    else:
        await update.message.reply_text(
            f"👋 С возвращением, {first_name}!\n\n"
            f"💎 Твой баланс: {balance} FA\n\n"
            f"/balance - баланс\n"
            f"/profile - профиль\n"
            f"/wallet - привязать кошелёк\n"
            f"/list_votes - голосования"
        )

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    balance = get_balance(telegram_id)
    log_action(telegram_id, "check_balance")
    await update.message.reply_text(f"💰 Твой баланс: *{balance} FA*", parse_mode="Markdown")

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT first_name, username, wallet_address, wallet_verified, fa_balance, registered_at FROM users WHERE telegram_id = ?', (telegram_id,))
    user = cursor.fetchone()
    cursor.execute('SELECT badge_name FROM nft_badges WHERE telegram_id = ?', (telegram_id,))
    badges = cursor.fetchall()
    conn.close()
    
    if user:
        first_name, username, wallet, wallet_verified, balance, registered_at = user
        wallet_status = f"✅ {wallet[:6]}...{wallet[-4:]}" if wallet_verified and wallet else "❌ Не привязан"
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
        "/list_votes - список голосований\n"
        "/vote <id> <номер> - проголосовать\n"
        "/results <id> - результаты голосования\n"
        "/help - помощь",
        parse_mode="Markdown"
    )

async def wallet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    log_action(telegram_id, "open_wallet_menu")
    
    WEB_APP_URL = "https://telegram-bot1-netslayer7.waw0.amvera.tech"
    
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

# ==================== КОМАНДЫ ГОЛОСОВАНИЙ ====================

async def list_votes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    log_action(telegram_id, "view_votings")
    
    votings = get_active_votings()
    if not votings:
        await update.message.reply_text("📭 *Активных голосований нет*\n\nПриходите позже!", parse_mode="Markdown")
        return
    
    message = "🗳️ *Активные голосования*\n\n"
    for v in votings:
        message += f"*{v['id']}. {v['title']}*\n"
        message += f"📝 {v['description'][:100]}\n"
        message += f"📊 Участников: {v['total_votes']}\n"
        message += f"📅 До: {v['end_at'][:16]}\n\n"
    
    message += "Чтобы проголосовать: `/vote <id> <номер>`\n"
    message += "Пример: `/vote 1 2`\n"
    message += "Результаты: `/results <id>`"
    
    await update.message.reply_text(message, parse_mode="Markdown")

async def vote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ *Как голосовать:*\n`/vote <id_голосования> <номер_варианта>`\n\n"
            "Пример: `/vote 1 2`\n"
            "Список голосований: `/list_votes`",
            parse_mode="Markdown"
        )
        return
    
    try:
        voting_id = int(context.args[0])
        option_index = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Используйте числа! Пример: `/vote 1 2`", parse_mode="Markdown")
        return
    
    voting = get_voting_by_id(voting_id)
    if not voting:
        await update.message.reply_text(f"❌ Голосование #{voting_id} не найдено")
        return
    
    if voting['status'] != 'active':
        await update.message.reply_text(f"❌ Голосование #{voting_id} уже закрыто")
        return
    
    if option_index < 1 or option_index > len(voting['options']):
        await update.message.reply_text(f"❌ Неверный номер. Доступны: 1..{len(voting['options'])}")
        return
    
    if user_has_voted(voting_id, telegram_id):
        await update.message.reply_text("❌ Вы уже голосовали в этом опросе!")
        return
    
    success = cast_vote(voting_id, telegram_id, option_index - 1)
    log_action(telegram_id, "vote", f"voting_{voting_id}_option_{option_index}")
    
    if success:
        selected_option = voting['options'][option_index - 1]
        await update.message.reply_text(
            f"✅ *Ваш голос учтён!*\n\n"
            f"🗳️ *{voting['title']}*\n"
            f"📌 Вы выбрали: *{selected_option}*\n\n"
            f"💰 +10 FA токенов за участие!",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("❌ Ошибка при сохранении голоса")

async def results_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    
    if len(context.args) < 1:
        await update.message.reply_text(
            "📊 *Как посмотреть результаты:*\n`/results <id_голосования>`\n\n"
            "Пример: `/results 1`\n"
            "Список голосований: `/list_votes`",
            parse_mode="Markdown"
        )
        return
    
    try:
        voting_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Используйте число! Пример: `/results 1`", parse_mode="Markdown")
        return
    
    voting = get_voting_by_id(voting_id)
    if not voting:
        await update.message.reply_text(f"❌ Голосование #{voting_id} не найдено")
        return
    
    results = get_voting_results(voting_id)
    total_votes = sum(results.values()) if results else 0
    options = voting['options']
    
    message = f"📊 *Результаты голосования #{voting_id}*\n\n"
    message += f"*{voting['title']}*\n"
    message += f"Статус: {'🟢 Активно' if voting['status'] == 'active' else '🔴 Закрыто'}\n"
    message += f"Всего голосов: {total_votes}\n\n"
    
    for i, option in enumerate(options):
        votes = results.get(i, 0)
        percent = (votes / total_votes * 100) if total_votes > 0 else 0
        bar_length = int(percent / 5)
        bar = "█" * bar_length + "░" * (20 - bar_length)
        message += f"{i+1}. {option}\n"
        message += f"   {bar} {votes} ({percent:.1f}%)\n\n"
    
    if voting['status'] == 'active':
        message += f"📅 До: {voting['end_at'][:16]}"
    else:
        message += "🏁 Голосование завершено"
    
    log_action(telegram_id, "view_results", f"voting_{voting_id}")
    await update.message.reply_text(message, parse_mode="Markdown")

# ==================== АДМИН-КОМАНДЫ ====================

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if telegram_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещён")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    cursor.execute('SELECT SUM(fa_balance) FROM users')
    total_fa = cursor.fetchone()[0] or 0
    cursor.execute('SELECT COUNT(*) FROM users WHERE wallet_verified = 1')
    verified = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM votings')
    total_votings = cursor.fetchone()[0]
    conn.close()
    
    await update.message.reply_text(
        f"📊 *Статистика*\n\n"
        f"👥 Пользователей: {total_users}\n"
        f"💎 Всего FA: {total_fa}\n"
        f"🔗 Привязали кошелёк: {verified}\n"
        f"🗳️ Голосований создано: {total_votings}",
        parse_mode="Markdown"
    )

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if telegram_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещён")
        return
    
    message_text = " ".join(context.args)
    if not message_text:
        await update.message.reply_text("📢 Использование: `/broadcast Текст`", parse_mode="Markdown")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT telegram_id FROM users')
    users = cursor.fetchall()
    conn.close()
    
    success = 0
    for user in users:
        try:
            await context.bot.send_message(chat_id=user[0], text=f"📢 *Массовое уведомление*\n\n{message_text}", parse_mode="Markdown")
            success += 1
        except:
            pass
    
    await update.message.reply_text(f"✅ Рассылка отправлена {success} пользователям")
    log_action(telegram_id, "admin_broadcast", f"sent_to_{success}")

async def admin_add_fa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if telegram_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещён")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("💰 Использование: `/add_fa TELEGRAM_ID КОЛИЧЕСТВО`", parse_mode="Markdown")
        return
    
    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Неверный формат")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT first_name FROM users WHERE telegram_id = ?', (target_id,))
    user = cursor.fetchone()
    
    if not user:
        await update.message.reply_text(f"❌ Пользователь {target_id} не найден")
        conn.close()
        return
    
    cursor.execute('UPDATE users SET fa_balance = fa_balance + ? WHERE telegram_id = ?', (amount, target_id))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"✅ Начислено {amount} FA пользователю {user[0]}")
    log_action(telegram_id, "admin_add_fa", f"user_{target_id}_amount_{amount}")

async def admin_create_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if telegram_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещён")
        return
    
    if len(context.args) < 1:
        await update.message.reply_text(
            "📝 *Создание голосования:*\n"
            "`/create_vote Название | Описание | Вариант1,Вариант2,Вариант3 | дни`\n\n"
            "Пример:\n"
            "`/create_vote Выбор | Лучшая платформа? | Telegram,Discord,WhatsApp | 7`",
            parse_mode="Markdown"
        )
        return
    
    full_text = " ".join(context.args)
    parts = full_text.split("|")
    
    if len(parts) < 3:
        await update.message.reply_text("❌ Неверный формат. Используйте разделитель `|`")
        return
    
    title = parts[0].strip()
    description = parts[1].strip() if len(parts) > 1 else ""
    options = [opt.strip() for opt in parts[2].split(",")] if len(parts) > 2 else []
    days = int(parts[3].strip()) if len(parts) > 3 and parts[3].strip().isdigit() else 7
    
    if len(options) < 2:
        await update.message.reply_text("❌ Нужно минимум 2 варианта")
        return
    
    voting_id = create_voting(title, description, options, telegram_id, days)
    log_action(telegram_id, "create_vote", f"voting_{voting_id}")
    
    options_text = "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(options)])
    await update.message.reply_text(
        f"✅ *Голосование создано!*\n\n"
        f"ID: {voting_id}\n"
        f"Название: {title}\n"
        f"Варианты:\n{options_text}\n"
        f"Длительность: {days} дней\n\n"
        f"Голосовать: `/vote {voting_id} <номер>`",
        parse_mode="Markdown"
    )
    
    # Рассылка уведомления
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT telegram_id FROM users')
    users = cursor.fetchall()
    conn.close()
    
    for user in users:
        try:
            await context.bot.send_message(
                chat_id=user[0],
                text=f"🗳️ *НОВОЕ ГОЛОСОВАНИЕ!*\n\n*{title}*\n{description}\n\nГолосовать: `/vote {voting_id} <номер>`",
                parse_mode="Markdown"
            )
        except:
            pass

async def admin_close_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if telegram_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещён")
        return
    
    if len(context.args) < 1:
        await update.message.reply_text("📝 Использование: `/close_vote <id>`", parse_mode="Markdown")
        return
    
    try:
        voting_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID должен быть числом")
        return
    
    voting = get_voting_by_id(voting_id)
    if not voting:
        await update.message.reply_text(f"❌ Голосование #{voting_id} не найдено")
        return
    
    close_voting(voting_id)
    await update.message.reply_text(f"🔒 Голосование #{voting_id} закрыто")
    log_action(telegram_id, "close_vote", f"voting_{voting_id}")

# ==================== ЗАПУСК ====================

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    
    # Пользовательские команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("wallet", wallet_command))
    app.add_handler(CommandHandler("list_votes", list_votes_command))
    app.add_handler(CommandHandler("vote", vote_command))
    app.add_handler(CommandHandler("results", results_command))
    
    # Админ-команды
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("broadcast", admin_broadcast))
    app.add_handler(CommandHandler("add_fa", admin_add_fa))
    app.add_handler(CommandHandler("create_vote", admin_create_vote))
    app.add_handler(CommandHandler("close_vote", admin_close_vote))
    
    print("🤖 Бот запущен!")
    print("📁 База данных: /data/students.db")
    print("\n📌 Команды:")
    print("  /start, /balance, /profile, /wallet")
    print("  /list_votes, /vote, /results")
    print("  Админ: /stats, /broadcast, /add_fa, /create_vote, /close_vote")
    app.run_polling()

# ==================== КОМАНДЫ МЕНЮ ====================

async def set_commands(app: Application):
    commands = [
        ("start", "🚀 Запустить бота и получить 100 FA"),
        ("balance", "💰 Проверить баланс FA токенов"),
        ("profile", "📱 Мой профиль и NFT бейджи"),
        ("wallet", "🔗 Привязать криптокошелёк"),
        ("list_votes", "🗳️ Список активных голосований"),
        ("vote", "🗳️ Проголосовать: /vote <id> <номер>"),
        ("results", "📊 Результаты голосования"),
        ("help", "❓ Помощь по командам"),
    ]
    await app.bot.set_my_commands([(cmd, desc) for cmd, desc in commands])
    print("✅ Команды зарегистрированы в Telegram")

# ==================== ЗАПУСК ====================

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("wallet", wallet_command))
    app.add_handler(CommandHandler("list_votes", list_votes_command))
    app.add_handler(CommandHandler("vote", vote_command))
    app.add_handler(CommandHandler("results", results_command))
    
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("broadcast", admin_broadcast))
    app.add_handler(CommandHandler("add_fa", admin_add_fa))
    app.add_handler(CommandHandler("create_vote", admin_create_vote))
    app.add_handler(CommandHandler("close_vote", admin_close_vote))
    
    import asyncio
    asyncio.get_event_loop().run_until_complete(set_commands(app))
    
    print("🤖 Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()