# GitHub Pages 发布

目标仓库：`visiondesignlab/vision-lib`。站点路径：`https://visiondesignlab.github.io/vision-lib/`。

## 内容边界

`data/`、原始 `media/`、密码、令牌、会话、审核记录、待发布内容、日志和测试输出均不提交。
`publish/` 是仅含已发布内容的快照；包含这些内容实际引用的媒体。Python 内容管理服务继续在本机运行。
Pages 使用静态 JSON，图片切图和 AI 提示词跳转在浏览器中运行，不需要云端 Python 服务。

品牌规范和三份公司介绍直接引用 Air 的 PDF 地址，继续使用站内阅读器。Air 没有通过 CORS 暴露 Accept-Ranges，因此阅读器使用 HEAD 获取在线文件长度，再通过 PDF.js Range Transport 分段读取；在线 PDF 可能经过 Air 压缩，大小不能取原始上传文件的元数据。下载地址使用 Air 的 `dl` 参数，避免跨域 download 属性失效后跳出页面。

公开案例视频从原站在线播放，`catalog/video-sources.json` 保存已验证的 X 原站视频地址。公开 API 和快照通过 `media_delivery.py` 转换引用，不修改私有 CMS 记录和本地原片；新增或地址失效的条目可回退到来源播放器。运行 `python3 scripts/sync_video_sources.py` 补充新来源，使用 `--refresh` 重新验证全部地址。日刊使用 YouTube、Vimeo、Framerate 在线播放器；原站不允许嵌入时保留「查看原片」。

`catalog/external-assets.json` 列出的本地 PDF 和日刊视频仅作备份，不复制到 Pages，也不从旧 Release 重新下载。旧 Release 保留作历史备份。

## 发布更新

先在本地完成审核，再执行：

```sh
python3 -m pip install -r requirements.txt
python3 scripts/sync_video_sources.py
python3 scripts/export_pages_snapshot.py
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tests/browser_routes.py   # 先安装 Playwright 和 Chromium，见 README
python3 scripts/build_pages.py --base-path /vision-lib
git add -u
git add static scripts tests docs publish catalog .github ai_directory.py media_delivery.py
git diff --cached --stat
git commit -m "Update Vision Lib published content"
git push origin main
```

提交前遵循项目 AGENTS.md，检查其他项目聊天、当前差异和本地运行结果；其他聊天仍在调整时暂停提交与部署。GitHub CLI 必须使用 `visiondesignlab`，Pages 发布来源为 GitHub Actions。`main` 的推送自动触发构建部署。

本地预览项目子目录：

```sh
python3 scripts/build_pages.py --output output/pages-preview/vision-lib --base-path /vision-lib
python3 -m http.server 8792 --bind 127.0.0.1 --directory output/pages-preview
```

打开 `http://127.0.0.1:8792/vision-lib/`。每条已发布详情、切图与品牌资产均生成独立入口文件，可刷新或直接分享。

构建会检查发布状态、内部字段、素材校验和及 1 GiB 体积上限。PDF 和在线来源视频不占 Pages 文件容量；无在线来源的本地上传附件仍计入体积，不应删除容量校验。

## 飞书发布通知

`Publish Vision Lab` 在每次 `main` 推送或手动发布结束后，通过同一个「Vision Lab Bot」应用机器人向「个个都是美工」和「上市 aura mate」发送信息卡片：标题为「Vision Lab · 发布成功」或「Vision Lab · 发布未完成」，正文显示操作人、提交编号与最新改动，底部提供「在线查看」「仓库地址」两个按钮。失败时补充构建和 Pages 状态，只有部署成功才标为发布成功。Pages 部署最多等待 30 分钟，避免同步文件超过默认 10 分钟时过早判定失败。

应用只需 `im:message:send_as_bot` 权限，并加入两个目标群。仓库 Actions Secrets 只保存 `FEISHU_APP_ID`、`FEISHU_APP_SECRET` 和逗号分隔的 `FEISHU_CHAT_IDS`。凭据不进入仓库、静态构建或日志。发布通知固定通过应用机器人发送，两个群共用同一个应用身份。

两个群分别发送并记录结果，一个群失败不会阻止另一个群发送；任何失败都会将通知任务标为失败供排查。应用发送使用工作流、目标群和卡片内容共同生成的 UUID，超时仅以相同 UUID 重试一次（飞书去重窗口为 1 小时）；重跑后发布结果改变时会产生新的 UUID。结果仍不明时必须回读群消息后处理；超过 1 小时重跑工作流也应先回读，避免重复。日志记录成功消息 ID，核验须确认两个群的发送者都是同一个应用。
