#!/bin/bash
source .venv/bin/activate
uvicorn main:app --port 8081 &
SERVER_PID=$!
sleep 3
python3 test_webhook.py
kill $SERVER_PID
