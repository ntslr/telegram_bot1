from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Test</title>
</head>
<body>
    <h1>✅ Mini App работает!</h1>
    <p>Если вы видите эту страницу, сервер запущен правильно.</p>
</body>
</html>
"""

@app.get("/")
@app.get("/wallet")
async def root():
    return HTMLResponse(HTML)

print("✅ Сервер загружен")