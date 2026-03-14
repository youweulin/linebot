"""
Skill: save_note
功能：將使用者的文字筆記、備忘錄、待辦事項存入 Google Sheets「📝 筆記本」分頁。
"""

TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "save_note",
        "description": "當使用者想要記錄文字筆記、備忘錄、待辦事項、或是任何需要記下來的資訊時呼叫此功能。",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "需要被完整記錄下來的筆記內容或重點。"
                }
            },
            "required": ["content"]
        }
    }
}

TAB_NAME = "📝 筆記本"
HEADERS = ["時間", "內容"]


def execute(args: dict, context: dict) -> dict:  
    """
    執行筆記儲存，寫入獨立的「📝 筆記本」分頁。
    """
    content = args.get("content", "")

    try:
        import gws_client
        from datetime import datetime
        import pytz

        tz_name = str(context.get("timezone") or "Asia/Taipei")
        tw_tz = pytz.timezone(tz_name)
        time_str = datetime.now(tw_tz).strftime("%Y/%m/%d %H:%M")
        gws_client.get_or_create_tab(TAB_NAME, HEADERS)  
        ok = gws_client.sheets_append_row(TAB_NAME, [time_str, content])  
        return {"saved": ok, "time_str": time_str, "content": content}  
    except Exception as e:  
        return {"saved": False, "time_str": "", "content": content, "error": str(e)}  
