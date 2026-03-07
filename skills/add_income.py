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
                },
                "transaction_date": {
                    "type": "string",
                    "description": "（選填）實際收入日期，格式為 YYYY/MM/DD。如果使用者有特別提到日期（如：昨天、3/5），請轉換為具體日期。若無則留空。"
                }
            },
            "required": ["item", "amount", "category"]
        }
    }
}

TAB_NAME = "💰 記帳本"
HEADERS = ["紀錄時間", "實際交易日期", "項目", "金額", "類別"]


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
        import pytz
        tw_tz = pytz.timezone('Asia/Taipei')
        now = datetime.now(tw_tz)
        
        # 紀錄時間 (System Time)
        creation_time = now.strftime("%Y/%m/%d %H:%M")
        
        # 實際交易日期 (預設今天)
        transaction_date = args.get("transaction_date", "")
        if not transaction_date:
            transaction_date = now.strftime("%Y/%m/%d")
        else:
            # 統一格式 YYYY/MM/DD
            transaction_date = transaction_date.replace("-", "/")

        gws_client.get_or_create_tab(TAB_NAME, HEADERS)
        ok = gws_client.sheets_append_row(TAB_NAME, [creation_time, transaction_date, item, amount, category])
        
        # 計算該交易日期所屬月份與年份的出金總計
        import re
        # 解析交易日期物件以取得年/月
        try:
            trans_dt = datetime.strptime(transaction_date, "%Y/%m/%d")
        except:
            trans_dt = now # fallback
            
        target_month = trans_dt.strftime("%Y/%m")
        target_year = trans_dt.strftime("%Y")
        
        records = gws_client.sheets_get_all_records(TAB_NAME)
        month_total = 0.0
        year_total = 0.0
        
        for r in records:
            r_date = str(r.get("實際交易日期", ""))
            r_cat = str(r.get("類別", ""))
            
            # 只計算類別為「出金」的項目
            if "出金" in r_cat:
                amount_str = str(r.get('金額', '0'))
                clean_amount = re.sub(r'[^\d.-]', '', amount_str)
                try:
                    val = float(clean_amount) if clean_amount else 0.0
                    if target_year in r_date:
                        year_total += val
                        if target_month in r_date:
                            month_total += val
                except Exception:
                    pass

        return {
            "saved": ok,
            "time_str": creation_time,
            "transaction_date": transaction_date,
            "item": item,
            "amount": amount,
            "category": category,
            "month_total": month_total,
            "year_total": year_total
        }
    except Exception as e:
        return {"saved": False, "item": item, "amount": amount, "category": category, "error": str(e)}
