from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import sqlite3
import secrets
from datetime import datetime
import os

app = FastAPI()

# Модели для запросов
class NonceRequest(BaseModel):
    telegram_id: int

class VerifyRequest(BaseModel):
    telegram_id: int
    wallet_address: str
    signature: str

# --- Функции БД ---
def get_user(telegram_id):
    conn = sqlite3.connect('/data/students.db')
    cursor = conn.cursor()
    cursor.execute('SELECT first_name, wallet_address, wallet_verified, fa_balance FROM users WHERE telegram_id = ?', (telegram_id,))
    user = cursor.fetchone()
    conn.close()
    if user:
        return {
            "first_name": user[0],
            "wallet_address": user[1],
            "wallet_verified": bool(user[2]) if user[2] else False,
            "fa_balance": user[3] or 0
        }
    return None

def get_badges(telegram_id):
    conn = sqlite3.connect('/data/students.db')
    cursor = conn.cursor()
    cursor.execute('SELECT badge_name, issued_at FROM nft_badges WHERE telegram_id = ?', (telegram_id,))
    badges = cursor.fetchall()
    conn.close()
    return [{"name": b[0], "date": b[1][:10]} for b in badges]

def get_history(telegram_id):
    conn = sqlite3.connect('/data/students.db')
    cursor = conn.cursor()
    cursor.execute('SELECT action, details, created_at FROM logs WHERE telegram_id = ? ORDER BY created_at DESC LIMIT 10', (telegram_id,))
    history = cursor.fetchall()
    conn.close()
    
    action_names = {
        'start': '🎉 Регистрация',
        'check_balance': '💰 Проверка баланса',
        'wallet_verified': '🔗 Привязка кошелька'
    }
    return [{"action": action_names.get(h[0], h[0]), "date": h[2][:10]} for h in history]

# --- API эндпоинты ---
@app.get("/api/profile/{telegram_id}")
async def profile(telegram_id: int):
    user = get_user(telegram_id)
    if not user:
        return {"fa_balance": 0, "first_name": "Гость", "wallet_verified": False}
    return user

@app.get("/api/badges/{telegram_id}")
async def badges(telegram_id: int):
    return get_badges(telegram_id)

@app.get("/api/history/{telegram_id}")
async def history(telegram_id: int):
    return get_history(telegram_id)

