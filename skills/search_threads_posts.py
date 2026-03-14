"""
Skill: search_threads_posts
功能：使用官方 Threads Graph API 做關鍵字搜尋（keyword_search），並可限制只看「今天」的貼文。
"""

from __future__ import annotations

import os
import logging
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import requests

try:
    from zoneinfo import ZoneInfo  # py3.9+
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "search_threads_posts",
        "description": (
            "當使用者要求你「搜尋 Threads 貼文 / 找今天某關鍵字 / 找 propfirm 免費帳號相關貼文或頻道」時，"
            "呼叫此功能以使用官方 Threads API 進行 keyword search，並整理今天的貼文與頻道清單。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "要搜尋的主要關鍵字（例如：propfirm、免費帳號、free account）。",
                },
                "must_include": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "額外必須同時包含的關鍵字（全部都要出現才算命中）。例如：[\"免費\", \"account\"]",
                },
                "search_type": {
                    "type": "string",
                    "enum": ["RECENT", "TOP"],
                    "description": "搜尋類型：RECENT(最新) 或 TOP(熱門)。預設 RECENT。",
                },
                "today_only": {
                    "type": "boolean",
                    "description": "是否只回傳今天(依 timezone)的貼文。預設 true。",
                },
                "timezone": {
                    "type": "string",
                    "description": "日期判斷用時區（IANA TZ，如 Asia/Taipei）。預設 Asia/Taipei。",
                },
                "limit": {
                    "type": "integer",
                    "description": "最多取回幾篇結果（API limit）。預設 25。",
                },
                "max_show": {
                    "type": "integer",
                    "description": "回覆訊息最多顯示幾篇。預設 10。",
                },
            },
            "required": ["query"],
        },
    },
}

THREADS_API_BASE = "https://graph.threads.net/v1.0"


@dataclass(frozen=True)
class _TimeWindow:
    since: int | None
    until: int | None
    label: str


def _get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    res = requests.get(f"{THREADS_API_BASE}{path}", params=params, timeout=20)
    return res.json()


def _today_window(timezone: str) -> _TimeWindow:
    if ZoneInfo is None:
        now = datetime.now()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return _TimeWindow(since=int(start.timestamp()), until=int(now.timestamp()), label=start.strftime("%Y/%m/%d"))

    tz = ZoneInfo(timezone)
    now = datetime.now(tz)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return _TimeWindow(since=int(start.timestamp()), until=int(now.timestamp()), label=start.strftime("%Y/%m/%d"))


def _safe_parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    # API timestamps commonly look like "2026-03-14T01:23:45+0000" or "...Z"
    try:
        if ts.endswith("Z"):
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if ts.endswith("+0000") and ":" not in ts[-5:]:
            return datetime.fromisoformat(ts[:-5] + "+00:00")
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def execute(args: dict, context: dict) -> dict:
    access_token = os.environ.get("THREADS_ACCESS_TOKEN")
    if not access_token:
        return {"success": False, "error": "缺少 THREADS_ACCESS_TOKEN 環境變數（需要包含 threads_keyword_search 權限）"}

    query = (args.get("query") or "").strip()
    if not query:
        return {"success": False, "error": "沒有提供 query"}

    must_include = args.get("must_include") or []
    if not isinstance(must_include, list):
        must_include = []
    must_include_norm = [str(x).strip().lower() for x in must_include if str(x).strip()]

    search_type = (args.get("search_type") or "RECENT").strip().upper()
    if search_type not in ("RECENT", "TOP"):
        search_type = "RECENT"

    today_only = args.get("today_only")
    if today_only is None:
        today_only = True
    timezone = (args.get("timezone") or "Asia/Taipei").strip() or "Asia/Taipei"

    limit = args.get("limit")
    try:
        limit = int(limit) if limit is not None else 25
    except Exception:
        limit = 25
    limit = max(1, min(limit, 50))

    max_show = args.get("max_show")
    try:
        max_show = int(max_show) if max_show is not None else 10
    except Exception:
        max_show = 10
    max_show = max(1, min(max_show, 20))

    window = _today_window(timezone) if today_only else _TimeWindow(None, None, "")

    params: dict[str, Any] = {
        "q": query,
        "search_type": search_type,
        "fields": "id,username,text,timestamp,permalink,owner",
        "limit": limit,
        "access_token": access_token,
    }
    if window.since is not None:
        params["since"] = window.since
    if window.until is not None:
        params["until"] = window.until

    data = _get("/keyword_search", params)
    if "error" in data:
        err = data.get("error") or {}
        msg = err.get("message") or str(err) or "Threads API 回傳錯誤"
        hint = "（常見原因：Access Token 沒有開啟/授權 `threads_keyword_search` 權限）"
        return {"success": False, "error": f"{msg} {hint}"}

    items = data.get("data") or []
    if not isinstance(items, list):
        items = []

    def match_item(item: dict[str, Any]) -> bool:
        text = str(item.get("text") or "").lower()
        return all(k in text for k in must_include_norm)

    matched: list[dict[str, Any]] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        if must_include_norm and not match_item(raw):
            continue
        matched.append(raw)

    if not matched:
        today_label = f"（{window.label}）" if today_only and window.label else ""
        extra = f"，且需包含：{', '.join(must_include)}" if must_include_norm else ""
        return {"success": True, "reply": f"找不到符合「{query}」{today_label}的 Threads 貼文{extra}。", "count": 0}

    # 頻道統計
    usernames = [str(x.get("username") or "").strip() for x in matched if str(x.get("username") or "").strip()]
    top_channels = Counter(usernames).most_common(8)

    # 組回覆文字
    show = matched[:max_show]
    lines: list[str] = []
    today_label = f"{window.label} " if today_only and window.label else ""
    extra = f"；且需包含：{', '.join(must_include)}" if must_include_norm else ""
    lines.append(f"找到 {len(matched)} 篇符合「{query}」的 Threads 貼文（{today_label}{search_type}）{extra}，顯示前 {len(show)} 篇：")

    for i, it in enumerate(show, start=1):
        username = str(it.get("username") or "").strip() or "unknown"
        ts_raw = it.get("timestamp")
        dt = _safe_parse_ts(str(ts_raw) if ts_raw else None)
        ts_disp = dt.strftime("%m/%d %H:%M") if dt else ""
        text = str(it.get("text") or "").replace("\n", " ").strip()
        snippet = (text[:60] + "…") if len(text) > 60 else text
        permalink = str(it.get("permalink") or "").strip()
        if permalink:
            lines.append(f"{i}) @{username} {ts_disp}｜{snippet}\n{permalink}")
        else:
            lines.append(f"{i}) @{username} {ts_disp}｜{snippet}")

    if top_channels:
        channel_str = "、".join([f"@{u}({c})" for u, c in top_channels if u])
        if channel_str:
            lines.append(f"\n可能相關的頻道/帳號（出現次數）：{channel_str}")

    return {
        "success": True,
        "count": len(matched),
        "query": query,
        "reply": "\n".join(lines).strip(),
        "channels": [{"username": u, "count": c} for u, c in top_channels],
        "posts": [
            {
                "id": it.get("id"),
                "username": it.get("username"),
                "timestamp": it.get("timestamp"),
                "permalink": it.get("permalink"),
                "text": it.get("text"),
            }
            for it in show
        ],
    }

