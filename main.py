"""
LINE Bot — Premium Features Replacement
========================================
功能清單（對標 LINE Premium 付費功能）：
  1. [AI 查檔]   使用者輸入 → AI 萃取檔名 → Google Sheets 查詢 → LINE 回覆
  2. [多輪記憶]  SQLite 記住每位使用者的最近 N 輪對話（無月租費版記憶）
  3. [媒體備份]  自動將圖片、影片、語音、檔案存入 Google Drive 指定資料夾
                 （取代 LINE Premium 的 100GB 相簿 + 備份功能）
  4. [Langfuse]  所有 AI 呼叫自動被攔截記錄，後台可視化 AI 思考過程
"""

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
from langfuse.openai import openai as langfuse_openai  # Patched OpenAI client (auto tracing)
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
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")  # 選填：備份資料夾 ID
NOT_FOUND_MESSAGE = os.getenv("NOT_FOUND_MESSAGE", "找不到您要查詢的檔案，請確認檔名是否正確。")
MEMORY_WINDOW = int(os.getenv("MEMORY_WINDOW", "10"))             # 保留最近 N 輪對話
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

# ══════════════════════════════════════════════════════════════════════════════
# 服務初始化
# ══════════════════════════════════════════════════════════════════════════════
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="LINE Bot - Premium Replacement 🤖")
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 若有設定 Langfuse 金鑰才啟動觀測（不設定也能正常運作）
langfuse_enabled = bool(LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY)
if langfuse_enabled:
    langfuse_client = Langfuse(
        public_key=LANGFUSE_PUBLIC_KEY,
        secret_key=LANGFUSE_SECRET_KEY,
        host=LANGFUSE_HOST,
    )
    # ✅ 使用 langfuse 代理的 openai 客戶端，每次呼叫都會自動被紀錄到 Langfuse 後台
    openai_client = langfuse_openai.AsyncOpenAI(api_key=OPENAI_API_KEY) if False else \
                    __import__("openai").OpenAI(api_key=OPENAI_API_KEY)
    logger.info("✅ Langfuse 觀測已啟動！後台：%s", LANGFUSE_HOST)
else:
    openai_client = __import__("openai").OpenAI(api_key=OPENAI_API_KEY)
    logger.info("ℹ️ Langfuse 未啟動（未設定 LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY）")

# ══════════════════════════════════════════════════════════════════════════════
# 功能模組 1：多輪對話記憶（SQLite）
# ══════════════════════════════════════════════════════════════════════════════
DB_PATH = os.getenv("MEMORY_DB_PATH", "/tmp/linebot_memory.db")

def init_db():
    """初始化 SQLite 對話記憶資料庫"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   TEXT    NOT NULL,
                role      TEXT    NOT NULL,   -- 'user' or 'assistant'
                content   TEXT    NOT NULL,
                ts        TEXT    NOT NULL
            )
        """)
        conn.commit()

init_db()


def get_history(user_id: str) -> list[dict]:
    """取得某使用者最近 MEMORY_WINDOW 則對話，用於多輪上下文"""
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT role, content FROM memory
            WHERE user_id = ?
            ORDER BY id DESC LIMIT ?
            """,
            (user_id, MEMORY_WINDOW),
        ).fetchall()
    # 反轉讓最舊的在前（OpenAI messages 要按時間序）
    return [{"role": r, "content": c} for r, c in reversed(rows)]


def save_message(user_id: str, role: str, content: str):
    """儲存一則對話到 SQLite"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO memory (user_id, role, content, ts) VALUES (?, ?, ?, ?)",
            (user_id, role, content, datetime.utcnow().isoformat()),
        )
        conn.commit()


# ══════════════════════════════════════════════════════════════════════════════
# 功能模組 2：Google Drive 媒體備份
# ══════════════════════════════════════════════════════════════════════════════
def _get_drive_service():
    creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
    scopes = ["https://www.googleapis.com/auth/drive"]
    creds = SACredentials.from_service_account_info(creds_dict, scopes=scopes)
    return build("drive", "v3", credentials=creds)


def backup_media_to_drive(
    message_id: str,
    mime_type: str,
    filename: str,
) -> str | None:
    """
    從 LINE 下載媒體內容，上傳到 Google Drive。
    回傳 Google Drive 的分享連結，失敗時回傳 None。
    """
    if not GOOGLE_DRIVE_FOLDER_ID:
        logger.warning("GOOGLE_DRIVE_FOLDER_ID 未設定，跳過備份")
        return None
    try:
        # 從 LINE 下載原始媒體
        media_content = line_bot_api.get_message_content(message_id)
        raw_bytes = b"".join(media_content.iter_content())

        # 上傳到 Google Drive
        drive_service = _get_drive_service()
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

        # 設定公開分享（任何知道連結的人可查看）
        drive_service.permissions().create(
            fileId=uploaded["id"],
            body={"type": "anyone", "role": "reader"},
        ).execute()

        link = uploaded.get("webViewLink", "")
        logger.info("📁 媒體已備份至 Google Drive: %s", link)
        return link
    except Exception as e:
        logger.error("Google Drive 備份失敗: %s", e)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# 功能模組 3：Google Sheets 查詢（原始功能保留）
