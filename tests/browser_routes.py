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
                         status="published", rank=rank, added_at=date, source={}, media={},
                         tags=["示例"] if n == "New" else [])
                    for n, rank, date in [("Old", 1, "2025-01-01"), ("New", 2, "2026-01-01")])
        rows.append(dict(id="qa-showcase", type="showcase", title="Handoff test", category="QA",
                         status="published", source={"url":"https://example.org/test"},
                         media=rows[0]["media"], description="示例 " * 150))
        rows.append(dict(id="qa-showcase-other", type="showcase", title="Keep in inspiration", category="QA",
                         status="published", source={"url":"https://example.org/other"}, media={}))
        for width in (390,1440):
            for n in range(4):
                rows.append(dict(id=f"transfer-{width}-{n}", type="video", title=f"Clip {n}",
                                 category=f"Review-{width}", tags=["示例"], status="published",
                                 source={"url":f"https://example.org/review/{width}/{n}"}, media=rows[0]["media"]))
        rows.append(dict(id="qa-deck", type="brand_skill", status="published", title="QA PPT",
                         source={"repo":"fixture/deck","url":"https://example.org/deck"},
                         how_to=[], assets=[{"url":"https://example.org/deck.pptx"}],
                         brand_repository={"sha":"1234567","docs":[],"installation":[],
                                           "samples":[{"label":f"示例 {i+1}","url":rows[0]["media"]["thumbnail"]}
                                                      for i in range(30)]}))
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


def verify_detail_actions(page, base, width):
    gallery=f"{base}/?tab=video&cat=Review-{width}&tag=示例"
    page.goto(gallery,wait_until="domcontentloaded")
    cards=page.locator(".card")
    expect(cards).to_have_count(4)
    ids=cards.evaluate_all("cards=>cards.map(c=>c.dataset.id)")
    cards.first.click()
    player=page.locator(".stage video")
    page.wait_for_function("document.querySelector('.stage video')?.currentTime>0.05")
    assert player.evaluate("v=>!v.muted && v.volume===0.5")
    prior=player.element_handle()
    toolbar=page.locator("#overlay>.detail-admin-tools")

    def apply(action):
        toolbar.locator(f'[data-quick="{action}"]').click()
        form=page.locator("dialog[open] form")
        expect(form).to_be_visible()
        if action=="migrate":
            ack=form.locator('[name=acknowledge]')
            if ack.is_visible():
                ack.check()
        form.locator('[type=submit]').click()

    apply("migrate")
    expect(page).to_have_url(base+"/c/"+ids[1])
    assert prior.evaluate("v=>v.paused && v.muted && !v.isConnected && !v.getAttribute('src')")
    apply("unpublish")
    expect(page).to_have_url(base+"/c/"+ids[2])
    page.locator('.ptop [title="下一条"]').click()
    expect(page).to_have_url(base+"/c/"+ids[3])
    apply("delete")
    expect(page).to_have_url(base+"/c/"+ids[2])
    apply("unpublish")
    expect(page.locator("#overlay")).to_be_hidden()
    expect(page.locator(".card")).to_have_count(0)
    assert "tab=video" in page.url and f"cat=Review-{width}" in page.url and "tag=" in page.url

