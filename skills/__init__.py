"""
Skills 插件自動註冊系統
===========================
每個 skill 是 skills/ 目錄下的一個 .py 檔案。
每個 skill 必須 export 兩樣東西：
  1. TOOL_DEF (dict) — OpenAI Function Calling 的 JSON Schema
  2. execute(args: dict, context: dict) -> str — 執行邏輯，回傳結果字串

使用方式：
  from skills import get_all_tools, run_skill
  tools = get_all_tools()          # 傳給 OpenAI
  result = run_skill("save_note", args, context)  # 執行某個 skill
"""

import importlib
import os
import logging

logger = logging.getLogger(__name__)

_registry: dict[str, dict] = {}  # name -> {"tool_def": ..., "execute": ...}


def _discover_skills():
    """掃描 skills/ 目錄下所有 .py 模組並自動註冊"""
    skills_dir = os.path.dirname(__file__)
    for filename in sorted(os.listdir(skills_dir)):
        if filename.startswith("_") or not filename.endswith(".py"):
            continue
        module_name = filename[:-3]
        try:
            mod = importlib.import_module(f"skills.{module_name}")
            if hasattr(mod, "TOOL_DEF") and hasattr(mod, "execute"):
                _registry[mod.TOOL_DEF["function"]["name"]] = {
                    "tool_def": mod.TOOL_DEF,
                    "execute": mod.execute,
                }
                logger.info("🔧 已載入 skill: %s", mod.TOOL_DEF["function"]["name"])
            else:
                logger.warning("⚠️ skills/%s 缺少 TOOL_DEF 或 execute，已跳過", filename)
        except Exception as e:
            logger.error("❌ 載入 skills/%s 失敗: %s", filename, e)


def get_all_tools() -> list[dict]:
    """回傳所有已註冊 skill 的 OpenAI tool 定義列表"""
    if not _registry:
        _discover_skills()
    return [s["tool_def"] for s in _registry.values()]


def run_skill(name: str, args: dict, context: dict) -> str:
    """根據名稱執行對應的 skill"""
    if not _registry:
        _discover_skills()
    skill = _registry.get(name)
    if not skill:
        return f"找不到名為 {name} 的技能"
    return skill["execute"](args, context)


def get_skill_names() -> list[str]:
    """回傳所有已註冊的 skill 名稱"""
    if not _registry:
        _discover_skills()
    return list(_registry.keys())
"""CodeContent"""
