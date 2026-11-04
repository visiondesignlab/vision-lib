"""Authenticated local uploads with size limits and generated filenames."""
import os
import shutil
import tempfile
import threading
import uuid
from urllib.parse import unquote
from PIL import Image, ImageOps, UnidentifiedImageError
import mediautil
import store
from cms_content import ContentError

LIMIT = 200 * 1024 * 1024
_slots = threading.BoundedSemaphore(2)


def upload(handler):
    kind = handler.headers.get('X-Upload-Kind', '')
    name = os.path.basename(unquote(handler.headers.get('X-File-Name', 'file')))
    ext = os.path.splitext(name)[1].lower()
    allowed = {'cover': {'.jpg', '.jpeg', '.png', '.webp'}, 'image': {'.jpg', '.jpeg', '.png', '.webp'},
               'video': {'.mp4', '.mov', '.webm'}, 'attachment': {'.md', '.txt', '.pdf'}}
    if kind not in allowed or ext not in allowed[kind]:
        raise ContentError('不支持这个文件格式，请按上传说明选择文件')
    size = int(handler.headers.get('Content-Length', '0'))
    limit = LIMIT if kind == 'video' else 20 * 1024 * 1024
    if not 0 < size <= limit:
        raise ContentError(f'文件大小需在 1 字节到 {limit // 1024 // 1024} MB 之间', 413)
    if not _slots.acquire(blocking=False):
        raise ContentError('正在处理其他素材，请稍后重试', 429)
    folder = 'cms-assets-' + uuid.uuid4().hex
    dest = os.path.join(store.MEDIA, folder)
    os.makedirs(dest)
    src = os.path.join(dest, 'source' + ext)
    try:
        handler.connection.settimeout(120)
        with open(src, 'wb') as f:
            left = size
            while left:
                chunk = handler.rfile.read(min(left, 1024 * 1024))
                if not chunk:
                    raise ContentError('上传中断，请重试')
                f.write(chunk)
                left -= len(chunk)
        base = '/media/' + folder + '/'
        if kind in {'cover', 'image'}:
            with Image.open(src) as image:
                if image.width * image.height > 40_000_000:
                    raise ContentError('图片尺寸过大，请缩小到 4000 万像素以内')
                image = ImageOps.exif_transpose(image).convert('RGB')
                image.thumbnail((2400, 2400))
                image.save(os.path.join(dest, 'image.jpg'), quality=90)
            result = {'url': base + 'image.jpg', 'name': name, 'kind': kind}
        elif kind == 'video':
            try:
                media = mediautil.process_video(src, folder)
            except Exception as exc:
                raise ContentError('视频处理失败，请使用有效的 MP4、MOV 或 WebM 文件') from exc
            result = {'media': media, 'name': name, 'kind': kind}
        else:
            with open(src, 'rb') as f:
                data = f.read()
            if ext == '.pdf' and not data.startswith(b'%PDF-'):
                raise ContentError('文件不是有效的 PDF')
            if ext in {'.md', '.txt'}:
                try:
                    data.decode('utf-8')
                except UnicodeDecodeError as exc:
                    raise ContentError('文本附件需为 UTF-8 编码') from exc
            shutil.copyfile(src, os.path.join(dest, 'attachment' + ext))
            result = {'url': base + 'attachment' + ext, 'name': name, 'kind': kind}
        os.unlink(src)
        return result
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
        shutil.rmtree(dest, ignore_errors=True)
        raise ContentError('文件无法读取，请检查格式后重试') from exc
    except Exception:
        shutil.rmtree(dest, ignore_errors=True)
        raise
    finally:
        _slots.release()
