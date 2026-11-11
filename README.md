# Vision Lab（caselib）

团队内部的 launch / 宣传视频案例库。GitHub Pages 发布与更新见 [部署说明](docs/github-pages.md)。包含以下内容：

| 类型 | 标签页 | 内容 |
| --- | --- | --- |
| AI 视频案例 `video`、平面 `graphic` | AI 视频案例 / 平面 | 可复现的好例子：复现 Prompt、步骤、依赖的 Skill、工具、资产，带「使用」按钮 |
| 品牌 Skill `brand_skill` | 品牌 Skill | 团队长期维护、带版本号的规范 / Skill（SKILL.md） |
| Skill 仓库 `skill_repo` | Skill 仓库 | 做视频用的 agent skill 仓库（手册 Top 50 + 每日 GitHub 新增） |
| 灵感库 `showcase` | 灵感库 | 纯展示：只看片，只存标题、品牌、来源、日期、数据、分类；每条可「一键拉片」，打开用户自己的 AI 并预填提示词 |

视觉风格参照 recent.design（Inter 13px、灰阶 oklch、药丸按钮、左侧纯文字导航、瀑布流卡片），详情面板的信息结构参照 Open Design。

## 站内使用说明

侧栏「使用说明」在 `/guide` 打开，复用当前导航与内容区，不新开标签页。旧 `/static/README.html` 地址也进入相同页面。本 README 保留开发与维护信息，不再直接展示给普通用户。

- 分组、名称、顺序和链接读取当前主导航；栏目简介与 AI 工具选项读取运行中的应用配置，内容数量读取公开内容数据，品牌分类、文件数、版本与字重读取品牌资产清单。
- 操作步骤维护在 `static/guide-content.json`。每次功能流程变化必须同步修改，新增或移除导航时由 `tests/test_guide.py` 检查说明覆盖，避免指南停留在旧版。
- GitHub Pages 同样生成 `/guide` 与旧说明地址；指南会按照公开站点实际显示的导航生成，不展示本机 CMS 的管理入口。

## AI 视频案例和 AI 导航
AI 视频案例默认按热度降序，使用已收录的热度值，缺省时按浏览数 + 50 ×（点赞数 + 仓库星数）计算。其他栏目保持各自的默认排序。

工具分组的「AI 导航」支持分类、搜索、管理员推荐与本机收藏；管理密码登录后可以在内容管理的「AI 导航」维护分类和入口。目录在本机读取 `data/ai-directory.json`，静态发布使用公开快照。

一级入口「AI 大模型」位于 `/tools/ai-models`。更新时从 Artificial Analysis 保存语言智能指数、文生图、文生视频（含音频）与文本转语音（提供商原生音色）的中文榜单页面，再运行 `python3 scripts/update_model_ranking.py --language language.html --image image.html --video video.html --speech speech.html --as-of YYYY-MM-DD`（需要 beautifulsoup4 和 Pillow）。四榜各取最多 50 个已排名模型。先在本地检查四个标签、数据和日期，确认后发布同一份快照。

## 「有点意思」日刊

浏览入口是 `/journal`；每一期都有可直接访问的 `/journal?vol=N` 地址。新增日刊后，在 caselib 下执行：

```sh
python3 scripts/import_journal.py "../../Design Reports/Vision Design 设计日报/daily"
```

导入器只读取正式命名的 `Vol.N 有点意思 A Little Something.html`，沿用原刊期号、日期、正文和配图，在 `static/journal/` 更新目录及阅读页；不会修改日报源文件或 CMS 记录。

## 拉片日志

「浏览 → 拉片日志」位于 `/motion-log`，每个单片报告通过 `?id=<report-id>` 直接打开。正文保留原 Markdown 的全部章节、表格和时间码，详情提供章节目录与原站嵌入播放器。进入详情请求有声自动播放，若受浏览器策略限制则由用户点击播放；滚过原片后缩为约一半宽度的右下角悬浮播放器，点击「回到原片」恢复。切换仅改变布局，保留同一个 iframe 与播放进度。视频文件不会下载、复制或写入发布包。

选录 Google Drive Nyx 拉片归档中的单片报告。原 Markdown 原样保存，关键帧、镜头索引代表帧及高清联系表按原路径与时间码匹配，保存在各报告的 `assets/`，点击可查看原图。音频、波形及分析数据链接至经核验的 Google Drive 原文件，不复制原视频。目录、正文 SHA-256、关键帧与代表帧数量见 `static/motion-log/index.json`，图片来源见各报告的 `asset-sources.json`。

