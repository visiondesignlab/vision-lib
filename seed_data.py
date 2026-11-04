# -*- coding: utf-8 -*-
"""Seed content. Every metric/source here comes from:
  - live X API reads on 2026-11-04 (data/_xposts_live.json), or
  - the Page "X 产品 Launch Video 制作手册" (Top 50 skill table, benchmark table), read 2026-11-04.
Reproduction prompts / how-to steps are written by the team (that's the point of the library)."""

PAGE = "https://cursor.com/canvas/store-31664c93-fdf7-4cc1-b4d8-271ca3ffe4d7/2be3f65d-b57b-4606-b278-439597dff0b7"

SK_HF = {"name": "HyperFrames", "repo": "heygen-com/hyperframes", "url": "https://github.com/heygen-com/hyperframes"}
SK_RM = {"name": "Remotion Skills", "repo": "remotion-dev/skills", "url": "https://github.com/remotion-dev/skills"}
SK_HM = {"name": "huashu-motion", "repo": "alchaincyf/huashu-motion", "url": "https://github.com/alchaincyf/huashu-motion"}
SK_VU = {"name": "video-use", "repo": "browser-use/video-use", "url": "https://github.com/browser-use/video-use"}
SK_BRAG = {"name": "brag", "repo": "latent-spaces/brag", "url": "https://github.com/latent-spaces/brag"}
SK_LOT = {"name": "motion-design-skill", "repo": "LottieFiles/motion-design-skill", "url": "https://github.com/LottieFiles/motion-design-skill"}
SK_FF = {"name": "ffmpeg-skill", "repo": "kajisho5/ffmpeg-skill", "url": "https://github.com/kajisho5/ffmpeg-skill"}
SK_HIG = {"name": "Higgsfield Skills", "repo": "higgsfield-ai/skills", "url": "https://github.com/higgsfield-ai/skills"}
SK_SEED = {"name": "seedance2-skill", "repo": "dexhunter/seedance2-skill", "url": "https://github.com/dexhunter/seedance2-skill"}
SK_SHOT = {"name": "video-shotcraft", "repo": "Vincentwei1021/video-shotcraft", "url": "https://github.com/Vincentwei1021/video-shotcraft"}

BRAND_REF = "开工前先读本库「品牌 Skill」里的《Launch 视频通用规范》，按它的导出规格和自检清单交付。"

