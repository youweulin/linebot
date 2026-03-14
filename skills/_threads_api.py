from __future__ import annotations

import os
from typing import Any

import requests

THREADS_API_BASE = "https://graph.threads.net/v1.0"
THREADS_REFRESH_ENDPOINT = "https://graph.threads.net/refresh_access_token"


def threads_get(path: str, params: dict[str, Any], timeout: int = 20) -> dict[str, Any]:
    res = requests.get(f"{THREADS_API_BASE}{path}", params=params, timeout=timeout)
    return res.json()


def is_token_error(data: dict[str, Any]) -> bool:
    err = (data or {}).get("error") or {}
    try:
        code = int(err.get("code")) if err.get("code") is not None else None
    except Exception:
        code = None
    msg = str(err.get("message") or "").lower()
    # Meta commonly uses code=190 for invalid/expired tokens.
    return code == 190 or ("validating access token" in msg) or ("session has expired" in msg)


def error_message(data: dict[str, Any]) -> str:
    err = (data or {}).get("error") or {}
    msg = err.get("message") or ""
    return str(msg) if msg else str(err) if err else "Threads API 回傳錯誤"


def refresh_access_token(access_token: str) -> dict[str, Any]:
    """
    嘗試刷新 long-lived access token（如果 token 已過期，通常會刷新失敗並回傳 error）。
    成功回傳格式一般含：access_token, token_type, expires_in
    """
    params = {"grant_type": "th_refresh_token", "access_token": access_token}
    res = requests.get(THREADS_REFRESH_ENDPOINT, params=params, timeout=20)
    return res.json()


def set_runtime_access_token(new_token: str) -> None:
    # 只會影響當前行程（不會寫回 Zeabur/系統環境變數）
    os.environ["THREADS_ACCESS_TOKEN"] = new_token

