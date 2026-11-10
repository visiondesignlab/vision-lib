import io
import json
import unittest
from unittest.mock import patch
from urllib.error import URLError

from scripts.notify_feishu import commit_lines, message, send, signature


class FeishuNotificationTests(unittest.TestCase):
    def setUp(self):
        self.env = {
            "GITHUB_REPOSITORY": "visiondesignlab/vision-lib",
            "GITHUB_SHA": "abcdef1234567890",
            "GITHUB_ACTOR": "visiondesignlab",
            "BUILD_RESULT": "success",
            "DEPLOY_RESULT": "success",
            "PAGES_URL": "https://visiondesignlab.github.io/vision-lib/",
        }
        self.webhook = "https://open.feishu.cn/open-apis/bot/v2/hook/test-only"

    def test_signature_known_vector(self):
        self.assertEqual(signature("test-secret", "1600000000"),
                         "BwqgZGo8lGLJAUAc/kiJR0TDtnLVnsITtszoHeRuXV0=")

    def test_success_card_has_requested_content_and_two_buttons(self):
        card = message({"commits": [{"message": "修复移动端表头\n\n实现细节"}]}, self.env)
        self.assertEqual(card["header"]["title"]["content"], "Vision Lab · 发布成功")
        self.assertEqual(card["header"]["template"], "blue")
        body = card["elements"][0]["text"]
        self.assertEqual(body["tag"], "plain_text")
        self.assertEqual(body["content"],
                         "操作人：visiondesignlab • abcdef1\n\n最新改动：\n• 修复移动端表头")
        buttons = card["elements"][1]["actions"]
        self.assertEqual([b["text"]["content"] for b in buttons], ["在线查看", "仓库地址"])
        self.assertEqual([b["url"] for b in buttons], [
            self.env["PAGES_URL"], "https://github.com/visiondesignlab/vision-lib"])
        self.assertNotIn("运行详情", json.dumps(card, ensure_ascii=False))

    def test_failure_is_also_a_card_and_does_not_claim_success(self):
        self.env.update(BUILD_RESULT="failure", DEPLOY_RESULT="skipped", PAGES_URL="")
        card = message({}, self.env)
        self.assertEqual(card["header"]["title"]["content"], "Vision Lab · 发布未完成")
        self.assertEqual(card["header"]["template"], "orange")
        self.assertIn("构建：失败 · Pages：未执行", card["elements"][0]["text"]["content"])
        self.assertEqual(card["elements"][1]["actions"][0]["url"],
                         "https://visiondesignlab.github.io/vision-lib/")

    def test_changes_show_newest_five_subjects(self):
        lines = commit_lines({"commits": [{"message": f"改动 {i}\n详情"} for i in range(8)]})
        self.assertEqual(lines, [f"• 改动 {i}" for i in range(7, 2, -1)] + ["另有 3 条提交。"])

    def test_head_commit_and_manual_release_fallback(self):
        self.assertEqual(commit_lines({"head_commit": {"message": "修复卡片"}}), ["• 修复卡片"])
        self.assertIn("手动发布当前版本。", message({}, self.env)["elements"][0]["text"]["content"])

    def test_post_uses_interactive_payload_and_signed_card(self):
        card = message({}, self.env)
        with patch("scripts.notify_feishu.urlopen", return_value=io.BytesIO(b'{"code":0}')) as opener:
            send(self.webhook, "test-secret", card, now=1600000000)
        request = opener.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(payload["msg_type"], "interactive")
        self.assertEqual(payload["card"], card)
        self.assertNotIn("content", payload)
        self.assertEqual(payload["timestamp"], "1600000000")
        self.assertEqual(payload["sign"], signature("test-secret", "1600000000"))
        self.assertEqual(request.method, "POST")
        opener.assert_called_once()

    def test_rejected_card_is_reported_without_text_fallback(self):
        with patch("scripts.notify_feishu.urlopen", return_value=io.BytesIO(b'{"code":19021}')) as opener:
            with self.assertRaises(RuntimeError):
                send(self.webhook, "test-secret", message({}, self.env))
        opener.assert_called_once()

    def test_ambiguous_timeout_is_not_retried_and_secret_is_not_exposed(self):
        with patch("scripts.notify_feishu.urlopen", side_effect=URLError(self.webhook)) as opener:
            with self.assertRaises(RuntimeError) as error:
                send(self.webhook, "test-secret", message({}, self.env))
        opener.assert_called_once()
        self.assertNotIn("test-only", str(error.exception))
        self.assertNotIn("test-secret", str(error.exception))

    def test_invalid_destination_or_missing_secret_never_sends(self):
        with patch("scripts.notify_feishu.urlopen") as opener:
            for webhook, secret in [(self.webhook, ""), ("https://example.com/hook/test", "secret")]:
                with self.assertRaises(ValueError):
                    send(webhook, secret, message({}, self.env))
        opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
