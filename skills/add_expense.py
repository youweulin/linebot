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
                },
                "transaction_date": {
                    "type": "string",
                    "description": "（選填）實際消費日期，格式為 YYYY/MM/DD。如果使用者有特別提到日期（如：昨天、3/5），請轉換為具體日期。若無則留空。"
                }
            },
            "required": ["item", "amount", "category"]
        }
    }
}

import gws_client
import re
from datetime import datetime
import pytz

TAB_NAME = "💰 記帳本"
HEADERS = ["時間", "項目時間", "項目", "金額", "類別"]


def execute(args: dict, context: dict) -> dict:
    """
    記錄一筆支出到「💰 記帳本」分頁。
    """
    item = args.get("item", "")
    amount = args.get("amount", 0)
    category = args.get("category", "其他")
    
    try:
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
        
        target_norm = gws_client.parse_date_string(transaction_date)
        target_year = target_norm[:4]
        target_month = target_norm[:7]
        
        records = gws_client.sheets_get_all_records(TAB_NAME)
        
        propfirm_daily_total = 0.0
        month_total = 0.0
        year_total = 0.0
        
        income_categories = ["出金", "收入", "薪水", "兼職", "其他收入", "投資獲利", "投資回報", "payout"]
        
        for r in records:
            # 統一比對用的日期格式
            r_date_raw = str(r.get("項目時間", ""))
            r_date_norm = gws_client.parse_date_string(r_date_raw)
            
            r_item = str(r.get("項目", "")).lower()
            r_cat = str(r.get("類別", ""))
            
            # 排除收入類別，剩下的都當作花費
            if r_cat not in income_categories:
                amount_str = str(r.get('金額', '0'))
                clean_amount = re.sub(r'[^\d.-]', '', amount_str)
                try:
                    val = float(clean_amount) if clean_amount else 0.0
                    
                    if target_year in r_date_norm:
                        year_total += val
                        if target_month in r_date_norm:
                            month_total += val
                            
                    # 原本的 propfirm 邏輯
                    if target_norm == r_date_norm:
                        if any(kw in r_item for kw in ["propfirm", "tpt", "考試", "通關"]):
                            propfirm_daily_total += val
                            
                except Exception:
                    pass

        return {
            "saved": ok,
            "time_str": creation_time,
            "transaction_date": transaction_date,
            "item": item,
            "amount": amount,
            "category": category,
            "propfirm_daily_total": propfirm_daily_total,
            "month_total": month_total,
            "year_total": year_total,
            "month_label": f"{int(target_month[5:7]):d}月",
            "year_label": f"{target_year}年",
            "is_current_month": (target_month == now.strftime("%Y/%m"))
        }
    except Exception as e:
        return {"saved": False, "item": item, "amount": amount, "category": category, "error": str(e)}
