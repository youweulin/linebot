import re

with open("main.py", "r") as f:
    text = f.read()

# remove unused TextSendMessage from the imports
text = text.replace("MessageEvent, TextMessage, TextSendMessage,", "MessageEvent, TextMessage,")

with open("main.py", "w") as f:
    f.write(text)

