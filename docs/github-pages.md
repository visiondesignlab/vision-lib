# GitHub Pages 发布

目标仓库：`visiondesignlab/vision-lib`。站点路径：`https://visiondesignlab.github.io/vision-lib/`。

## 内容边界

`data/`、原始 `media/`、密码、令牌、会话、审核记录、待发布内容、日志和测试输出均不提交。
`publish/` 是仅含已发布内容的快照；包含这些内容实际引用的媒体。Python 内容管理服务继续在本机运行。
Pages 使用静态 JSON，图片切图和 AI 提示词跳转在浏览器中运行，不需要云端 Python 服务。

品牌大 PDF 原文件保存在仓库的 `brand-assets-2026-11-04` Release；`publish/large-assets.json` 固定下载地址、大小与 SHA-256。构建时还原到站点内，保留同源 PDF 预览及原文件下载。它们不进入 Git 历史。

## 发布更新

先在本地完成审核，再执行：

```sh
python3 -m pip install -r requirements.txt
python3 scripts/export_pages_snapshot.py
python3 -m unittest discover -s tests -p 'test_*.py'
python3 scripts/build_pages.py --base-path /vision-lib
git add static scripts tests docs publish .github .gitignore README.md
git diff --cached --stat
git commit -m "Update Vision Lib published content"
git push origin main
```

首次发布需以 `visiondesignlab` 登录 GitHub CLI、创建仓库、上传上述 Release 素材，并把 Pages 发布来源设为 GitHub Actions。`main` 的推送自动触发构建部署。

本地预览项目子目录：

```sh
python3 scripts/build_pages.py --output output/pages-preview/vision-lib --base-path /vision-lib
python3 -m http.server 8792 --bind 127.0.0.1 --directory output/pages-preview
```

打开 `http://127.0.0.1:8792/vision-lib/`。每条已发布详情、切图与品牌资产均生成独立入口文件，可刷新或直接分享。

构建会检查发布状态、内部字段、素材校验和及 1 GiB 体积上限。当前素材接近 Pages 容量上限，后续大批增加视频时需先安排独立媒体存储，不应删除校验。
