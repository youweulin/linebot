"""
Skill: search_file
功能：根據關鍵字在 Google Sheets 索引中搜尋過去曾備份過的檔案。
"""

TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "search_file",
        "description": "當使用者想要尋找某個過去存過的檔案、照片或文件時呼叫此功能。",
        "parameters": {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "string",
                    "description": "從語意中提煉出的搜尋關鍵字，多個關鍵字請用逗號分隔。例如: '日本, 照片'"
                }
            },
            "required": ["keywords"]
        }
    }
}


def execute(args: dict, context: dict) -> dict:
    """
    執行檔案搜尋。
    回傳: {"found": True/False, "url": "...", "keywords": "..."}
    """
    keywords = args.get("keywords", "")
    lookup_fn = context.get("lookup_file_in_sheets_by_tags")

    if lookup_fn:
        url = lookup_fn(keywords)
        if url:
            return {"found": True, "url": url, "keywords": keywords}

    return {"found": False, "url": "", "keywords": keywords}
