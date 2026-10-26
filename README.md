# Global Signal · 全球资讯大屏

一个纯静态的国际新闻聚合大屏，自动每小时抓取国际中文媒体 RSS，生成公开网页。

## 部署步骤（GitHub Pages）

### 1. 新建仓库
在 GitHub 上新建一个仓库（名字随便，比如 `news-dashboard`），把本文件夹所有文件 push 上去。

### 2. 开启 GitHub Pages
- 仓库 → Settings → Pages
- Source 选 `Deploy from a branch`
- Branch 选 `main`，目录选 `/ (root)`
- 保存，等 1 分钟后得到网址：`https://你的用户名.github.io/news-dashboard/`

### 3. 开启 Actions 定时任务
- 仓库 → Actions → 左侧选 "Fetch News Hourly"
- 点 "Enable workflow"（首次需要手动触发一次）
- 之后每小时自动运行，抓取新闻并更新 `data/news.json`

### 4. 完成
打开你的 Pages 网址，就是大屏了。前端每 5 分钟自动刷新一次数据。

## 本地预览

直接双击 `index.html` 即可（本地 `data/news.json` 是空数据，需部署后才有真实新闻）。

## 自定义数据源

编辑 `scripts/fetch_news.py` 顶部的 `FEEDS` 列表，按格式添加：

```python
{
    "category": "world",      # world / tech / finance / trending
    "source": "BBC中文",      # 显示在新闻列表里的来源名
    "url": "https://...",    # RSS 地址
},
```

改完 push 到 GitHub，下次 Actions 自动跑就生效。

## 项目结构

```
news-dashboard/
├── index.html                  # 前端大屏
├── data/
│   └── news.json               # 抓取脚本生成的数据（不要手动改）
├── scripts/
│   └── fetch_news.py           # RSS 抓取脚本
├── .github/
│   └── workflows/
│       └── fetch-news.yml      # GitHub Actions 定时任务
└── README.md
```

## 技术说明

- 纯前端 + GitHub Actions，零服务器、零费用
- 数据在海外服务器（GitHub Actions）抓取，避免国内 CORS 问题
- 前端通过 fetch 读取同目录的 `news.json`，无需后端 API
- 每小时自动更新数据源，前端每 5 分钟自动轮询
