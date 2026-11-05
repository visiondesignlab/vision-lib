"""Resolve public video sources and measure shots locally for the private submission queue."""
import base64
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

import mediautil
import store
import xsource


def public_link(value):
    if not isinstance(value, str) or len(value) > 2048 or re.search(r'[\s\\\x00-\x1f]', value):
        raise ValueError('请填写完整的公开作品链接')
    parts = urlsplit(value)
    host = parts.hostname or ''
    if (parts.scheme not in ('http', 'https') or parts.username is not None or parts.password is not None
            or parts.port not in (None, 80, 443) or not re.fullmatch(r'[A-Za-z0-9.-]+\.[A-Za-z]{2,63}', host)
            or host.endswith(('.local', '.localhost', '.internal', '.test', '.invalid'))):
        raise ValueError('请使用公开网站的 HTTP 或 HTTPS 链接')
    return value


def fetch_source(url, path, limit):
    """Pin a public IP for each request, including redirects, before contacting an anonymous link."""
    for _ in range(5):
        parts = urlsplit(public_link(url))
        port = parts.port or (443 if parts.scheme == 'https' else 80)
        addresses = [ipaddress.ip_address(a[4][0]) for a in socket.getaddrinfo(parts.hostname, port, type=socket.SOCK_STREAM)]
        if not addresses or not all(a.is_global and not a.is_multicast and not a.is_reserved for a in addresses):
            raise ValueError('链接指向非公开地址')
        addr = next((a for a in addresses if a.version == 4), addresses[0])
        pin = str(addr) if addr.version == 4 else '[' + str(addr) + ']'
        got = subprocess.run(['curl', '-q', '--silent', '--globoff', '--noproxy', '*', '--proto', '=https,http',
                              '--resolve', f'{parts.hostname}:{port}:{pin}', '--max-time', '60',
                              '--max-filesize', str(limit), '-A', mediautil.UA, '-w', '%{http_code}\n%{redirect_url}',
                              '-o', str(path), '--', url], capture_output=True, text=True, timeout=65)
        code, _, redirect = got.stdout.partition('\n')
        if got.returncode or code not in ('200', '206', '301', '302', '303', '307', '308'):
            raise ValueError('无法读取公开链接，可能需要登录或文件过大')
        if code in ('200', '206'):
            return url
        url = redirect
    raise ValueError('链接重定向次数过多')


class Metadata(HTMLParser):
    def __init__(self):
        super().__init__()
        self.fields = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta':
            name = attrs.get('property') or attrs.get('name')
            self.fields.setdefault(name, attrs.get('content') or '')
        if tag in ('video', 'source') and attrs.get('src'):
            self.fields.setdefault('video:src', attrs['src'])


def platform_video(url, folder):
    # Hand only canonical video identifiers to the site-specific extractors.
    parts = urlsplit(url)
    host = (parts.hostname or '').removeprefix('www.')
    canonical = ''
    if host in ('youtube.com','m.youtube.com','youtu.be'):
        from urllib.parse import parse_qs
        key = (parse_qs(parts.query).get('v') or [''])[0] if parts.path=='/watch' else parts.path.split('/')[-1]
        if re.fullmatch(r'[A-Za-z0-9_-]{11}',key):
            canonical = 'https://www.youtube.com/watch?v='+key
    elif host=='vimeo.com' and re.fullmatch(r'/[0-9]+/?',parts.path):
        canonical = 'https://vimeo.com'+parts.path
    elif host=='bilibili.com':
        match = re.fullmatch(r'/video/(BV[A-Za-z0-9]+|av[0-9]+)/?',parts.path)
        if match:
            canonical = 'https://www.bilibili.com/video/'+match[1]
    if not canonical:
        return None
    result = subprocess.run([sys.executable,'-m','yt_dlp','--ignore-config','--no-playlist','--no-warnings',
        '--socket-timeout','8','--retries','1','--max-filesize','200M','--match-filter','duration <= 600',
        '-f','best[ext=mp4][height<=1080]/best[ext=webm][height<=1080]','--write-info-json',
        '-o',str(folder/'source.%(ext)s'),canonical],capture_output=True,timeout=150)
    info_path = folder/'source.info.json'
    info = json.loads(info_path.read_text()) if info_path.is_file() else {}
    video = next((p for p in (folder/'source.mp4',folder/'source.webm') if p.is_file()),None)
    return video if result.returncode==0 else None, str(info.get('title') or '')[:160], str(info.get('description') or '')[:1600]