@app.post("/api/get_nonce")
async def get_nonce(request: NonceRequest):
    nonce = secrets.token_hex(32)
    conn = sqlite3.connect('/data/students.db')
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS wallet_nonce (telegram_id INTEGER PRIMARY KEY, nonce TEXT, created_at TEXT)')
    cursor.execute('INSERT OR REPLACE INTO wallet_nonce (telegram_id, nonce, created_at) VALUES (?, ?, ?)',
                   (request.telegram_id, nonce, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    message = f"Подтверждаю привязку Telegram аккаунта к кошельку\n\nNonce: {nonce}"
    return {"nonce": nonce, "message": message}

@app.post("/api/verify_wallet")
async def verify_wallet(request: VerifyRequest):
    conn = sqlite3.connect('/data/students.db')
    cursor = conn.cursor()
    cursor.execute('SELECT nonce FROM wallet_nonce WHERE telegram_id = ?', (request.telegram_id,))
    result = cursor.fetchone()
    if not result:
        raise HTTPException(status_code=400, detail="Nonce не найден")
    
    cursor.execute('UPDATE users SET wallet_address = ?, wallet_verified = 1 WHERE telegram_id = ?',
                   (request.wallet_address, request.telegram_id))
    cursor.execute('UPDATE users SET fa_balance = fa_balance + 100 WHERE telegram_id = ?', (request.telegram_id,))
    cursor.execute('INSERT INTO logs (telegram_id, action, details, created_at) VALUES (?, ?, ?, ?)',
                   (request.telegram_id, "wallet_verified", request.wallet_address, datetime.now().isoformat()))
    cursor.execute('INSERT INTO nft_badges (telegram_id, badge_type, badge_name, issued_at) VALUES (?, ?, ?, ?)',
                   (request.telegram_id, "wallet_verified", "🔗 Pioneer", datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return {"success": True, "message": "Кошелёк привязан! +100 FA, получен бейдж Pioneer"}

# --- HTML страница ---
HTML_PAGE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FA Ecosystem</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            padding: 16px;
            background: var(--tg-theme-bg-color);
            color: var(--tg-theme-text-color);
        }
        .container { max-width: 500px; margin: 0 auto; }
        .balance-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 24px;
            padding: 24px;
            text-align: center;
            color: white;
            margin-bottom: 20px;
        }
        .balance-value { font-size: 48px; font-weight: bold; margin-top: 8px; }
        .tabs {
            display: flex;
            gap: 8px;
            background: var(--tg-theme-secondary-bg-color);
            border-radius: 16px;
            padding: 4px;
            margin-bottom: 20px;
        }
        .tab-btn {
            flex: 1;
            padding: 10px;
            border: none;
            background: transparent;
            color: var(--tg-theme-text-color);
            font-size: 14px;
            border-radius: 12px;
            cursor: pointer;
        }
        .tab-btn.active {
            background: var(--tg-theme-button-color);
            color: var(--tg-theme-button-text-color);
        }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .card {
            background: var(--tg-theme-secondary-bg-color);
            border-radius: 16px;
            padding: 16px;
            margin-bottom: 16px;
        }
        .info-row {
            display: flex;
            justify-content: space-between;
            padding: 12px 0;
            border-bottom: 1px solid rgba(128,128,128,0.2);
        }
        .info-row:last-child { border-bottom: none; }
        button {
            width: 100%;
            padding: 14px;
            background: var(--tg-theme-button-color);
            color: var(--tg-theme-button-text-color);
            border: none;
            border-radius: 12px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
        }
        .badge-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px;
            background: var(--tg-theme-secondary-bg-color);
            border-radius: 12px;
            margin-bottom: 8px;
        }
        .history-item {
            display: flex;
            justify-content: space-between;
            padding: 12px;
            border-bottom: 1px solid rgba(128,128,128,0.1);
        }
        .status {
            padding: 12px;
            margin: 15px 0;
            border-radius: 10px;
            text-align: center;
        }
        .info { background: #2196F3; color: white; }
        .success { background: #4CAF50; color: white; }
        .error { background: #f44336; color: white; }
    </style>
</head>
<body>
    <div class="container">
        <div class="balance-card">
            <div>💰 FA BALANCE</div>
            <div class="balance-value" id="balance">0</div>
        </div>
        
        <div class="tabs">
            <button class="tab-btn active" data-tab="profile">👤 Профиль</button>
            <button class="tab-btn" data-tab="badges">🏆 Бейджи</button>
            <button class="tab-btn" data-tab="history">📜 История</button>
        </div>
        
        <div id="profile-tab" class="tab-content active">
            <div class="card">
                <div class="info-row"><span>👤 Имя</span><span id="first_name">-</span></div>
                <div class="info-row"><span>🔗 Кошелёк</span><span id="wallet_status">❌ Не привязан</span></div>
            </div>
            <button id="connectBtn">🦊 Подключить MetaMask</button>
            <div id="status" class="status info" style="margin-top: 16px;">⚠️ Нажмите кнопку для привязки кошелька</div>
        </div>
        
        <div id="badges-tab" class="tab-content"><div id="badges_list"></div></div>
        <div id="history-tab" class="tab-content"><div id="history_list"></div></div>
    </div>

    <script>
        const tg = window.Telegram.WebApp;
        tg.expand();
        const telegramId = tg.initDataUnsafe.user?.id;
        
        let currentUser = null;
        
        async function loadProfile() {
            const res = await fetch(`/api/profile/${telegramId}`);
            currentUser = await res.json();
            document.getElementById('balance').innerText = currentUser.fa_balance || 0;
            document.getElementById('first_name').innerText = currentUser.first_name || '-';
            if (currentUser.wallet_verified && currentUser.wallet_address) {
                const short = currentUser.wallet_address.slice(0,6)+'...'+currentUser.wallet_address.slice(-4);
                document.getElementById('wallet_status').innerHTML = `✅ ${short}`;
                document.getElementById('connectBtn').style.display = 'none';
                document.getElementById('status').innerHTML = '✅ Кошелёк привязан!';
                document.getElementById('status').className = 'status success';
            }
        }
        
        async function loadBadges() {
            const res = await fetch(`/api/badges/${telegramId}`);
            const badges = await res.json();
            const container = document.getElementById('badges_list');
            if (!badges.length) {
                container.innerHTML = '<div class="card" style="text-align:center;">🎖️ Нет бейджей</div>';
                return;
            }
            container.innerHTML = badges.map(b => `
                <div class="badge-item">
                    <span>🏆</span>
                    <div><strong>${b.name}</strong><br><small>${b.date}</small></div>
                </div>
            `).join('');
        }
        
        async function loadHistory() {
            const res = await fetch(`/api/history/${telegramId}`);
            const history = await res.json();
            const container = document.getElementById('history_list');
            if (!history.length) {
                container.innerHTML = '<div class="card" style="text-align:center;">📭 Нет действий</div>';
                return;
            }
            container.innerHTML = history.map(h => `
                <div class="history-item">
                    <span>${h.action}</span>
                    <small>${h.date}</small>
                </div>
            `).join('');
        }
        
        async function connectWallet() {
            const statusDiv = document.getElementById('status');
            if (typeof window.ethereum === 'undefined') {
                statusDiv.innerHTML = '❌ Установите MetaMask!';
                statusDiv.className = 'status error';
                return;
            }
            try {
                statusDiv.innerHTML = '🔄 Подключение...';
                statusDiv.className = 'status info';
                const accounts = await ethereum.request({ method: 'eth_requestAccounts' });
                const walletAddress = accounts[0];
                const nonceRes = await fetch('/api/get_nonce', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ telegram_id: telegramId })
                });
                const nonceData = await nonceRes.json();
                const signature = await ethereum.request({
                    method: 'personal_sign',
                    params: [nonceData.message, walletAddress]
                });
                const verifyRes = await fetch('/api/verify_wallet', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ telegram_id: telegramId, wallet_address: walletAddress, signature })
                });
                const result = await verifyRes.json();
                if (result.success) {
                    statusDiv.innerHTML = '✅ ' + result.message;
                    statusDiv.className = 'status success';
                    tg.showAlert(result.message);
                    loadProfile();
                    loadBadges();
                    loadHistory();
                } else {
                    statusDiv.innerHTML = '❌ Ошибка';
                    statusDiv.className = 'status error';
                }
            } catch(e) {
                statusDiv.innerHTML = '❌ ' + e.message;
                statusDiv.className = 'status error';
            }
        }
        
        // Табы
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.onclick = () => {
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
                btn.classList.add('active');
                document.getElementById(`${btn.dataset.tab}-tab`).classList.add('active');
                if (btn.dataset.tab === 'badges') loadBadges();
                if (btn.dataset.tab === 'history') loadHistory();
            };
        });
        
        document.getElementById('connectBtn').onclick = connectWallet;
        loadProfile();
        loadBadges();
        loadHistory();
    </script>
</body>
</html>
'''

@app.get("/")
@app.get("/wallet")
async def root():
    return HTMLResponse(HTML_PAGE)

print("✅ Mini App сервер загружен")