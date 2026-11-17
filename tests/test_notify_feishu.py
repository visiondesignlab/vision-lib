import io
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import URLError

from scripts.notify_feishu import (DeliveryUnknown, app_request, app_token, chat_ids,
                                   commit_lines, load_event, message, notify, send_app)


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

    def test_success_card_has_requested_content_and_two_buttons(self):
        card = message({"commits": [{"message": "修复移动端表头\n\n实现细节"}]}, self.env)
        self.assertEqual(card["header"]["title"]["content"], "Vision Lab · 发布成功")
        self.assertEqual(card["header"]["template"], "blue")
        body = card["elements"][0]["text"]
        self.assertEqual(body["tag"], "lark_md")
        self.assertEqual(body["content"],
                         "操作人：visiondesignlab • abcdef1\n\n**最新改动**\n1. 修复移动端表头")
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

    def test_changes_show_newest_subjects_with_numbered_limit(self):
        lines = commit_lines({"commits": [{"message": f"改动 {i}\n详情"} for i in range(8)]}, limit=5)
        self.assertEqual(lines, [f"{n}. 改动 {i}" for n, i in enumerate(range(7, 2, -1), 1)] + ["另有 3 项改动，详见仓库提交记录。"])

    def test_head_commit_and_manual_release_fallback(self):
        self.assertEqual(commit_lines({"head_commit": {"message": "修复卡片"}}), ["1. 修复卡片"])
        self.assertIn("手动发布当前版本。", message({}, self.env)["elements"][0]["text"]["content"])

    def test_single_commit_preserves_detailed_release_notes_and_links(self):
        event = {"commits": [{"message": "更新平台\n\n1. 更新四类榜单 [查看榜单](https://example.com/models)\n"
                  "2、修复解析\n- 增加回归检查\n• 优化发布卡片\n\n验证：测试通过"}]}
        lines = commit_lines(event)
        self.assertEqual(lines, [
            '1. 更新四类榜单 [查看榜单](https://example.com/models)',
            '2. 修复解析', '3. 增加回归检查', '4. 优化发布卡片'])
        card = message(event, self.env)
        self.assertIn('\n\n4. 优化发布卡片', card['elements'][0]['text']['content'])
        self.assertNotIn('验证：', card['elements'][0]['text']['content'])

    def test_notes_are_deduplicated_and_code_and_mentions_are_not_executed(self):
        event = {'commits': [{'message': '标题\n- 同一项\n```\n- 代码示例\n```\n- <at id=all>全员</at>'},
                             {'message': '另一标题\n- 同一项'}]}
        lines = commit_lines(event)
        self.assertEqual(lines, ['1. 同一项', '2. <at id=all>全员</at>'])
        self.assertNotIn('<at', message(event, self.env)['elements'][0]['text']['content'])

    def test_git_fallback_preserves_multiline_commit_bodies(self):
        before, after = 'a' * 40, 'b' * 40
        body = '更新平台\n\n- 榜单同步\n- 发布卡片'
        with tempfile.TemporaryDirectory() as tmp:
            event_file = Path(tmp)/'event.json'
            event_file.write_text(json.dumps({'before': before}))
            for kind in ('push', 'workflow_dispatch'):
                env = {**self.env, 'GITHUB_EVENT_NAME': kind, 'GITHUB_EVENT_PATH': str(event_file), 'GITHUB_SHA': after}
                with patch('scripts.notify_feishu.subprocess.run', return_value=SimpleNamespace(stdout=f'{after}\0{body}\n\0\n')) as git:
                    event = load_event(env)
                self.assertEqual(commit_lines(event), ['1. 榜单同步', '2. 发布卡片'])
                args = git.call_args.args[0]
                self.assertIn('--format=%H%x00%B%x00', args)
                self.assertIn(f'{before}..{after}' if kind == 'push' else '-1', args)