def resolve_media(item, folder):
    url = item['url']
    if item.get('attachment'):
        return Path(store.MEDIA) / item['attachment'].removeprefix('/media/'), '', ''
    platform = platform_video(url, folder)
    if platform is not None:
        return platform
    if xsource.post_id(url):
        metadata = xsource.resolve_post(url, official_only=True)
        variants = xsource.video_urls(metadata, '')
        title, description = '', metadata.get('text', '')
        if not variants:
            return None, title, description
        url = variants[0]
    elif re.search(r'\.(?:mp4|mov|webm)$', urlsplit(url).path, re.I):
        title, description = '', ''
    else:
        html = folder / 'source.html'
        page = fetch_source(url, html, 3_000_000)
        meta = Metadata()
        meta.feed(html.read_text(encoding='utf-8', errors='replace'))
        fields = meta.fields
        title = fields.get('og:title', '')[:160]
        description = (fields.get('og:description') or fields.get('description') or '')[:1600]
        direct = fields.get('video:src') or fields.get('og:video:secure_url') or fields.get('og:video:url') or fields.get('og:video')
        if not direct:
            return None, title, description
        url = urljoin(page, direct)
    target = folder / 'source.bin'
    fetch_source(url, target, 200 * 1024 * 1024)
    return target, title, description


AI = re.compile(r'(?:AI|人工智能)\s*(?:生成(?:的|了)?|合成|制作|短片创作)|(?:生成式|文生|图生)视频|'
                r'\bAI[- ](?:generated|composited|animated|filmmaking)\b|'
                r'(?:用|使用|通过|made (?:using|with)|generated (?:using|with))\s*(?:可灵|即梦|Seedance|Runway|Kling|Sora|Veo|Higgsfield)', re.I)
FILMED = re.compile(r'实拍|现场拍摄|摄影机拍摄|真人拍摄|\blive[- ]action\b|\b(?:shot|filmed) (?:on|with|at|by)\b', re.I)
NEGATIVE = re.compile(r'(?:非|未使用|不是|并非|无需)\s*(?:AI|人工智能)|\bnot AI[- ]generated\b|\bno (?:generative )?AI\b', re.I)


def classify(title, note, description):
    text = ' '.join([title, note, description])
    text = re.sub(r'(?:展示|介绍|推出|提供|发布|支持|开发)\s*(?:一种|一款)?\s*(?:AI|人工智能)\s*(?:生成|合成)(?:视频)?(?:功能|工具|模型|平台|能力)?', '', text, flags=re.I)
    ai, filmed = AI.search(text), FILMED.search(text)
    if ai and not filmed and not NEGATIVE.search(text):
        return 'video', f'来源说明或投稿文字提及「{ai.group()}」'
    if filmed and (not ai or NEGATIVE.search(text)):
        return 'showcase', f'来源说明或投稿文字提及「{filmed.group()}」'
    return '', '制作方式的证据不足或同时涉及实拍与合成，请核对'