# ---------------------------------------------------------------- Ambi (local files)
AMBI = [
 dict(pid="2109292120301519094", category="动效特效", title="Ambi 上线预告：玻璃焦散文字",
      subtitle="7 秒方形预告 · 磨砂玻璃光影 + 逐字折射文字 · 「Ambi launches tomorrow」",
      kind_note="动态图形（非实拍）：整片是柔焦的绿色磨砂玻璃背景，光斑缓慢流动，文字局部被玻璃折射扭曲。",
      tags=["预告", "teaser", "玻璃质感", "文字动画", "1:1", "Ambi"],
      skills=[SK_HF, SK_LOT], tools=["HyperFrames 或 After Effects", "WebGL / CSS 滤镜做焦散", "ffmpeg 导出"],
      prompt="""用 HyperFrames skill 做一支 7 秒、1080×1080、30fps 的产品上线预告（参考 Ambi 的 launch 前一天预告）。

画面：
- 背景：柔和的鼠尾草绿到米色的磨砂玻璃渐变，叠加缓慢漂移的水波焦散光（caustics），整体低对比、有颗粒感。
- 左上角放 {产品} 的小 logo，右上角写发布日期「{Oct 12}」，下面一条细小的进度刻度。
- 左侧文字层级：两行浅灰小字「Real-time context. / Real-time interactive.」→ 一行白色大标题「Real-time action.」→ 三行全大写小标签「ROUTINE / TASK / FOR YOU」，标签之间留宽行距。
- 底部：「One day.」+ 小字「{产品} App Coming Soon」。

动效：
- 0–1s 背景先出现，光斑开始流动；1–3s 大标题逐字出现，每个字被一条竖向玻璃折痕扫过时轻微折射变形；3–6s 小标签依次淡入（每个 0.3s 间隔）；6–7s 保持，结尾能无缝循环回开头。
- 不要旋转、弹跳；所有缓动用 ease-out，单个动作约 0.6–1s。

先给我一张 4 格 contact sheet（0s/2s/4s/6.5s）确认风格，再渲染 MP4（H.264，≤25Mbps）。""",
      how_to=["把文案换成自己的产品：三行小标签写 3 个能力关键词，日期写真实发布日。",
              "安装 HyperFrames skill：`npx skills add heygen-com/hyperframes`，在 Cursor / Claude Code 里粘贴上面的 Prompt。",
              "先让 agent 出 contact sheet，确认背景颜色、字重和留白，再渲染整片。",
              "焦散效果不理想时，让 agent 改用一张焦散纹理图 + 位移滤镜（displacement）代替实时 shader。",
              "导出 1080×1080 MP4，发布前一天发帖；文案一句话说「明天上线」+ 去哪等上线（如 Discord / waitlist）。"]),
 dict(pid="2109660371296424352", category="营销产品", title="Ambi 主片：Life happens mid-thought",
      subtitle="54 秒 4K 产品主片 · Watch → iPhone → Mac 一条上下文主线 · 无人物",
      kind_note="动态图形 + 设备渲染：雾面绿色背景上放 Apple Watch、iPhone、Mac 窗口，UI 卡片在设备之间接力；左侧小字标注「ON YOUR PHONE / ON YOUR DESK」。",
      tags=["主片", "UI 动效", "设备样机", "跨设备", "16:9", "4K", "Ambi"],
      skills=[SK_RM, SK_HF, SK_LOT], tools=["Remotion 或 HyperFrames", "设备样机（Watch / iPhone / Mac 透明 PNG 或 3D 渲染）", "Figma 出 UI 卡片", "ElevenLabs 配乐"],
      prompt="""用 Remotion skill（或 HyperFrames）做一支 50–55 秒、3840×2160（可先 1920×1080 预览）的产品主片，结构参考 Ambi「Life happens mid-thought」。

风格：雾面鼠尾草绿背景，慢速漂移的柔光；UI 卡片是白色半透明圆角卡（圆角 16px、细阴影）；字体用无衬线细体；全片无人物。

镜头表（每个场景一条左侧小字「ON YOUR {设备}」+ 两行标题）：
1. 0–6s  Apple Watch 正面特写，表盘上显示 {产品} 动画 → 推近。
2. 6–14s iPhone 居中，屏幕里一条 {功能 1} 的卡片生成；左侧标题「Tell {产品} once. It keeps watch.」
3. 14–22s Mac 窗口：一个周历/任务面板，{功能 2} 的条目逐条出现；标题「Give it a standing brief.」
4. 22–30s 记忆/主题面板：几张彩色主题卡片 + 下方摘要；标题「What matters is already organized around the topic.」
5. 30–40s 对话面板：右上用户问题气泡 → 下方 3 条带图标的回答逐条出现；标题「Ask from the context that is already there.」
6. 40–46s 设置列表里一个开关被打开（一个点击 + 一个音效）。
7. 46–50s 大字「Real-time Context.」后半句渐隐。
8. 50–55s 居中 logo + tagline「{你的 tagline}」+ 一行 CTA（如 Join the waitlist）。

规则：用我们产品真实的 UI 组件和假数据（不要做今天不存在的功能）；每个动作约 1 秒；推近不超过 1.5 倍；切点落在 120 BPM 的小节上。
先给我镜头表（带时长）确认，再一次只做一个场景。""",
      how_to=["把产品真实界面（Figma 或前端组件）交给 agent，指向设计系统或仓库，而不是让它凭记忆画 UI。",
              "新建项目：`npx create-video --yes --blank my-video` → `npx remotion skills add` → `npm run dev`，另开终端启动 agent。",
              "先让 agent 写逐场景镜头表（台词、画面、时长），团队确认后一次只做一个场景。",
              "设备样机用透明 PNG 或 3D 渲染导出的序列，UI 卡片用代码做，方便改一行重渲染。",
              "用 ElevenLabs 生成约 120 BPM 的配乐，把切点和点击对上拍子。",
              "导出 16:9 主片 + 4:5 竖版各一版（竖版重新排版，不要直接裁切）。", BRAND_REF]),
 dict(pid="2109720765667172355", category="电影感叙事", title="Ambi Moment 01：Be Right Back",
      subtitle="45 秒真人场景 · 4:3 · 父亲被女儿叫走，Watch 帮他记住会议 · 后期叠加 UI 卡片",
      kind_note="很可能是真人实拍 + 后期叠加 UI：居家暖光、浅景深、手持感；通知卡片（会议提醒、日历确认）以半透明小卡片形式贴在画面角落。",
      tags=["真人实拍", "生活场景", "UI 叠加", "系列片", "4:3", "Ambi"],
      skills=[SK_VU, SK_HF], tools=["相机 / 手机电影模式", "Premiere / Final Cut / CapCut", "HyperFrames 或 Remotion 做透明 UI 卡片", "可选：Seedance / Kling 生成空镜"],
      prompt="""帮我把一支 45 秒「生活场景 + 产品 UI 卡片」短片拆成可执行的拍摄与后期计划，参考 Ambi Moment 01: Be Right Back。

故事：主角在家用电脑工作 → 孩子过来叫他（涂指甲油）→ 他离开电脑，手表弹出「{产品} 帮你记着会议」的卡片并确认 → 陪孩子 → 回到电脑前，卡片显示「已检查日历 / 已准备好」→ 结尾两只手击掌，手腕上是设备，字幕「{tagline}」。

请输出：
1. 带时长的镜头表（约 10–12 个镜头，每个 3–5 秒），写清景别、机位、动作、台词/环境声、需要叠加的 UI 卡片文字。
2. 拍摄清单：场地、道具、灯光（暖色自然光、浅景深）、演员要求、每个镜头拍几条。
3. 3 张 UI 卡片的设计规格（尺寸、圆角、半透明背景、字号、出现/消失动画 0.4s ease-out），并用 HyperFrames 生成带透明通道的 MOV/WebM，方便在剪辑软件里叠加。
4. 剪辑节奏：前 3 秒就出现产品相关的画面；卡片停留 ≥1.5 秒，静音也能看懂；结尾固定 tagline。""",
      how_to=["先写故事：一个生活中「被打断」的瞬间 + 产品帮你接住的那一下，一集只讲一个能力。",
              "用 Prompt 让 agent 出镜头表和拍摄清单，团队确认后再约人和场地。",
              "实拍：手机电影模式或相机都行，暖色自然光、浅景深，每个镜头多拍几条、多角度。",
              "UI 卡片用 HyperFrames / Remotion 单独渲染成透明视频，剪辑时贴在画面角落，不要挡脸。",
              "有口播或环境声时，可用 video-use 自动粗剪、去口癖、加字幕。",
              "结尾用固定 tagline，系列命名「Moment 0X: 标题」，每集一个功能。",
              "预算紧时可用 AI 视频（Seedance / Kling）补空镜，但主角镜头建议实拍，AI 精细控制难。"]),
 dict(pid="2111109914303299925", category="电影感叙事", title="Ambi Moment 02：Leave It with Me",
      subtitle="30 秒真人场景 · 16:9 · 厨房剥橙子的间隙，产品提议「准备 3 件事」",
      kind_note="很可能是真人实拍 + 后期叠加 UI：绿色百叶窗的厨房、两人对话、橙子特写；画面左侧叠加「Suggested · Prepare 3 things」卡片和 Accept 按钮。",
      tags=["真人实拍", "生活场景", "UI 叠加", "系列片", "16:9", "Ambi"],
      skills=[SK_HF, SK_VU], tools=["相机 / 手机电影模式", "剪辑软件", "HyperFrames 做透明 UI 卡片"],
      prompt="""帮我规划一支 30 秒真人场景短片，参考 Ambi Moment 02: Leave It with Me（主题：把一件事交给 {产品}，它会做完）。

结构：
- 0–3s 开场：厨房/客厅远景 + 左侧 logo，环境声。
- 3–12s 两人日常对话（一人在电脑前，一人剥橙子），提到一件要准备的事。
- 12–20s 画面左侧出现建议卡片「Suggested · {任务名}」+ 两行要点，一人点 Accept。
- 20–26s 插入特写镜头（橙子、咖啡、表情），节奏放慢。
- 26–30s 结尾物件特写（剥开的橙子）+ 字幕「{tagline}」。

请输出：带时长镜头表、每条台词、卡片文案（标题 ≤ 14 个英文字符/行或 6–8 个中文字/行），以及用 HyperFrames 生成卡片透明视频的代码。""",
      how_to=["选一个真实、具体的小任务（准备 3 件事、订位、查资料），让卡片文案就是那个任务。",
              "按镜头表拍摄：远景交代场景，中景对话，特写做节奏。",
              "卡片用代码渲染透明视频，剪辑时放在留白一侧，停留够读两遍。",
              "结尾落在一个有记忆点的物件上，再接 tagline。", BRAND_REF]),
 dict(pid="2112197075945308175", category="电影感叙事", title="Ambi Moment 03：In Passing",
      subtitle="55 秒真人场景 · 4:3 · 公园长椅闲聊，产品记住提到的人和事",
      kind_note="很可能是真人实拍 + 后期叠加 UI：户外公园、两人坐长椅吃冰淇淋，画面中依次出现「Listening Insight 1/2/3」小标签和「Suggested action」卡片。",
      tags=["真人实拍", "户外", "UI 叠加", "记忆", "系列片", "4:3", "Ambi"],
      skills=[SK_HF, SK_VU], tools=["相机 / 手机电影模式", "剪辑软件", "HyperFrames 做标签动画"],
      prompt="""帮我规划一支 50–55 秒真人场景短片，参考 Ambi Moment 03: In Passing（主题：{产品} 在闲聊中记住提到的人和事，不用说第二遍）。

结构：
- 开场：户外长椅两人远景 + 左侧 logo。
- 对话中每提到一个人/信息，画面旁边出现一个小标签「Listening Insight · 1. {人名}」「2. {人名} · {备注}」「3. …」，标签带一个细竖线指向说话人。
- 中段一个极近特写（食物或手部）做节奏停顿。
- 后段出现「Suggested action」卡片：根据刚才的信息给出一个行动，点 Accept。
- 结尾远景 + logo + tagline。

请输出：带时长镜头表、对白（自然口语，不念广告词）、每个标签出现的时间点和文案，以及标签动画的 HyperFrames 代码（细线生长 0.3s + 文字淡入 0.4s）。""",
      how_to=["写一段真实的闲聊对白，里面自然带出 2–3 个「值得记住的信息」。",
              "户外拍摄注意收音：对白要清楚，必要时补录。",
              "标签动画用代码统一做，位置跟随说话人，不要盖住脸。",
              "结尾的行动卡片要和前面听到的信息对得上，这是这支片的「证明」。",
              "用 video-use 处理对白素材：去口癖、加字幕。"]),
 dict(pid="2114733804535377947", category="动效特效", title="Ambi 硬件预告：Life doesn't happen inside an app",
      subtitle="10.5 秒 CG 硬件特写 · 只露设备边缘 · 虚焦转 logo",
      kind_note="3D 渲染（CG）：暖白背景上一台鼠尾草绿金属设备的极近特写（按键、扬声孔），慢速推移，最后虚焦转到居中 logo。",
      tags=["CG", "3D 渲染", "硬件", "预告", "16:9", "Ambi"],
      skills=[SK_HIG], tools=["Blender（或 C4D）", "可选：AI 视频首尾帧（Kling / Veo）", "剪辑软件"],
      prompt="""帮我做一支 10 秒的硬件预告，参考 Ambi「Life doesn't happen inside an app」。

画面：暖白色（#F1EEEA 左右）无缝背景；{设备} 的一角极近特写——金属倒角、一个圆形按键、两条扬声孔，屏幕是纯黑。镜头沿着设备边缘缓慢平移 + 轻微推近（0–6s），6–7.5s 焦点拉虚，整个画面变成柔和的灰色色块，7.5–10.5s 淡出到居中 logo（深墨绿色，小号）。

方案 A（Blender）：给我建模要点（倒角半径、材质：拉丝金属 + 轻微 clearcoat）、三点布光（大面积柔光 + 一条边缘高光）、相机参数（85–100mm，f/2.8 景深）、动画关键帧和渲染设置（1920×1080，30fps，Cycles）。
方案 B（AI 视频）：先用图像模型出首帧（设备特写）和尾帧（虚焦色块），再用首尾帧生成 6 秒过渡；给我两张图的提示词和视频提示词。
不要露出完整设备，不要文字以外的任何 UI。""",
      how_to=["只给局部：边缘、按键、材质，越少越吊胃口；文案写「Coming early next year」一类的时间预告。",
              "有 3D 能力就用 Blender：先定材质和布光，再做 1 条慢速相机运动。",
              "没有 3D 能力：用 Higgsfield / Kling 的首尾帧控制做 AI 过渡，但要多抽几次。",
              "结尾 logo 停留 ≥2 秒，背景色和 logo 色延续品牌主色。"]),
]

