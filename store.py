"""Shared JSON store for the case library (used by server.py, ingest.py, seed.py).

Data lives in data/cases.json (list of case records) and data/rejected.json
(normalized source URLs that were rejected and must never be re-proposed).
Writes are atomic (temp file + rename) and guarded by an flock on data/.lock,
so the web server and the daily ingest job can run at the same time.
"""
import fcntl, json, os, re, secrets, tempfile, time
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("CASELIB_DATA_DIR", os.path.join(ROOT, "data"))
MEDIA = os.environ.get("CASELIB_MEDIA_DIR", os.path.join(ROOT, "media"))
CASES = os.path.join(DATA, "cases.json")
REJECTED = os.path.join(DATA, "rejected.json")
LOCK = os.path.join(DATA, ".lock")
TOKEN_FILE = os.path.join(DATA, "admin_token.txt")
CST = timezone(timedelta(hours=8))

TYPES = {"video": "视频", "graphic": "平面", "brand_skill": "品牌 Skill", "skill_repo": "Skill 仓库"}
STATUSES = ("draft", "pending", "published", "rejected", "archived")


def now_iso():
    return datetime.now(CST).isoformat(timespec="seconds")


def norm_url(u):
    """Normalize a source URL for dedupe: lowercase host, strip query/fragment/trailing slash,
    map twitter.com/x.com/mobile variants and /i/status/ to x.com/status/<id>."""
    if not u:
        return ""
    u = u.strip()
    m = re.search(r"(?:twitter\.com|x\.com)/(?:[^/]+|i(?:/web)?)/status(?:es)?/(\d+)", u, re.I)
    if m:
        return "x.com/status/" + m.group(1)
    m = re.search(r"github\.com/([\w.-]+)/([\w.-]+)", u, re.I)
    if m:
        return ("github.com/" + m.group(1) + "/" + re.sub(r"\.git$", "", m.group(2))).lower()
    u = re.sub(r"^https?://(www\.)?", "", u, flags=re.I).split("#")[0].split("?")[0].rstrip("/")
    return u.lower()


@contextmanager
def locked():
    os.makedirs(DATA, exist_ok=True)
    with open(LOCK, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def _read(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write(path, obj):
    d = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def load_cases():
    return _read(CASES, [])


def save_cases(cases):
    _write(CASES, cases)


def load_rejected():
    return _read(REJECTED, [])


def save_rejected(rej):
    _write(REJECTED, sorted(set(rej)))


def known_urls(cases=None, rejected=None):
    cases = load_cases() if cases is None else cases
    rejected = load_rejected() if rejected is None else rejected
    s = set(rejected)
    for c in cases:
        s.add(norm_url((c.get("source") or {}).get("url", "")))
    s.discard("")
    return s


def admin_token():
    tok = os.environ.get("CASELIB_ADMIN_TOKEN")
    if tok:
        return tok.strip()
    if not os.path.exists(TOKEN_FILE):
        os.makedirs(DATA, exist_ok=True)
        with open(TOKEN_FILE, "w") as f:
            f.write(secrets.token_urlsafe(24) + "\n")
        os.chmod(TOKEN_FILE, 0o600)
    return open(TOKEN_FILE).read().strip()


def slug(s):
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s[:60] or "case-" + str(int(time.time()))
