from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import sqlite3
import secrets
from datetime import datetime

app = FastAPI()

# Модели для запросов
class NonceRequest(BaseModel):
    telegram_id: int

class VerifyRequest(BaseModel):
    telegram_id: int
    wallet_address: str
    signature: str

# Создаём таблицы если их нет
def init_db():
    conn = sqlite3.connect('students.db')
    cursor = conn.cursor()
    
    # Добавляем колонку wallet_verified если её нет
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN wallet_verified INTEGER DEFAULT 0')
    except:
        pass  # колонка уже существует
    
    # Таблица для nonce
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS wallet_nonce (
            telegram_id INTEGER PRIMARY KEY,
            nonce TEXT,
            created_at TEXT
        )
    ''')
    
    # Таблица для NFT бейджей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS nft_badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            badge_type TEXT,
            badge_name TEXT,
            issued_at TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

# Генерация nonce для подписи
@app.post("/get_nonce")
async def get_nonce(request: NonceRequest):
    nonce = secrets.token_hex(32)
    
    conn = sqlite3.connect('students.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO wallet_nonce (telegram_id, nonce, created_at)
        VALUES (?, ?, ?)
    ''', (request.telegram_id, nonce, datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    
    message = f"Подтверждаю привязку Telegram аккаунта к кошельку\n\nNonce: {nonce}"
    
    return {"nonce": nonce, "message": message}

# Верификация подписи
@app.post("/verify_wallet")
async def verify_wallet(request: VerifyRequest):
    conn = sqlite3.connect('students.db')
    cursor = conn.cursor()
    
    # Получаем nonce
    cursor.execute('SELECT nonce FROM wallet_nonce WHERE telegram_id = ?', (request.telegram_id,))
    result = cursor.fetchone()
    
    if not result:
        raise HTTPException(status_code=400, detail="Nonce не найден. Попробуйте снова.")
    
    # Сохраняем кошелёк в профиль пользователя
    cursor.execute('''
        UPDATE users 
        SET wallet_address = ?, wallet_verified = 1 
        WHERE telegram_id = ?
    ''', (request.wallet_address, request.telegram_id))
    
    # Добавляем бонус 100 FA
    cursor.execute('''
        UPDATE users 
        SET fa_balance = fa_balance + 100 
        WHERE telegram_id = ?
    ''', (request.telegram_id,))
    
    # Логируем действие
    cursor.execute('''
        INSERT INTO logs (telegram_id, action, details, created_at)
        VALUES (?, ?, ?, ?)
    ''', (request.telegram_id, "wallet_verified", request.wallet_address, datetime.now().isoformat()))
    
    # Добавляем NFT бейдж
    cursor.execute('''
        INSERT INTO nft_badges (telegram_id, badge_type, badge_name, issued_at)
        VALUES (?, ?, ?, ?)
    ''', (request.telegram_id, "wallet_verified", "🔗 Pioneer", datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    
    return {"success": True, "message": "Кошелёк успешно привязан! +100 FA и NFT бейдж"}

# Страница Mini App
@app.get("/wallet", response_class=HTMLResponse)
async def wallet_page():
    return HTML_CONTENT

# HTML для страницы привязки кошелька
HTML_CONTENT = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Привязка кошелька</title>
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
        h1 {
            font-size: 24px;
            margin-bottom: 20px;
        }
        button {
            width: 100%;
            padding: 14px;
            margin: 10px 0;
            background: var(--tg-theme-button-color);
            color: var(--tg-theme-button-text-color);
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
        }
        .status {
            padding: 12px;
            margin: 15px 0;
            border-radius: 10px;
            background: var(--tg-theme-secondary-bg-color);
            font-size: 14px;
        }
        .success {
            background: #4CAF50;
            color: white;
        }
        .error {
            background: #f44336;
            color: white;
        }
        .info {
            background: #2196F3;
            color: white;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔗 Привязка кошелька</h1>
        
        <div id="status" class="status info">
            ⚠️ Нажмите кнопку для подключения кошелька
        </div>
        
        <button id="connectBtn">🦊 Подключить MetaMask</button>
    </div>

    <script>
        let tg = window.Telegram.WebApp;
        tg.expand();
        
        const telegramId = tg.initDataUnsafe.user?.id;
        
        if (!telegramId) {
            document.getElementById('status').className = 'status error';
            document.getElementById('status').innerHTML = '❌ Ошибка: не удалось получить ID пользователя';
        }
        
        document.getElementById('connectBtn').onclick = async () => {
            const statusDiv = document.getElementById('status');
            
            if (typeof window.ethereum === 'undefined') {
                statusDiv.className = 'status error';
                statusDiv.innerHTML = '❌ MetaMask не установлен!<br>Установите расширение MetaMask';
                return;
            }
            
            try {
                statusDiv.className = 'status info';
                statusDiv.innerHTML = '🔄 Подключаемся к MetaMask...';
                
                const accounts = await ethereum.request({ method: 'eth_requestAccounts' });
                const walletAddress = accounts[0];
                
                statusDiv.innerHTML = '🔄 Получаем nonce для подписи...';
                
                const nonceResponse = await fetch('/get_nonce', {
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
                
                statusDiv.innerHTML = '🔄 Отправляем подпись на сервер...';
                
                const verifyResponse = await fetch('/verify_wallet', {
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
                    statusDiv.className = 'status success';
                    statusDiv.innerHTML = '✅ ' + result.message + '<br>🎉 Закройте это окно и напишите /profile в боте!';
                    tg.showAlert(result.message);
                } else {
                    statusDiv.className = 'status error';
                    statusDiv.innerHTML = '❌ Ошибка: ' + (result.detail || 'Неизвестная ошибка');
                }
                
            } catch (error) {
                statusDiv.className = 'status error';
                statusDiv.innerHTML = '❌ Ошибка: ' + error.message;
            }
        };
    </script>
</body>
</html>
"""

# Запуск сервера
if __name__ == "__main__":
    import uvicorn
    init_db()
    print("🚀 FastAPI сервер запущен на http://localhost:8000")
    print("📱 Mini App доступен по адресу: http://localhost:8000/wallet")
    uvicorn.run(app, host="0.0.0.0", port=8000)