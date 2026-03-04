"""
LINE Bot — Google Sheets File Lookup with AI
============================================
功能複製自 n8n 工作流：
  Webhook → Edit Fields → AI Agent → Google Sheets Lookup → IF → LINE Reply

環境變數統一放在 .env，請勿將真實金鑰提交到 GitHub！
"""

import os
import json
import logging

import gspread
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from openai import OpenAI

# ── 讀取環境變數 ────────────────────────────────────────────────────────
load_dotenv()

LINE_CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
LINE_CHANNEL_SECRET = os.environ["LINE_CHANNEL_SECRET"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")          # 預設免費省錢模型
GOOGLE_SHEET_ID = os.environ["GOOGLE_SHEET_ID"]
GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "工作表1")
GOOGLE_CREDENTIALS_JSON = os.environ["GOOGLE_CREDENTIALS_JSON"]  # Service Account JSON 字串
NOT_FOUND_MESSAGE = os.getenv("NOT_FOUND_MESSAGE", "找不到您要查詢的檔案，請確認檔名是否正確。")

# ── 初始化服務 ───────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="LINE Bot - File Lookup")
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
openai_client = OpenAI(api_key=OPENAI_API_KEY)


def get_google_sheet():
    """回傳指定的 Google Sheets 工作表物件（使用 Service Account 驗證）"""
    creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
    gc = gspread.service_account_from_dict(creds_dict)
    return gc.open_by_key(GOOGLE_SHEET_ID).worksheet(GOOGLE_SHEET_NAME)


def extract_filename_with_ai(user_message: str) -> str:
    """
    使用 OpenAI 從使用者訊息中萃取想查詢的檔名。
    複製 n8n AI Agent 節點的 System Prompt。
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
    response = openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0,
        max_tokens=100,
    )
    return response.choices[0].message.content.strip()


def lookup_file_in_sheets(filename: str) -> str | None:
    """
    在 Google Sheets 的 A 欄（Filename）中查詢：
      - A 欄存放檔名（即 Lookup Column）
      - B 欄存放 File URL
    回傳 File URL，找不到則回傳 None。
    """
    try:
        sheet = get_google_sheet()
        # 取得所有資料行 (list of dicts，以第 1 列為 Header)
        records = sheet.get_all_records()
        for row in records:
            if str(row.get("Filename", "")).strip().lower() == filename.strip().lower():
                url = str(row.get("File URL", "")).strip()
                return url if url else None
        return None
    except Exception as e:
        logger.error("Google Sheets 查詢失敗: %s", e)
        return None


# ── LINE Webhook 路由 ────────────────────────────────────────────────────

@app.get("/")
async def health_check():
    return {"status": "ok", "message": "LINE Bot is running 🤖"}


@app.post("/webhook")
async def webhook(request: Request):
    """LINE Platform 呼叫的 Webhook 端點"""
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    body_str = body.decode("utf-8")

    try:
        handler.handle(body_str, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    return JSONResponse(content={"status": "ok"})


@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event: MessageEvent):
    """
    主要業務邏輯 — 對應 n8n 工作流的核心流程：
    1. [Edit Fields]   取出使用者訊息
    2. [AI Agent]      用 OpenAI 萃取查詢的檔名
    3. [Sheets Lookup] 在 Google Sheets 找 File URL
    4. [IF + Reply]    找到就回傳 URL，找不到就回傳「找不到」訊息
    """
    user_message: str = event.message.text
    logger.info("收到訊息: %s", user_message)

    # Step 1: AI Agent — 萃取檔名
    extracted_filename = extract_filename_with_ai(user_message)
    logger.info("AI 萃取的檔名: %s", extracted_filename)

    # Step 2: Google Sheets Lookup
    if extracted_filename == "No filename detected.":
        reply_text = NOT_FOUND_MESSAGE
    else:
        file_url = lookup_file_in_sheets(extracted_filename)

        # Step 3: IF File Exists
        if file_url:
            reply_text = file_url
            logger.info("找到檔案 URL: %s", file_url)
        else:
            reply_text = NOT_FOUND_MESSAGE
            logger.info("找不到檔案: %s", extracted_filename)

    # Step 4: 回覆 LINE 使用者
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text),
    )
