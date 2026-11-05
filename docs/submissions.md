# 私密投稿

本地和 Pages 共用「提交作品」表单。访客免登录，只收到本次投稿回执。本地 CMS 的「作品投稿」是唯一的汇总清单。投稿清单保存在忽略版本控制的 data 目录内，Pages 导出只包含审核发布的作品。

## 接通 Pages 收件

在项目的 intake 目录中，用有部署权限的 Cloudflare 账号运行以下命令。工作器的 SQLite Durable Object 会随首次部署创建。SITE_ORIGIN 须与 Pages 的域名一致（不含项目路径）。

~~~sh
npx wrangler@4 login
npx wrangler@4 secret put READ_TOKEN
npx wrangler@4 deploy
~~~

READ_TOKEN 使用随机生成的私密值。在 GitHub 仓库 Settings → Secrets and variables → Actions → Variables 设置公开变量 VISION_INTAKE_URL，值为部署得到的 HTTPS 工作器地址。它只指定写入入口。读取密钥只配置在工作器和本机，不能放进 Pages 的变量或静态文件。

在本机设置 VISION_INTAKE_URL 和 VISION_INTAKE_READ_TOKEN 环境变量，或在忽略版本控制的 data/submission-relay.json 写入以下结构并将文件权限设为 600。文件设置会在下一次同步时生效。

~~~json
{"url":"https://your-worker.workers.dev","token":"与 READ_TOKEN 一致的私密值"}
~~~

本地服务运行时每分钟拉取增量投稿。管理员也可以点击「同步线上投稿」。同步游标与本地入库在同一次写入保存，重复同步不会重复建档。电脑离线期间，线上收件服务会保留投稿。

## 本地处理

链接需指向公开作品。系统尝试读取视频直链、网页公开的视频元数据、X 官方嵌入信息，以及 YouTube、Vimeo 和哔哩哔哩的公开视频。明确的生成、合成或实拍线索用于推荐栏目；混合制作或证据不足时，由管理员核对。需要登录、限制访问或未提供视频的页面，可在「处理投稿」中补传 MP4、MOV 或 WebM 原片。每支片支持 200 MB、10 分钟。

本机用 FFmpeg 实测切点、抽关键帧并估算运动，生成分镜表和 AI 复现建议。普通访客不能触发公开拉片接口。可选的 VISION_SUBMISSION_VISION_MODEL 指定已安装的 Ollama 视觉模型；启用时将代表帧发往本机 127.0.0.1:11434。未配置视觉模型时，以来源线索和实测画面为准，不能判定的投稿留待核对。复现建议与作者实际使用的工具分开标注。

已收录的相同来源只标记关联。新作品依旧经过 CMS 审核，发布后再随本地快照导出到 Pages。投稿人的私密说明不复制到公开作品。
