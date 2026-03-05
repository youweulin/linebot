"""
Skill: save_note
功能：將使用者的文字筆記、備忘錄、待辦事項存入 Google Sheets。
"""

TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "save_note",
        "description": "當使用者想要記錄文字筆記、備忘錄、待辦事項、或是任何需要記下來的資訊時呼叫此功能。",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "需要被完整記錄下來的筆記內容或重點。"
                }
            },
            "required": ["content"]
        }
    }
}


def execute(args: dict, context: dict) -> dict:
    """
    執行筆記儲存。
    回傳: {"saved": True/False, "time_str": "...", "content": "..."}
    """
    content = args.get("content", "")
    save_note_fn = context.get("save_note_to_sheets")

    if save_note_fn:
        time_str = save_note_fn(content)
        return {"saved": True, "time_str": time_str, "content": content}

    return {"saved": False, "time_str": "", "content": content}