详情顶部与底部可按目录顺序切换上一篇 / 下一篇，并支持方向键。代表帧通过 `frame-viewer.js` 在页内对话框中预览，方向键切换帧，Esc 关闭并返回原阅读位置；预览打开时，方向键不会切换报告。视频控件、输入框和已聚焦的横向表格保留自身的键盘操作。

`python3 scripts/import_motion_log.py output/motion-log-source.json` 将已读取的 Drive 正文、经核验的原站播放器地址和 `assets` 映射转换为静态内容。输入须包含全部已选报告；`assets` 将原 Markdown 相对路径映射至报告目录中的本地图片，导入时验证路径、文件存在与尺寸；`attachmentLinks` 将分析附件原路径映射至核验过的 HTTPS Google Drive 文件地址。图片使用懒加载，并按当前站点基础路径解析，兼容本地与 Pages。

## 运行

```bash
cd caselib  # 从 Vision Design Platform v2 项目目录进入
python3 server.py --host 127.0.0.1 --port 8787          # 只用 Python 标准库；媒体入库时需要 ffmpeg（转码 / 缩略图）
# 打开 http://localhost:8787
```

依赖：Python 3.10+（标准库 + numpy + Pillow，用于拉片和占位图）、ffmpeg/ffprobe、yt-dlp（ingest 下载 X 视频时用）。
数据都是文件：`data/cases.json`（全部条目）、`data/rejected.json`（被拒绝的来源链接，去重用）、`media/<id>/`（转码视频、预览、缩略图、拉片结果）。

## Playground

「工具 → Playground」在 `/tools/playground` 打开，提供 OpenHiggsfield 的图片、视频生成与模型参数、参考素材、创作记录、收藏、下载和复用。使用者在页面连接自己的 Higgsfield API Key，服务地址已预置。界面复用本站样式；生成与素材上传由独立服务连接 Higgsfield，不把密钥或生成媒体写入 GitHub Pages。接入、更新和验证说明见 [Playground](docs/playground.md)。

## 图片切图工具

侧栏「工具 → 图片切图」，地址 `/tools/image-slicer`。工具使用平台现有的字体、灰阶、药丸按钮与侧栏导航。

- 支持多图自动切片、等比缩放（输出高度向下取整）、单图定点裁切、单张切片下载与 ZIP 打包。切片最大宽高默认均为 4096px。
- 已选图片显示缩略图和尺寸，可逐张取消选择。
- 定点裁切支持点击预览或输入整数 Y 坐标；鼠标超过当前分段的最大高度时，预览切线吸附到「上一条切线 + 最大高度」，每次点击添加一条切线。导出前检查最大分段高度。修改输出宽度后需要重新加载预览。
- 图片仅在浏览器内处理。在平台栏目间切换会保留图片、标记和结果；刷新页面或关闭页面后清空。
- 实现位于 `static/tools/image-slicer.js`，样式限定在工具内。JSZip 3.10.1 随平台存放于 `static/vendor/`，保留上游许可证，无需运行时访问 CDN。源自独立的「Assets 切图」工具，原目录不受影响。

## 品牌资产

侧栏「资产 → 品牌资产」，地址 `/assets/brand`。界面沿用平台的字体、灰阶、药丸按钮、导航和卡片样式；分类由 URL 参数 `section` 保存，可直接打开、刷新和前后导航。

2026-11-04 从本机 `http://localhost:5174/` 对应的 `Vision Design Platform/public/brand-assets` 导入已有内容：品牌规范 PDF 1 份、单 Logo 3 组、组合 Logo 24 组、App Logo 2 组、MiSans 字重 10 个，共 70 个文件。产品素材、产品界面保留源站的空分类状态；品牌 Skill 统一使用「资产」分组下的现有入口。

