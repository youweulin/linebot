# 🤖 LINE Bot — Google Sheets File Lookup with AI

> 功能完整複製自 [AI Auto Studio](https://aiauto.zeabur.app) 的 n8n 工作流範本，
> 但以 **Python + Docker** 實現，可讓 AI 直接維護程式碼、並在 Zeabur 上一鍵部署。

---

## 🛠️ 功能說明 (超越 LINE Premium)

1. **語義備份**：接收圖片/影片/檔案 → 自動備份至 Google Drive。若為圖片，將自動透過 GPT-4o Vision 閱讀圖片內容，總結成「標籤(Tags)」，並連同時間與網址寫回 Google Sheets 建立資料庫。
2. **AI 智能查檔**：使用者自然對話詢問檔案 → AI 判斷搜尋意圖 → 以「標籤 或 檔名」在 Sheets 中進行模糊比對 → 回傳正確下載連結。

### 工作流對應關係

| n8n 節點 | Python 模組 |
|---|---|
| Webhook | `POST /webhook` (FastAPI) |
| Edit Fields | `event.message.text` |
| AI Agent (OpenAI) | `extract_filename_with_ai()` |
| Google Sheets Lookup | `lookup_file_in_sheets()` |
| IF File Exists | `if file_url:` |
| HTTP Request (Reply) | `line_bot_api.reply_message()` |

---

## 📋 Google Sheets 格式

| 欄位 | A 欄 | B 欄 |
|---|---|---|
| Header | `Filename` | `File URL` |
| 範例 | `專案報告.pdf` | `https://drive.google.com/file/d/xxx` |

---

## 🔑 環境變數設定

複製 `.env.example` 並重新命名為 `.env`，填入您的真實金鑰：

```bash
cp .env.example .env
```

| 變數名稱 | 必填 | 說明 |
|---|---|---|
| `LINE_CHANNEL_ACCESS_TOKEN` | ✅ | LINE Developers Console 取得 |
| `LINE_CHANNEL_SECRET` | ✅ | LINE Developers Console 取得 |
| `OPENAI_API_KEY` | ✅ | OpenAI Platform 取得 |
| `OPENAI_MODEL` | ❌ | 預設 `gpt-4o-mini`（最省錢） |
| `GOOGLE_SHEET_ID` | ✅ | 試算表網址中的 ID 部分 |
| `GOOGLE_SHEET_NAME` | ❌ | 預設 `工作表1` |
| `GOOGLE_CREDENTIALS_JSON` | ✅ | Service Account JSON（整個 JSON 貼成字串） |
| `NOT_FOUND_MESSAGE` | ❌ | 查無檔案時的回覆文字 |

---

## 🚀 部署方法

### 方法 A：在 Zeabur 上一鍵部署（推薦）

1. Fork 此 Repo 到您自己的 GitHub 帳號。
2. 在 [Zeabur](https://zeabur.com) 建立新服務 → 選擇 **GitHub**，連接此 Repo。
3. 在 Zeabur 服務設定中，逐一填入所有**環境變數**（同上表）。
4. 部署完成後，在 **Networking** 頁面產生網域（Domain）。
5. 將 Webhook URL 填入 LINE Developers Console：`https://您的網域/webhook`

### 方法 B：本地開發

```bash
# 1. 安裝套件
pip install -r requirements.txt

# 2. 設定環境變數
cp .env.example .env
# 填入 .env 中的所有金鑰

# 3. 啟動服務
uvicorn main:app --reload --port 8080

# 4. 使用 ngrok 或 Cloudflare Tunnel 取得公開 URL
ngrok http 8080
```

---

## 📂 專案結構

```
linebot/
├── main.py              # 核心程式碼（Webhook + AI + Sheets 邏輯）
├── requirements.txt     # Python 套件清單
├── Dockerfile           # Docker 容器設定（供 Zeabur 部署）
├── .env.example         # 環境變數範本（不含真實金鑰）
├── .gitignore           # 排除 .env 等敏感檔案
└── README.md            # 本文件
```

---

## 🗺️ 未來功能規劃

- [x] 多輪對話記憶（SQLite）
- [x] 支援圖片訊息 → AI(GPT-4o) 自動識圖標籤化 → 自動存入 Google Drive
- [x] Langfuse 觀測儀表板整合（追蹤 AI 思考過程）
- [x] 基於語義標籤的模糊查詢系統
- [ ] 支援自定義 System Prompt（從 Google Sheets 讀取）
- [ ] 多語言支援（中英文自動偵測）

---

## 📚 教學資源

- [AI Auto Studio 完整教學](https://aiauto.zeabur.app)
- [n8n LINE Bot 工作流教學](https://aiauto.zeabur.app/tutorials/zeabur-n8n-deployment/)
- [LINE Developers 官方文件](https://developers.line.biz/en/docs/)
