"""
Skill: publish_post
功能：將使用者的文字內容發布到社群媒體（目前支援 Threads）。
"""
import os
import logging
from threadspipepy.threadspipe import ThreadsPipe

logger = logging.getLogger(__name__)

TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "publish_post",
        "description": "當使用者確認並要求你自動發文、推入社群媒體（如 Threads）時，呼叫此功能。重要：如果是發布剛剛產生的草稿，請『一字不漏』地提取上一則訊息中的草稿內容作為 content，絕對不要重新改寫或擴寫。",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "要發布到社群的完整貼文內容。"
                }
            },
            "required": ["content"]
        }
    }
}

def execute(args: dict, context: dict) -> dict:
    content = args.get("content", "")
    if not content:
        return {"success": False, "error": "沒有提供發文內容"}

    access_token = os.environ.get("THREADS_ACCESS_TOKEN")
    user_id = os.environ.get("THREADS_USER_ID")
    
    if not access_token or not user_id:
        return {"success": False, "error": "缺少 Threads API 金鑰或使用者 ID，請先在環境變數中設定"}

    try:
        api = ThreadsPipe(access_token=access_token, user_id=user_id)
        pipe_result = api.pipe(post=content)
        
        logger.info(f"Threads API response: {pipe_result}")
        return {"success": True, "platform": "Threads", "content": content}
    except Exception as e:
        logger.error(f"發布至 Threads 失敗: {e}", exc_info=True)
        return {"success": False, "platform": "Threads", "error": str(e)}
