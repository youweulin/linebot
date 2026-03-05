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
OPENAI_VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-4o")
GOOGLE_SHEET_ID = os.environ["GOOGLE_SHEET_ID"]
GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "工作表1")
GOOGLE_CREDENTIALS_JSON = os.environ["GOOGLE_CREDENTIALS_JSON"]
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
GOOGLE_DRIVE_OAUTH_JSON = os.getenv("GOOGLE_DRIVE_OAUTH_JSON", "")
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
def _parse_json_credentials(raw_json: str, label: str = "JSON") -> dict:
    """安全解析 JSON 金鑰，處理 Zeabur 環境變數的各種奇怪跳脫問題"""
    raw_json = raw_json.strip().strip("'").strip('"')
    raw_json = raw_json.replace('\n', '\\n')
    raw_json = raw_json.replace('\r', '')
    if '\\"' in raw_json:
        raw_json = raw_json.replace('\\"', '"')
    try:
        return json.loads(raw_json, strict=False)
    except json.JSONDecodeError as e:
        logger.error("🛑 解析 %s 失敗。長度=%d, 錯誤=%s", label, len(raw_json), e)
        raise e

def get_google_credentials_dict() -> dict:
    """取得 Service Account 金鑰 (主要用於 Google Sheets)"""
    if not GOOGLE_CREDENTIALS_JSON:
        raise ValueError("GOOGLE_CREDENTIALS_JSON 未設定")
    return _parse_json_credentials(GOOGLE_CREDENTIALS_JSON, "GOOGLE_CREDENTIALS_JSON")

def _get_drive_credentials():
    """取得 Google Drive 專用認證。優先使用 OAuth2 Token (用所長的個人儲存空間)，否則 fallback 到 SA。"""
    if GOOGLE_DRIVE_OAUTH_JSON:
        try:
            creds_dict = _parse_json_credentials(GOOGLE_DRIVE_OAUTH_JSON, "GOOGLE_DRIVE_OAUTH_JSON")
            from google.oauth2.credentials import Credentials
            logger.info("📁 Drive 使用 OAuth2 個人帳號認證")
            return Credentials.from_authorized_user_info(creds_dict)
        except Exception as e:
            logger.warning("⚠️ GOOGLE_DRIVE_OAUTH_JSON 解析失敗，回退 Service Account: %s", e)
    
    # Fallback: 使用 Service Account
    creds_dict = get_google_credentials_dict()
    scopes = ["https://www.googleapis.com/auth/drive"]
    logger.info("📁 Drive 使用 Service Account 認證")
    return SACredentials.from_service_account_info(creds_dict, scopes=scopes)

def _get_sheets_credentials():
    """取得 Google Sheets 專用認證 (永遠使用 Service Account)"""
    creds_dict = get_google_credentials_dict()
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    return SACredentials.from_service_account_info(creds_dict, scopes=scopes)


def get_google_sheet():
    """使用 Service Account 認證來存取 Google Sheets (檔案索引分頁)"""
    gc = gspread.service_account_from_dict(get_google_credentials_dict())
    spreadsheet = gc.open_by_key(GOOGLE_SHEET_ID)
    try:
        return spreadsheet.worksheet(GOOGLE_SHEET_NAME)
    except Exception:
        logger.warning("⚠️ 找不到名為 '%s' 的分頁，改用第一個分頁", GOOGLE_SHEET_NAME)
        return spreadsheet.sheet1


def get_or_create_sheet_tab(tab_name: str, headers: list[str]):
    """
    取得或自動建立指定名稱的 Sheets 分頁。
    如果分頁不存在，會自動建立並寫入標題列 (headers)。
    這是所有功能分頁的通用方法。
    """
    gc = gspread.service_account_from_dict(get_google_credentials_dict())
    spreadsheet = gc.open_by_key(GOOGLE_SHEET_ID)

    try:
        sheet = spreadsheet.worksheet(tab_name)
    except gspread.exceptions.WorksheetNotFound:
        logger.info("🆕 建立新分頁: %s", tab_name)
        sheet = spreadsheet.add_worksheet(title=tab_name, rows=1000, cols=20)
        sheet.append_row(headers)

    return sheet

