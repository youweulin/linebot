"""
Skill: set_trading_goals
功能：設定使用者的交易夢想與長遠目標，作為 AI 提供建議時的依據。
"""

TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "set_trading_goals",
        "description": "當使用者想要設定、更新或提到他的交易夢想、長遠目標、為什麼要交易的原因時呼叫此功能。",
        "parameters": {
            "type": "object",
            "properties": {
                "dreams": {
                    "type": "string",
                    "description": "使用者的交易夢想，例如：財富自由、帶家人環遊世界。"
                },
                "goals": {
                    "type": "string",
                    "description": "具體的交易目標，例如：每月穩定獲利 2000 美金、考過 300k 帳號。"
                }
            },
            "required": ["dreams", "goals"]
        }
    }
}

TAB_NAME = "🎯 夢想與目標"
HEADERS = ["時間", "夢想", "目標"]


def execute(args: dict, context: dict) -> dict:
    dreams = args.get("dreams", "未設定")
    goals = args.get("goals", "未設定")

    try:
        import gws_client
        from datetime import datetime
        import pytz
        
        tw_tz = pytz.timezone('Asia/Taipei')
        time_str = datetime.now(tw_tz).strftime("%Y/%m/%d %H:%M")
        
        gws_client.get_or_create_tab(TAB_NAME, HEADERS)
        ok = gws_client.sheets_append_row(TAB_NAME, [time_str, dreams, goals])
        
        return {
            "saved": ok, 
            "time_str": time_str, 
            "dreams": dreams, 
            "goals": goals
        }
    except Exception as e:
        return {"saved": False, "error": str(e)}