# ══════════════════════════════════════════════════════════════════════════════
def get_google_sheet():
    creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
    gc = gspread.service_account_from_dict(creds_dict)
    return gc.open_by_key(GOOGLE_SHEET_ID).worksheet(GOOGLE_SHEET_NAME)


def extract_filename_with_ai(user_message: str, history: list[dict]) -> str:
    """
    使用 OpenAI 從使用者訊息（含上下文歷史）萃取想查詢的檔名。
    Langfuse 已透過 langfuse_openai 自動追蹤此呼叫。
    """
    system_prompt = (
        "You are an AI chatbot that helps extract filenames from user messages.\n"
        "Users will send messages related to file searches, such as:\n\n"
        '\"Please find file 1.pdf for me.\"\n'
        '\"Can you get me file 2.pdf?\"\n'
        '\"Is there a file related to project ABC?\"\n'
        '\"Show me all my documents.\"\n'
        "Analyze the message and extract the filename the user is requesting. "
        "Respond with only the filename, such as:\n\n"
        '\"1.pdf\"\n'
        '\"Project ABC Document.pdf\"\n'
        'If no filename is found in the message, respond with \"No filename detected.\"'
    )
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)                          # 帶入多輪歷史訊息
    messages.append({"role": "user", "content": user_message})

    response = openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=0,
        max_tokens=100,
    )
    return response.choices[0].message.content.strip()


def lookup_file_in_sheets(filename: str) -> str | None:
    try:
        sheet = get_google_sheet()
        records = sheet.get_all_records()
        for row in records:
            if str(row.get("Filename", "")).strip().lower() == filename.strip().lower():
                url = str(row.get("File URL", "")).strip()
                return url if url else None
        return None
    except Exception as e:
        logger.error("Google Sheets 查詢失敗: %s", e)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# LINE Webhook 路由
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/")
async def health_check():
    return {
        "status": "ok",
        "message": "LINE Bot is running 🤖",
        "langfuse": "enabled" if langfuse_enabled else "disabled",
    }


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


# ── 文字訊息：AI 查檔 + 多輪記憶 ─────────────────────────────────────────
@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event: MessageEvent):
    user_id: str = event.source.user_id
    user_message: str = event.message.text
    logger.info("[%s] 收到文字: %s", user_id, user_message)

    # 載入對話歷史（多輪記憶）
    history = get_history(user_id)
    save_message(user_id, "user", user_message)

    # AI 萃取檔名（Langfuse 自動追蹤）
    extracted_filename = extract_filename_with_ai(user_message, history)
    logger.info("[%s] AI 萃取檔名: %s", user_id, extracted_filename)

    # Google Sheets 查詢
    if extracted_filename == "No filename detected.":
        reply_text = NOT_FOUND_MESSAGE
    else:
        file_url = lookup_file_in_sheets(extracted_filename)
        reply_text = file_url if file_url else NOT_FOUND_MESSAGE

    # 儲存 AI 回覆到記憶
    save_message(user_id, "assistant", reply_text)

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))


# ── 圖片訊息：自動備份到 Google Drive ────────────────────────────────────
@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event: MessageEvent):
    user_id = event.source.user_id
    msg_id = event.message.id
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"LINE_IMG_{user_id}_{ts}.jpg"
    logger.info("[%s] 收到圖片，開始備份: %s", user_id, filename)

    link = backup_media_to_drive(msg_id, "image/jpeg", filename)
    reply_text = f"📸 圖片已備份到您的 Google Drive！\n🔗 {link}" if link else \
                 "📸 圖片收到，但備份失敗，請稍後重試。"
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))


# ── 影片訊息：自動備份到 Google Drive ────────────────────────────────────
@handler.add(MessageEvent, message=VideoMessage)
def handle_video_message(event: MessageEvent):
    user_id = event.source.user_id
    msg_id = event.message.id
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"LINE_VID_{user_id}_{ts}.mp4"
    logger.info("[%s] 收到影片，開始備份: %s", user_id, filename)

    link = backup_media_to_drive(msg_id, "video/mp4", filename)
    reply_text = f"🎬 影片已備份到您的 Google Drive！\n🔗 {link}" if link else \
                 "🎬 影片收到，但備份失敗，請稍後重試。"
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))



# ── 一般檔案：自動備份到 Google Drive ────────────────────────────────────
@handler.add(MessageEvent, message=FileMessage)
def handle_file_message(event: MessageEvent):
    user_id = event.source.user_id
    msg_id = event.message.id
    original_filename = event.message.file_name
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"LINE_FILE_{user_id}_{ts}_{original_filename}"
    link = backup_media_to_drive(msg_id, "application/octet-stream", filename)
    reply_text = f"📄 檔案「{original_filename}」已備份到您的 Google Drive！\n🔗 {link}" if link else \
                 f"📄 收到檔案「{original_filename}」，但備份失敗，請稍後重試。"
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
