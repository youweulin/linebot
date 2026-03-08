"""
Skill: fetch_threads_data
功能：抓取 Threads 帳號與貼文數據，整理寫入 Google Sheets，並產生 AI 洞察總結。
注意：直接使用 Meta Graph API HTTP 請求，避免 threadspipepy 的 get_user_insights 無限等待問題。
"""

import os
import logging
import requests
from datetime import datetime
from openai import OpenAI
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

THREADS_API_BASE = "https://graph.threads.net/v1.0"

def _get(path: str, params: dict) -> dict:
    """帶 timeout 的 GET 請求，避免無限等待。"""
    res = requests.get(f"{THREADS_API_BASE}{path}", params=params, timeout=15)
    return res.json()

def execute(args: dict, context: dict) -> dict:
    access_token = os.environ.get("THREADS_ACCESS_TOKEN")
    threads_user_id = os.environ.get("THREADS_USER_ID")

    if not access_token or not threads_user_id:
        return {"success": False, "error": "缺少 THREADS_ACCESS_TOKEN 或 THREADS_USER_ID 環境變數"}

    today = datetime.now().strftime("%Y/%m/%d")

    # ── 1. 抓取粉絲數 ────────────────────────────────────────────────────────
    # 官方文件：GET /{user_id}/threads_insights?metric=followers_count
    # 回傳格式：{"data": [{"name": "followers_count", "period": "day", "total_value": {"value": 123}}]}
    # 注意：/me endpoint 不含 followers_count 欄位，不可做 fallback
    follower_count = 0
    try:
        data = _get(f"/{threads_user_id}/threads_insights", {
            "metric": "followers_count",
            "access_token": access_token
        })
        logger.info(f"Threads followers_count API 原始回傳: {data}")
        if "error" in data:
            logger.error(f"Insights API 錯誤: {data['error']}")
        else:
            for m in data.get("data", []):
                if m.get("name") == "followers_count":
                    follower_count = m.get("total_value", {}).get("value", 0)
                    logger.info(f"解析到粉絲數: {follower_count}")
                    break
    except Exception as e:
        logger.warning(f"抓取粉絲數失敗 (非致命): {e}")

    # ── 2. 確保 Sheet Tabs 存在 ──────────────────────────────────────────────
    daily_tab = "📊 Threads 日報"
    post_tab  = "📝 Threads 貼文表現"
    gws_client.get_or_create_tab(daily_tab, ["日期", "粉絲數"])
    gws_client.get_or_create_tab(post_tab, ["日期", "貼文ID", "貼文內容", "按讚數", "回覆數", "瀏覽量", "轉發", "引用", "分享"])

    # ── 3. 寫入日報 ──────────────────────────────────────────────────────────
    gws_client.sheets_append_row(daily_tab, [today, follower_count])

    # ── 4. 抓取貼文列表 ──────────────────────────────────────────────────────
    posts_data = []
    summary_text = f"今日粉絲數：{follower_count}\n"

    try:
        posts_raw = _get(f"/{threads_user_id}/threads", {
            "fields": "id,text,timestamp,like_count,reply_count",
            "access_token": access_token
        })
        posts = posts_raw.get("data", [])

        for post in posts[:5]:
            post_id  = post.get("id", "")
            text     = post.get("text", "")
            short_text = (text[:30] + "...") if len(text) > 30 else text
            likes    = post.get("like_count", 0)
            replies  = post.get("reply_count", 0)
            views = reposts = quotes = shares = 0

            # 嘗試抓貼文 insights
            # 官方文件回傳格式：{"data": [{"name": "likes", "values": [{"value": 100}]}]}
            try:
                insights_raw = _get(f"/{post_id}/insights", {
                    "metric": "views,likes,replies,reposts,quotes,shares",
                    "access_token": access_token
                })
                logger.info(f"貼文 {post_id} insights 原始回傳: {insights_raw}")
                for m in insights_raw.get("data", []):
                    name = m.get("name")
                    # 官方格式: values[0].value，fallback 到 total_value.value
                    if m.get("values") and len(m["values"]) > 0:
                        val = m["values"][0].get("value", 0)
                    else:
                        val = m.get("total_value", {}).get("value", 0)
                    if name == "views":     views   = val
                    elif name == "likes":   likes   = val
                    elif name == "replies": replies = val
                    elif name == "reposts": reposts = val
                    elif name == "quotes":  quotes  = val
                    elif name == "shares":  shares  = val
            except Exception as ei:
                logger.warning(f"貼文 {post_id} insights 失敗: {ei}")

            gws_client.sheets_append_row(post_tab, [today, post_id, text, likes, replies, views, reposts, quotes, shares])
            posts_data.append(f"- 「{short_text}」: 讚 {likes}, 回覆 {replies}, 瀏覽 {views}")

    except Exception as e:
        logger.error(f"抓取貼文失敗: {e}")
        return {"success": False, "error": f"抓取貼文失敗: {str(e)}"}

    if posts_data:
        summary_text += "\n近期貼文表現：\n" + "\n".join(posts_data)

    # ── 5. AI 洞察總結 ───────────────────────────────────────────────────────
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    prompt = f"""你是一位專業的社群營運私人秘書。以下是老闆今天最新的 Threads 帳號數據：
{summary_text}

請用簡潔、帶點鼓勵與專業洞察的語氣，寫一段大約 100~150 字的【今日 Threads 洞察總結】回報給老闆。
你可以指出哪種類型的貼文表現較好（例如讚數或瀏覽量較高），並給予發文方向的一個小建議。
請直接以對話形式回覆，不要加上任何 Markdown 標題、不用說這是一份報告。"""
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
        ai_insight = f"您的 Threads 數據已成功備份！\n{summary_text}"

    return {"success": True, "insight": ai_insight}
