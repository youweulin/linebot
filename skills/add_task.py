"""
Skill: add_task
功能：將使用者的待辦事項、任務存入 Google Sheets「✅ 待辦清單」分頁。
"""

TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "add_task",
        "description": "當使用者要求幫忙建一個待辦、任務、或者提醒要完成某件事時呼叫此功能。例如：「幫我建一個待辦：週五前交報告」「提醒我明天要去繳費」。",
        "parameters": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "具體的待辦事項內容，例如：交報告、繳水電費"
                },
                "due_date": {
                    "type": "string",
                    "description": "預計完成日或期限，請盡量轉換為 YYYY/MM/DD 格式，如果是明天或下週，也請推算成具體日期。若無指定則留空。"
                }
            },
            "required": ["task"]
        }
    }
}

TAB_NAME = "✅ 待辦清單"
HEADERS = ["建立時間", "待辦事項", "預計完成日", "狀態(未完成/已完成)"]


def execute(args: dict, context: dict) -> dict:
    """
    執行待辦事項儲存，寫入「✅ 待辦清單」分頁。
    """
    task = args.get("task", "")
    due_date = args.get("due_date", "")
    status = "未完成"  # 預設狀態

    try:
        import gws_client
        from datetime import datetime
        import pytz
        tw_tz = pytz.timezone('Asia/Taipei')
        time_str = datetime.now(tw_tz).strftime("%Y/%m/%d %H:%M")
        gws_client.get_or_create_tab(TAB_NAME, HEADERS)
        ok = gws_client.sheets_append_row(TAB_NAME, [time_str, task, due_date, status])
        return {"saved": ok, "time_str": time_str, "task": task, "due_date": due_date, "status": status}
    except Exception as e:
        return {"saved": False, "time_str": "", "task": task, "due_date": due_date, "error": str(e)}
