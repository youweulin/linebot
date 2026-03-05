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
    get_or_create_sheet_tab = context.get("get_or_create_sheet_tab")

    if not get_or_create_sheet_tab:
        return {"saved": False, "time_str": "", "content": content}

    try:
        from datetime import datetime
        time_str = datetime.now().strftime("%Y/%m/%d %H:%M")
        sheet = get_or_create_sheet_tab(TAB_NAME, HEADERS)
        sheet.append_row([time_str, content])
        return {"saved": True, "time_str": time_str, "content": content}
    except Exception as e:
        return {"saved": False, "time_str": "", "content": content, "error": str(e)}