AMBI_SPEC_NOTE = {"2109292120301519094": "1080×1080 · 7s", "2109660371296424352": "3840×2160 · 54s",
                  "2109720765667172355": "2048×1536 · 45s", "2111109914303299925": "1920×1080 · 30s",
                  "2112197075945308175": "2048×1536 · 55s", "2114733804535377947": "1920×1080 · 10.5s"}

# ---------------------------------------------------------------- Benchmark cases (Page §3)
# (pid, handle, product, type label, spec, learn point, category)
BENCH = [
 ("2046736181002645520", "nikitabier", "X Custom Timelines", "UI 动效", "25s · 16:9", "黑底讲承诺、白底放证明；全片只有一个数字「75+」，马上用滚动列表证明", "营销产品"),
 ("2036825558084878467", "linear", "Linear Agent", "UI 动效", "55s · 2:1 4K", "暗色透视 UI 镜头 → 亮色真实界面 → logo；文案只有「Introducing X.」+ 一句价值", "营销产品"),
 ("1957489735527502301", "ElevenLabs", "ElevenLabs Music API", "UI / 作品墙", "39s · 16:9", "用产品生成的作品墙当画面，show 而非 tell", "营销产品"),
 ("2107503346504634463", "ElevenLabs", "ElevenAgents Architect", "UI 动效", "67s · 16:9", "不说 introducing，开场就是 agent 在干活；首个 tagline 到 0:48 才出现", "营销产品"),
 ("2112335838801731970", "WisprFlow", "Wispr Flow 深色模式", "UI 动效", "40s · 4:3", "用一个开关的趣味动画讲功能，文案只有「it's here (finally) 🌑」", "动效特效"),
 ("2080353769565348142", "meetgranola", "Granola Speaker Tags", "字体 + UI", "13s · 4:5", "小功能用 4:5 竖版 13 秒讲清", "社交短视频"),
 ("2090865782246769016", "humfhuang", "Kleo 真人电影感短片", "真人电影感短片", "—", "2 人 3 周，借来的佳能相机 + 网购灯和麦，Final Cut 剪辑，未用 AI", "电影感叙事"),
 ("1942213709088149719", "diabrowser", "Dia Sidebar", "用户声音 + 梗剪辑", "40s · 720p", "开场直接放用户抱怨「I miss the Arc sidebar」的推文，再给答案；文案提示 Sound on", "社交短视频"),
 ("2105327223431737780", "ideogram_ai", "Ideogram 4.5", "AI 画面 + 大字排版", "47s · 16:9 4K", "5 段：品类 hook → 论点+揭晓 → 核心能力 → 用例升级 → 预告+CTA", "营销产品"),
 ("1971211680664388053", "iamjasonlevin", "Memelord", "AI 生成叙事片", "107s · 16:9", "作者自述 $300 做完；先造一个「主角」再生成各场景", "电影感叙事"),
 ("1947636878158565795", "beechinour", "Whop GTA 风格片", "几乎全 AI", "—", "角色重建、context profile、提示词、超分全流程（教程帖）", "电影感叙事"),
 ("2092175528396493189", "tomiwebstr", "Marmar App", "3D 渲染 + 实拍 + 文字", "—", "工具：After Effects + Blender + Premiere", "动效特效"),
 ("2029604182286856663", "cursor_ai", "Cursor Automations", "UI 演示 + 团队口播", "95s · 16:9", "团队成员讲「为什么」，真实界面演示「怎么用」", "营销产品"),
 ("1942969263305671143", "perplexity_ai", "Perplexity Comet", "字体动效 + UI + 背书", "72s · 16:9", "开场大字「A browser built for you.」，中段插入发布会片段做社会证明", "营销产品"),
 ("2115803472037572751", "raycast", "Raycast iOS 键盘", "主讲人长版讲解", "356s · 16:9 4K", "6 分钟长片 + 手机特写；文案用 emoji 列功能清单", "营销产品"),
]

