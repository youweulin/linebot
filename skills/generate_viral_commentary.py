"""
Skill: generate_viral_commentary
功能：根據社群爆紅文章或他人貼文，以使用者的「交易心法與紀律」視角，產出一篇高價值延伸評論。
"""

import os
from openai import OpenAI

TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "generate_viral_commentary",
        "description": "當使用者傳送社群貼文內容（例如 Threads 上的別人的崩潰文、抱怨文）、或是要求你對某個市場觀點發表評論時呼叫此功能。它會自動幫使用者寫出一篇準備發到 Threads 上的高價值評論草稿。",
        "parameters": {
            "type": "object",
            "properties": {
                "source_content": {
                    "type": "string",
                    "description": "其他人原始的貼文內容、你想評論的主題或抱怨。"
                }
            },
            "required": ["source_content"]
        }
    }
}

def execute(args: dict, context: dict) -> dict:
    source = args.get("source_content", "")
    if not source:
        return {"success": False, "error": "需要提供原始貼文內容才能進行評論喔！"}
        
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    
    prompt = f"""
你現在是一位經驗豐富、曾經歷過大戶洗盤、繳過無數學費，現在領悟「臣服市場、依靠客觀紀律系統（如 PFLock）」的職業交易員。
你的語氣特徵是：
- 開頭喜歡一針見血地點出散戶痛點（例如上頭、凹單、過度交易）。
- 會以「過來人」的同理心安撫，但語氣充滿「殘酷的現實感」，不用過多的華麗文藻，用最直白真實的話。
- 強調「紀律無法靠意志力，必須靠外在框架（如 PFLock 等系統）來保護自己」。

現在有一篇社群上的熱門貼文（或市場現象討論）：
"{source}"

請根據上述內容，寫出一篇約 150~250 字的 Threads 評論/延伸貼文草稿。
（結尾加上相關的 hashtags，如 #交易心理 #停損 #紀律）
這只是一份草稿，請純粹輸出貼文內容本身，『絕對不要』包含「這是一份為您草擬的貼文」之類的開場白或結尾廢話！
"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=600
        )
        draft = response.choices[0].message.content.strip()
        
        reply_message = f"✍️ 這是幫你寫的高價值延伸評論草稿：\n\n---\n{draft}\n---\n\n✅ 如果你覺得這篇寫得不錯，請直接回覆：\n「發布 Threads: {draft[:15]}...」"
        
        return {"success": True, "draft": draft, "reply_message": reply_message}
    except Exception as e:
        return {"success": False, "error": str(e)}
