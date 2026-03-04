"""
LINE Bot — Semantic Backup & Retrieval
=======================================
功能：
  1. [語義備份]   收到圖片/檔案 → 自動備份到 Google Drive。
                 如果是圖片，則呼叫 GPT-4o-vision 分析內容，給予標籤 (Tags) 與描述。
                 將「時間、檔名、標籤、Drive連結」自動寫入 Google Sheets 建立索引。
  2. [AI 智能查詢] 使用者文字查詢 → AI 判斷是在搜尋什麼 → 
                 在 Sheets (檔名, 標籤) 中模糊比對 → 回傳 Drive 連結。
  3. [多輪記憶]   記錄上下文。
  4. [Langfuse]   觀測 AI 行為。
"""

import base64
import io
import json
import logging
import os
import sqlite3
import tempfile
from contextlib import contextmanager
from datetime import datetime

import gspread
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.service_account import Credentials as SACredentials
from langfuse import Langfuse
from langfuse.openai import openai as langfuse_openai  
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    ImageMessage, VideoMessage, FileMessage,
)

# ══════════════════════════════════════════════════════════════════════════════
# 環境變數讀取
# ══════════════════════════════════════════════════════════════════════════════
load_dotenv()

LINE_CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
LINE_CHANNEL_SECRET = os.environ["LINE_CHANNEL_SECRET"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
GOOGLE_SHEET_ID = os.environ["GOOGLE_SHEET_ID"]
GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "工作表1")
GOOGLE_CREDENTIALS_JSON = os.environ["GOOGLE_CREDENTIALS_JSON"]
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
NOT_FOUND_MESSAGE = os.getenv("NOT_FOUND_MESSAGE", "找不到您要查詢的檔案，請嘗試其他關鍵字。")
MEMORY_WINDOW = int(os.getenv("MEMORY_WINDOW", "10"))
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

# ══════════════════════════════════════════════════════════════════════════════
# 服務初始化
# ══════════════════════════════════════════════════════════════════════════════
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="LINE Bot - Semantic Backup 🤖")
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

langfuse_enabled = bool(LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY)
if langfuse_enabled:
    langfuse_client = Langfuse(
        public_key=LANGFUSE_PUBLIC_KEY,
        secret_key=LANGFUSE_SECRET_KEY,
        host=LANGFUSE_HOST,
    )
    openai_client = langfuse_openai.AsyncOpenAI(api_key=OPENAI_API_KEY) if False else \
                    __import__("openai").OpenAI(api_key=OPENAI_API_KEY)
    logger.info("✅ Langfuse 觀測已啟動！")
else:
    openai_client = __import__("openai").OpenAI(api_key=OPENAI_API_KEY)
    logger.info("ℹ️ Langfuse 未啟動")