def get_recent_records_from_sheet(tab_name: str, headers: list[str] = [], limit: int = 5) -> list[dict]:
    """從指定分頁取得最新 N 筆資料（反排序）並封裝成字典的 List。如果分頁不存在，會自動建立空分頁然後回傳空 List。"""
    try:
        sheet = get_or_create_sheet_tab(tab_name, headers)
        values = sheet.get_all_values()
        if not values or len(values) < 2:
            return []
            
        sheet_headers = values[0]
        records = []
        for row in values[1:]:
            # 將資料列補齊長度，如果不足的地方用空字串填補
            row_data = row + [""] * (len(sheet_headers) - len(row))
            records.append(dict(zip(sheet_headers, row_data)))
            
        # 反序排列，最新的在前面
        records.reverse()
        return records[:limit]
    except Exception as e:
        logger.error("讀取分頁 %s 失敗: %s", tab_name, e)
        return []


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

        drive_service = build("drive", "v3", credentials=_get_drive_credentials())
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
            model=OPENAI_VISION_MODEL,  # 強制使用具備視覺能力的模型
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


def process_user_message_with_tools(user_message: str, history: list[dict]) -> dict:
    """
    Agent Router 核心：使用 OpenAI Function Calling + Skills Registry 決定要執行什麼動作。
    回傳: {"action": "chat"|skill_name, "args": {...}, "reply": "..."}
    """
    from skills import get_all_tools

    system_prompt = (
        "你是一個萬能的雲端助理。使用者可能會：\n"
        "1. 請你幫忙尋找以前存過的檔案。\n"
        "2. 請你幫忙記下筆記或備忘錄。\n"
        "3. 請你幫忙記帳（花費、消費、支出）。\n"
        "4. 請你儲存聯絡人資訊或電話號碼。\n"
        "5. 請你幫忙排程、記錄未來的行程或會議。\n"
        "6. 請你幫忙建立待辦事項、任務清單或提醒。\n"
        "如果有對應的工具 (tools)，請務必呼叫該工具來完成任務。\n"
        "如果使用者只是單純閒聊（例如：你好、早安、謝謝），請不要呼叫任何工具，直接友善地回覆一小段話即可。"
    )

    tools = get_all_tools()

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    try:
        response = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            tools=tools if tools else None,
            tool_choice="auto" if tools else None,
            temperature=0,
            max_tokens=200,
        )

        reply_msg = response.choices[0].message

        if reply_msg.tool_calls:
            tool_call = reply_msg.tool_calls[0]
            function_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            return {"action": function_name, "args": args}

        return {"action": "chat", "reply": reply_msg.content or "您好！請問需要什麼找檔案或幫忙記下來的嗎？"}

    except Exception as e:
        logger.error("Function Calling 分析失敗: %s", e)
        return {"action": "chat", "reply": "抱歉，我現在大腦卡卡的，請稍後再試。"}


def lookup_file_in_sheets_by_tags(search_query: str) -> str | None:
    """
    在 Google Sheets 中尋找符合關鍵字的檔案。
    欄位彈性比對：會對整列的所有文字欄位做搜尋。
    """
    try:
        sheet = get_google_sheet()
        records = sheet.get_all_records()

        if records:
            logger.info("🔍 Sheets 欄位名稱 (除錯用): %s", list(records[0].keys()))
        else:
            logger.warning("⚠️ Google Sheets 是空的，沒有任何記錄！")
            return None

        keywords = [k.strip().lower() for k in search_query.split(",")]

        for row in records:
            all_values_str = " ".join(str(v) for v in row.values()).lower()
            match_count = sum(1 for k in keywords if k and k in all_values_str)

            if match_count > 0:
                url = str(row.get("File URL", row.get("file url", row.get("URL", "")))).strip()
                if not url:
                    for v in row.values():
                        sv = str(v).strip()
                        if sv.startswith("http"):
                            url = sv
                            break
                if url:
                    return url

        logger.info("🔍 搜尋 '%s' 後，在 %d 筆記錄中找不到符合項目。", search_query, len(records))
        return None
    except Exception as e:
        logger.error("Google Sheets 查詢失敗: %s", e)
        return None

def save_note_to_sheets(content: str) -> str:
    """將文字筆記直接寫入 Google Sheets"""
    timestamp_display = datetime.now().strftime("%Y/%m/%d %H:%M")
    append_to_google_sheet(timestamp_display, "📝 文字筆記", content, "筆記內文")
    return timestamp_display

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
from skills import run_skill

