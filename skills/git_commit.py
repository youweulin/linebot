"""
Skill: git_commit
功能：將專案中的變更進行 git add . 與 git commit，並推送到遠端倉庫。
"""

TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "git_commit",
        "description": "當使用者要求幫忙 commit、提交程式碼、或者將目前變更推送到 git 時呼叫此功能。例如：「幫我 commit：修好某個 bug」「把目前的進度推上去」。",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Commit 訊息，描述這次變更的內容。如果使用者沒給，請你根據對話內容產生一個簡短的描述。"
                },
                "push": {
                    "type": "boolean",
                    "description": "是否要同時執行 git push。預設為 true。",
                    "default": True
                }
            },
            "required": ["message"]
        }
    }
}

def execute(args: dict, context: dict) -> dict:
    """
    執行 git commit 邏輯。
    """
    import subprocess
    import os
    from datetime import datetime
    
    message = args.get("message", "Update from LINE Bot")
    do_push = args.get("push", True)
    cwd = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # 假設在 skills/ 之下

    try:
        # 1. git add .
        add_res = subprocess.run(["git", "add", "."], cwd=cwd, capture_output=True, text=True)
        if add_res.returncode != 0:
            return {"success": False, "error": f"git add 失敗: {add_res.stderr}"}

        # 2. git commit -m
        commit_res = subprocess.run(["git", "commit", "-m", message], cwd=cwd, capture_output=True, text=True)
        
        # 如果沒有東西可以 commit，commit 會回傳 1
        if commit_res.returncode != 0 and "nothing to commit" not in commit_res.stdout:
            return {"success": False, "error": f"git commit 失敗: {commit_res.stderr or commit_res.stdout}"}

        status = "committed"
        output = commit_res.stdout

        # 3. git push (optional)
        if do_push:
            push_res = subprocess.run(["git", "push"], cwd=cwd, capture_output=True, text=True)
            if push_res.returncode != 0:
                 return {"success": True, "status": "committed but push failed", "error": push_res.stderr, "commit_msg": message}
            status = "committed and pushed"

        return {
            "success": True,
            "status": status,
            "commit_msg": message,
            "output": output,
            "time_str": datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        }

    except Exception as e:
        return {"success": False, "error": str(e)}
