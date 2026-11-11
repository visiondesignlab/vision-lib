#!/usr/bin/env python3
"""Send Pages results through one Feishu application bot to multiple chats."""

import base64
import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class DeliveryUnknown(RuntimeError):
    """A message might have arrived: never switch transports in this case."""


def app_request(path, payload, token=None):
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = ("https://accounts.feishu.cn/oauth/v3/token" if path == "oauth/v3/token"
           else "https://open.feishu.cn/open-apis/" + path)
    request = Request(url,
                      data=json.dumps(payload, ensure_ascii=False).encode(),
                      headers=headers, method="POST")
    try:
        with urlopen(request, timeout=20) as response:
            result = json.load(response)
    except HTTPError as error:
        try:
            result = json.load(error)
        except (ValueError, OSError):
            raise DeliveryUnknown("飞书应用请求结果未确认，请先回读群消息") from None
    except (URLError, TimeoutError, ValueError, OSError):
        # Do not include response bodies, tokens or exception URLs in logs.
        raise DeliveryUnknown("飞书应用请求结果未确认，请先回读群消息") from None
    if not isinstance(result, dict) or not isinstance(result.get("code"), int):
        raise DeliveryUnknown("飞书应用返回结果无效，请先回读群消息")
    if result["code"] != 0:
        raise RuntimeError(f"飞书应用拒绝请求，错误码：{result['code']}")
    return result


def app_token(env):
    app_id, secret = env.get("FEISHU_APP_ID", ""), env.get("FEISHU_APP_SECRET", "")
    if not app_id or not secret:
        raise ValueError("未配置 FEISHU_APP_ID 或 FEISHU_APP_SECRET")
    result = app_request("oauth/v3/token",
                         {"grant_type": "client_credentials", "client_id": app_id,
                          "client_secret": secret, "scope": "im:message:send_as_bot"})
    token = result.get("access_token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("飞书未返回有效的应用凭证")
    return token


def chat_ids(env):
    ids = list(dict.fromkeys(x.strip() for x in env.get("FEISHU_CHAT_IDS", "").split(",") if x.strip()))
    if not ids or any(not re.fullmatch(r"oc_[0-9a-f]{32}", x) for x in ids):
        raise ValueError("FEISHU_CHAT_IDS 必须包含有效的群 ID 列表")
    return ids


def send_app(token, chat_id, card, env):
    # Same workflow, chat and content reuse a UUID (Feishu deduplicates for 1h).
    run_id = env.get("GITHUB_RUN_ID")
    if not run_id:
        raise ValueError("应用通知需要 GITHUB_RUN_ID 生成幂等键")
    content = json.dumps(card, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(content.encode()).hexdigest()
    key = str(uuid.uuid5(uuid.NAMESPACE_URL,
                        f"{env['GITHUB_REPOSITORY']}:{run_id}:{chat_id}:{digest}"))
    payload = {"receive_id": chat_id, "msg_type": "interactive",
               "content": content, "uuid": key}
    # A timeout can be retried safely with the same UUID, never via the Webhook.
    for attempt in range(2):
        try:
            result = app_request("im/v1/messages?receive_id_type=chat_id", payload, token)
            message_id = (result.get("data") or {}).get("message_id")
            if not isinstance(message_id, str) or not message_id.startswith("om_"):
                raise DeliveryUnknown("飞书未返回消息 ID，请先回读群消息")
            return message_id
        except DeliveryUnknown:
            if attempt:
                raise
        except RuntimeError:
            if attempt:
                raise DeliveryUnknown("飞书重试未确认成功，请先回读群消息") from None
            raise


def notify(card, env):
    mode = env.get("FEISHU_NOTIFY_MODE", "webhook") or "webhook"
    webhook, secret = env.get("FEISHU_BOT_WEBHOOK", ""), env.get("FEISHU_BOT_SIGNING_SECRET", "")

    def legacy():
        send(webhook, secret, card)
        print("原群 Webhook 通知已发送。")

    if mode == "webhook":
        legacy()
        return
    if mode != "app":
        raise ValueError("FEISHU_NOTIFY_MODE 仅支持 webhook 或 app")
    fallback_chat = env.get("FEISHU_FALLBACK_CHAT_ID", "")
    try:
        targets = chat_ids(env)
        if fallback_chat and fallback_chat not in targets:
            raise ValueError("原群必须包含在 FEISHU_CHAT_IDS 中")
        if not env.get("GITHUB_RUN_ID"):
            raise ValueError("应用通知需要 GITHUB_RUN_ID 生成幂等键")
        token = app_token(env)
    except (ValueError, RuntimeError):
        # Token/config failures happen before any message is sent.
        if fallback_chat and webhook and secret:
            legacy()
        raise

    failures = []
    for index, chat_id in enumerate(targets, start=1):
        try:
            message_id = send_app(token, chat_id, card, env)
            print(f"群 {index} 应用通知已发送，message_id={message_id}")
        except (ValueError, RuntimeError) as error:
            failures.append(f"群 {index}：{error}")
            if not isinstance(error, DeliveryUnknown) and chat_id == fallback_chat and webhook and secret:
                try:
                    legacy()
                except (ValueError, RuntimeError) as fallback_error:
                    failures.append(f"原群回退：{fallback_error}")
    if failures:
        raise RuntimeError("；".join(failures))


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
    notify(message(load_event(env), env), env)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
