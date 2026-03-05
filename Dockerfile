# ── Python + Node.js Base Image ──────────────────────────────────────────────
FROM python:3.11-slim

# 安裝 Node.js 18 + gws CLI
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g @googleworkspace/cli && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 設定工作目錄
WORKDIR /app

# 安裝套件（先優先 copy requirements 以善用 Docker cache layer）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製所有程式碼
COPY .  .

# 開放 Port（Zeabur 預設偵測環境變數 PORT，fallback 為 8080）
EXPOSE 8080

# ── 啟動指令 ─────────────────────────────────────────────────────────────
# 1. 將 GOOGLE_CREDENTIALS_JSON 環境變數寫入檔案供 gws CLI 使用
# 2. 啟動 uvicorn
CMD ["sh", "-c", "echo \"$GOOGLE_CREDENTIALS_JSON\" > /tmp/sa-key.json && export GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE=/tmp/sa-key.json && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
