import hmac
import hashlib
import base64
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()
secret = os.environ.get("LINE_CHANNEL_SECRET", "")
if not secret:
    print("No secret found")
    exit(1)

body = json.dumps({
    "events": [
        {
            "type": "message",
            "message": {
                "type": "text",
                "id": "1234567890",
                "text": "#待辦"
            },
            "timestamp": 1625665242211,
            "source": {
                "type": "user",
                "userId": "U1234567890"
            },
            "replyToken": "dummy_reply_token"
        }
    ]
})

hash = hmac.new(secret.encode('utf-8'), body.encode('utf-8'), hashlib.sha256).digest()
signature = base64.b64encode(hash).decode('utf-8')

res = requests.post("http://localhost:8081/webhook", data=body, headers={
    "Content-Type": "application/json",
    "X-Line-Signature": signature
})
print("Result Status:", res.status_code)
print("Result Body:", res.text)