def format_records_as_text(cmd: str, records: list[dict], base_url: str) -> TextSendMessage:
    if not records:
        return TextSendMessage(text=f"目前沒有 {cmd} 紀錄喔！")
    
    lines = [f"🔍 最近的 {cmd} 紀錄：\n"]
    for r in records:
        if cmd == "記帳":
            lines.append(f"💰 {r.get('項目', '未知')} : ${r.get('金額', '0')} ({str(r.get('紀錄時間', ''))[:10]})")
        elif cmd == "待辦":
            status = str(r.get("狀態(未完成/已完成)", "未完成"))
            mark = "✅" if "已完成" in status else "❌"
            lines.append(f"{mark} {r.get('待辦事項', '')} (期限: {r.get('預計完成日', '無')})")
        elif cmd in ["排程", "行程", "行事曆"]:
            lines.append(f"📅 {r.get('事件名稱', '')} : {r.get('事件日期', '')} {r.get('事件時間', '')}")
        elif cmd in ["名片", "通訊錄", "聯絡人"]:
            lines.append(f"📇 {r.get('姓名', '未知')} - {r.get('公司', '')} {r.get('職稱', '')}")
            if r.get("電話"):
                lines.append(f"   📞 {r.get('電話')}")
            if r.get("Email"):
                lines.append(f"   📩 {r.get('Email')}")
        elif cmd in ["筆記", "備忘錄"]:
            content = str(r.get("筆記內容", ""))
            short_content = (content[:30] + "...") if len(content) > 30 else content
            lines.append(f"📝 {short_content} ({str(r.get('紀錄時間', ''))[:10]})")
            
    lines.append(f"\n🔗 開啟完整試算表：\n{base_url}")
    return TextSendMessage(text="\n".join(lines))

