"""
Skill: add_event
功能：儲存行事曆、排程、行程、待辦事項到 Google Sheets「📅 行事曆」分頁。
"""

TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "add_event",
        "description": "當使用者提到未來的計畫、開會、約會、排程、行程、提醒、待辦事項時呼叫此功能。例如：「下週三下午兩點要開會」「明天晚上記得買牛奶」。",
        "parameters": {
            "type": "object",
            "properties": {
                "event_name": {
                    "type": "string",
                    "description": "事件或排程的名稱，例如：開會, 買牛奶, 跟客戶吃飯"
                },
                "event_date": {
                    "type": "string",
                    "description": "事件的日期，請盡量轉換為 YYYY/MM/DD 格式，如果是明天或下週，也請推算成具體日期。若無指定則留空。"
                },
                "event_time": {
                    "type": "string",
                    "description": "事件的時間，例如：14:00, 早上 9 點。若無指定則留空。"
                },
                "notes": {
                    "type": "string",
                    "description": "其他備註說明，若無則留空"
                }
            },
            "required": ["event_name"]
        }
    }
}

TAB_NAME = "📅 行事曆"
HEADERS = ["紀錄時間", "事件名稱", "事件日期", "事件時間", "備註"]


def execute(args: dict, context: dict) -> dict:
    """
    儲存排程資訊到「📅 行事曆」分頁。
    """
    event_name = args.get("event_name", "")
    event_date = args.get("event_date", "")
    event_time = args.get("event_time", "")
    notes = args.get("notes", "")

    get_or_create_sheet_tab = context.get("get_or_create_sheet_tab")

    if not get_or_create_sheet_tab:
        return {"saved": False, "event_name": event_name}

    try:
        from datetime import datetime
        time_str = datetime.now().strftime("%Y/%m/%d %H:%M")
        sheet = get_or_create_sheet_tab(TAB_NAME, HEADERS)
        sheet.append_row([time_str, event_name, event_date, event_time, notes])
        return {
            "saved": True,
            "time_str": time_str,
            "event_name": event_name,
            "event_date": event_date,
            "event_time": event_time,
            "notes": notes,
        }
    except Exception as e:
        return {"saved": False, "event_name": event_name, "error": str(e)}
