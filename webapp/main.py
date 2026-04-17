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
def init_db():
    conn = sqlite3.connect('/data/students.db')
    cursor = conn.cursor()
    
    # Проверяем и добавляем колонки если нужно
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN wallet_verified INTEGER DEFAULT 0')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN wallet_address TEXT')
    except:
        pass
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS wallet_nonce (
            telegram_id INTEGER PRIMARY KEY,
            nonce TEXT,
            created_at TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

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

# --- API эндпоинты ---
@app.get("/api/profile/{telegram_id}")
async def get_profile(telegram_id: int):
    user = get_user(telegram_id)
    if not user:
        return {"fa_balance": 0, "first_name": "Гость", "wallet_verified": False}
    return user

@app.post("/api/get_nonce")
async def get_nonce(request: NonceRequest):
    nonce = secrets.token_hex(32)
    
    conn = sqlite3.connect('/data/students.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO wallet_nonce (telegram_id, nonce, created_at)
        VALUES (?, ?, ?)
    ''', (request.telegram_id, nonce, datetime.now().isoformat()))
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
    
    # Сохраняем кошелёк
    cursor.execute('''
        UPDATE users 
        SET wallet_address = ?, wallet_verified = 1 
        WHERE telegram_id = ?
    ''', (request.wallet_address, request.telegram_id))
    
    # Начисляем бонус
    cursor.execute('''
        UPDATE users 
        SET fa_balance = fa_balance + 100 
        WHERE telegram_id = ?
    ''', (request.telegram_id,))
    
    # Логируем
    cursor.execute('''
        INSERT INTO logs (telegram_id, action, details, created_at)
        VALUES (?, ?, ?, ?)
    ''', (request.telegram_id, "wallet_verified", request.wallet_address, datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    
    return {"success": True, "message": "Кошелёк успешно привязан! +100 FA"}

# --- HTML страница Mini App (полная версия) ---
HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FA Ecosystem | Личный кабинет</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            padding: 20px;
            background: var(--tg-theme-bg-color);
            color: var(--tg-theme-text-color);
            margin: 0;
        }
        .container {
            max-width: 400px;
            margin: 0 auto;
            text-align: center;
        }
        .balance-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 24px;
            padding: 24px;
            margin-bottom: 24px;
            color: white;
        }
        .balance-value {
            font-size: 48px;
            font-weight: bold;
        }
        .info-card {
            background: var(--tg-theme-secondary-bg-color);
            border-radius: 16px;
            padding: 16px;
            margin-bottom: 16px;
            text-align: left;
        }
        .info-row {
            display: flex;
            justify-content: space-between;
            padding: 12px 0;
            border-bottom: 1px solid rgba(128, 128, 128, 0.2);
        }
        .info-row:last-child {
            border-bottom: none;
        }
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
            margin-bottom: 10px;
        }
        .status {
            padding: 12px;
            margin: 15px 0;
            border-radius: 10px;
            font-size: 14px;
        }
        .success { background: #4CAF50; color: white; }
        .error { background: #f44336; color: white; }
        .info { background: #2196F3; color: white; }
        .hidden { display: none; }
    </style>
</head>
<body>
    <div class="container">
        <div class="balance-card">
            <div>💰 FA BALANCE</div>
            <div class="balance-value" id="balance">0</div>
        </div>
        
        <div class="info-card">
            <div class="info-row">
                <span>👤 Имя</span>
                <span id="first_name">-</span>
            </div>
            <div class="info-row">
                <span>🔗 Кошелёк</span>
                <span id="wallet_status">❌ Не привязан</span>
            </div>
        </div>
        
        <div id="status" class="status info">⚠️ Нажмите кнопку для подключения кошелька</div>
        
        <button id="connectBtn">🦊 Подключить MetaMask</button>
        <button id="refreshBtn" style="background: gray;">🔄 Обновить</button>
    </div>

    <script>
        const tg = window.Telegram.WebApp;
        tg.expand();
        
        const telegramId = tg.initDataUnsafe.user?.id;
        const firstName = tg.initDataUnsafe.user?.first_name;
        
        // Загрузка профиля
        async function loadProfile() {
            if (!telegramId) {
                document.getElementById('status').innerHTML = '❌ Не удалось получить ID пользователя';
                document.getElementById('status').className = 'status error';
                return;
            }
            
            try {
                const response = await fetch('/api/profile/' + telegramId);
                const data = await response.json();
                
                document.getElementById('balance').textContent = data.fa_balance || 0;
                document.getElementById('first_name').textContent = data.first_name || firstName;
                
                if (data.wallet_verified && data.wallet_address) {
                    const shortAddr = data.wallet_address.slice(0, 6) + '...' + data.wallet_address.slice(-4);
                    document.getElementById('wallet_status').innerHTML = `✅ ${shortAddr}`;
                    document.getElementById('connectBtn').style.display = 'none';
                    document.getElementById('status').innerHTML = '✅ Кошелёк привязан!';
                    document.getElementById('status').className = 'status success';
                } else {
                    document.getElementById('connectBtn').style.display = 'block';
                }
            } catch (error) {
                console.error('Ошибка загрузки профиля:', error);
                document.getElementById('status').innerHTML = '⚠️ Ошибка связи с сервером';
                document.getElementById('status').className = 'status error';
            }
        }
        
        // Подключение кошелька
        async function connectWallet() {
            const statusDiv = document.getElementById('status');
            
            if (typeof window.ethereum === 'undefined') {
                statusDiv.innerHTML = '❌ Установите MetaMask!';
                statusDiv.className = 'status error';
                return;
            }
            
            try {
                statusDiv.innerHTML = '🔄 Подключаемся к MetaMask...';
                statusDiv.className = 'status info';
                
                const accounts = await ethereum.request({ method: 'eth_requestAccounts' });
                const walletAddress = accounts[0];
                
                statusDiv.innerHTML = '🔄 Получаем nonce...';
                
                const nonceResponse = await fetch('/api/get_nonce', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ telegram_id: telegramId })
                });
                
                const nonceData = await nonceResponse.json();
                
                statusDiv.innerHTML = '🔄 Подпишите сообщение в MetaMask...';
                
                const signature = await ethereum.request({
                    method: 'personal_sign',
                    params: [nonceData.message, walletAddress]
                });
                
                statusDiv.innerHTML = '🔄 Отправляем подпись...';
                
                const verifyResponse = await fetch('/api/verify_wallet', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        telegram_id: telegramId,
                        wallet_address: walletAddress,
                        signature: signature
                    })
                });
                
                const result = await verifyResponse.json();
                
                if (result.success) {
                    statusDiv.innerHTML = '✅ ' + result.message;
                    statusDiv.className = 'status success';
                    tg.showAlert(result.message);
                    loadProfile();
                } else {
                    statusDiv.innerHTML = '❌ ' + (result.detail || 'Ошибка');
                    statusDiv.className = 'status error';
                }
                
            } catch (error) {
                console.error('Ошибка подключения:', error);
                statusDiv.innerHTML = '❌ Ошибка: ' + error.message;
                statusDiv.className = 'status error';
            }
        }
        
        // Обработчики
        document.getElementById('connectBtn').onclick = connectWallet;
        document.getElementById('refreshBtn').onclick = loadProfile;
        
        // Загружаем профиль при старте
        loadProfile();
    </script>
</body>
</html>
"""

@app.get("/")
@app.get("/wallet")
async def root():
    return HTMLResponse(HTML_PAGE)

if __name__ == "__main__":
    import uvicorn
    init_db()
    print("🚀 Mini App сервер запущен на http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)