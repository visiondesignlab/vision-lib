"""Editorial tags for cases: keep human labels, consolidate synonyms and discard import metadata."""
import re
from unicodedata import normalize

# These tokens already live in rank, featured, source, or review metadata.
IMPORT_LABELS = {'合集帖', '专帖', '推荐', '候补', 'GitHub 搜索', 'launchvideos.gallery', '热门补充',
                 '标杆案例', '其他', '待分类', 'remotion skill'}
ALIASES = {
    'AI Agent': ('Agent', 'ai-agent', 'agent', 'autonomous-agents', 'Agent 全流程'),
    'Agent Skill': ('agent-skills', 'agent-skill'),
    '动态图形': ('动效', 'motion', 'motion-graphics'),
    '设计': ('design',), '图像与视频生成': ('视频图像生成',),
    '语音与音频': ('语音音频',), '金融科技': ('金融',),
    '产品发布片': ('产品主片',), '功能演示': ('功能短片',), '预告片': ('预告',),
    '品牌宣传片': ('品牌片',), '电影感短片': ('真人电影感短片',),
    '混剪': ('用户声音 + 梗剪辑',), '合成特效': ('AI 原型 + AE 精修',),
    '口播解说': ('口播/解说',), '字幕制作': ('发布/字幕',),
    '视频拉片': ('视频拆解', '拉片'), '语音合成': ('tts',),
    '创意编程': ('creative-coding',), '编程助手': ('ai-coding-assistant',),
    '短视频': ('short-video',), '点云': ('point-cloud',), 'ACP': ('acp','agent-client-protocol'),
    'Claude Code': ('claude-code',), 'DeepSeek': ('deepseek-harness',),
    '演示文稿': ('ppt',), 'AI': (), 'Codex': (), 'Claude': (), 'Anthropic': (),
    'Remotion': (), 'FFmpeg': (), 'Figma': (), 'After Effects': (), 'HTML': (), 'PPTX': (),
}
CANONICAL = {name.casefold(): label for label, names in ALIASES.items() for name in (label, *names)}
# Derive only from the work's own title, description line or repository, never its generic prompts.
EVIDENCE = {
    'Remotion': r'\bRemotion\b', 'FFmpeg': r'\bffmpeg\b', 'After Effects': r'After Effects|AE 精修',
    'React': r'\bReact\b', 'Three.js': r'\bthree\.js\b', 'GSAP': r'\bGSAP\b', 'Lottie': r'\bLottie\b',
    'Claude Code': r'Claude[ -]Code', 'Codex': r'\bCodex\b', 'HyperFrames': r'\bHyperFrames\b',
    '口播解说': r'口播|解说视频', '字幕制作': r'字幕|subtitles?', '自动剪辑': r'自动剪辑|自动粗剪|去口癖',
    '语音合成': r'生成语音|语音合成|text.to.speech', '音效': r'音效|\bSFX\b',
    'UI 动效': r'UI 动效|界面动效', '图像生成': r'生成图像|图像生成|generate images?|make images',
    '品牌宣传片': r'品牌愿景片|品牌宣传片', '功能演示': r'功能发布|功能演示',
    '产品发布片': r'产品主片|产品发布片', '预告片': r'上线预告|硬件预告',
    '机器人': r'机器人|robotics', '视频拉片': r'逐镜拆解|拉片分析',
    '开发者工具': r'developer tools?|开发者工具', '硬件': r'wearable|硬件预告',
}


def canonical_tags(tags):
    result = {}
    for value in tags or []:
        raw = ' '.join(normalize('NFC', value).split())
        if not raw or raw in IMPORT_LABELS or re.fullmatch(r'Top 50\s*#\d+|\d{4}-\d{2} 热度刷新', raw, re.I):
            continue
        name = CANONICAL.get(raw.casefold(), raw)
        result.setdefault(name.casefold(), name)
    return list(result.values())


def suggested_tags(case):
    source = case.get('source') or {}
    evidence = ' '.join([case.get('title',''), case.get('subtitle',''), source.get('repo','')])
    tags = list(case.get('tags') or [])
    category = case.get('category')
    if category:
        tags.append(category)
    tags.extend(tag for tag, pattern in EVIDENCE.items() if re.search(pattern, evidence, re.I))
    return canonical_tags(tags)
