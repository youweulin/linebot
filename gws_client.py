"""
gws_client — Google Workspace CLI 封裝層
=========================================
透過 subprocess 呼叫 gws CLI 操作 Google Sheets / Drive。
取代原本的 gspread + google-api-python-client。

環境變數：
  GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE  → SA 金鑰 JSON 路徑
  GOOGLE_SHEET_ID                        → 預設試算表 ID
"""

import json
import logging
import os
import subprocess

import tempfile

logger = logging.getLogger(__name__)

def _get_sheet_id() -> str:
    return os.getenv("GOOGLE_SHEET_ID", "")

def _get_creds_file() -> str:
    creds_file = os.getenv("GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE", "")
    if creds_file:
        return creds_file
    
    # 自動從 GOOGLE_CREDENTIALS_JSON 產生憑證檔案
    creds_json_str = os.getenv("GOOGLE_CREDENTIALS_JSON", "").strip()
    if creds_json_str and creds_json_str != "{}" and creds_json_str != "''":
        if creds_json_str.startswith("'") and creds_json_str.endswith("'"):
            creds_json_str = creds_json_str[1:-1]
        try:
            json.loads(creds_json_str) # 驗證格式
            temp_file = os.path.join(tempfile.gettempdir(), "gws-sa-key.json")
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(creds_json_str)
            return temp_file
        except Exception as e:
            logger.error("🛑 解析 GOOGLE_CREDENTIALS_JSON 失敗: %s", e)
    return ""