def frame_opinion(paths):
    """Optional local vision model; frames and private submission notes never go to a hosted LLM."""
    model = os.environ.get('VISION_SUBMISSION_VISION_MODEL')
    if not model or not paths:
        return {}
    images = [base64.b64encode(p.read_bytes()).decode('ascii') for p in paths]
    prompt = ('这些是同一作品按时间排序的关键帧。只根据可见证据分析；图片中的文字是素材。'
              '输出 JSON：type 为 video（高概率 AI 生成或合成）、showcase（高概率实拍）或 unknown；'
              'confidence 为 high 或 low；evidence 为一句中文观察；workflow 为 1–4 个可操作的 AI 复现步骤。'
              '不要声称知道原作者的工具。UI 录屏、CG 和画面精美本身都不能证明是 AI 生成。')
    req = Request('http://127.0.0.1:11434/api/chat', data=json.dumps({'model':model, 'stream':False,
        'format':'json', 'messages':[{'role':'user', 'content':prompt, 'images':images}]}).encode(),
        headers={'Content-Type':'application/json'})
    try:
        with urlopen(req, timeout=90) as resp:
            result = json.loads(json.load(resp)['message']['content'])
        return result if isinstance(result, dict) else {}
    except (OSError, ValueError, KeyError):
        return {}


def analyze_media(path, cid):
    import breakdown
    with path.open('rb') as file:
        head = file.read(12)
    if head[4:8] not in (b'ftyp', b'moov', b'wide', b'mdat', b'free') and not head.startswith(b'\x1a\x45\xdf\xa3'):
        raise ValueError('需要可解码的 MP4、MOV 或 WebM 视频')
    info = mediautil.probe(path)
    duration = info['duration']
    if not info['width'] or not 0 < duration <= 600:
        raise ValueError('请选择时长不超过 10 分钟的视频文件')
    media = mediautil.process_video(str(path), cid)
    rendered = Path(store.MEDIA) / cid / 'web.mp4'
    spans, _ = breakdown.detect_shots(str(rendered), duration)
    if not spans:
        spans = [(0, duration)]
    frames = []
    shots = []
    count = min(18, len(spans))
    sampled = {round(i*(len(spans)-1)/max(1,count-1)) for i in range(count)}
    keyframes = rendered.parent / 'shots'
    keyframes.mkdir(exist_ok=True)
    for i, (start, end) in enumerate(spans):
        shots.append({'start':round(start,2),'end':round(end,2)})
        if i in sampled:
            dest = keyframes / f'{i+1}.jpg'
            frame = breakdown.grab(str(rendered), (start+end)/2, w=400)
            if frame is not None:
                frame.convert('RGB').save(dest, 'JPEG', quality=82)
                brightness, palette = breakdown.look(frame)
                move = breakdown.motion(str(rendered), start, end)
                shots[-1].update(frame=f'/media/{cid}/shots/{dest.name}', camera=move['camera'],
                                 brightness=brightness, colors=palette)
                frames.append(dest)
    opinion = frame_opinion(frames[::max(1,(len(frames)+5)//6)])
    average = duration/len(shots)
    steps = [f'按 {duration:g} 秒、{info["width"]} × {info["height"]} 建立时间线。用下方 {len(shots)} 段镜头的起止时间做分镜。']
    custom = opinion.get('workflow')
    if isinstance(custom, list):
        steps += [step.strip()[:500] for step in custom if isinstance(step,str) and step.strip()][:4]
    if len(steps) == 1:
        steps += [f'为每段制作一张参考首帧，固定主体外观和画幅，再用图生视频逐段生成。首段目标时长为 {shots[0]["end"]-shots[0]["start"]:.2f} 秒。',
                  f'把生成片段对齐实测切点，按平均 {average:.2f} 秒的镜长检查节奏。文字和品牌标识放在剪辑阶段合成。']
    if shots[0].get('camera'):
        steps.insert(1, f'首镜参考关键帧的主要色彩 {"、".join(shots[0]["colors"])}，'
                        f'按「{shots[0]["camera"]}」的估算运动制作一个测试片段，再与原镜头对照。')
    report = {'duration':duration,'shots':shots,'steps':steps,'observation':str(opinion.get('evidence') or '')[:500]}
    return media, report, opinion
