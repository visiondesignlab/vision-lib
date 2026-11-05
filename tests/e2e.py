"""Headless E2E: gallery, showcase, detail, use-dropdown deeplinks, handoff (read-only).
Run:  /workspace/pwvenv/bin/python tests/e2e.py [base_url]"""
import json, sys, os, time
from playwright.sync_api import sync_playwright
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8787"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = os.path.join(ROOT, "screens")
os.makedirs(S, exist_ok=True)
res = {}
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=BASE)
    pg = ctx.new_page()
    pg.add_init_script("""window.__opened=[];const oc=HTMLAnchorElement.prototype.click;HTMLAnchorElement.prototype.click=function(){if(!/^https?:/.test(this.href)){window.__opened.push(this.href);return;}return oc.call(this)};
      const wo=window.open;window.open=function(u){window.__opened.push(u);return null};""")
    pg.goto(BASE + "/?tab=video", wait_until="domcontentloaded"); pg.wait_for_selector(".card")
    res["video_cards"] = pg.locator(".card").count()
    pg.get_by_role("link", name="使用说明", exact=True).click()
    pg.get_by_role("heading", name="使用说明", exact=True).wait_for()
    pg.reload(wait_until="domcontentloaded")
    pg.get_by_role("heading", name="常见问题", exact=True).wait_for()
    pg.go_back(wait_until="domcontentloaded")
    pg.get_by_role("heading", name="AI 视频案例", exact=True).wait_for()
    pg.locator(".card").first.hover(); pg.wait_for_timeout(1500)
    pg.screenshot(path=f"{S}/01-gallery-video.png")
    pg.goto(BASE + "/?tab=showcase", wait_until="domcontentloaded"); pg.wait_for_selector(".card")
    res["showcase_cards"] = pg.locator(".card").count()
    pg.screenshot(path=f"{S}/02-showcase.png")
    pg.goto(BASE + "/c/ambi-2109660371296424352", wait_until="domcontentloaded"); pg.wait_for_timeout(2000)
    res["detail_title"] = pg.locator(".phead h3").inner_text()
    pg.locator("#overlay .split .caret").first.click(); pg.wait_for_timeout(300)
    pg.screenshot(path=f"{S}/03-detail-use-menu.png")
    for k in ["cursor", "codex", "claude", "copy"]:
        if not pg.locator("#overlay .menu").count():
            pg.locator("#overlay .split .caret").first.click()
        pg.locator(f'#overlay .menu button[data-value="{k}"]').first.click(); pg.wait_for_timeout(400)
        res[f"use_{k}_toast"] = pg.locator("#toast").inner_text()
    res["opened"] = [u[:90] for u in pg.evaluate("window.__opened")]
    res["clipboard_head"] = pg.evaluate("navigator.clipboard.readText()")[:60]
    assert res["video_cards"] and res["showcase_cards"]
    pg.goto(BASE + "/c/show-2109720765667172355/breakdown?run=1", wait_until="domcontentloaded")
    pg.wait_for_url("**/c/show-2109720765667172355")
    pg.wait_for_selector(".prompt-preview")
    assert pg.locator(".bd").count() == 0
    res["handoff_label"] = pg.locator("#overlay .split .main").inner_text()
    pg.screenshot(path=f"{S}/04-handoff.png")
    b.close()
print(json.dumps(res, ensure_ascii=False, indent=1))
