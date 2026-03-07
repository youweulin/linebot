"""
Skill: add_expense
功能：記錄收支項目到 Google Sheets「💰 記帳本」分頁。
支援自然語言輸入，AI 自動拆解出項目名稱、金額、分類。
"""

TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "add_expense",
        "description": "當使用者提到花費、支出、付款、記帳、消費、或是打 propfirm/考試/通關 時呼叫此功能。例如：「午餐花了150」「買咖啡80元」「打propfirm花了200」「通關費 150」。",
        "parameters": {
            "type": "object",
            "properties": {
                "item": {
                    "type": "string",
                    "description": "消費項目名稱，例如：午餐、咖啡、計程車"
                },
                "amount": {
                    "type": "number",
                    "description": "金額數字（不含貨幣符號），例如：150"
                },
                "category": {
                    "type": "string",
                    "description": "消費類別，從以下選擇最接近的一個：餐飲、交通、娛樂、購物、生活、工作、醫療、教育、其他",
                    "enum": ["餐飲", "交通", "娛樂", "購物", "生活", "工作", "醫療", "教育", "其他"]
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
    記錄一筆支出到「💰 記帳本」分頁。
    """
    item = args.get("item", "")
    amount = args.get("amount", 0)
    category = args.get("category", "其他")

    try:
        import gws_client
        from datetime import datetime
        time_str = datetime.now().strftime("%Y/%m/%d %H:%M")
        gws_client.get_or_create_tab(TAB_NAME, HEADERS)
        ok = gws_client.sheets_append_row(TAB_NAME, [time_str, item, amount, category])
        
        # 取得今日累積花費與 Propfirm 特定花費
        import re
        today_str = datetime.now().strftime("%Y/%m/%d")
        records = gws_client.sheets_get_all_records(TAB_NAME)
        
        propfirm_daily_total = 0.0
        
        for r in records:
            r_time = str(r.get("時間", ""))
            r_item = str(r.get("項目", "")).lower()
            
            # 只計算今天的紀錄
            if today_str in r_time:
                # 嘗試清理數字
                amount_str = str(r.get('金額', '0'))
                clean_amount = re.sub(r'[^\d.-]', '', amount_str)
                try:
                    val = float(clean_amount) if clean_amount else 0.0
                    
                    # 辨識是否為 propfirm 相關花費
                    if any(kw in r_item for kw in ["propfirm", "tpt", "考試", "通關"]):
                        propfirm_daily_total += val
                        
                except Exception:
                    pass

        return {
            "saved": ok,
            "time_str": time_str,
            "item": item,
            "amount": amount,
            "category": category,
            "propfirm_daily_total": propfirm_daily_total
        }
    except Exception as e:
        return {"saved": False, "item": item, "amount": amount, "category": category, "error": str(e)}