DB_PATH = os.getenv("MEMORY_DB_PATH", "/tmp/linebot_memory.db")
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   TEXT    NOT NULL,
                role      TEXT    NOT NULL,
                content   TEXT    NOT NULL,
                ts        TEXT    NOT NULL
            )
        """)
        conn.commit()
init_db()


def get_history(user_id: str) -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT role, content FROM memory WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, MEMORY_WINDOW),
        ).fetchall()
    return [{"role": r, "content": c} for r, c in reversed(rows)]


def save_message(user_id: str, role: str, content: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO memory (user_id, role, content, ts) VALUES (?, ?, ?, ?)",
            (user_id, role, content, datetime.utcnow().isoformat()),
        )
        conn.commit()

# ══════════════════════════════════════════════════════════════════════════════
# Google 服務整合 (Drive & Sheets)
# ══════════════════════════════════════════════════════════════════════════════
def get_google_credentials_dict() -> dict:
    """安全解析 GCP Service Account JSON，處理從環境變數讀取可能會造成的跳脫字元問題"""
    raw_json = GOOGLE_CREDENTIALS_JSON
    # 有些平台環境變數會擅自把換行符號跳脫，修正 `\n` 為真的換行
    if "\\n" in raw_json:
        raw_json = raw_json.replace("\\n", "\n")
    try:
        return json.loads(raw_json)
    except json.JSONDecodeError as e:
        logger.error("🛑 解析 GOOGLE_CREDENTIALS_JSON 失敗，請檢查 Zeabur 環境變數格式是否正確。長度=%d, 錯誤內容=%s", len(raw_json), e)
        raise e

def _get_google_credentials():
    scopes = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets"
    ]
    return SACredentials.from_service_account_info(get_google_credentials_dict(), scopes=scopes)


def get_google_sheet():
    gc = gspread.service_account_from_dict(get_google_credentials_dict())
    return gc.open_by_key(GOOGLE_SHEET_ID).worksheet(GOOGLE_SHEET_NAME)


def append_to_google_sheet(timestamp: str, filename: str, tags: str, file_url: str):
    """將備份紀錄寫入 Google Sheets (自動新增一列)"""
    try:
        sheet = get_google_sheet()
        # 假設 Sheets 的欄位：A=Timestamp, B=Filename, C=Tags, D=File URL
        sheet.append_row([timestamp, filename, tags, file_url])
        logger.info("✅ 成功將索引寫入 Google Sheets: %s", filename)
    except Exception as e:
        logger.error("寫入 Google Sheets 失敗: %s", e)


def backup_media_to_drive(
    message_id: str,
    mime_type: str,
    filename: str,
) -> tuple[str | None, bytes | None]:
    """
    從 LINE 下載媒體，上傳至 Drive。
    回傳 (Drive 連結, 原始 bytes)。
    """
    if not GOOGLE_DRIVE_FOLDER_ID:
        logger.warning("GOOGLE_DRIVE_FOLDER_ID 未設定，跳過備份")
        return None, None
    try:
        media_content = line_bot_api.get_message_content(message_id)
        raw_bytes = b"".join(media_content.iter_content())

        drive_service = build("drive", "v3", credentials=_get_google_credentials())
        file_metadata = {
            "name": filename,
            "parents": [GOOGLE_DRIVE_FOLDER_ID],
        }
        media = MediaIoBaseUpload(
            io.BytesIO(raw_bytes),
            mimetype=mime_type,
            resumable=True,
        )
        uploaded = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id,webViewLink",
        ).execute()

        drive_service.permissions().create(
            fileId=uploaded["id"],
            body={"type": "anyone", "role": "reader"},
        ).execute()

        link = uploaded.get("webViewLink", "")
        return link, raw_bytes
    except Exception as e:
        logger.error("Google Drive 備份失敗: %s", e)
        return None, None

# ══════════════════════════════════════════════════════════════════════════════
# AI 語義模組 (Vision 識圖 & 文字關鍵字萃取)
# ══════════════════════════════════════════════════════════════════════════════
def analyze_image_with_vision(image_bytes: bytes) -> str:
    """使用 GPT-4o Vision 分析圖片內容，產生語義標籤"""
    try:
        base64_image = base64.b64encode(image_bytes).decode("utf-8")
        response = openai_client.chat.completions.create(
            model="gpt-4o",  # 強制使用具備視覺能力的模型
            messages=[
                {
                    "role": "system",
                    "content": "你是一個歸檔助理。請用簡短的幾個關鍵字（用逗號分隔）描述這張圖片的主要內容。不要有其他廢話。"
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "請給這張圖片產生標籤 (tags)："},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}", "detail": "low"},
                        },
                    ],
                }
            ],
            max_tokens=50,
        )
        tags = response.choices[0].message.content.strip()
        logger.info("👁️ Vision 識圖結果: %s", tags)
        return tags
    except Exception as e:
        logger.error("Vision 識圖失敗: %s", e)
        return "自動備份圖片"


def extract_search_query_with_ai(user_message: str, history: list[dict]) -> str:
    """從使用者的提問中，萃取出「搜尋關鍵字」"""
    system_prompt = (
        "你是一個檔案查詢助理。用戶會跟你尋找之前存過的檔案（可能是照片、影片或文件）。\n"
        "請從用戶的話中，精煉出「最核心的搜尋關鍵字」。\n"
        "如果用戶只是在閒聊（例如：你好、早安、謝謝），請回覆「NOT_A_SEARCH」。\n\n"
        "範例 1：\n用戶：「幫我找上次那份 Q4 財報」\n你：「Q4, 財報」\n\n"
        "範例 2：\n用戶：「有沒有之前去日本玩的照片？」\n你：「日本, 照片」\n\n"
        "範例 3：\n用戶：「你好嗎？」\n你：「NOT_A_SEARCH」\n"
    )
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    response = openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=0,
        max_tokens=50,
    )
    return response.choices[0].message.content.strip()


def lookup_file_in_sheets_by_tags(search_query: str) -> str | None:
    """
    在 Google Sheets 中尋找符合關鍵字的檔案。
    假設欄位：A=Timestamp, B=Filename, C=Tags, D=File URL
    """
    try:
        sheet = get_google_sheet()
        records = sheet.get_all_records()
        
        # 關鍵字切分，變成小寫比對
        keywords = [k.strip().lower() for k in search_query.split(",")]
        
        # 尋找第一筆「Filename」或「Tags」涵蓋所有關鍵字的記錄
        for row in records:
            filename = str(row.get("Filename", "")).lower()
            tags = str(row.get("Tags", "")).lower()
            
            # 若任意關鍵字存在於 filename 或 tags 裡，我們當作符合
            match_count = 0
            for k in keywords:
                if k in filename or k in tags:
                    match_count += 1
            
            if match_count > 0:
                url = str(row.get("File URL", "")).strip()
                if url:
                    return url
        return None
    except Exception as e:
        logger.error("Google Sheets 查詢失敗: %s", e)
        return None

# ══════════════════════════════════════════════════════════════════════════════
# LINE Webhook 路由
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/")
async def health_check():
    return {"status": "ok", "message": "Semantic Backup Bot is running 🤖"}

@app.post("/webhook")
async def webhook(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    body_str = body.decode("utf-8")
    try:
        handler.handle(body_str, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    return JSONResponse(content={"status": "ok"})


import flex_messages

# ── 文字訊息：AI 查檔 + 一般對話 ─────────────────────────────────────────
@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event: MessageEvent):
    user_id = event.source.user_id
    user_message = event.message.text
    logger.info("[%s] 收到文字: %s", user_id, user_message)

    history = get_history(user_id)
    save_message(user_id, "user", user_message)

    search_query = extract_search_query_with_ai(user_message, history)
    logger.info("[%s] AI 判斷搜尋關鍵字: %s", user_id, search_query)

    if search_query == "NOT_A_SEARCH":
        # 如果不是搜尋，跳出美美的選單 Flex Message
        reply_message = flex_messages.get_welcome_flex()
        save_message(user_id, "assistant", "已傳送主選單卡片")
    else:
        file_url = lookup_file_in_sheets_by_tags(search_query)
        if file_url:
            reply_message = flex_messages.get_search_result_flex(search_query, file_url)
            save_message(user_id, "assistant", f"找到了！已傳送搜尋結果卡片: {file_url}")
        else:
            reply_message = TextSendMessage(text=NOT_FOUND_MESSAGE)
            save_message(user_id, "assistant", NOT_FOUND_MESSAGE)

    line_bot_api.reply_message(event.reply_token, reply_message)


# ── 圖片訊息：Vision 分析 + Drive 備份 + Sheets 索引 ────────────────────────
@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event: MessageEvent):
    user_id = event.source.user_id
    msg_id = event.message.id
    
    # 時間特徵
    now = datetime.now()
    ts_str = now.strftime("%Y%m%d_%H%M%S")
    timestamp_display = now.strftime("%Y/%m/%d %H:%M")
    
    filename = f"IMG_{ts_str}.jpg"
    
    # LINE Webhook 一次事件只能調用一次 reply_message
    # 如果要先回「處理中」，再回「結果」，第二則必須用 push_message
    # 為避免過於複雜，這裡我們讓用戶等一下，直接給最後一張精美收據
    link, raw_bytes = backup_media_to_drive(msg_id, "image/jpeg", filename)
    if not link:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="❌ 備份寫入失敗"))
        return

    # 呼叫 GPT-4o Vision 識圖
    tags = analyze_image_with_vision(raw_bytes) if raw_bytes else "無標籤"

    # 寫入 Google Sheets
    append_to_google_sheet(timestamp_display, filename, tags, link)

    # 傳送歸檔收據 (Flex)
    receipt_flex = flex_messages.get_backup_receipt_flex(filename, tags, timestamp_display, link)
    line_bot_api.reply_message(event.reply_token, receipt_flex)

    # 4. (非同步) 若需要可在這發第二段確認訊息，但因為 LINE Webhook 有限制，我們簡化處理。


# ── 影片/檔案：只能記檔名與時間，無 Vision 分析 ───────────────────────
@handler.add(MessageEvent, message=VideoMessage)
def handle_video_message(event: MessageEvent):
    user_id = event.source.user_id
    msg_id = event.message.id
    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    timestamp_display = datetime.now().strftime("%Y/%m/%d %H:%M")
    filename = f"VID_{ts_str}.mp4"

    link, _ = backup_media_to_drive(msg_id, "video/mp4", filename)
    if link:
        tags = "影片"
        append_to_google_sheet(timestamp_display, filename, tags, link)
        receipt_flex = flex_messages.get_backup_receipt_flex(filename, tags, timestamp_display, link)
        line_bot_api.reply_message(event.reply_token, receipt_flex)
    else:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="❌ 影片備份失敗"))


@handler.add(MessageEvent, message=FileMessage)
def handle_file_message(event: MessageEvent):
    user_id = event.source.user_id
    msg_id = event.message.id
    original_filename = event.message.file_name
    
    timestamp_display = datetime.now().strftime("%Y/%m/%d %H:%M")
    filename = f"FILE_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{original_filename}"

    link, _ = backup_media_to_drive(msg_id, "application/octet-stream", filename)
    if link:
        tags = f"檔案, {original_filename}"
        append_to_google_sheet(timestamp_display, filename, tags, link)
        receipt_flex = flex_messages.get_backup_receipt_flex(filename, tags, timestamp_display, link)
        line_bot_api.reply_message(event.reply_token, receipt_flex)
    else:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="❌ 檔案備份失敗"))
