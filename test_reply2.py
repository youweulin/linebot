import traceback
import sys

try:
    from linebot import LineBotApi
    from linebot.models import TextSendMessage
    import json
    import os

    api = LineBotApi(os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "dummy"))
    msg = TextSendMessage(text="Hello")
    print(f"Type of msg: {type(msg)}")
    
    api.reply_message("dummy", msg)
except Exception as e:
    traceback.print_exc(file=sys.stdout)
