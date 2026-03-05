from linebot import LineBotApi
from linebot.models import TextSendMessage
api = LineBotApi("dummy")
msg = TextSendMessage(text="Hello")
try:
    api.reply_message("dummy", msg)
except Exception as e:
    import traceback
    traceback.print_exc()