- 品牌规范支持完整 PDF 预览、版本信息和下载；视觉资产支持分类、搜索、平铺/列表以及 SVG、PNG、PDF 原文件下载。
- 图片大图使用平台详情弹窗，支持左右切换、放大/缩小、拖拽和适应窗口；切换图片后恢复初始视图。
- 品牌规范与三份公司介绍均在站内阅读，预览和版本入口不另开标签页。PDF 默认连续纵向滚动，缩放由工具栏控制；支持页码跳转与大图弹窗，进入弹窗保留当前页。使用本地 PDF.js 6.5.438，按需读取和渲染附近页面，不依赖浏览器 PDF 插件或外部 CDN。
- 「公司介绍」位于「品牌规范」之后，收录用户提供的 v260924 国内版（38 页）、日语版（28 页）、英语版（29 页），支持版本切换、在线预览和保留原文件名下载。三份原 PDF 保持完整并已校验 SHA-256，资产文件现共 73 个；URL 参数 `document=cn|ja|en` 可定位具体版本。
- MiSans 支持字重切换、自定义文本预览及 OTF 下载；字体仅用于样张，平台 UI 字体保持不变。
- 页面代码和样式：`static/assets/brand-assets.js`、`static/assets/brand-assets.css`；内容清单：`static/assets/viaim/manifest.json`。
- 文件存放于 `static/assets/viaim/files/`，采用安全文件名服务，下载保留源文件名。`provenance.json` 记录来源相对路径、大小和 SHA-256，70 个文件导入时均已校验一致。
- 这是本次内容的本地副本，运行不依赖 5174 端口；源站之后的更新需另行同步。

## 内容管理平台（CMS）

从侧栏底部「管理员登录」或「管理 → 内容管理」进入 `/review`，输入管理密码后进入 CMS（也支持 `/cms`）。它与其他栏目共用同一个页面路由和侧栏，切换时只替换右侧内容；界面直接使用本站字体、颜色、药丸按钮与下拉菜单。

- 首次启动自动生成密码，保存在本机 `data/cms_initial_password.txt`（权限 600）；认证文件 `data/cms_password.json` 只存加盐 scrypt 哈希。也可在首次启动时用 `CASELIB_CMS_INITIAL_PASSWORD` 指定初始密码。
- 登录后可以在「账号设置」修改密码（至少 12 个字符）。修改后删除初始密码文件并注销全部会话。浏览器使用 12 小时有效的 HttpOnly / SameSite Cookie，不在 localStorage 保存密码或 token。退出会注销当前会话；服务重启需要重新登录。
- 「新建内容」支持 AI 视频案例、灵感库、平面、品牌 Skill、Skill 仓库。可以填写标题、分类、介绍、来源、Prompt、操作步骤、工具、版本与标签，上传封面、图片、视频和 MD / TXT / PDF 附件。
- 流程：**保存草稿 → 提交审核 → 审核并发布**。普通用户仅能访问已发布内容与关联的站内素材；草稿、审核意见、内部备注与未审核的修改不对外展示。
- 已发布内容再次编辑会保存独立修订稿，原版仍正常展示；新修订审核通过后才替换线上版本。退回时填写原因，修改后可再次提交；下架后前台隐藏，CMS 内保留内容。
- 已下架内容可从列表或编辑页删除，确认后从内容库移除，平台内无法恢复。后端检查登录、CSRF、已下架状态与当前 `_version`，已发布内容和其他状态不可删除。删除的来源进入去重记录，避免自动采集重新加入；保留媒体文件以免损坏其他内容共用的素材。
- 「我的内容」展示在 CMS 中创建的条目；「全部内容」也包括既有和自动收录的条目。列表支持状态、类型、搜索与滚动加载，每条内容保留操作记录。
- 图片支持 JPG / PNG / WebP，单个最多 20 MB；视频支持 MP4 / MOV / WebM，最多 200 MB，自动生成转码、封面与预览；附件单个最多 20 MB。未保存的上传文件会保留在媒体目录，但不能被匿名访问。
- 仍保留 `X-Admin-Token` 供已有本机脚本调用；token 来自 `data/admin_token.txt` 或 `CASELIB_ADMIN_TOKEN`，网页不再使用它。编辑和状态操作需传入返回的 `_version`，过期修改返回 409，防止覆盖其他人的更新。
- 若部署到 HTTPS，设置 `CASELIB_COOKIE_SECURE=1`。当前配置运行在本机 127.0.0.1。
- 运行隔离测试时可设置 `CASELIB_DATA_DIR` / `CASELIB_MEDIA_DIR`，不会影响正式案例和素材。

