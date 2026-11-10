import io
import json
import unittest
from unittest.mock import patch
from urllib.error import URLError

from scripts.notify_feishu import commit_lines, message, send, signature


class FeishuNotificationTests(unittest.TestCase):
    def setUp(self):
        self.env = dict(GITHUB_REPOSITORY="visiondesignlab/vision-lib", GITHUB_SHA="abcdef1234",
                        GITHUB_RUN_ID="123", GITHUB_ACTOR="visiondesignlab", GITHUB_REF_NAME="main",
                        BUILD_RESULT="success", DEPLOY_RESULT="success",
                        PAGES_URL="https://visiondesignlab.github.io/vision-lib/")
        self.webhook = "https://open.feishu.cn/open-apis/bot/v2/hook/test-only"

    def test_signature_matches_known_vector(self):
        self.assertEqual(signature("test-secret", "1600000000"),
                         "BwqgZGo8lGLJAUAc/kiJR0TDtnLVnsITtszoHeRuXV0=")

    def test_message_contains_commits_and_success_url(self):
        result = message({"commits": [{"id": "123456789", "message": "修复移动端表头\n细节"}]}, self.env)
        self.assertIn("1234567 修复移动端表头", result)
        self.assertNotIn("细节", result)
        self.assertIn("发布成功", result)
        self.assertIn(self.env["PAGES_URL"], result)
        self.assertIn("/actions/runs/123", result)

    def test_failure_does_not_claim_published(self):
        self.env.update(BUILD_RESULT="failure", DEPLOY_RESULT="skipped")
        result = message({}, self.env)
        self.assertIn("发布未完成", result)
        self.assertIn("构建：失败 · Pages：未执行", result)
        self.assertNotIn(self.env["PAGES_URL"], result)

    def test_commit_list_is_bounded(self):
        lines = commit_lines({"commits": [{"id": str(i), "message": "标题"} for i in range(15)]})
        self.assertEqual(len(lines), 13)
        self.assertIn("另有 3 条提交", lines[-1])

    def test_send_includes_signature_and_utf8_content(self):
        with patch("scripts.notify_feishu.urlopen", return_value=io.BytesIO(b'{"code":0}')) as request:
            send(self.webhook, "test-secret", "更新完成", now=1600000000)
        payload = json.loads(request.call_args.args[0].data)
        self.assertEqual(payload["timestamp"], "1600000000")
        self.assertEqual(payload["sign"], signature("test-secret", "1600000000"))
        self.assertEqual(payload["content"]["text"], "更新完成")

    def test_api_rejection_is_a_failure(self):
        with patch("scripts.notify_feishu.urlopen", return_value=io.BytesIO(b'{"code":19021}')):
            with self.assertRaisesRegex(RuntimeError, "19021"):
                send(self.webhook, "test-secret", "更新")

    def test_timeout_is_not_retried_or_logged_with_secret(self):
        with patch("scripts.notify_feishu.urlopen", side_effect=URLError(self.webhook)) as request:
            with self.assertRaises(RuntimeError) as caught:
                send(self.webhook, "test-secret", "更新")
            self.assertEqual(request.call_count, 1)
            self.assertNotIn("test-only", str(caught.exception))

    def test_missing_secret_and_invalid_host_never_send(self):
        with patch("scripts.notify_feishu.urlopen") as request:
            for url, secret in [(self.webhook, ""), ("https://example.com/hook", "secret")]:
                with self.assertRaises(ValueError):
                    send(url, secret, "更新")
            request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
