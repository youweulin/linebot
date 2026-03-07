"""
Skill: query_records
功能：查詢各類別的最新紀錄（記帳、待辦、排程、名片、筆記）。
當使用者傳送非快捷鍵的模糊指令（例如「查一下我最近有什麼待辦」），AI 會呼叫此技能。
"""
import logging

logger = logging.getLogger(__name__)

TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "query_records",
        "description": "當使用者想查詢、列出或檢視他儲存的「記帳/花費/出金/淨利潤」、「待辦事項/任務」、「行程/排程」、「名片/聯絡人」或「筆記/備忘錄」時呼叫此功能。例如：「列出我近期的記帳」、「算一下淨利潤」、「看最近的出金紀錄」、「查一下王老闆的電話」。",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["expense", "task", "event", "contact", "note"],
                    "description": "要查詢的資料類別。expense(記帳/花費/出金/收入/淨利潤), task(待辦/任務), event(排程/行程), contact(名片/通訊錄/人脈), note(筆記/備忘錄)。"
                },
                "keyword": {
                    "type": "string",
                    "description": "（選填）使用者想查詢的特定關鍵字，例如人名、公司名、特定開銷。若無則留空。"
                }
            },
            "required": ["category"]
        }
    }
}

def execute(args: dict, context: dict) -> dict:
    """執行紀錄查詢。此結果會由 main.py 轉換為 Carousel UI 顯示。"""
    category = args.get("category")
    keyword = args.get("keyword", "")
    
    # 這裡我們只負責回傳給 main.py 知道 AI 要查什麼，真正的查詢邏輯與 UI 組合會在 main.py 統一處理
    # 定義對應的快捷鍵字眼，讓 main.py 模擬使用者輸入了快捷鍵
    cmd_map = {
        "expense": "記帳",
        "task": "待辦",
        "event": "行程",
        "contact": "通訊錄",
        "note": "筆記"
    }
    
    return {
        "queried": True,
        "category": category,
        "keyword": keyword,
        "mapped_cmd": cmd_map.get(category, "筆記")
    }