class AppNotificationTests(unittest.TestCase):
    def setUp(self):
        self.original = "oc_" + "1" * 32
        self.second = "oc_" + "2" * 32
        self.env = {
            "GITHUB_REPOSITORY": "visiondesignlab/vision-lib", "GITHUB_RUN_ID": "12345",
            "FEISHU_APP_ID": "cli_test",
            "FEISHU_APP_SECRET": "app-secret-test",
            "FEISHU_CHAT_IDS": f"{self.original},{self.second},{self.original}",
        }
        self.card = {"header": {"title": {"content": "发布结果"}}}
        # Mocked delivery logs should not resemble real sends in workflow logs.
        printer = patch("builtins.print")
        printer.start()
        self.addCleanup(printer.stop)

    def test_same_app_sends_each_unique_chat_and_preserves_card(self):
        with patch("scripts.notify_feishu.app_request", side_effect=[
            {"access_token": "test-token"},
            {"data": {"message_id": "om_one"}}, {"data": {"message_id": "om_two"}},
        ]) as api:
            notify(self.card, self.env)
        self.assertEqual(api.call_count, 3)
        messages = api.call_args_list[1:]
        self.assertEqual([c.args[1]["receive_id"] for c in messages], [self.original, self.second])
        self.assertEqual([c.args[2] for c in messages], ["test-token"] * 2)
        self.assertEqual([json.loads(c.args[1]["content"]) for c in messages], [self.card] * 2)
        self.assertNotEqual(messages[0].args[1]["uuid"], messages[1].args[1]["uuid"])

    def test_original_rejection_does_not_block_second(self):
        with patch("scripts.notify_feishu.app_token", return_value="test-token"), \
                patch("scripts.notify_feishu.send_app", side_effect=[RuntimeError("rejected"), "om_two"]) as api:
            with self.assertRaisesRegex(RuntimeError, "群 1"):
                notify(self.card, self.env)
        self.assertEqual(api.call_count, 2)
        self.assertEqual([c.args[1] for c in api.call_args_list], [self.original, self.second])

    def test_second_chat_rejection_never_duplicates_original(self):
        with patch("scripts.notify_feishu.app_token", return_value="test-token"), \
                patch("scripts.notify_feishu.send_app", side_effect=["om_one", RuntimeError("rejected")]) as api:
            with self.assertRaisesRegex(RuntimeError, "群 2"):
                notify(self.card, self.env)
        self.assertEqual([c.args[1] for c in api.call_args_list], [self.original, self.second])

    def test_auth_failure_is_reported_without_sending(self):
        with patch("scripts.notify_feishu.app_token", side_effect=DeliveryUnknown("token timeout")), \
                patch("scripts.notify_feishu.send_app") as api:
            with self.assertRaises(DeliveryUnknown):
                notify(self.card, self.env)
        api.assert_not_called()

    def test_ambiguous_send_does_not_block_second_chat(self):
        with patch("scripts.notify_feishu.app_token", return_value="test-token"), \
                patch("scripts.notify_feishu.send_app", side_effect=[DeliveryUnknown("timeout"), "om_two"]) as api:
            with self.assertRaises(RuntimeError):
                notify(self.card, self.env)
        self.assertEqual(api.call_count, 2)

    def test_timeout_retry_and_workflow_rerun_use_identical_uuid(self):
        with patch("scripts.notify_feishu.app_request", side_effect=[
            DeliveryUnknown("timeout"), {"data": {"message_id": "om_one"}},
            {"data": {"message_id": "om_one"}},
        ]) as api:
            send_app("token", self.original, self.card, self.env)
            send_app("token", self.original, self.card, {**self.env, "GITHUB_RUN_ATTEMPT": "2"})
        keys = [c.args[1]["uuid"] for c in api.call_args_list]
        self.assertEqual(len(set(keys)), 1)

    def test_rejection_after_ambiguous_attempt_remains_ambiguous(self):
        with patch("scripts.notify_feishu.app_request", side_effect=[DeliveryUnknown("timeout"), RuntimeError("rejected")]):
            with self.assertRaises(DeliveryUnknown):
                send_app("token", self.original, self.card, self.env)

    def test_changed_release_result_is_not_suppressed_on_rerun(self):
        with patch("scripts.notify_feishu.app_request", return_value={"data": {"message_id": "om_one"}}) as api:
            send_app("token", self.original, self.card, self.env)
            send_app("token", self.original, {"result": "failed"}, self.env)
        self.assertNotEqual(api.call_args_list[0].args[1]["uuid"], api.call_args_list[1].args[1]["uuid"])

    def test_transport_errors_never_expose_secrets(self):
        with patch("scripts.notify_feishu.urlopen", side_effect=URLError("test-token app-secret-test")):
            with self.assertRaises(DeliveryUnknown) as error:
                app_request("im/v1/messages", {}, "test-token")
        self.assertNotIn("test-token", str(error.exception))
        self.assertNotIn("app-secret-test", str(error.exception))

    def test_invalid_configuration_never_sends_to_app(self):
        with self.assertRaises(ValueError):
            chat_ids({"FEISHU_CHAT_IDS": "not-a-chat"})
        with patch("scripts.notify_feishu.app_token") as token:
            with self.assertRaises(ValueError):
                notify(self.card, {**self.env, "FEISHU_CHAT_IDS": "not-a-chat"})
        token.assert_not_called()

    def test_missing_application_secret_fails_without_network_request(self):
        with patch("scripts.notify_feishu.urlopen") as opener:
            with self.assertRaises(ValueError):
                app_token({**self.env, "FEISHU_APP_SECRET": ""})
        opener.assert_not_called()

    def test_post_uses_app_identity_and_preserves_interactive_card(self):
        response = io.BytesIO(b'{"code":0,"data":{"message_id":"om_one"}}')
        with patch("scripts.notify_feishu.urlopen", return_value=response) as opener:
            send_app("test-token", self.original, self.card, self.env)
        request = opener.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(request.full_url, "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-token")
        self.assertEqual(payload["receive_id"], self.original)
        self.assertEqual(payload["msg_type"], "interactive")
        self.assertEqual(json.loads(payload["content"]), self.card)
        self.assertEqual(request.method, "POST")
        opener.assert_called_once()


if __name__ == "__main__":
    unittest.main()