def verify(base, pw, width):
    browser = pw.chromium.launch(channel=os.getenv("BROWSER_CHANNEL") or None)
    errors = []
    with browser.new_context(viewport={"width": width, "height": 900}) as ctx:
        ctx.route("https://**/*", lambda route: route.abort())
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
        go("/journal/")
        page.locator('.journal-card[href$="vol=14"]').click()
        back = page.get_by_role("link", name="全部期刊", exact=True)
        expect(back).to_be_visible()
        assert back.bounding_box()["height"] == 28
        film = page.locator(".journal-film video")
        assert film.evaluate("v=>v.volume === 0.5 && !v.muted")
        film.scroll_into_view_if_needed()
        page.wait_for_function("document.querySelector('.journal-film video').currentTime > 0.05")
        old_film = film.element_handle()
        back.click()
        expect(page.locator(".journal-latest")).to_be_visible()
        assert old_film.evaluate("v=>v.paused && !v.isConnected")
        # Migrated videos can have no authored prompt. They must still offer a usable handoff.
        go("/c/transfer-%s-0" % width)
        handoff = page.locator("#overlay > .ptop .split")
        expect(handoff.locator(".main")).to_have_text("使用 · Cursor")
        prompt = page.locator("#overlay .prompt").first.inner_text()
        assert "Clip 0" in prompt and "/web.mp4" in prompt and "逐镜头" in prompt
        if width == 390:
            tag = page.locator("#overlay .tags a.tag").first
            assert tag.evaluate("""el=>{
                const range = new Range(); range.selectNodeContents(el);
                const text = range.getBoundingClientRect(), chip = el.getBoundingClientRect();
                return Math.abs(text.x + text.width / 2 - chip.x - chip.width / 2) <= 1 &&
                       Math.abs(text.y + text.height / 2 - chip.y - chip.height / 2) <= 2;
            }""")
        handoff.locator(".caret").click()
        expect(page.get_by_role("menuitemradio", name="Codex", exact=True)).to_be_visible()
        page.keyboard.press("Escape")
        if width == 390:
            go("/c/qa-showcase")
            page.locator("#overlay .split .caret").click()
            page.get_by_role("menuitemradio", name="复制 Prompt").click()
            page.reload(wait_until="domcontentloaded")
            expect(page.locator("#overlay .split .main")).to_have_text("复制拉片 Prompt")
        go("/c/qa-deck")
        jump = page.get_by_role("button", name="跳至页面")
        jump.click()
        options = page.get_by_role("menuitemradio")
        expect(options).to_have_count(30)
        page.keyboard.press("End")
        page.keyboard.press("Enter")
        expect(jump).to_have_text("30 · 示例 30")
        page.locator("[data-sample-prev]").click()
        expect(jump).to_have_text("29 · 示例 29")
        jump.click()
        expect(options.nth(28)).to_have_attribute("aria-checked", "true")
        page.keyboard.press("Escape")
        expect(jump).to_be_focused()
        go("/submit")
        public_form=page.locator(".submission-form").first
        public_form.get_by_label("作品链接").fill("https://example.org/test")
        public_form.get_by_label("作品名称").fill("私密来稿")
        public_form.get_by_label("制作线索").fill("仅供审核的投稿备注")
        public_form.get_by_role("button",name="提交作品").click()
        expect(page.get_by_text("已收到投稿")).to_be_visible()
        assert page.request.get(base+"/api/admin/submissions").status == 401
        assert "私密来稿" not in page.request.get(base+"/api/cases").text()
        go("/review")
        expect(page.locator("#password")).to_be_visible()
        expect(page.get_by_text("输入管理员 token")).to_have_count(0)
        page.fill("#password", PASSWORD)
        page.get_by_role("button", name="登录工作台").click()
        expect(page.get_by_role("heading", name="内容工作台")).to_be_visible()
        go("/cms/submissions")
        expect(page.locator(".submission-list article").filter(has_text="私密来稿")).to_contain_text("已有相同来源")
        go("/cms/content?type=showcase")
        row = page.locator('tr[data-id="qa-showcase"]')
        box = page.locator('input[data-all]')
        box.click()
        expect(box).to_be_checked()
        assert box.evaluate("e=>getComputedStyle(e).outlineStyle") == "none"
        row.get_by_role("button", name="预览", exact=True).click()
        close = page.locator("dialog .preview-close")
        expect(close).to_be_visible()
        close.evaluate("e=>Promise.all(e.closest('dialog').getAnimations().map(a=>a.finished))")
        canvas, icon = close.evaluate("e=>[e,e.querySelector('svg')].map(i=>i.getBoundingClientRect().toJSON())")
        assert canvas['width'] == canvas['height'] == 32
        for coord, size in [('x','width'), ('y','height')]:
            assert abs(canvas[coord] + 16 - icon[coord] - icon[size]/2) < 0.5
        close.click()
        expect(page.locator("dialog")).to_have_count(0)
        page.locator('[data-move=video]').click()
        form = page.locator("dialog form")
        master = form.get_by_role("checkbox", name="全选", exact=True)
        master.uncheck()
        expect(form.get_by_role("button", name="确认迁移")).to_be_disabled()
        expect(form.locator("[data-count]")).to_have_text("已选 0 / 2 条")
        form.locator('[data-pick="qa-showcase"]').check()
        expect(form.locator("[data-count]")).to_have_text("已选 1 / 2 条")
        expect(form.get_by_text("疑似重复", exact=True)).to_be_visible()
        form.get_by_text("疑似重复", exact=True).click()
        expect(form.get_by_role("link", name="QA video 0")).to_be_visible()
        category = form.get_by_role("button",name="目标分类")
        category.click()
        page.get_by_role("menuitemradio", name="待分类", exact=True).click()
        expect(category).to_have_text("待分类")
        form.get_by_role("checkbox", name="已核对", exact=False).check()
        form.get_by_role("button", name="确认迁移").click()
        expect(row).to_have_count(0)
        expect(page.locator('tr[data-id="qa-showcase-other"]')).to_be_visible()
        go("/cms/content?type=video")
        page.locator('#search').fill("Handoff test")
        row = page.locator('tr[data-id="qa-showcase"]')
        expect(row).to_contain_text("待分类")
        row.locator("input").check()
        page.locator('[data-move=showcase]').click()
        category.click()
        page.get_by_role('menuitemradio', name='自定义分类…').click()
        custom = form.get_by_label('新分类名称')
        expect(custom).to_be_focused()
        custom.fill('QA')
        form.get_by_role("button",name="确认迁移").click()
        expect(row).to_have_count(0)
        expect(page.locator("#stats")).to_contain_text("管理库共")
        go("/?tab=skill_repo")
        expect(page.get_by_text("管理本栏目", exact=True).first).to_be_visible()
        page.locator(".card").first.click()
        edit = page.locator("#overlay").get_by_role("link", name="编辑内容")
        expect(edit).to_be_visible()
        edit.click()
        expect(page).to_have_url(base + "/cms/edit/skill-Old")
        page.get_by_role("button",name="内容类型",exact=True).click()
        expect(page.get_by_role("menuitemradio",name="Skill 仓库")).to_have_attribute("aria-checked","true")
        page.keyboard.press("Escape")
        page.get_by_role("button",name="添加已有标签").click()
        expect(page.get_by_role("menuitemradio",name="示例",exact=True)).to_be_visible()
        page.keyboard.press("Escape")
        go("/cms/ai-nav")
        page.get_by_role("button",name="筛选目录分类").click()
        page.get_by_role("menuitemradio",name="UI 设计",exact=True).click()
        page.get_by_role("button",name="新建入口").click()
        form = page.locator("dialog[open]")
        form.get_by_role("button",name="选择入口分类").click()
        expect(form.get_by_role("menuitemradio", name="UI 设计",exact=True)).to_be_visible()
        page.keyboard.press("Escape")
        expect(form).to_be_visible()
        form.get_by_role("button",name="取消").click()
        go("/tools/ai-nav")
        expect(page.locator(".ai-link").first).to_be_visible()
        if width == 390:
            page.get_by_role("button", name="选择分类").click()
            page.get_by_role("menuitemradio", name="UI 设计", exact=True).click()
            expect(page.get_by_role("heading", name="UI 设计", exact=False)).to_be_visible()
        go("/tools/ai-nav?category=model-rankings")
        expect(page).to_have_url(base + "/tools/ai-models")
        tabs = page.get_by_role("navigation", name="榜单类型")
        assert tabs.get_by_role("link").evaluate_all("links=>links.every(a=>a.getBoundingClientRect().height===28)")
        for label in ("语言模型", "图像", "视频", "语音"):
            tabs.get_by_role("link", name=label, exact=True).click()
            expect(tabs.locator('[aria-current="page"]')).to_have_text(label)
            expect(page.locator(".ai-ranking tbody tr").first).to_be_visible()
            assert page.locator(".ai-ranking tbody tr").count() >= 30
            scroller = page.locator(".ai-ranking-scroll")
            top = page.locator(".ai-ranking thead").evaluate("e=>e.getBoundingClientRect().top")
            assert scroller.evaluate("e=>{e.scrollTop=e.scrollHeight;return e.scrollTop}") > 0
            assert abs(page.locator(".ai-ranking thead").evaluate("e=>e.getBoundingClientRect().top") - top) < 1
            assert page.evaluate("scrollY===0")
        search = page.get_by_role("searchbox", name="搜索模型或开发商")
        search.fill("qa-missing-model")
        expect(page.get_by_text("没有匹配的模型", exact=True)).to_be_visible()
        page.get_by_role("button", name="清除搜索").click()
        expect(search).to_be_focused()
        expect(page).to_have_url(base + "/tools/ai-models?type=speech")
        verify_detail_actions(page,base,width)
        go("/guide")
        expect(page.get_by_role("heading", name="常见问题")).to_be_visible()
        expect(page.locator("body")).not_to_contain_text("输入管理员 token")
        go("/assets/design")
        expect(page.get_by_role("heading", name="设计资产")).to_be_visible()
        expect(page.get_by_text("含新品 · 谨慎公开", exact=True)).to_be_visible()
        air = page.get_by_role("link", name="打开 Air", exact=True)
        ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=base)
        page.get_by_role("button", name="复制链接").click()
        expect(page.locator("#toast")).to_have_text("设计资源包链接已复制")
        assert page.evaluate("navigator.clipboard.readText()") == air.get_attribute("href")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    browser.close()
    assert not errors, errors
    print(f"{width} px: menus, PPT navigation, login, media, content management, AI tools and guide passed.")


if __name__ == "__main__":
    with sync_playwright() as pw:
        for width in (390, 1440):
            with fixture() as base:
                verify(base, pw, width)
