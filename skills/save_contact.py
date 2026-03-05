"""
Skill: save_contact
功能：儲存聯絡人資訊到 Google Sheets「📇 通訊錄」分頁。
可透過文字輸入，或者由名片掃描 (Vision) 自動觸發。
"""

TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "save_contact",
        "description": "當使用者想要儲存聯絡人資訊、記下某人的電話或Email、或提到名片時呼叫此功能。例如：「記下王大明的電話0912345678」「存一下李經理的信箱 lee@abc.com」。",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "聯絡人姓名"
                },
                "company": {
                    "type": "string",
                    "description": "公司名稱（若有的話）"
                },
                "title": {
                    "type": "string",
                    "description": "職稱（若有的話）"
                },
                "phone": {
                    "type": "string",
                    "description": "電話號碼（若有的話）"
                },
                "email": {
                    "type": "string",
                    "description": "Email 地址（若有的話）"
                },
                "notes": {
                    "type": "string",
                    "description": "其他備註資訊"
                }
            },
            "required": ["name"]
        }
    }
}

TAB_NAME = "📇 通訊錄"
HEADERS = ["時間", "姓名", "公司", "職稱", "電話", "Email", "備註", "名片圖檔"]


def execute(args: dict, context: dict) -> dict:
    """
    儲存聯絡人資訊到「📇 通訊錄」分頁。
    """
    name = args.get("name", "")
    company = args.get("company", "")
    title = args.get("title", "")
    phone = args.get("phone", "")
    email = args.get("email", "")
    notes = args.get("notes", "")
    card_url = args.get("card_url", "")  # 名片圖檔連結（由圖片處理流程傳入）

    get_or_create_sheet_tab = context.get("get_or_create_sheet_tab")

    if not get_or_create_sheet_tab:
        return {"saved": False, "name": name}

    try:
        from datetime import datetime
        time_str = datetime.now().strftime("%Y/%m/%d %H:%M")
        sheet = get_or_create_sheet_tab(TAB_NAME, HEADERS)
        sheet.append_row([time_str, name, company, title, phone, email, notes, card_url])
        return {
            "saved": True,
            "time_str": time_str,
            "name": name,
            "company": company,
            "title": title,
            "phone": phone,
            "email": email,
            "notes": notes,
        }
    except Exception as e:
        return {"saved": False, "name": name, "error": str(e)}