ROUTE = {  # how-to per production route, from Page §6
 "code": (["UI 动效", "字体 + UI", "UI / 作品墙", "字体动效 + UI + 背书", "AI 画面 + 大字排版"],
          [SK_RM, SK_HF, SK_LOT],
          ["先写一页 brief 和一句核心信息，再写 15 个 hook 选 1 个。",
           "建项目并装 skill：`npx create-video --yes --blank my-video` → `npx remotion skills add`；或 `npx skills add heygen-com/hyperframes`。",
           "让 agent 先写逐场景分镜（文字 + 画面/动画说明），一次只做一个场景。",
           "把真实产品 UI / 设计系统交给 agent，用真实组件和假数据。",
           "用精确指令修改，如「这个场景缩短 0.25 秒」。",
           "ElevenLabs 配乐，切点对上节拍；导出 16:9 + 4:5 两版。"]),
 "live": (["真人电影感短片", "用户声音 + 梗剪辑", "UI 演示 + 团队口播", "主讲人长版讲解"],
          [SK_VU, SK_FF],
          ["先写脚本和带时长的镜头表，团队确认后再拍。",
           "拍摄时就把画面拍对：多拍、多角度、多条；对白收音要干净。",
           "用 video-use 处理原始素材：去口癖、加字幕、调色，出粗剪。",
           "UI 演示部分用 Screen Studio 录真实操作，或用代码做 UI 动效后叠加。",
           "加烧录字幕，静音自检「3 秒内看懂了吗」。"]),
 "ai": (["AI 生成叙事片", "几乎全 AI"],
        [SK_HIG, SK_SEED],
        ["产品负责人自己写脚本。",
         "先用图像模型（Nano Banana / GPT Image）出首帧，再用 Veo / Kling / Seedance 做视频，控制力更强。",
         "先造一个固定「主角」形象，再生成各场景，保持一致。",
         "用首尾帧控制转场；创意方向别写太死，模糊方向有时更有效。",
         "产品 demo 不能埋太深：第 10 秒内要看到产品。"]),
 "3d": (["3D 渲染 + 实拍 + 文字"],
        [SK_HIG],
        ["Blender 做设备 / 3D 场景，AE 做文字和合成，Premiere 剪辑。",
         "没有 3D 能力时：先出 contact sheet，再用 AI 视频的首尾帧做过渡。",
         "每个镜头只讲一件事，3–5 秒。"]),
}


