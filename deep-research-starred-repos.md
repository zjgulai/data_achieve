# Deep Research: GitHub Starred Repos Analysis for Data-Achieve Platform

**研究目标**: 深度调研 zjgulai/data-achieve starred list 中的 27 个仓库，输出 MECE 能力融合解决方案

**当前平台能力基线**:
- 208 endpoints, 197 verified
- 21 capability groups:
  - TikHub Social (17 endpoints): TikTok/IG/XHS/YouTube/Reddit/X/Threads/LinkedIn
  - Apify Actors (98 endpoints): 全方位社媒/电商/新闻采集
  - MediaCrawler (9 endpoints): Bilibili/Weibo/Zhihu/Kuaishou
  - Firecrawl (3 endpoints): 全站爬取/结构化提取/批量抓取
  - SpiderFoot OSINT (3 endpoints): domain/IP/email 威胁情报
  - Tech blog (3 endpoints): Dev.to/Juejin/Substack
  - Wappalyzer: 技术栈检测
  - Jina Reader: Markdown 转换
  - AnyDoc: 文档解析
  - SERP (3 engines): Baidu/Bing/DuckDuckGo
  - Manual JSON/CSV/Web ingest

---

## Starred Repos 清单 (27 repos, 按 stars 排序)

### 超大流量项目 (50k+ stars)
1. **browser-use/browser-use** - 109k ⭐ | Python | Browser automation agent
2. **Panniantong/Agent-Reach** - 73k ⭐ | ? | Agent-based reach system
3. **obscura (h4ckf0r0day)** - 21k ⭐ | Rust | Headless browser
4. **browser-use/browser-harness** - 16k ⭐ | ? | Browser automation harness

### 大型项目 (5k-10k stars)
5. **alirezamika/autoscraper** - 7.9k ⭐ | Python | Smart rule-free scraper
6. **proxifly/free-proxy-list** - 6.6k ⭐ | ? | Free proxy aggregator
7. **apurvsinghgautam/robin** - 6.4k ⭐ | Python | Dark web OSINT tool
8. **epiral/bb-browser** - 6k ⭐ | ? | Browser with login state persistence
9. **anysearch-ai/anysearch-skill** - 5.7k ⭐ | ? | Unified search skill

### 中型项目 (2k-5k stars)
10. **KnockOutEZ/wigolo** - 4.6k ⭐ | ? | Local MCP search/fetch/crawl
11. **vladkens/twscrape** - 4k ⭐ | Python | Twitter scraper (已在平台集成)
12. **mubeng/mubeng** - 2.4k ⭐ | Go | Proxy IP rotator
13. **apify/agent-skills** - 2.4k ⭐ | Python | Collection of Apify agent skills

### 小型项目 (<2k stars)
14. **NanmiCoder/MediaCrawler** - 63.1k ⭐ | Python | 小红书/抖音/快手/B站/微博/贴吧/知乎采集器 (已在平台集成 9 endpoints)
15. **apify/agent-skills** - 2.4k ⭐ | Python | Apify Agent Skills (Apify 官方 AI agent 技能包，覆盖 30k+ Actors)
16. 其他 12+ repos 待深度分析

---

## MECE 能力分层框架

### Layer 1: Infrastructure 基础设施层
- **代理轮换**: mubeng, proxifly
- **浏览器引擎**: browser-use, obscura, browser-harness, bb-browser
- **智能提取**: autoscraper

### Layer 2: Data Sources 数据源层
- **社媒平台**: Agent-Reach, twscrape, MediaCrawler (已有)
- **暗网 OSINT**: robin
- **通用搜索**: anysearch-skill, wigolo

### Layer 3: Agent Orchestration 编排层
- **Apify agent skills**: 已集成但可能有遗漏
- **MCP 本地服务**: wigolo

### Layer 4: Domain-specific 领域层
- **技术栈检测**: Wappalyzer (已有)
- **威胁情报**: SpiderFoot (已有)
- **文档解析**: AnyDoc (已有)

---

## 调研执行状态

### 并行调研任务 (4 tasks, in progress)
1. ✅ Task bg_699e37fe: mubeng + autoscraper + proxifly (proxy rotation + smart scraping)
2. ✅ Task bg_c14f3d37: browser-use + obscura + browser-harness (browser tier upgrade)
3. ✅ Task bg_ea7e3599: wigolo + bb-browser + anysearch-skill + robin (multi-capability)
4. ✅ Task bg_a722a822: Agent-Reach (73k stars mega-project)

### 待补充调研 (深度二轮)
- [x] MediaCrawler: 63.1k stars, Playwright 爬取小红书/抖音/快手/B站/微博/贴吧/知乎，支持评论爬取、IP 代理、生成词云图，WebUI 可视化界面
- [x] twscrape: 2.7k stars, 基于 cookie 的 X/Twitter 多账号轮换采集器，支持搜索/用户/评论/关注者，自动处理 rate limit
- [x] apify/agent-skills: 2.4k stars, Apify 官方 AI agent 技能包，130+ 精选 Actors + 30k+ Apify Store 自动回退，支持 Claude Code/Cursor/Windsurf/Codex/Gemini CLI
- [ ] 剩余 13+ repos 需二轮深度分析

---

## 输出交付物 (待完成)

1. **能力矩阵**: 27 repos × 当前平台 MECE 覆盖度分析
2. **融合优先级**: P0/P1/P2 分级，ROI 排序
3. **集成方案**: 每个高优先级 repo 的集成路径 (sidecar / SDK / API wrap)
4. **技术债评估**: 哪些当前能力可以被新方案替代
5. **部署清单**: Docker compose / systemd / 环境变量配置

---

## 下一步
等待 4 个并行调研任务完成，收集结构化 findings，输出融合解决方案。