API：`POST /api/auth/login`、`GET /api/auth/session`、`POST /api/auth/logout|password`；`GET/POST /api/admin/cases`、`GET/PUT /api/admin/cases/<id>`、`POST /api/admin/cases/<id>/submit|approve|reject|unpublish|delete`、`POST /api/admin/uploads`。浏览器写请求需携带登录返回的 `X-CSRF-Token`。

## 每日 ingest（给定时任务调用）

### Eagle 素材同步

每天 10:15 的同一聊天心跳也读取 `Sync to Vision Lab.library`。单个视频进入灵感库；单张图片进入平面视觉；同源多素材合成一张平面视觉卡片，详情右侧按顺序纵向浏览，图片和视频可以混排。Eagle 源库保持只读。

先运行 `python3 scripts/import_eagle.py "<library 路径>" --output output/eagle-intake/<日期>` 保存扫描清单，再抓取原帖准备编辑清单。清单包含 `groups`，每组填写 `sourceUrl`、有序 `eagleIds`、保存的来源 `evidence` 文件路径，以及 `fields`（标题、介绍、分类、标签、作者与来源信息）；已验证的 X 原站视频可填 `remoteVideo`。原帖不可读时保留待补全状态，不用文件名猜作者。

运行同一命令并加 `--apply <编辑清单.json>`，通过 CMS 草稿、提交、发布流程入库。`output/eagle-intake/state.json` 保存来源、Eagle ID、文件哈希、自动分类基线与 CMS ID 的私有映射；同源重复跳过，已导入来源新增素材时更新原卡片并保留人工文案、栏目迁移和分类调整。删除或拒绝过的来源不恢复，源库删除不传播到 CMS。公开快照不包含源库路径、映射或抓取证据。发布仍遵循下述项目协作与 Pages 验证流程。

### 其他来源

```bash
bash /workspace/caselib/run_daily.sh
# 等价于：cd /workspace/caselib && python3 ingest.py --sources inbox,github,lvg --limit 30
```

- 新条目一律进 `pending`，等人在 /review 审核；以来源 URL 规范化后去重（x.com / twitter.com / i/status 视为同一条；GitHub 按 owner/repo 小写），同时排除 `rejected.json`。
- 每次结束打印一行 JSON（`{"ok":true,"added":N,"by_source":{...}}`），`run_daily.sh` 把它追加到 `data/ingest.log`，错误写到 `data/ingest.err.log`；失败时退出码非 0。
- 和 server 同时跑没问题：写 `cases.json` 用文件锁 + 原子替换。
- 其他参数：`--sources lvg,inbox`（只跑部分来源）、`--limit N`（每个来源最多新增 N 条）、`--publish`（直接发布，仅用于首次批量导入）、`--dry-run`。

### 来源 1：GitHub（skill 仓库）
公开 search API，关键词 remotion skill / hyperframes / motion graphics skill / ffmpeg skill / video skill claude code / launch video agent 等，只取本月有 push、≥20 star、非 fork 的仓库。未设 `GITHUB_TOKEN` 时每次搜索间隔 7 秒（未认证限额 10 次/分钟）。

### 来源 2：inbox（外部 agent 投递的 X 帖子）
把 JSON 文件放进 `data/inbox/`，下次 ingest 处理后移到 `data/inbox/processed/`：

```json
{"items": [
  {"type": "case",                      // case = AI 视频案例（带复现方法）；showcase = 灵感库（纯展示）
   "url": "https://x.com/<user>/status/<id>",
   "author": "@user", "title": "可选", "brand": "可选（showcase 用）",
   "text": "帖子正文", "date": "2026-11-03",
   "metrics": {"views": 0, "likes": 0, "reposts": 0, "bookmarks": 0}, "metrics_fetched_at": "2026-11-04",
   "media_urls": ["https://video.twimg.com/...mp4", "https://pbs.twimg.com/media/...jpg"],
   "category": "营销产品", "tags": ["..."]}
]}
```
媒体：先直接下载 `media_urls`，没有就用 yt-dlp 抓帖子里的视频；ffmpeg 转成 1080p web.mp4、8 秒无声 hover 预览、缩略图。下载不到就生成一张「暂无媒体」文字卡（不会冒充画面）。

