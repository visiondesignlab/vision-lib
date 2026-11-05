"""Exercise the actual CMS gate and gallery menus on a private, disposable server.

Run with: python tests/browser_routes.py
Use BROWSER_CHANNEL=chrome to test the system Chrome instead of bundled Chromium.
"""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "qa-browser-password-12345"  # only used in the disposable test store


@contextmanager
def fixture():
    with tempfile.TemporaryDirectory(prefix="vision-lab-qa-") as d:
        directory = Path(d)
        media = directory / "media"
        example = "ambi-2114733804535377947"
        shutil.copytree(ROOT / "publish/media" / example, media / example)
        rows = [
            dict(id=f"qa-{i}", title=f"QA video {i}", category="QA", type="video",
                 tags=[], _version=1, status="pending" if i < 4 else "archived" if i < 6 else "published",
                 source={"url": f"https://example.org/video/{i}"},
                 media={"kind":"video", "video": f"/media/{example}/web.mp4",
                        "thumbnail": f"/media/{example}/thumb.jpg"} if i == 0 else {})
            for i in range(63)
        ]
        rows.extend(dict(id=f"skill-{n}", title=n, category="QA", type="skill_repo",
                         status="published", rank=rank, added_at=date, source={}, media={})
                    for n, rank, date in [("Old", 1, "2025-01-01"), ("New", 2, "2026-01-01")])
        rows.append(dict(id="qa-showcase", type="showcase", title="Handoff test", category="QA",
                         status="published", source={"url":"https://example.org/test"},
                         media=rows[0]["media"], description="示例 " * 150))
        (directory / "cases.json").write_text(json.dumps(rows))
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        url = f"http://127.0.0.1:{port}"
        env = dict(os.environ, CASELIB_DATA_DIR=d, CASELIB_MEDIA_DIR=str(media),
                   CASELIB_CMS_INITIAL_PASSWORD=PASSWORD)
        with (directory / "server.log").open("w") as log:
            process = subprocess.Popen([sys.executable, "server.py", "--host", "127.0.0.1", "--port", str(port)],
                                       cwd=ROOT, env=env, stdout=log, stderr=log)
            try:
                for _ in range(100):
                    if process.poll() is not None:
                        raise RuntimeError("Fixture server exited before startup")
                    try:
                        with urlopen(url + "/api/cases", timeout=1):
                            break
                    except OSError:
                        time.sleep(.1)
                else:
                    raise RuntimeError("Fixture server did not respond")
                yield url
            finally:
                process.terminate()
                process.wait(timeout=10)


def verify(base, pw):
    browser = pw.chromium.launch(channel=os.getenv("BROWSER_CHANNEL") or None)
    errors = []
    for width in (390, 1440):
        ctx = browser.new_context(viewport={"width": width, "height": 900})
        ctx.route("https://fonts.**", lambda route: route.abort())
        page = ctx.new_page()
        page.on("pageerror", lambda err: errors.append(str(err)))
        def go(path):
            page.goto(base + path, wait_until="domcontentloaded")
        go("/?tab=skill_repo")
        menu = page.get_by_role("button", name="排序", exact=True)
        expect(menu).to_have_text("按排名")
        expect(page.locator("#sort")).to_be_hidden()
        menu.focus()
        page.keyboard.press("ArrowDown")
        expect(page.get_by_role("menuitemradio")).to_have_text(["按排名", "最新", "按热度"])
        page.get_by_role("menuitemradio", name="最新", exact=True).click()
        expect(page.locator(".card").first).to_have_attribute("data-id", "skill-New")
        expect(page.get_by_role("button", name="排序")).to_have_text("最新")
        if width == 390:
            go("/c/qa-showcase")
            page.locator("#overlay .split .caret").click()
            page.get_by_role("menuitemradio", name="复制 Prompt").click()
            page.reload(wait_until="domcontentloaded")
            expect(page.locator("#overlay .split .main")).to_have_text("复制拉片 Prompt")
        go("/review")
        expect(page.locator("#password")).to_be_visible()
        expect(page.get_by_text("输入管理员 token")).to_have_count(0)
        page.fill("#password", PASSWORD)
        page.get_by_role("button", name="登录工作台").click()
        expect(page.get_by_role("heading", name="内容工作台")).to_be_visible()
        go("/?tab=skill_repo")
        expect(page.get_by_text("管理本栏目", exact=True).first).to_be_visible()
        page.locator(".card").first.click()
        edit = page.locator("#overlay").get_by_role("link", name="编辑内容")
        expect(edit).to_be_visible()
        edit.click()
        expect(page).to_have_url(base + "/cms/edit/skill-Old")
        go("/tools/ai-nav")
        expect(page.locator(".ai-link").first).to_be_visible()
        if width == 390:
            page.get_by_role("button", name="选择分类").click()
            page.get_by_role("menuitemradio", name="UI 设计", exact=True).click()
            expect(page.get_by_role("heading", name="UI 设计", exact=False)).to_be_visible()
        go("/guide")
        expect(page.get_by_role("heading", name="常见问题")).to_be_visible()
        expect(page.locator("body")).not_to_contain_text("输入管理员 token")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        ctx.close()
    browser.close()
    assert not errors, errors
    print("Desktop + mobile: password login, workspace, contextual edit, custom sorting and order, AI navigation, guide passed.")


if __name__ == "__main__":
    with fixture() as base, sync_playwright() as pw:
        verify(base, pw)
