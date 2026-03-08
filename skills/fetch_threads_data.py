"""
Skill: fetch_threads_data
功能：抓取 Threads 帳號與貼文數據，整理寫入 Google Sheets，並產生 AI 洞察總結。
"""

import os
import logging
from datetime import datetime
from openai import OpenAI
from threadspipepy.threadspipe import ThreadsPipe
import gws_client

logger = logging.getLogger(__name__)

TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "fetch_threads_data",
        "description": "當使用者要求你「整理 Threads 數據」、「分析今天的 Threads」、「查看粉絲與貼文成效」時，呼叫此功能以抓取 Threads 自動化數據並彙整報表。",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
}

def execute(args: dict, context: dict) -> dict:
    access_token = os.environ.get("THREADS_ACCESS_TOKEN")
    user_id = os.environ.get("THREADS_USER_ID")
    
    if not access_token or not user_id:
        return {"success": False, "error": "缺少 Threads API 金鑰或使用者 ID，請先在環境變數中設定"}
        
    api = ThreadsPipe(access_token=access_token, user_id=user_id)
    
    today = datetime.now().strftime("%Y/%m/%d")
    
    try:
        profile = api.get_profile()
        follower_count = profile.get('follower_count', profile.get('followers_count', 0))
    except Exception as e:
        logger.error(f"抓取 Profile 失敗: {e}")
        follower_count = 0
        
    # Headers
    daily_tab = "📊 Threads 日報"
    post_tab = "📝 Threads 貼文表現"

    gws_client.get_or_create_tab(daily_tab, ["日期", "粉絲數"])
    gws_client.get_or_create_tab(post_tab, ["日期", "貼文ID", "貼文內容", "按讚數", "回覆數", "瀏覽量", "轉發", "引用", "分享"])
    
    # 寫入日報
    gws_client.sheets_append_row(daily_tab, [today, follower_count])
    
    posts_data = []
    summary_text = f"今日粉絲數：{follower_count}\n"
    
    try:
        posts = api.get_posts()
        data = posts.get("data", [])
        
        # 抓取最近 5 篇
        for i, post in enumerate(data[:5]):
            post_id = post.get("id")
            text = post.get("text", "")
            short_text = (text[:30] + "...") if len(text) > 30 else text
            
            views = 0; likes = post.get("like_count", 0); replies = post.get("reply_count", 0)
            reposts = 0; quotes = 0; shares = 0
            
            try:
                insights = api.get_post_insights(post_id)
                for metric in insights.get("data", []):
                    name = metric.get("name")
                    val = metric.get("values", [{}])[0].get("value", 0)
                    if name == "views": views = val
                    elif name == "likes": likes = val
                    elif name == "replies": replies = val
                    elif name == "reposts": reposts = val
                    elif name == "quotes": quotes = val
                    elif name == "shares": shares = val
            except Exception as e:
                logger.warning(f"Failed to get insights for post {post_id}: {e}")
                
            # Write row
            gws_client.sheets_append_row(post_tab, [today, post_id, text, likes, replies, views, reposts, quotes, shares])
            posts_data.append(f"- 貼文「{short_text}」: 讚 {likes}, 回覆 {replies}, 瀏覽 {views}")
            
    except Exception as e:
        logger.error(f"抓取貼文失敗: {e}")
        return {"success": False, "error": f"抓取貼文失敗: {str(e)}"}
        
    if posts_data:
        summary_text += "\n近期貼文表現：\n" + "\n".join(posts_data)
        
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    prompt = f"""
你是一位專業的社群營運私人秘書。以下是老闆今天最新的 Threads 帳號數據：
{summary_text}

請用簡潔、帶點鼓勵與專業洞察的語氣，寫一段大約 100~150 字的【今日 Threads 洞察總結】回報給老闆。
你可以指出哪種類型的貼文表現較好（例如讚數或瀏覽量較高），並給予發文方向的一個小建議。
請直接以對話形式回覆，不要加上任何 Markdown 標題、不用說這是一份報告。
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=300
        )
        ai_insight = response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"AI 分析失敗: {e}")
        ai_insight = "您的 Threads 數據已成功備份至 Google Sheets！"
        
    return {"success": True, "insight": ai_insight}
