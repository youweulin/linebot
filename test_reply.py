import traceback
from linebot import LineBotApi
from linebot.models import TextSendMessage

api = LineBotApi("dummy_token")
msg = TextSendMessage(text="Hello")
try:
    api.reply_message("dummy_reply_token", msg)
except Exception as e:
    traceback.print_exc()
