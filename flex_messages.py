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


def get_backup_receipt_flex(filename: str, tags: str, time_str: str, file_url: str, folder_url: str = "", folder_label: str = "📁 開啟雲端資料夾") -> FlexSendMessage:
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
    }
    # 動態建構 footer 按鈕（只有合法 URI 才建立按鈕）
    footer_buttons = []
    if file_url and file_url.startswith("http"):
        footer_buttons.append({
            "type": "button",
            "style": "primary",
            "color": "#000000",
            "action": {"type": "uri", "label": "📂 開啟檔案", "uri": file_url}
        })
    if folder_url and folder_url.startswith("http"):
        footer_buttons.append({
            "type": "button",
            "style": "secondary",
            "action": {"type": "uri", "label": folder_label, "uri": folder_url}
        })
    if footer_buttons:
        bubble["footer"] = {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": footer_buttons
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


# ══════════════════════════════════════════════════════════════════════════════
# 百寶箱查詢：Carousel UI
# ══════════════════════════════════════════════════════════════════════════════
def _get_empty_carousel(title: str, message: str) -> FlexSendMessage:
    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": title, "weight": "bold", "size": "xl"},
                {"type": "text", "text": message, "margin": "md", "color": "#888888"}
            ]
        }
    }
    return FlexSendMessage(alt_text=message, contents={"type": "carousel", "contents": [bubble]})

def get_expense_carousel(records: list[dict], sheet_url: str) -> FlexSendMessage:
    if not records:
        return _get_empty_carousel("💰 記帳本", "目前沒有記帳紀錄喔！")
    bubbles = []
    for r in records:
        b = {
            "type": "bubble",
            "size": "micro",
            "header": {"type": "box", "layout": "vertical", "backgroundColor": "#FF7E67", "contents": [{"type": "text", "text": "💰 花費", "color": "#FFFFFF", "weight": "bold"}]},
            "body": {
                "type": "box", "layout": "vertical", "contents": [
                    {"type": "text", "text": str(r.get("項目", "")) or " ", "weight": "bold", "size": "lg", "wrap": True},
                    {"type": "text", "text": f"${r.get('金額', '')}" if str(r.get('金額', '')) else " ", "color": "#FF3333", "weight": "bold", "size": "xl"},
                    {"type": "text", "text": str(r.get("紀錄時間", "")) or " ", "color": "#aaaaaa", "size": "xs", "margin": "md"},
                    {"type": "text", "text": str(r.get("類別", "")) or " ", "color": "#aaaaaa", "size": "xs"}
                ]
            }
        }
        bubbles.append(b)
    # 最後一頁放開啟 Sheet 按鈕
    bubbles.append({
        "type": "bubble", "size": "micro",
        "body": {"type": "box", "layout": "vertical", "justifyContent": "center", "alignItems": "center", "contents": [{"type": "button", "style": "primary", "color": "#1DB446", "action": {"type": "uri", "label": "開啟完整帳本", "uri": sheet_url}}]}
    })
    return FlexSendMessage(alt_text="💰 近期記帳紀錄", contents={"type": "carousel", "contents": bubbles})


def get_task_carousel(records: list[dict], sheet_url: str) -> FlexSendMessage:
    if not records:
        return _get_empty_carousel("✅ 待辦清單", "目前沒有待辦事項，太棒了！")
    bubbles = []
    for r in records:
        status = str(r.get("狀態(未完成/已完成)", "未完成"))
        color = "#1DB446" if "已完成" in status else "#FF7E67"
        b = {
            "type": "bubble",
            "size": "micro",
            "header": {"type": "box", "layout": "vertical", "backgroundColor": "#4B89DC", "contents": [{"type": "text", "text": "✅ 任務", "color": "#FFFFFF", "weight": "bold"}]},
            "body": {
                "type": "box", "layout": "vertical", "contents": [
                    {"type": "text", "text": str(r.get("待辦事項", "")) or " ", "weight": "bold", "size": "md", "wrap": True},
                    {"type": "text", "text": f"期限: {r.get('預計完成日', '無')}" or " ", "color": "#666666", "size": "xs", "margin": "sm"},
                    {"type": "text", "text": status or " ", "color": color, "weight": "bold", "size": "sm", "margin": "md"}
                ]
            }
        }
        bubbles.append(b)
    bubbles.append({
        "type": "bubble", "size": "micro",
        "body": {"type": "box", "layout": "vertical", "justifyContent": "center", "alignItems": "center", "contents": [{"type": "button", "style": "primary", "color": "#1DB446", "action": {"type": "uri", "label": "前往打勾", "uri": sheet_url}}]}
    })
    return FlexSendMessage(alt_text="✅ 近期待辦清單", contents={"type": "carousel", "contents": bubbles})


