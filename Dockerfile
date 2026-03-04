# ── Python Base Image ─────────────────────────────────────────────────────
FROM python:3.11-slim

# 設定工作目錄
WORKDIR /app

# 安裝套件（先優先 copy requirements 以善用 Docker cache layer）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製所有程式碼
COPY . .

# 開放 Port（Zeabur 預設偵測環境變數 PORT，fallback 為 8080）
EXPOSE 8080

# ── 啟動指令 ─────────────────────────────────────────────────────────────
# uvicorn 會讀取 $PORT 環境變數，如果沒有就 fallback 8080
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
