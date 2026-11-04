#!/usr/bin/env python3
"""Launch 案例库 web server (stdlib only).  python3 server.py [--port 8787] [--host 0.0.0.0]"""
import argparse, hmac, json, mimetypes, os, re, sys, traceback
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote
import store
import cms_auth
import cms_content as cms
from cms_upload import upload

STATIC = os.path.join(store.ROOT, "static")
SERVE_DIRS = {"static": STATIC, "media": store.MEDIA, "brand_skills": os.path.join(store.ROOT, "brand_skills")}
mimetypes.add_type("text/markdown; charset=utf-8", ".md")
mimetypes.add_type("video/mp4", ".mp4")


def public_view(c):
    return cms.public_view(c)


class H(BaseHTTPRequestHandler):
    server_version = "LaunchCaseLib/1.0"

    def log_message(self, fmt, *a):
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % a))

    # ---------------- helpers
    def send_json(self, obj, code=200, headers=None):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(b)

    def token_admin(self):
        tok = self.headers.get("X-Admin-Token", "")
        return bool(tok) and hmac.compare_digest(tok.encode(), store.admin_token().encode())

    def is_admin(self):
        return bool(cms_auth.session(self.headers)) or self.token_admin()

    def same_origin(self):
        origin = self.headers.get("Origin")
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            return False
        if not origin:
            return True
        parsed = urlparse(origin)
        return parsed.scheme in ("http", "https") and parsed.netloc == self.headers.get("Host")

    def mutation_allowed(self):
        if not self.same_origin():
            return False
        if self.token_admin():
            return True
        session = cms_auth.session(self.headers)
        return bool(session) and hmac.compare_digest(self.headers.get("X-CSRF-Token", "").encode(), session['csrf'].encode())

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        super().end_headers()

    def body(self):
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            raise cms.ContentError("需要 application/json 请求", 415)
        n = int(self.headers.get("Content-Length") or 0)
        if not 0 <= n <= 2 * 1024 * 1024:
            raise cms.ContentError("请求内容过大", 413)
        value = json.loads(self.rfile.read(n) or b"{}")
        if not isinstance(value, dict):
            raise cms.ContentError("内容需为 JSON 对象")
        return value

    def send_file(self, path, head=False):
        if not os.path.isfile(path):
            return self.send_json({"error": "not found"}, 404)
        size = os.path.getsize(path)
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        rng = self.headers.get("Range")
        start, end, code = 0, size - 1, 200
        if rng and size:
            m = re.match(r"bytes=(\d*)-(\d*)", rng)
            if m:
                if m.group(1):
                    start = int(m.group(1)); end = int(m.group(2)) if m.group(2) else size - 1
                else:
                    start = max(0, size - int(m.group(2)))
                end = min(end, size - 1)
                code = 206
        if start > end or start >= size and size:
            return self.send_json({"error": "range not satisfiable"}, 416)
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if code == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Cache-Control", "no-store" if not path.startswith(STATIC + os.sep) or os.path.basename(path) == "cms.html" else "no-cache")
        self.end_headers()
        if head:
            return
        with open(path, "rb") as f:
            f.seek(start)
            left = end - start + 1
            try:
                while left > 0:
                    chunk = f.read(min(256 * 1024, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def find(self, cid):
        return next((c for c in store.load_cases() if c["id"] == cid), None)

    # ---------------- routing
    def do_HEAD(self):
        self.route("GET", head=True)

    def do_GET(self):
        self.route("GET")

    def do_POST(self):
        self.route("POST")

    def do_PUT(self):
        self.route("PUT")

    def route(self, method, head=False):
        try:
            u = urlparse(self.path)
            p = unquote(u.path)
            q = parse_qs(u.query)
            if p.startswith("/api/"):
                return self.api(method, p, q)
            # The existing public manual is an intentional symlink outside static.
            if p == "/static/README.md" and method == "GET":
                return self.send_file(os.path.join(store.ROOT, "README.md"), head)
            first = p.strip("/").split("/")[0]
            if first in SERVE_DIRS and method == "GET":
                base = SERVE_DIRS[first]
                rel = os.path.normpath(p[len(first) + 2:])
                target = os.path.realpath(os.path.join(base, rel))
                if not target.startswith(os.path.realpath(base) + os.sep):
                    return self.send_json({"error": "bad path"}, 400)
                if first in {"media", "brand_skills"} and not self.is_admin() and not cms.public_asset(p):
                    return self.send_json({"error": "not found"}, 404)
                return self.send_file(target, head)
            # Public pages and the authenticated CMS share one persistent SPA shell.
            return self.send_file(os.path.join(STATIC, "index.html"), head)
        except cms.ContentError as exc:
            return self.send_json({"error": str(exc)}, exc.status)
        except (ValueError, UnicodeError):
            return self.send_json({"error": "请求格式不正确"}, 400)
        except Exception:
            traceback.print_exc()
            return self.send_json({"error": "server error"}, 500)

    def api(self, method, p, q):
        if re.match(r"^/api/cases/[\w.-]+/breakdown/?$", p):
            return self.send_json({"error": "在线拉片已取消，请在案例详情中选择自己的 AI 工具", "code": "online_breakdown_removed"}, 410)
        m = re.match(r"^/api/cases/([\w.-]+)$", p)
        if p == "/api/cases" and method == "GET":
            cs = [public_view(c) for c in store.load_cases() if c.get("status") == "published"]
            return self.send_json({"cases": cs, "generated_at": store.now_iso()})
        if m and method == "GET":
            c = self.find(m.group(1))
            if not c or (c.get("status") != "published" and not self.is_admin()):
                return self.send_json({"error": "not found"}, 404)
            return self.send_json(public_view(c))
        if p == "/api/auth/login" and method == "POST":
            if not self.same_origin():
                return self.send_json({"error": "请求来源无效"}, 403)
            result, error, code = cms_auth.login(self.body().get("password"), self.client_address[0])
            if error:
                return self.send_json({"error": error}, code)
            token, session = result
            return self.send_json({"ok": True, "csrf": session['csrf']}, headers={"Set-Cookie": cms_auth.cookie_header(token)})
        if p in {"/api/auth/session", "/api/admin/check"} and method == "GET":
            session = cms_auth.session(self.headers)
            return self.send_json({"ok": self.is_admin(), "csrf": session['csrf'] if session else ""}, 200 if self.is_admin() else 401)
        if p.startswith("/api/admin/") or p in {"/api/auth/logout", "/api/auth/password"}:
            if not self.is_admin():
                return self.send_json({"error": "请先登录内容管理平台"}, 401)
            if method != "GET" and not self.mutation_allowed():
                return self.send_json({"error": "会话校验失败，请刷新后重试"}, 403)
            if p == "/api/auth/logout" and method == "POST":
                cms_auth.logout(self.headers)
                return self.send_json({"ok": True}, headers={"Set-Cookie": cms_auth.cookie_header(max_age=0)})
            if p == "/api/auth/password" and method == "POST":
                body = self.body()
                # Reuse the login limiter for current-password verification.
                result, error, code = cms_auth.login(body.get("current_password"), self.client_address[0])
                if error:
                    return self.send_json({"error": error}, code)
                cms_auth.set_password(body.get("new_password"))
                initial = os.path.join(store.DATA, 'cms_initial_password.txt')
                if os.path.exists(initial):
                    os.unlink(initial)
                return self.send_json({"ok": True}, headers={"Set-Cookie": cms_auth.cookie_header(max_age=0)})
            if p == "/api/admin/uploads" and method == "POST":
                return self.send_json(upload(self), 201)
            if p == "/api/admin/cases":
                if method == "POST":
                    return self.send_json(cms.create(self.body()), 201)
                if method == "GET":
                    st = (q.get("status") or ["all"])[0]
                    cs = [cms.admin_view(c) for c in store.load_cases()]
                    cs = [c for c in cs if st == "all" or c.get("status") == st]
                    cs.sort(key=lambda c: c.get("updated_at", c.get("added_at", "")), reverse=True)
                    return self.send_json({"cases": cs})
            m2 = re.fullmatch(r"/api/admin/cases/([\w.-]+)(?:/(submit|approve|reject|unpublish))?", p)
            if m2:
                cid, action = m2.groups()
                if method == "GET" and not action:
                    c = self.find(cid)
                    return self.send_json(cms.admin_view(c)) if c else self.send_json({"error": "内容不存在"}, 404)
                if method == "PUT" and not action or method == "POST" and action:
                    return self.send_json(cms.change(cid, action or 'edit', self.body()))
        return self.send_json({"error": "not found"}, 404)



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8787)))
    ap.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    a = ap.parse_args()
    store.admin_token()
    cms_auth.ensure_password()
    print(f"Launch 案例库 on http://{a.host}:{a.port}  CMS: /review", flush=True)
    ThreadingHTTPServer((a.host, a.port), H).serve_forever()


if __name__ == "__main__":
    main()