def get_event_carousel(records: list[dict], sheet_url: str) -> FlexSendMessage:
    if not records:
        return _get_empty_carousel("📅 行事曆", "近期沒有排定的行程喔！")
    bubbles = []
    for r in records:
        b = {
            "type": "bubble",
            "size": "micro",
            "header": {"type": "box", "layout": "vertical", "backgroundColor": "#967ADC", "contents": [{"type": "text", "text": "📅 排程", "color": "#FFFFFF", "weight": "bold"}]},
            "body": {
                "type": "box", "layout": "vertical", "contents": [
                    {"type": "text", "text": str(r.get("事件名稱", "")) or " ", "weight": "bold", "size": "md", "wrap": True},
                    {"type": "text", "text": str(r.get("事件日期", "")) or " ", "color": "#1DB446", "size": "sm", "weight": "bold", "margin": "sm"},
                    {"type": "text", "text": str(r.get("事件時間", "")) or " ", "color": "#666666", "size": "xs"},
                    {"type": "text", "text": str(r.get("備註", ""))[:20] or " ", "color": "#aaaaaa", "size": "xs", "margin": "sm"}
                ]
            }
        }
        bubbles.append(b)
    bubbles.append({
        "type": "bubble", "size": "micro",
        "body": {"type": "box", "layout": "vertical", "justifyContent": "center", "alignItems": "center", "contents": [{"type": "button", "style": "primary", "color": "#1DB446", "action": {"type": "uri", "label": "開啟行事曆", "uri": sheet_url}}]}
    })
    return FlexSendMessage(alt_text="📅 近期行程", contents={"type": "carousel", "contents": bubbles})


def get_contact_carousel(records: list[dict], sheet_url: str) -> FlexSendMessage:
    if not records:
        return _get_empty_carousel("📇 通訊錄", "目前通訊錄是空的喔！")
    bubbles = []
    for r in records:
        phone = str(r.get("電話", ""))
        email = str(r.get("Email", ""))
        buttons = []
        if phone:
            tel_uri = f"tel:{phone.replace(' ', '').replace('-', '')}"
            buttons.append({"type": "button", "style": "secondary", "height": "sm", "margin": "sm", "action": {"type": "uri", "label": "📞 撥號", "uri": tel_uri}})
        if email:
            buttons.append({"type": "button", "style": "secondary", "height": "sm", "margin": "sm", "action": {"type": "uri", "label": "📩 寫信", "uri": f"mailto:{email}"}})

        body_contents = [
            {"type": "text", "text": str(r.get("公司", "")) or " ", "color": "#888888", "size": "xs"},
            {"type": "text", "text": str(r.get("姓名", "")) or "未知", "weight": "bold", "size": "xl", "margin": "md"},
            {"type": "text", "text": str(r.get("職稱", "")) or " ", "color": "#666666", "size": "sm"},
            {"type": "text", "text": str(r.get("行業類別", "")) or " ", "color": "#1DB446", "size": "xs", "margin": "sm", "weight": "bold"},
            {"type": "text", "text": str(r.get("業務總結", "")) or " ", "color": "#aaaaaa", "size": "xs", "wrap": True}
        ]
        if buttons:
            body_contents.append({"type": "box", "layout": "vertical", "margin": "lg", "contents": buttons})

        b = {
            "type": "bubble",
            "size": "kilo",
            "body": {
                "type": "box", "layout": "vertical", "contents": body_contents
            }
        }
        bubbles.append(b)
    bubbles.append({
        "type": "bubble", "size": "micro",
        "body": {"type": "box", "layout": "vertical", "justifyContent": "center", "alignItems": "center", "contents": [{"type": "button", "style": "primary", "color": "#1DB446", "action": {"type": "uri", "label": "看完整名片", "uri": sheet_url}}]}
    })
    return FlexSendMessage(alt_text="📇 通訊錄", contents={"type": "carousel", "contents": bubbles})


def get_note_carousel(records: list[dict], sheet_url: str) -> FlexSendMessage:
    if not records:
        return _get_empty_carousel("📝 筆記本", "目前沒有筆記喔！")
    bubbles = []
    for r in records:
        note_content = str(r.get("筆記內容", ""))
        display_content = (note_content[:50] + "...") if len(note_content) > 50 else note_content
        b = {
            "type": "bubble",
            "size": "micro",
            "header": {"type": "box", "layout": "vertical", "backgroundColor": "#F3C13A", "contents": [{"type": "text", "text": "📝 筆記", "color": "#FFFFFF", "weight": "bold"}]},
            "body": {
                "type": "box", "layout": "vertical", "contents": [
                    {"type": "text", "text": display_content or " ", "size": "md", "wrap": True},
                    {"type": "text", "text": str(r.get("紀錄時間", "")) or " ", "color": "#aaaaaa", "size": "xs", "margin": "md"}
                ]
            }
        }
        bubbles.append(b)
    bubbles.append({
        "type": "bubble", "size": "micro",
        "body": {"type": "box", "layout": "vertical", "justifyContent": "center", "alignItems": "center", "contents": [{"type": "button", "style": "primary", "color": "#1DB446", "action": {"type": "uri", "label": "開啟筆記本", "uri": sheet_url}}]}
    })
    return FlexSendMessage(alt_text="📝 近期筆記", contents={"type": "carousel", "contents": bubbles})
