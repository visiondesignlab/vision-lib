#!/usr/bin/env python3
"""Send one signed Feishu notification after a Pages workflow finishes."""

import base64
import hashlib
import hmac
import json
import os
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def signature(secret, timestamp):
    key = f"{timestamp}\n{secret}".encode()
    return base64.b64encode(hmac.new(key, b"", hashlib.sha256).digest()).decode()


def commit_lines(event, limit=5):
    commits = event.get("commits") or []
    if not commits and event.get("head_commit"):
        commits = [event["head_commit"]]
    lines = []
    for commit in reversed(commits[-limit:]):
        subject = str(commit.get("message", "")).splitlines()
        subject = subject[0][:200] if subject else "无提交说明"
        lines.append(f"• {subject}")
    if len(commits) > limit:
        lines.append(f"另有 {len(commits) - limit} 条提交。")
    return lines


def message(event, env):
    build = env.get("BUILD_RESULT", "unknown")
    deploy = env.get("DEPLOY_RESULT", "unknown")
    success = build == "success" and deploy == "success"
    statuses = {"success": "成功", "failure": "失败", "cancelled": "已取消", "skipped": "未执行", "unknown": "未知"}
    repo = env["GITHUB_REPOSITORY"]
    server = env.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    sha = env.get("GITHUB_SHA", "")[:7]
    changes = commit_lines(event)
    body = f"操作人：{env.get('GITHUB_ACTOR', '未知')} • {sha}\n\n最新改动：\n"
    body += "\n".join(changes or ["手动发布当前版本。"])
    if not success:
        body += f"\n\n构建：{statuses.get(build, '未知')} · Pages：{statuses.get(deploy, '未知')}"
    owner, name = repo.split("/", 1)
    pages_url = env.get("PAGES_URL") or f"https://{owner}.github.io/{name}/"
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "blue" if success else "orange",
            "title": {"tag": "plain_text", "content": "Vision Lab · 发布成功" if success else "Vision Lab · 发布未完成"},
        },
        "elements": [
            {"tag": "div", "text": {"tag": "plain_text", "content": body}},
            {"tag": "action", "actions": [
                {"tag": "button", "text": {"tag": "plain_text", "content": "在线查看"},
                 "type": "primary", "url": pages_url},
                {"tag": "button", "text": {"tag": "plain_text", "content": "仓库地址"},
                 "type": "default", "url": f"{server}/{repo}"},
            ]},
        ],
    }


def load_event(env):
    with open(env["GITHUB_EVENT_PATH"], encoding="utf-8") as file:
        event = json.load(file)
    # Actions push payloads may omit the commits array. Read the checked-out range.
    if env.get("GITHUB_EVENT_NAME") == "push" and not event.get("commits"):
        before, after = event.get("before", ""), env.get("GITHUB_SHA", "")
        valid_sha = lambda value: len(value) == 40 and all(c in "0123456789abcdef" for c in value.lower())
        if valid_sha(after):
            revision = f"{before}..{after}" if valid_sha(before) and set(before) != {"0"} else after
            try:
                result = subprocess.run(["git", "log", "--reverse", "--format=%H%x09%s", revision, "--"],
                                        check=True, capture_output=True, text=True, timeout=20)
                event["commits"] = [{"id": row.split("\t", 1)[0], "message": row.split("\t", 1)[1]}
                                    for row in result.stdout.splitlines() if "\t" in row]
            except (subprocess.SubprocessError, OSError):
                pass  # head_commit remains available as the fallback.
    return event


def send(webhook, secret, card, now=None):
    target = urlparse(webhook)
    if target.scheme != "https" or target.netloc != "open.feishu.cn" or not target.path.startswith("/open-apis/bot/v2/hook/"):
        raise ValueError("飞书 Webhook 地址无效")
    if not secret:
        raise ValueError("缺少飞书签名配置")
    timestamp = str(int(time.time() if now is None else now))
    payload = {"timestamp": timestamp, "sign": signature(secret, timestamp),
               "msg_type": "interactive", "card": card}
    request = Request(webhook, data=json.dumps(payload, ensure_ascii=False).encode(),
                      headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=20) as response:
            result = json.load(response)
    except (URLError, TimeoutError, ValueError, OSError):
        # Do not print exception URLs (they contain the bot credential), or retry
        # an ambiguous timeout that might already have delivered the message.
        raise RuntimeError("飞书通知请求未确认成功，请检查本次运行和群消息后再重试") from None
    if result.get("code") != 0:
        raise RuntimeError(f"飞书拒绝通知，错误码：{result.get('code', 'unknown')}")
    return result


def main():
    env = os.environ
    webhook, secret = env.get("FEISHU_BOT_WEBHOOK", ""), env.get("FEISHU_BOT_SIGNING_SECRET", "")
    if not webhook or not secret:
        raise ValueError("未配置 FEISHU_BOT_WEBHOOK 或 FEISHU_BOT_SIGNING_SECRET")
    send(webhook, secret, message(load_event(env), env))
    print("Vision Lab Bot 通知已发送。")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
