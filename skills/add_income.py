"""
Skill: add_income
功能：記錄收入/出金項目到 Google Sheets「💰 記帳本」分頁。
支援自然語言輸入，AI 自動拆解出項目名稱、金額、分類。
"""

TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "add_income",
        "description": "當使用者提到收入、出金、payout、賺了、入帳時呼叫此功能。例如：「收到 propfirm 出金 3000」「這個月薪水 50000」「賣掉二手手機賺了 5000」。",
        "parameters": {
            "type": "object",
            "properties": {
                "item": {
                    "type": "string",
                    "description": "收入項目名稱，例如：Propfirm 出金、薪水、二手手機"
                },
                "amount": {
                    "type": "number",
                    "description": "金額數字（不含貨幣符號），例如：3000"
                },
                "category": {
                    "type": "string",
                    "description": "收入類別，針對 Propfirm 出金務必選擇「出金」，其他可選「薪水」、「投資」、「兼職」、「其他收入」等",
                    "enum": ["出金", "薪水", "投資", "兼職", "其他收入"]
                }
            },
            "required": ["item", "amount", "category"]
        }
    }
}

TAB_NAME = "💰 記帳本"
HEADERS = ["時間", "項目", "金額", "類別"]


def execute(args: dict, context: dict) -> dict:
    """
    記錄一筆收入到「💰 記帳本」分頁。
    """
    item = args.get("item", "")
    amount = args.get("amount", 0)
    category = args.get("category", "其他收入")

    try:
        import gws_client
        from datetime import datetime
        time_str = datetime.now().strftime("%Y/%m/%d %H:%M")
        gws_client.get_or_create_tab(TAB_NAME, HEADERS)
        ok = gws_client.sheets_append_row(TAB_NAME, [time_str, item, amount, category])
        return {
            "saved": ok,
            "time_str": time_str,
            "item": item,
            "amount": amount,
            "category": category
        }
    except Exception as e:
        return {"saved": False, "item": item, "amount": amount, "category": category, "error": str(e)}
