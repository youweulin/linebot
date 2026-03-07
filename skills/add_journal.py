"""
Skill: add_journal
功能：記錄使用者的交易日記，包含打單心理狀態、優點以及缺點到 Google Sheets「📈 交易日記」分頁。
"""

TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "add_journal",
        "description": "當使用者想要記錄交易日記、交易筆記、打單心得、檢討、或是提到心理狀態、優缺點時呼叫此功能。此功能會將心得存入專屬的「📈 交易日記」表。例如：「幫我記一下今天的交易日記，心情有點急躁，優點是有停損，缺點是亂建倉」。",
        "parameters": {
            "type": "object",
            "properties": {
                "psychology": {
                    "type": "string",
                    "description": "打單心理狀態或心情，例如：有點急躁、心情很差、壓力大"
                },
                "pros": {
                    "type": "string",
                    "description": "做得好的地方、優點，例如：確實執行停損、耐心等待"
                },
                "cons": {
                    "type": "string",
                    "description": "需要改進的地方、缺點，例如：亂建倉、急躁提早進場、沒照計畫"
                },
                "act_suggestion": {
                    "type": "string",
                    "description": "根據心理狀態與缺點，提供具體的 ACT (接納與承諾療法) 改善作法標籤或簡短建議。"
                },
                "commitment": {
                    "type": "string",
                    "description": "使用者的交易承諾或下週計畫，例如：一天只用一個帳號、不喝酒交易。"
                },
                "transaction_date": {
                    "type": "string",
                    "description": "（選填）日記所屬日期，格式為 YYYY/MM/DD。如果使用者提到昨天、3/6 等，請填入該日期。若無則留空。"
                }
            },
            "required": ["psychology", "pros", "cons"]
        }
    }
}

TAB_NAME = "📈 交易日記"
HEADERS = ["時間", "日期", "心理狀態", "優點", "缺點", "ACT 建議", "交易承諾"]


def execute(args: dict, context: dict) -> dict:
    """
    執行交易日記儲存，寫入獨立的「📈 交易日記」分頁。
    """
    psychology = args.get("psychology", "無")
    pros = args.get("pros", "無")
    cons = args.get("cons", "無")
    act_suggestion = args.get("act_suggestion", "無")
    commitment = args.get("commitment", "無")

    try:
        import gws_client
        from datetime import datetime
        import pytz
        
        tw_tz = pytz.timezone('Asia/Taipei')
        now = datetime.now(tw_tz)
        
        # 紀錄時間 (System Time)
        creation_time = now.strftime("%Y/%m/%d %H:%M")
        
        # 實際日期 (預設今天)
        transaction_date = args.get("transaction_date", "")
        if not transaction_date:
            transaction_date = now.strftime("%Y/%m/%d")
        else:
            transaction_date = transaction_date.replace("-", "/")

        gws_client.get_or_create_tab(TAB_NAME, HEADERS)
        ok = gws_client.sheets_append_row(TAB_NAME, [creation_time, transaction_date, psychology, pros, cons, act_suggestion, commitment])
        
        return {
            "saved": ok, 
            "time_str": creation_time, 
            "transaction_date": transaction_date,
            "psychology": psychology, 
            "pros": pros, 
            "cons": cons,
            "act_suggestion": act_suggestion,
            "commitment": commitment
        }
    except Exception as e:
        return {
            "saved": False, 
            "time_str": "", 
            "psychology": psychology, 
            "pros": pros, 
            "cons": cons, 
            "error": str(e)
        }