### 来源 3：launchvideos.gallery（灵感库）
- 站点是 SvelteKit，没有公开 RSS / JSON 接口；robots.txt 允许 `/`，禁止 `/api/`、`/admin`、`/saved`。适配器只读**公开列表页**（首页、`/latest`，以及 sitemap 里的 18 个分类页），解析页面里服务端渲染的列表数据（每页 24 条最新），不调用它背后的数据库接口；请求间隔 2 秒，User-Agent 写明用途，抓取前按 robots.txt 检查。
- 每条记录的字段：标题、tagline、描述、品牌（名称、X 账号、官网）、原帖链接（X）、原视频地址（video.twimg.com）、缩略图、分类、发布时间、X 数据（浏览 / 点赞 / 转发 / 收藏 / 回复，含更新时间）。
- 入库：`type=showcase`，`source.url` = 原帖，`source.via_url` = 该条在 launchvideos.gallery 的页面，列表站只用于发现原帖。入库时从 X 原帖获取原视频，生成站内 `web.mp4`、8 秒无声预览和封面，详情静音自动播放、卡片悬停播放；同时缓存真实作者头像，缺失时隐藏占位。前台只展示 X 原作者和原帖，发现路径保留在内部 `discovery` 字段，不作为作品来源展示。网站的一键拉片仍只预填用户自己的 AI，不执行在线分析。
- 已有条目迁移：`python3 refresh_sources.py --workers 2`；可用 `--id <case_id>` 更新单条及同来源条目。运行前备份案例数据，逐组写入，只更新媒体与来源字段，不改变审核状态。
- 限制：每个列表页只给最新 24 条，所以每天最多看到约 20 页 × 24 条（去重后本次 313 条）；更老的条目只有 sitemap 里的链接，详情页只有 og 元数据（标题、描述、视频、缩略图），没有日期 / 分类 / 数据，适配器目前不抓。分类为英文 slug，已映射成中文（AI、Agent、开发者工具、消费、效率、硬件…）。

## 一键拉片（用户自己的 AI）

- 灵感库卡片和详情页的「一键拉片」使用与「使用」相同的深链，打开用户电脑上的 Cursor / Codex / Claude Code，预填视频地址、原帖、案例信息与拉片要求，由用户确认发送。
- 详情页下拉菜单可选择目标；选择保存在当前浏览器的 localStorage，刷新、关闭重开后继续使用，并同步同站点其他标签页；「复制 Prompt」适用于其他 AI 工具。提示词可以展开查看、手动复制。
- 提示词要求读取真实视频与音轨，输出逐镜头表、节奏、结构、字体排版、可借鉴手法和结构模板；不能读取时请用户上传文件，不编造分析。
- 网页不调用模型、不排队分析，也不保存新拉片结果。原 `/c/<id>/breakdown` 链接返回案例详情，旧 `/api/cases/<id>/breakdown` 接口返回 HTTP 410，不再执行任务。
- `breakdown.py` 和已有结果文件保留作为本地历史工具 / 资料，未接入网站。若需自行使用命令行：`python3 breakdown.py <case_id> [--force]`。
- 这项功能无需云端拉片服务器或网站侧模型密钥。用户在所选工具中发送提示词后，使用其自己的账号、模型及相应额度。

## 使用按钮（深链）

| 目标 | 链接 | 依据 |
| --- | --- | --- |
| Cursor | `cursor://anysphere.cursor-deeplink/prompt?text=<编码后的 prompt>`；网页版 `https://cursor.com/link/prompt?text=...`；整个 URL 上限 10,000 字符；只预填不执行 | https://cursor.com/docs/integrations/deeplinks |
| Codex（ChatGPT 桌面 App 的 Codex） | `codex://new?prompt=<编码>`（也可带 `path` / `originUrl`）；预填到输入框，不自动发送 | https://developers.openai.com/codex/app/commands （跳转到 learn.chatgpt.com/docs/reference/commands 的 Deep links 一节） |
| Claude Code | `claude-cli://open?q=<编码>`（可带 `cwd` / `repo`），`q` 上限 5,000 字符；需要 v2.1.91+，并且在这台电脑上至少在交互式会话里发过一次消息才会注册协议；打开新终端预填，不自动发送 | https://code.claude.com/docs/en/deep-links |

点目标会同时尝试复制 Prompt 和打开对应工具；超出链接长度上限时改为复制，未安装工具时可手动粘贴。复制失败会提示手动复制，不会声称复制成功。上次选的目标会记住，成为主按钮的默认值。Codex 网页版 / CLI、claude.ai 没找到官方的预填链接，所以没做。