# ── 文字訊息：Skills 智能路由 ─────────────────────────────────────────────
@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event: MessageEvent):
    user_id = event.source.user_id
    user_message = event.message.text.strip()
    logger.info("[%s] 收到文字: %s", user_id, user_message)

    # 👉 攔截捷徑指令 (為了 Rich Menu 準備)
    if user_message.startswith("#"):
        cmd = user_message[1:].strip()
        reply_message = None
        base_url = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/edit"
        records = None
        
        if cmd == "記帳":
            records = get_recent_records_from_sheet("💰 記帳本", limit=5)
        elif cmd == "待辦":
            records = get_recent_records_from_sheet("✅ 待辦清單", limit=5)
        elif cmd in ["排程", "行程", "行事曆"]:
            records = get_recent_records_from_sheet("📅 行事曆", limit=5)
        elif cmd in ["名片", "通訊錄", "聯絡人"]:
            records = get_recent_records_from_sheet("📇 通訊錄", limit=5)
        elif cmd in ["筆記", "備忘錄"]:
            records = get_recent_records_from_sheet("📝 筆記本", limit=5)
            
        if records is not None:
            reply_message = format_records_as_text(cmd, records, base_url)
            
        if reply_message:
            try:
                # 送出前記錄 JSON 方便 debug
                import json as _json
                logger.info("📤 即將送出 Flex: %s", _json.dumps(reply_message.contents, ensure_ascii=False, default=str)[:2000])
                line_bot_api.reply_message(event.reply_token, reply_message)
            except Exception as e:
                logger.error("🛑 快捷指令回覆失敗: %s", e)
                # reply_token 已被消耗，不能再 reply，只記 log
            return

    history = get_history(user_id)
    save_message(user_id, "user", user_message)

    # 核心大腦：Function Calling + Skills Registry
    decision = process_user_message_with_tools(user_message, history)
    action = decision.get("action")
    logger.info("[%s] AI 決策動作: %s", user_id, decision)

    if action == "chat":
        reply_message = flex_messages.get_welcome_flex()
        save_message(user_id, "assistant", decision.get("reply", ""))

    else:
        # 動態執行 skill
        context = {
            "lookup_file_in_sheets_by_tags": lookup_file_in_sheets_by_tags,
            "save_note_to_sheets": save_note_to_sheets,
            "get_or_create_sheet_tab": get_or_create_sheet_tab,
        }
        result = run_skill(action, decision.get("args", {}), context)
        logger.info("[%s] Skill '%s' 回傳: %s", user_id, action, result)

        # 根據 skill 回傳結果產生對應的 Flex Message
        if action == "search_file":
            if result.get("found"):
                reply_message = flex_messages.get_search_result_flex(result["keywords"], result["url"])
                save_message(user_id, "assistant", f"找到了！{result['url']}")
            else:
                reply_message = TextSendMessage(text=NOT_FOUND_MESSAGE)
                save_message(user_id, "assistant", NOT_FOUND_MESSAGE)

        elif action == "save_note":
            if result.get("saved"):
                reply_message = flex_messages.get_backup_receipt_flex(
                    "📝 文字筆記", result["content"], result["time_str"], "#"
                )
                save_message(user_id, "assistant", "已幫您把筆記存下來了！")
            else:
                reply_message = TextSendMessage(text="❌ 筆記儲存失敗，請稍後再試。")

        elif action == "add_expense":
            if result.get("saved"):
                reply_message = flex_messages.get_backup_receipt_flex(
                    f"💰 {result['category']}", f"{result['item']} ${result['amount']}", result["time_str"], "#"
                )
                save_message(user_id, "assistant", f"已記帳: {result['item']} ${result['amount']}")
            else:
                reply_message = TextSendMessage(text="❌ 記帳失敗，請稍後再試。")

        elif action == "add_event":
            if result.get("saved"):
                info = f"{result['event_date']} {result['event_time']}".strip()
                if not info:
                    info = "時間未定"
                reply_message = flex_messages.get_backup_receipt_flex(
                    f"📅 {result['event_name']}", info, result["time_str"], "#"
                )
                save_message(user_id, "assistant", f"已排程: {result['event_name']}")
            else:
                reply_message = TextSendMessage(text="❌ 排程儲存失敗，請稍後再試。")

        elif action == "add_task":
            if result.get("saved"):
                due_info = result["due_date"] if result.get("due_date") else "無期限"
                reply_message = flex_messages.get_backup_receipt_flex(
                    f"✅ {result['task']}", f"期限: {due_info} | {result['status']}", result["time_str"], "#"
                )
                save_message(user_id, "assistant", f"已建立待辦: {result['task']}")
            else:
                reply_message = TextSendMessage(text="❌ 待辦儲存失敗，請稍後再試。")

        elif action == "query_records":
            if result.get("queried"):
                cmd = result["mapped_cmd"]
                base_url = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/edit"
                
                records = None
                if cmd == "記帳":
                    records = get_recent_records_from_sheet("💰 記帳本", limit=5)
                elif cmd == "待辦":
                    records = get_recent_records_from_sheet("✅ 待辦清單", limit=5)
                elif cmd in ["排程", "行程", "行事曆"]:
                    records = get_recent_records_from_sheet("📅 行事曆", limit=5)
                elif cmd in ["名片", "通訊錄", "聯絡人"]:
                    records = get_recent_records_from_sheet("📇 通訊錄", limit=5)
                elif cmd in ["筆記", "備忘錄"]:
                    records = get_recent_records_from_sheet("📝 筆記本", limit=5)
                
                if records is not None:    
                    reply_message = format_records_as_text(cmd, records, base_url)
                    
                save_message(user_id, "assistant", f"為您查詢 {cmd} 紀錄。")
            else:
                reply_message = TextSendMessage(text="❌ 查詢失敗，請稍後再試。")

        elif action == "save_contact":
            if result.get("saved"):
                info_parts = [result.get("name", "")]
                if result.get("company"):
                    info_parts.append(result["company"])
                if result.get("phone"):
                    info_parts.append(result["phone"])
                reply_message = flex_messages.get_backup_receipt_flex(
                    "📇 通訊錄", " | ".join(info_parts), result["time_str"], "#"
                )
                save_message(user_id, "assistant", f"已儲存聯絡人: {result['name']}")
            else:
                reply_message = TextSendMessage(text="❌ 聯絡人儲存失敗，請稍後再試。")

        else:
            # 未來新增的 skill 若沒有特殊 UI，回傳純文字
            reply_message = TextSendMessage(text=str(result))
            save_message(user_id, "assistant", str(result))

    line_bot_api.reply_message(event.reply_token, reply_message)


