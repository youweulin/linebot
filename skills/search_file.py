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
    lookup_many_fn = context.get("lookup_files_in_sheets_by_tags")
    lookup_one_fn = context.get("lookup_file_in_sheets_by_tags")

    if lookup_many_fn:
        user_id = context.get("user_id")
        try:
            candidates = lookup_many_fn(keywords, 5, user_id)
        except TypeError:
            # 向下相容：舊函式簽名
            candidates = lookup_many_fn(keywords)
        if candidates:
            return {
                "found": True,
                "url": candidates[0].get("url", ""),
                "keywords": keywords,
                "candidates": candidates,
            }

    if lookup_one_fn:
        url = lookup_one_fn(keywords)
        if url:
            return {"found": True, "url": url, "keywords": keywords, "candidates": [{"url": url}]}

    return {"found": False, "url": "", "keywords": keywords, "candidates": []}