def _run_gws(*args: str, input_data: str | None = None) -> dict | list | None:
    """
    執行 gws 指令並回傳解析後的 JSON。
    所有 gws 回傳都是 JSON，直接 parse。
    """
    env = os.environ.copy()
    
    creds_file = _get_creds_file()
    if creds_file:
        env["GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE"] = creds_file

    cmd = ["gws", *args]
    logger.debug("🔧 gws 指令: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
            input=input_data,
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip()
            logger.error("🛑 gws 執行失敗 (code %d): %s", result.returncode, error_msg)
            # 嘗試解析 JSON 格式的錯誤
            try:
                err_json = json.loads(error_msg)
                return err_json
            except json.JSONDecodeError:
                return {"error": {"message": error_msg}}

        output = result.stdout.strip()
        if not output:
            return {}

        return json.loads(output)

    except subprocess.TimeoutExpired:
        logger.error("🛑 gws 指令超時 (30s)")
        return {"error": {"message": "gws command timeout"}}
    except FileNotFoundError:
        logger.error("🛑 找不到 gws 指令，請確認已安裝 @googleworkspace/cli")
        return {"error": {"message": "gws not found"}}
    except json.JSONDecodeError as e:
        logger.error("🛑 gws 回傳非 JSON: %s", e)
        return {"error": {"message": f"Invalid JSON: {e}"}}


# ══════════════════════════════════════════════════════════════════════════════
# Google Sheets 操作
# ══════════════════════════════════════════════════════════════════════════════

def sheets_get_values(range_str: str, sheet_id: str = "") -> list[list[str]]:
    """
    讀取 Sheets 指定範圍的值。
    回傳二維陣列 [[row1_col1, row1_col2, ...], [row2_col1, ...], ...]
    """
    sid = sheet_id or _get_sheet_id()
    result = _run_gws(
        "sheets", "spreadsheets", "values", "get",
        "--params", json.dumps({
            "spreadsheetId": sid,
            "range": range_str,
        })
    )
    if not result or "error" in result:
        logger.error("Sheets 讀取失敗: %s", result)
        return []
    return result.get("values", [])


def sheets_append_row(tab_name: str, values: list, sheet_id: str = "") -> bool:
    """
    追加一行到指定分頁。
    values: [col1, col2, col3, ...]
    """
    sid = sheet_id or _get_sheet_id()
    # 將所有值轉成字串
    str_values = [str(v) for v in values]
    result = _run_gws(
        "sheets", "spreadsheets", "values", "append",
        "--params", json.dumps({
            "spreadsheetId": sid,
            "range": f"{tab_name}!A1",
            "valueInputOption": "USER_ENTERED",
        }),
        "--json", json.dumps({
            "values": [str_values]
        })
    )
    if not result or "error" in result:
        logger.error("Sheets 追加行失敗: %s", result)
        return False
    logger.info("✅ Sheets 已追加一行到 %s", tab_name)
    return True


def sheets_get_all_values(tab_name: str, sheet_id: str = "") -> list[list[str]]:
    """
    讀取指定分頁的所有值（A:Z 全範圍）。
    """
    sid = sheet_id or _get_sheet_id()
    return sheets_get_values(f"{tab_name}!A:Z", sid)


def sheets_get_tab_names(sheet_id: str = "") -> list[str]:
    """
    列出試算表的所有分頁名稱。
    """
    sid = sheet_id or _get_sheet_id()
    result = _run_gws(
        "sheets", "spreadsheets", "get",
        "--params", json.dumps({
            "spreadsheetId": sid,
            "fields": "sheets.properties.title",
        })
    )
    if not result or "error" in result:
        logger.error("列出分頁失敗: %s", result)
        return []
    sheets = result.get("sheets", [])
    return [s.get("properties", {}).get("title", "") for s in sheets]


def sheets_create_tab(tab_name: str, sheet_id: str = "") -> bool:
    """
    建立新的分頁。
    """
    sid = sheet_id or _get_sheet_id()
    result = _run_gws(
        "sheets", "spreadsheets", "batchUpdate",
        "--params", json.dumps({"spreadsheetId": sid}),
        "--json", json.dumps({
            "requests": [{
                "addSheet": {
                    "properties": {"title": tab_name}
                }
            }]
        })
    )
    if not result or "error" in result:
        logger.error("建立分頁 %s 失敗: %s", tab_name, result)
        return False
    logger.info("🆕 已建立分頁: %s", tab_name)
    return True


def get_or_create_tab(tab_name: str, headers: list[str] = [], sheet_id: str = ""):
    """
    取得或自動建立指定名稱的分頁。
    如果分頁不存在，會自動建立並寫入標題列。
    回傳 tab_name（成功）或 None（失敗）。
    """
    sid = sheet_id or _get_sheet_id()
    existing_tabs = sheets_get_tab_names(sid)

    if tab_name not in existing_tabs:
        logger.info("🆕 分頁 %s 不存在，自動建立...", tab_name)
        if not sheets_create_tab(tab_name, sid):
            return None
        if headers:
            sheets_append_row(tab_name, headers, sid)

    return tab_name


def get_recent_records(tab_name: str, headers: list[str] = [], limit: int = 5, sheet_id: str = "") -> list[dict]:
    """
    從指定分頁取得最新 N 筆資料（反排序）並封裝成字典的 List。
    如果分頁不存在，會自動建立空分頁然後回傳空 List。
    """
    sid = sheet_id or _get_sheet_id()

    # 確保分頁存在
    tab = get_or_create_tab(tab_name, headers, sid)
    if not tab:
        return []

    try:
        values = sheets_get_all_values(tab_name, sid)
        if not values or len(values) < 2:
            return []

        sheet_headers = values[0]
        records = []
        for row in values[1:]:
            # 將資料列補齊長度
            row_data = row + [""] * (len(sheet_headers) - len(row))
            records.append(dict(zip(sheet_headers, row_data)))

        # 反序排列，最新的在前面
        records.reverse()
        return records[:limit]
    except Exception as e:
        logger.error("讀取分頁 %s 失敗: %s", tab_name, e)
        return []


# ══════════════════════════════════════════════════════════════════════════════
# Google Drive 操作
# ══════════════════════════════════════════════════════════════════════════════

def drive_upload(filepath: str, folder_id: str, filename: str, mime_type: str = "application/octet-stream") -> str | None:
    """
    上傳檔案到 Google Drive。
    回傳 webViewLink 或 None。
    """
    metadata = {"name": filename}
    if folder_id:
        metadata["parents"] = [folder_id]

    result = _run_gws(
        "drive", "files", "create",
        "--json", json.dumps(metadata),
        "--upload", filepath,
        "--params", json.dumps({"fields": "id,webViewLink"}),
    )
    if not result or "error" in result:
        logger.error("Drive 上傳失敗: %s", result)
        return None

    file_id = result.get("id", "")
    link = result.get("webViewLink", "")

    # 設定公開權限
    if file_id:
        drive_set_public(file_id)

    logger.info("✅ Drive 上傳成功: %s → %s", filename, link)
    return link


def drive_set_public(file_id: str) -> bool:
    """
    設定 Drive 檔案為「任何人可檢視」。
    """
    result = _run_gws(
        "drive", "permissions", "create",
        "--params", json.dumps({"fileId": file_id}),
        "--json", json.dumps({"type": "anyone", "role": "reader"}),
    )
    if not result or "error" in result:
        logger.error("Drive 權限設定失敗: %s", result)
        return False
    return True
