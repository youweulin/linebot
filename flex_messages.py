from linebot.models import FlexSendMessage
import json

def get_welcome_flex() -> FlexSendMessage:
    """產生主選單 (Dashboard) 的 Flex Message"""
    bubble = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "🛡️ 您的專屬雲端保險箱",
                    "weight": "bold",
                    "size": "lg",
                    "color": "#1DB446"
                }
            ],
            "paddingAll": "20px",
            "backgroundColor": "#F4F6F8"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "歡迎！我可以幫您：",
                    "weight": "bold",
                    "size": "md",
                    "margin": "md"
                },
                {
                    "type": "text",
                    "text": "1. 收到照片/檔案自動存入 Google Drive\n2. AI 自動看圖幫您貼標籤\n3. 用對話語意隨時搜出歷史檔案",
                    "wrap": True,
                    "size": "sm",
                    "color": "#666666",
                    "margin": "sm"
                }
            ],
            "paddingAll": "20px"
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "height": "sm",
                    "color": "#1DB446",
                    "action": {
                        "type": "message",
                        "label": "🔍 試試搜尋功能",
                        "text": "幫我找上次那張發票"
                    }
                },
                {
                    "type": "button",
                    "style": "secondary",
                    "height": "sm",
                    "action": {
                        "type": "message",
                        "label": "📂 如何備份檔案？",
                        "text": "只要把照片、影片或檔案直接傳給我，我就會自動幫您打包存進雲端囉！"
                    }
                }
            ],
            "paddingAll": "20px"
        }
    }
    return FlexSendMessage(alt_text="雲端小秘書主選單", contents=bubble)


def get_backup_receipt_flex(filename: str, tags: str, time_str: str, file_url: str) -> FlexSendMessage:
    """產生備份成功的收據 Flex Message"""
    bubble = {
        "type": "bubble",
        "size": "mega",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "✅ 歸檔成功",
                    "weight": "bold",
                    "color": "#1DB446",
                    "size": "sm"
                },
                {
                    "type": "text",
                    "text": "已安全存入 Google Drive",
                    "weight": "bold",
                    "size": "xl",
                    "margin": "md"
                },
                {
                    "type": "separator",
                    "margin": "xxl"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "xxl",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "檔名",
                                    "size": "sm",
                                    "color": "#aaaaaa",
                                    "flex": 1
                                },
                                {
                                    "type": "text",
                                    "text": filename,
                                    "size": "sm",
                                    "color": "#111111",
                                    "flex": 3,
                                    "wrap": True
                                }
                            ]
                        },
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "標籤",
                                    "size": "sm",
                                    "color": "#aaaaaa",
                                    "flex": 1
                                },
                                {
                                    "type": "text",
                                    "text": tags,
                                    "size": "sm",
                                    "color": "#1DB446",
                                    "weight": "bold",
                                    "flex": 3,
                                    "wrap": True
                                }
                            ]
                        },
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "時間",
                                    "size": "sm",
                                    "color": "#aaaaaa",
                                    "flex": 1
                                },
                                {
                                    "type": "text",
                                    "text": time_str,
                                    "size": "sm",
                                    "color": "#111111",
                                    "flex": 3
                                }
                            ]
                        }
                    ]
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": "#000000",
                    "action": {
                        "type": "uri",
                        "label": "📂 開啟檔案",
                        "uri": file_url
                    }
                }
            ]
        }
    }
    return FlexSendMessage(alt_text="備份成功收據", contents=bubble)


def get_search_result_flex(keyword: str, file_url: str) -> FlexSendMessage:
    """產生檔案搜尋成功的 Flex Message"""
    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "🎉 AI 為您找到了！",
                    "weight": "bold",
                    "color": "#1DB446",
                    "size": "md"
                },
                {
                    "type": "text",
                    "text": "搜尋結果",
                    "weight": "bold",
                    "size": "xl",
                    "margin": "md"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "lg",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "box",
                            "layout": "baseline",
                            "spacing": "sm",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "命中語意",
                                    "color": "#aaaaaa",
                                    "size": "sm",
                                    "flex": 2
                                },
                                {
                                    "type": "text",
                                    "text": keyword,
                                    "wrap": True,
                                    "color": "#666666",
                                    "size": "sm",
                                    "flex": 5
                                }
                            ]
                        }
                    ]
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": "#1DB446",
                    "action": {
                        "type": "uri",
                        "label": "⬇️ 立即開啟此檔案",
                        "uri": file_url
                    }
                }
            ],
            "flex": 0
        }
    }
    return FlexSendMessage(alt_text=f"找到檔案: {keyword}", contents=bubble)
