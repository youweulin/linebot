"""
Skill: set_user_settings
功能：設定每個 user_id 的個人化偏好（timezone/mode/翻譯目標語言等）。
資料會寫入 Google Sheets「⚙️ 設定」分頁。
"""

from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "set_user_settings",
        "description": (
            "當使用者要求你設定或更新偏好（例如：設定時區、設定每日摘要時間）時呼叫此功能。"
            "例如：「把我的時區改成 America/Los_Angeles」。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "IANA 時區名稱，例如 Asia/Taipei、America/Los_Angeles。",
                },
                "mode": {
                    "type": "string",
                    "enum": ["auto", "receipt", "translate"],
                    "description": "Bot 模式：auto(自動判斷)、receipt(收據/發票)、translate(翻譯)。",
                },
                "translate_target_lang": {
                    "type": "string",
                    "description": "翻譯目標語言/地區，例如 zh-TW、en、ja。",
                },
                "receipt_autobook": {
                    "type": "boolean",
                    "description": "收據模式下，是否自動記帳（先預留）。預設 false。",
                },
            },
            "required": [],
        },
    },
}

TAB_NAME = "⚙️ 設定"
HEADERS = ["更新時間", "user_id", "timezone", "mode", "translate_target_lang", "receipt_autobook"]


def execute(args: dict, context: dict) -> dict:
    user_id = context.get("user_id", "")
    if not user_id:
        return {"saved": False, "error": "缺少 user_id（請從 main.py context 傳入）"}

    timezone = str(args.get("timezone") or "").strip()
    mode = str(args.get("mode") or "").strip().lower()
    translate_target_lang = str(args.get("translate_target_lang") or "").strip()
    receipt_autobook = args.get("receipt_autobook", None)

    if not any([timezone, mode, translate_target_lang, receipt_autobook is not None]):
        return {"saved": False, "error": "請至少提供一個設定欄位（timezone/mode/translate_target_lang/receipt_autobook）"}

    try:
        import gws_client

        if timezone:
            # 驗證 timezone 是否可用（zoneinfo/pytz 任一可解析即可）
            ok_tz = False
            try:
                from zoneinfo import ZoneInfo

                ZoneInfo(timezone)
                ok_tz = True
            except Exception:
                try:
                    import pytz

                    pytz.timezone(timezone)
                    ok_tz = True
                except Exception:
                    ok_tz = False

            if not ok_tz:
                return {"saved": False, "error": f"不支援的 timezone：{timezone}（請用 IANA 名稱，例如 Asia/Taipei）"}

        if mode and mode not in {"auto", "receipt", "translate"}:
            return {"saved": False, "error": f"不支援的 mode：{mode}（可用：auto/receipt/translate）"}

        if receipt_autobook is not None and not isinstance(receipt_autobook, bool):
            # LLM 有時會傳 "true"/"false" 字串
            if str(receipt_autobook).strip().lower() in {"true", "1", "yes"}:
                receipt_autobook = True
            elif str(receipt_autobook).strip().lower() in {"false", "0", "no"}:
                receipt_autobook = False
            else:
                return {"saved": False, "error": "receipt_autobook 必須是布林值 true/false"}

        gws_client.get_or_create_tab(TAB_NAME, HEADERS)

        # 簡化：每次更新就 append 一列，讀取時取最新一筆
        now_str = datetime.utcnow().strftime("%Y/%m/%d %H:%M")
        ok = gws_client.sheets_append_row(
            TAB_NAME,
            [
                now_str,
                user_id,
                timezone,
                mode,
                translate_target_lang,
                "" if receipt_autobook is None else str(receipt_autobook),
            ],
        )
        return {
            "saved": ok,
            "user_id": user_id,
            "timezone": timezone,
            "mode": mode,
            "translate_target_lang": translate_target_lang,
            "receipt_autobook": receipt_autobook,
            "time_str": now_str,
        }
    except Exception as e:
        logger.error("set_user_settings 失敗: %s", e, exc_info=True)
        return {"saved": False, "error": str(e)}