def route_for(tlabel):
    for k, (labels, sk, steps) in ROUTE.items():
        if tlabel in labels:
            return k, sk, steps
    return "code", ROUTE["code"][1], ROUTE["code"][2]


def bench_prompt(product, tlabel, spec, learn):
    return (f"参考「{product}」这支 launch 视频（{tlabel}，{spec}）的做法，为 {{产品}} 的 {{功能}} 做一支同类型的视频。\n\n"
            f"要学的核心手法：{learn}。\n\n"
            "请先输出：\n1. 一句话核心信息 + 3 个备选 hook（首帧就是 hook）。\n"
            "2. 带时长的镜头表：每个镜头写清画面、文案（两行标题 + 一句说明）、声音、时长；第 10 秒前必须看到产品在工作。\n"
            "3. 用哪种做法实现（代码动效 / 实拍 / AI 生成 / 3D），每个镜头需要的素材清单。\n"
            "镜头表经我确认后，再一次只做一个场景；导出 MP4（H.264 + AAC，1080p，30fps），另出一版 4:5 竖版。")

# ---------------------------------------------------------------- Top 50 skill repos (Page §10)
SKILLS = [
 (1,"remotion-dev/skills","Remotion 官方 Agent Skills：让 agent 用 React 代码写视频","代码动效","https://x.com/Remotion/status/2013626968386765291","Remotion",18881366,21879,6255,"2026-01-20","专帖",None),
 (2,"heygen-com/hyperframes","HTML 渲染成 MP4，为 agent 设计；HeyGen 自己的 launch 片用它做","代码动效","https://x.com/HeyGen/status/2044827454460871072","HeyGen",3016760,8323,78339,"2026-04-17","专帖",None),
 (3,"mcncarl/yichen-skills","含 yichen-jianying-edit：Codex + 剪映，口播视频全自动粗剪","自动剪辑","https://x.com/gengdaJ/status/2100748639228367257","gengdaJ",1409175,3962,5171,"2026-09-18","专帖","帖中配套的 mcncarl/jianying-headless 现已 404"),
 (4,"higgsfield-ai/skills","Higgsfield 官方 CLI + 营销视频 Skills","AI 生成","https://x.com/higgsfield/status/2051346056039039487","higgsfield",342289,2296,1873,"2026-05-05","专帖",None),
 (5,"browser-use/video-use","原始素材文件夹 → 成片：去口癖、加字幕、调色","自动剪辑","https://x.com/Fujin_Metaverse/status/2046431352367780274","Fujin_Metaverse",308822,901,30483,"2026-04-21","专帖","日文教程长文；官方发布帖 @gregpr07 为 272,814 浏览 / 1,926 赞"),
 (6,"alchaincyf/huashu-motion","一键直出商业级产品宣传片，会配乐，能指着画面改","代码动效","https://x.com/AlchainHust/status/2111811721471897618","AlchainHust",250739,951,2247,"2026-10-18","专帖",None),
 (7,"veedstudio/open-edit","VEED 开源的 agent 剪辑管线：字幕、动效、开头 hook","自动剪辑","https://x.com/veedstudio/status/2084602908331647471","veedstudio",122276,449,1773,"2026-08-04","专帖",None),
 (8,"nemovideo/nemovideo_skills","给 OpenClaw 等 agent 的专业剪辑 Skill","自动剪辑","https://x.com/nemovideoai/status/2034271715958886562","nemovideoai",108420,61,18,"2026-03-18","专帖","浏览远高于点赞和 Star，疑似投放流量"),
 (9,"limin112/min-skill","从零搭建口播视频 Skill（中文长文配套）","口播/解说","https://x.com/MinLiBuilds/status/2081412645513818542","MinLiBuilds",107088,226,549,"2026-07-27","专帖",None),
 (10,"kajisho5/ffmpeg-skill","42 个 FFmpeg 剪辑工具 + MCP，给 Claude Code / Cursor / Codex","自动剪辑","https://x.com/tom_doerr/status/2115405924646985924","tom_doerr",101807,2142,4453,"2026-10-28","专帖",None),
 (11,"calesthio/OpenMontage","把 Claude Code 变成视频工作室：12 条管线、500+ skill","AI 生成","https://x.com/calesthioailabs/status/2056904779188814143","calesthioailabs",60419,7,75959,"2026-05-20","专帖","专帖浏览≫点赞；GitHub 很热但 X 单帖互动低"),
 (12,"Vincentwei1021/video-shotcraft","产品截图、网页 → 带运镜和音效的宣传片（Remotion）","代码动效","https://x.com/zhongying14/status/2095555063565434941","zhongying14",27486,361,16518,"2026-09-04","专帖","作者 10 月初称账号被封、仓库曾 404，现已恢复"),
 (13,"Vincentwei1021/video-talkcraft","口播稿 + 配音 → 动态解说视频","口播/解说","https://x.com/zhongying14/status/2095555063565434941","zhongying14",27486,361,2056,"2026-09-04","专帖","与 #12 同一帖"),
 (14,"lemomo-ai/lemo-opuscar","66 种代码电影风格，让 Opus 出带旁白和配乐的短片","代码动效","https://x.com/Voxyz_ai/status/2110838129326473353","Voxyz_ai",22978,351,11737,"2026-10-16","专帖",None),
 (15,"Leonxlnx/cinetic","让 coding agent 当导演，做 launch 片或短片","代码动效","https://x.com/LexnLin/status/2106891315371737480","LexnLin",19221,437,983,"2026-10-05","专帖",None),
 (16,"LottieFiles/motion-design-skill","动效原则：时序、缓动、编排、迪士尼动画法则","代码动效","https://x.com/reallynattu/status/2089721988734759247","reallynattu",5426,83,2756,"2026-08-18","专帖",None),
 (17,"zhuyansen/awesome-claude-video-skills","180 个让 agent 做视频的仓库分类索引","合集索引","https://x.com/GoSailGlobal/status/2107396095165014409","GoSailGlobal",4170,42,1520,"2026-10-06","专帖",None),
 (18,"latent-spaces/brag","一条 /brag 命令把项目做成 launch 短片（基于 HyperFrames）","代码动效","https://x.com/0xrux/status/2104831340428308509","0xrux",3628,36,20171,"2026-09-29","专帖",None),
 (19,"songguoxs/seedance-prompt-skill","生成 Seedance 2.0 视频提示词","提示词","https://x.com/0xSilver_Time/status/2081681059868234067","0xSilver_Time",3209,20,2982,"2026-07-27","专帖",None),
 (20,"nateherkai/herk-edit-kit","15 个剪辑 Skill，做 Reels / Shorts","自动剪辑","N01","N01ennn",517528,6016,2500,"2026-10-08","合集帖","合集里写的 hyperframes-student-kit 现跳转到此仓库；Star 约 2.5k"),
 (21,"cth9191/animate","任意风格的程序化动画短片，带分镜自检","代码动效","N01","N01ennn",517528,6016,1459,"2026-10-08","合集帖",None),
 (22,"Barty-Bart/motion-graphics","Claude Code / Codex 动效 Skills","代码动效","N01","N01ennn",517528,6016,1042,"2026-10-08","合集帖",None),
 (23,"whaleyxbt/claude-motion","动效工具包：自检帧、用代码写声音","代码动效","N01","N01ennn",517528,6016,812,"2026-10-08","合集帖",None),
 (24,"haidrrrry/claude-remotion-skill","教 Claude 用 Remotion 做专业动效","代码动效","N01","N01ennn",517528,6016,805,"2026-10-08","合集帖",None),
 (25,"howseen-ai/claude-motion-design","HTML + Playwright + ffmpeg 纯代码做动效视频","代码动效","N01","N01ennn",517528,6016,761,"2026-10-08","合集帖",None),
 (26,"charlie947/motion-graphics-skills","13 个 launch 级动效 Skill","代码动效","N01","N01ennn",517528,6016,541,"2026-10-08","合集帖",None),
 (27,"AbubakrChan/product-launch-motion","Dribbble 级产品 launch 视频","代码动效","N01","N01ennn",517528,6016,418,"2026-10-08","合集帖",None),
 (28,"199-biotechnologies/motion-dev-animations-skill","Motion.dev 网页动画 Skill（120fps、弹簧、滚动）","代码动效","N01","N01ennn",517528,6016,219,"2026-10-08","合集帖",None),
 (29,"iart-ai/motion-design-skills","动效基础、引擎和品牌元素 Skills","代码动效","N01","N01ennn",517528,6016,194,"2026-10-08","合集帖",None),
 (30,"Sunwood-ai-labs/hyperframes-motion-reel-skill","HyperFrames 卡点 showreel 动效","代码动效","N01","N01ennn",517528,6016,170,"2026-10-08","合集帖",None),
 (31,"frankxai/awesome-motion-design-agent-skills","动效 Agent Skills 精选索引（GSAP / Remotion / Lottie / Rive）","合集索引","N01","N01ennn",517528,6016,94,"2026-10-08","合集帖",None),
 (32,"t3knobox/klik-anim-skill-creation","Remotion 动效行业规范 Skills","代码动效","N01","N01ennn",517528,6016,89,"2026-10-08","合集帖",None),
 (33,"dexhunter/seedance2-skill","写出最佳 Seedance 2.0 视频提示词","提示词","SER","369Serena",288126,3636,4399,"2026-06-04","合集帖",None),
 (34,"Agentchengfeng/chengfeng-videocut-skills","Claude Code Skills 做的剪辑 Agent","自动剪辑","SER","369Serena",288126,3636,3178,"2026-06-04","合集帖","原名 Ceeon/videocut-skills，已跳转"),
 (35,"SamurAIGPT/Generative-Media-Skills","多模态生成媒体 Skills","AI 生成","SER","369Serena",288126,3636,33,"2026-06-04","合集帖","Star 很少"),
 (36,"oil-oil/video-publisher-skill","把视频、标题、封面整理成多平台发布草稿，停在发布前","发布/字幕","XW1","xaiwind",225607,1827,267,"2026-10-08","合集帖",None),
 (37,"imlewc/video-to-subtitle-summary-skill","抖音 / 小红书 / B 站视频转字幕 + AI 总结","发布/字幕","XW1","xaiwind",225607,1827,245,"2026-10-08","合集帖",None),
 (38,"alchaincyf/huashu-art-motion","35 种艺术风格动画、9 种解说语法","代码动效","XW2","xaiwind",76596,369,6120,"2026-10-10","合集帖",None),
 (39,"kaomei/stickman-video-director","剧本 → 多风格火柴人动画，适合无脸频道","AI 生成","XW2","xaiwind",76596,369,4064,"2026-10-10","合集帖",None),
 (40,"chengyi-ai/native-subtitle-quote-image","保留视频内嵌字幕取帧，生成 3:4 社交长图","发布/字幕","XW2","xaiwind",76596,369,2851,"2026-10-10","合集帖",None),
 (41,"Alisa0808/vox-director","一个选题 → Vox 风格拼贴解说片 / 广告","口播/解说","XW2","xaiwind",76596,369,2607,"2026-10-10","合集帖",None),
 (42,"s1dashu/director","多模式视频导演：调研、脚本、分镜、生成","AI 生成","XW2","xaiwind",76596,369,845,"2026-10-10","合集帖",None),
 (43,"trustfuture/simon-skills","不露脸视频账号：调查长片 + 手绘白板讲解","口播/解说","XW2","xaiwind",76596,369,516,"2026-10-10","合集帖",None),
 (44,"Mr-funny/hbg-classical-poem-silk-video","古诗 → 竖屏国风视频","AI 生成","XW2","xaiwind",76596,369,383,"2026-10-10","合集帖",None),
 (45,"kaomei/hand-drawn-video-prompts","中文脚本 → 9:16 手绘分镜与提示词","提示词","XW2","xaiwind",76596,369,294,"2026-10-10","合集帖",None),
 (46,"kaomei/kid-papercraft","生日主题定格折纸动画短片","AI 生成","XW2","xaiwind",76596,369,260,"2026-10-10","合集帖",None),
 (47,"Kianzzz/book-sales-video","中文图书带货视频：配音、双语字幕、自动剪辑","口播/解说","XW2","xaiwind",76596,369,237,"2026-10-10","合集帖",None),
 (48,"Mr-funny/hbg-life-simulation","人生模拟类叙事视频","AI 生成","XW2","xaiwind",76596,369,150,"2026-10-10","合集帖",None),
 (49,"greensock/gsap-skills","GSAP 官方 AI Skills（网页动画）","代码动效","https://x.com/thegreatest_sv/status/2112609040962359354","thegreatest_sv",47181,584,17818,"2026-10-21","合集帖",None),
 (50,"FireRedTeam/FireRed-OpenStoryline","AI 剪辑 Agent：从手动剪辑变成按意图导演","自动剪辑","https://x.com/heyrimsha/status/2111407556929425790","heyrimsha",26910,574,3627,"2026-10-17","合集帖",None),
]
POSTS = {"N01": "https://x.com/N01ennn/status/2108182955671580771", "SER": "https://x.com/369Serena/status/2062495055034958159",
         "XW1": "https://x.com/xaiwind/status/2108205644033806837", "XW2": "https://x.com/xaiwind/status/2108866001672741199"}

