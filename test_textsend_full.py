from linebot import LineBotApi
from linebot.models import TextSendMessage
api = LineBotApi("dummy")
msg = TextSendMessage(text="Test\nline2")
print(msg.as_json_dict())
