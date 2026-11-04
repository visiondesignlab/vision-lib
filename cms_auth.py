"""Password authentication; browser credentials never enter localStorage."""
import hashlib
import hmac
import os
import secrets
import threading
import time
from http.cookies import SimpleCookie
import store

COOKIE = 'vision_cms_session'
TTL = 12 * 3600
_lock = threading.RLock()
_sessions = {}
_attempts = {}


def password_path():
    return os.path.join(store.DATA, 'cms_password.json')


def hash_password(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()


def set_password(password):
    if not isinstance(password, str) or not 12 <= len(password) <= 256:
        raise ValueError('密码需为 12–256 个字符')
    salt = secrets.token_hex(16)
    with store.locked():
        store._write(password_path(), {'salt': salt, 'hash': hash_password(password, salt)})
    with _lock:
        _sessions.clear()


def ensure_password():
    if os.path.exists(password_path()):
        return
    initial = os.environ.get('CASELIB_CMS_INITIAL_PASSWORD') or ('Vision-' + secrets.token_urlsafe(12))
    set_password(initial)
    if not os.environ.get('CASELIB_CMS_INITIAL_PASSWORD'):
        path = os.path.join(store.DATA, 'cms_initial_password.txt')
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(initial + '\n')


def verify(password):
    if not isinstance(password, str) or len(password) > 256:
        return False
    data = store._read(password_path(), {})
    return bool(data) and hmac.compare_digest(hash_password(password, data['salt']), data['hash'])


def session(headers):
    try:
        cookie = SimpleCookie(headers.get('Cookie', ''))
        token = cookie[COOKIE].value
    except (KeyError, ValueError):
        return None
    key = hashlib.sha256(token.encode()).hexdigest()
    with _lock:
        entry = _sessions.get(key)
        if entry and entry['expires'] > time.time():
            return entry
        _sessions.pop(key, None)
    return None


def login(password, ip):
    with _lock:
        now = time.time()
        for key in list(_attempts):
            _attempts[key] = [t for t in _attempts[key] if now - t < 300]
            if not _attempts[key]:
                del _attempts[key]
        attempts = _attempts.setdefault(ip, [])
        if len(attempts) >= 5:
            return None, '尝试次数过多，请 5 分钟后重试', 429
        if not verify(password):
            attempts.append(now)
            return None, '密码不正确，请重新输入', 401
        _attempts.pop(ip, None)
        token = secrets.token_urlsafe(32)
        entry = {'csrf': secrets.token_urlsafe(24), 'expires': now + TTL}
        for key, value in list(_sessions.items()):
            if value['expires'] <= now:
                _sessions.pop(key, None)
        _sessions[hashlib.sha256(token.encode()).hexdigest()] = entry
        return (token, entry), None, 200


def logout(headers):
    try:
        token = SimpleCookie(headers.get('Cookie', ''))[COOKIE].value
        with _lock:
            _sessions.pop(hashlib.sha256(token.encode()).hexdigest(), None)
    except (KeyError, ValueError):
        pass


def cookie_header(token='', max_age=TTL):
    secure = '; Secure' if os.environ.get('CASELIB_COOKIE_SECURE') == '1' else ''
    return f'{COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={max_age}{secure}'