FEATURED = {  # 5 recommended picks (Page §10 "launch 片团队推荐先试")
 "heygen-com/hyperframes": ("HeyGen 自己的 launch 片就是用它做的；写 HTML 就能出片，brag 等不少 Skill 都基于它。", "npx skills add heygen-com/hyperframes"),
 "remotion-dev/skills": ("官方维护，X 上曝光最高；适合会 React 的同学，镜头即代码，改一行就能重渲染。", "npx skills add remotion-dev/skills"),
 "latent-spaces/brag": ("在项目里跑一条 /brag，直接从代码库生成带配乐的 launch 短片，最快拿到第一版初稿。", None),
 "alchaincyf/huashu-motion": ("中文作者，专做商业级产品宣传片，能指着画面让 agent 改，适合中文团队上手。", None),
 "browser-use/video-use": ("有真人口播或实拍素材时用，自动去口癖、加字幕、调色，和动效片互补。", None),
}

# Pending demo: "候补（真实存在，排在 50 名之后）" from the Page
CANDIDATES = [
 ("0xsline/OpenChatCut", 2890, "对话式本地 AI 剪辑器，带 Agent Skills", "自动剪辑", "出自 @heyrimsha 合集帖（26,910 浏览）"),
 ("openfilm/openfilm", 4440, "出自 @socialwithaayan 合集帖的视频仓库", "AI 生成", "出自 @socialwithaayan 合集帖（21,608 浏览）"),
 ("Vincentwei1021/anything2explainer", 3024, "出自 @socialwithaayan 合集帖的解说视频仓库", "口播/解说", "出自 @socialwithaayan 合集帖（21,608 浏览）"),
 ("hypit-ai/hypit", 27752, "用 agent 复刻爆款视频", "AI 生成", "只出现在 801 浏览的合集帖里"),
]
