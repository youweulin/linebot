"""Test gws_client.py locally"""
import json
from dotenv import load_dotenv
load_dotenv()
import gws_client

# Test 1: 列出所有分頁
tabs = gws_client.sheets_get_tab_names()
print("All tabs:", tabs)

# Test 2: 讀取工作表1前3行
values = gws_client.sheets_get_values("工作表1!A1:D3")
print("First 3 rows:", json.dumps(values, ensure_ascii=False, indent=2))

# Test 3: 讀取待辦清單
records = gws_client.get_recent_records("✅ 待辦清單", limit=3)
print("Tasks:", json.dumps(records, ensure_ascii=False, indent=2))

# Test 4: 追加測試行
ok = gws_client.sheets_append_row("📝 筆記本", ["2026/03/05 21:45", "gws test note"])
print("Append result:", ok)