## 手动加一个品牌 Skill

GitHub 来源的 Skill 维护在 `catalog/brand-skill-sources.json`。添加仓库及其安装说明、示例路径后，运行 `python3 scripts/sync_brand_skills.py`。同步读取各公开仓库默认分支的实际提交，更新同一条记录，并打包包含 `SKILL.md`、脚本、素材与许可证的安装 ZIP。配置 `presentation` 时，同步工具使用 LibreOffice（`soffice`）、Poppler（`pdftoppm`）和 Pillow 从仓库 PPTX 生成全套逐页预览，并提供源文件下载。卡片示例直接读取配置的仓库 PNG。同步后按本地验证与 Pages 发布流程更新公开站点。

1. 新建 `brand_skills/<slug>/SKILL.md`（frontmatter 写 `name`、`description`、`version`），可以参考 `brand_skills/launch-video-spec/SKILL.md`。
2. 在 `data/cases.json` 里加一条（或先用 /review 的编辑功能改一条已有的）：
```json
{"id": "brand-<slug>", "type": "brand_skill", "status": "published", "category": "规范",
 "title": "...", "subtitle": "...", "trust": "官方", "featured": true, "version": "1.0.0",
 "media": {"kind": "image", "thumbnail": "/media/brand-<slug>/thumb.jpg"},
 "source": {"platform": "团队", "author": "...", "url": "", "date": "2026-11-04"},
 "prompt": "先读这份规范再开始：/brand_skills/<slug>/SKILL.md ……",
 "how_to": ["……"], "assets": [{"name": "SKILL.md", "url": "/brand_skills/<slug>/SKILL.md"}],
 "tags": ["品牌规范"], "changelog": [{"version": "1.0.0", "date": "2026-11-04", "note": "首版"}],
 "added_at": "2026-11-04T00:00:00+08:00"}
```
3. 缩略图：放一张 jpg 到 `media/brand-<slug>/thumb.jpg`（或在 Python 里调用 `mediautil.placeholder_thumb(id, 标题, 副标题)` 生成文字卡）。
4. 升级时：改 SKILL.md → `version` +1 → `changelog` 追加一行。prompt 里的 `/brand_skills/...` 会自动替换成站点的完整地址。

## 种子数据（seed.py）

`python3 seed.py` 重建种子条目（保留 ingest 进来的和审核过的）：
- 6 支 @hello_ambi 视频（本地文件），每支有复现 Prompt 和步骤；也作为灵感库条目出现。
- 手册 §3 标杆案例 15 支（14 支能用 yt-dlp 下载到视频；Kleo 下载失败，用文字卡），同样也进灵感库。
- 手册 §10 的 Top 50 skill 仓库（数据来自手册，读取于 2026-11-04），其中 hyperframes、remotion skills、brag、huashu-motion、video-use 标为「推荐」。
- 手册「候补」里的 4 个仓库作为待审核示例。
- 1 个品牌 Skill：《Launch 视频通用规范》v1.0.0。
- X 数据（浏览 / 点赞等）是 2026-11-04 用 X API 读的（`data/_xposts_live.json`）。

## 测试

回归：`python3 -m unittest discover -s tests -p 'test_*.py'`。CMS 测试使用临时数据、素材目录与端口，覆盖认证、草稿/审核/发布/退回/下架、修订隔离、素材权限和并发版本，不改正式案例。

```bash
/workspace/pwvenv/bin/python tests/e2e.py http://localhost:8787   # 无头浏览器：列表、详情、使用菜单、拉片跳转、前台只读检查，截图存 screens/
```
`tests/e2e.py` 只做前台浏览回归，不发布或拒绝真实内容。CMS 的浏览器操作应使用独立的临时数据目录。

首次安装浏览器测试依赖：`python3 -m pip install playwright`，然后 `python3 -m playwright install chromium`。运行 `python3 tests/browser_routes.py` 会启动临时服务器，检查桌面和移动端的密码登录、管理工作台、卡片编辑、Skill 排序、AI 导航以及使用说明。在已安装 Chrome 的 Mac 上也可以用 `BROWSER_CHANNEL=chrome python3 tests/browser_routes.py`。

匿名链接投稿的收件服务、本地同步和媒体处理设置见 [私密投稿](docs/submissions.md)。
