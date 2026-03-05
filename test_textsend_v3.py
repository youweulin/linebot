import json
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, TextMessage, ReplyMessageRequest
msg = TextMessage(text="Hello v3")
try:
    req = ReplyMessageRequest(replyToken="dummy", messages=[msg])
    print(req.to_dict())
    print("Success")
except Exception as e:
    import traceback
    traceback.print_exc()
