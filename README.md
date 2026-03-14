# 🤖 LINE Bot — Google Sheets File Lookup with AI

> 功能完整複製自 [AI Auto Studio](https://aiauto.zeabur.app) 的 n8n 工作流範本，
> 但以 **Python + Docker** 實現，可讓 AI 直接維護程式碼、並在 Zeabur 上一鍵部署。

---

## 🛠️ 功能說明 (超越 LINE Premium)

1. **語義備份**：接收圖片/影片/檔案 → 自動備份至 Google Drive。若為圖片，將自動透過 GPT-4o Vision 閱讀圖片內容，總結成「標籤(Tags)」，並連同時間與網址寫回 Google Sheets 建立資料庫。
2. **AI 智能查檔**：使用者自然對話詢問檔案 → AI 判斷搜尋意圖 → 以「標籤 或 檔名」在 Sheets 中進行模糊比對 → 回傳正確下載連結。
3. **個人助理 Skills**：待辦、行程、筆記、記帳/出金、通訊錄(含名片掃描)、交易日記。
4. **Threads 工具**：貼文發布、帳號洞察、關鍵字搜尋（需要 Threads API 權限與 token）。
5. **每人設定**：可為每個 `user_id` 設定時區（影響「今天」與時間戳）。

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
| `GOOGLE_DRIVE_FOLDER_ID` | ❌ | Drive 備份目標資料夾 ID（不填則跳過 Drive 備份） |
| `GOOGLE_DRIVE_OAUTH_JSON` | ❌ | Drive OAuth token（有些 Drive 權限/共享設定可用，未填則 fallback 用 SA） |
| `THREADS_ACCESS_TOKEN` | ❌ | Threads API token（發文/洞察/搜尋會用到） |
| `THREADS_USER_ID` | ❌ | Threads user id（抓洞察/貼文表現會用到） |
| `NOT_FOUND_MESSAGE` | ❌ | 查無檔案時的回覆文字 |

---

## 🧭 使用方式（使用者端）

### 1) 備份檔案/圖片/影片（取代掃描器/檔案整理）
- 直接把 **照片 / 影片 / 檔案（含 PDF）**傳給 LINE Bot
- Bot 會：
  - 上傳到 Google Drive（檔案預設「任何人有連結可檢視」）
  - 寫入 Sheets 索引（含時間、檔名、標籤、URL）
  - 圖片會額外用 AI 產生標籤；若偵測到名片會自動寫入通訊錄

範例：
- 傳一張收據照片（目前會：備份 + 標籤；收據 OCR/自動入帳屬下一階段）
- 傳一張名片照片（會：自動存到 `📇 通訊錄`）

### 2) 找檔案（Top-N 結果）
- 直接用聊天描述你要找的東西，Bot 會回傳 1~多筆結果連結

範例：
- 「幫我找上次那張發票」
- 「找一下日本旅行的照片」
- 「找：護照、簽證」

### 3) 筆記（取代筆記 App 快記）
範例：
- 「記一下：下週要跟設計師確認 Logo 版本」
- 「幫我存筆記：n8n webhook 端點是 …」

### 4) 待辦/提醒（取代 To-do App 基本功能）
範例：
- 「幫我建待辦：週五前交報告」
- 「提醒我明天要去繳費」

### 5) 行程/排程（取代日曆快記）
範例：
- 「下週三下午兩點要開會」
- 「明天 19:30 跟客戶吃飯，地點信義」

### 6) 記帳/出金（取代記帳 App 快速記一筆）
範例（支出）：
- 「午餐花了150」
- 「打 propfirm 花了 200」

範例（收入/出金）：
- 「收到 propfirm 出金 3000」
- 「這個月薪水 50000」

### 7) 交易日記
範例：
- 「幫我記交易日記：心情有點急躁，優點是有停損，缺點是亂建倉」

### 8) 通訊錄/名片
範例（文字存聯絡人）：
- 「記下王大明的電話 0912345678」
- 「存一下李經理的信箱 lee@abc.com」

範例（名片掃描）：
- 直接傳名片照片

### 9) Threads
範例（洞察/成效）：
- 「分析今天的 Threads」
- 或用快捷：`#threads`

範例（關鍵字搜尋：找 propfirm 免費帳號貼文與來源帳號）：
- 「搜尋今天 Threads 有沒有送 propfirm 免費帳號的貼文跟頻道」
- 若你設定了時區，Bot 會用你的時區來判斷「今天」

範例（生成社群延伸評論草稿 → 發布）：
- 先貼上別人的貼文內容並說：「幫我寫一段高價值延伸評論」
- 你確認草稿後回：「發布threads」

---

## ⌨️ 快捷指令（`#` 開頭）
- `#記帳`：顯示近期記帳/出金統計
- `#待辦`：顯示近期待辦
- `#行程`：顯示近期行程
- `#通訊錄`：顯示近期聯絡人
- `#筆記`：顯示近期筆記
- `#交易`：顯示近期交易日記
- `#threads`：抓取 Threads 洞察
- `#myid`：回傳你的 `user_id`

---

## ⚙️ 個人設定
### 設定時區（每個 user_id）
範例：
- 「把我的時區改成 America/Los_Angeles」
- 「設定時區 Asia/Taipei」

---

## 📊 Google Sheets 分頁（會自動建立）
- `工作表1`（或 `GOOGLE_SHEET_NAME`）：備份索引（時間/檔名/標籤/URL）
- `📥 Inbox 索引`：更完整的媒體索引（含 user_id/message_id）
- `📝 筆記本`、`✅ 待辦清單`、`📅 行事曆`、`💰 記帳本`、`📈 交易日記`、`🎯 夢想與目標`、`📇 通訊錄`
- Threads：`📊 Threads 日報`、`📝 Threads 貼文表現`
- 設定：`⚙️ 設定`

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