# ── 圖片訊息：Vision 分析 + Drive 備份 + Sheets 索引 + 名片偵測 ──────────
def extract_namecard_info(image_bytes: bytes) -> dict | None:
    """
    使用 GPT-4o Vision 偵測並提取名片資訊。
    若圖片不是名片，回傳 None。
    """
    try:
        base64_image = base64.b64encode(image_bytes).decode("utf-8")
        response = openai_client.chat.completions.create(
            model=OPENAI_VISION_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是名片辨識助理。先判斷圖片是否為名片/商務卡：\n"
                        "- 如果【是名片】，請回傳純 JSON：{\"is_namecard\": true, \"name\": \"姓名\", \"company\": \"公司\", \"title\": \"職稱\", \"phone\": \"電話\", \"email\": \"Email\", \"address\": \"地址\", \"industry\": \"行業類別(如:水電、設計)\", \"summary\": \"一句話總結此人業務\", \"notes\": \"其他資訊\"}\n"
                        "- 如果【不是名片】，請回傳：{\"is_namecard\": false}\n"
                        "只回傳 JSON，不要加任何其他文字。"
                    )
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "這是名片嗎？如果是，請提取聯絡資訊："},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}", "detail": "low"}},
                    ],
                }
            ],
            max_tokens=300,
            temperature=0,
        )
        raw = response.choices[0].message.content.strip()
        # 清理可能的 markdown code block
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(raw)
        if result.get("is_namecard"):
            return result
        return None
    except Exception as e:
        logger.warning("名片偵測失敗 (non-fatal): %s", e)
        return None


@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event: MessageEvent):
    user_id = event.source.user_id
    msg_id = event.message.id

    now = datetime.now()
    ts_str = now.strftime("%Y%m%d_%H%M%S")
    timestamp_display = now.strftime("%Y/%m/%d %H:%M")

    filename = f"IMG_{ts_str}.jpg"

    link, raw_bytes = backup_media_to_drive(msg_id, "image/jpeg", filename)
    if not link:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="❌ 備份寫入失敗"))
        return

    # 名片偵測：先看看是不是名片
    namecard_info = extract_namecard_info(raw_bytes) if raw_bytes else None

    if namecard_info:
        # 🎉 是名片！自動存入通訊錄
        logger.info("📇 偵測到名片: %s", namecard_info.get("name"))
        tags = f"名片, {namecard_info.get('name', '')}, {namecard_info.get('company', '')}"

        # 寫入檔案索引
        append_to_google_sheet(timestamp_display, filename, tags, link)

        # 寫入通訊錄分頁
        from skills import run_skill
        context = {"get_or_create_sheet_tab": get_or_create_sheet_tab}
        namecard_info["card_url"] = link
        contact_result = run_skill("save_contact", namecard_info, context)
        logger.info("📇 通訊錄寫入結果: %s", contact_result)

        # 組合回覆：通訊錄資訊
        info_parts = [namecard_info.get("name", "")]
        if namecard_info.get("company"):
            info_parts.append(namecard_info["company"])
        if namecard_info.get("phone"):
            info_parts.append(namecard_info["phone"])

        receipt_flex = flex_messages.get_backup_receipt_flex(
            "📇 名片掃描", " | ".join(info_parts), timestamp_display, link,
            folder_url=f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/edit",
            folder_label="📊 開啟通訊錄"
        )
    else:
        # 普通圖片：走原本的標籤流程
        tags = analyze_image_with_vision(raw_bytes) if raw_bytes else "無標籤"
        append_to_google_sheet(timestamp_display, filename, tags, link)

        receipt_flex = flex_messages.get_backup_receipt_flex(
            filename, tags, timestamp_display, link,
            folder_url=f"https://drive.google.com/drive/folders/{GOOGLE_DRIVE_FOLDER_ID}" if GOOGLE_DRIVE_FOLDER_ID else ""
        )

    line_bot_api.reply_message(event.reply_token, receipt_flex)


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
        receipt_flex = flex_messages.get_backup_receipt_flex(filename, tags, timestamp_display, link, folder_url=f"https://drive.google.com/drive/folders/{GOOGLE_DRIVE_FOLDER_ID}" if GOOGLE_DRIVE_FOLDER_ID else "")
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
        receipt_flex = flex_messages.get_backup_receipt_flex(filename, tags, timestamp_display, link, folder_url=f"https://drive.google.com/drive/folders/{GOOGLE_DRIVE_FOLDER_ID}" if GOOGLE_DRIVE_FOLDER_ID else "")
        line_bot_api.reply_message(event.reply_token, receipt_flex)
    else:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="❌ 檔案備份失敗"))
