# Deep Research Phase 2: 补全剩余 13 Repos (MECE)

**执行时间**: 2026-08-20  
**目标**: 补全剩余未详细分析的 13 个 repos，完成完整的 MECE 覆盖

---

## 剩余待分析 Repos (13/27)

### 已分析 (14 repos) ✅
1. browser-use (109k) - LLM browser agent
2. Agent-Reach (73k) - Multi-platform agent
3. Firecrawl (169k) - Web crawl/extract
4. sherlock (89k) - Username OSINT 400+ sites
5. maigret (36.9k) - Username OSINT 3000+ sites
6. MediaCrawler (63k) - 中文社媒爬虫
7. obscura (21k) - Rust headless browser
8. anydoc (17k) - Document to Markdown
9. browser-harness (16k) - Self-healing browser
10. autoscraper (7.9k) - Smart scraper
11. bb-browser (6k) - Browser with login state
12. proxifly (6.6k) - Free proxy list
13. anysearch-skill (5.7k) - Unified search
14. wigolo (4.6k) - Local MCP search

### 待补全分析 (13 repos) ⏳

| # | Repo | Stars | Category | 初步判断 |
|---|------|-------|----------|---------|
| 15 | **SpiderFoot** | 21.2k | OSINT | 已集成 3 endpoints，需对比完整能力 |
| 16 | **TikHub-API-Python-SDK** | 857 | Social API | 已集成 TikHub 17 endpoints，SDK 封装 |
| 17 | **models.dev** | 6.5k | AI Models DB | 开源 AI 模型数据库，与采集平台关联度？ |
| 18 | **BestBlogs** | 4k | Content Aggregator | 技术博客聚合 + LLM 摘要评分 |
| 19 | **AnythingAtlas** | 253 | Learning Path | 学习路径规划工具 |
| 20 | **StackPrism** | 837 | Tech Stack Detection | 技术栈检测（已有 Wappalyzer） |
| 21 | **awesome-osint-arsenal** | 1.8k | OSINT Toolkit | 100+ OSINT 工具集合 |
| 22 | **blackbird** | 7.8k | OSINT | Username + Email OSINT（与 Sherlock/Maigret 对比） |
| 23 | **AnyCrawl** | 3.4k | SERP + Crawler | Node.js SERP + LLM-ready 数据 |
| 24 | **twscrape** | 2.7k | X/Twitter | 已通过 TikHub 覆盖 |
| 25 | **apify/agent-skills** | 2.4k | Apify Actors | 已集成 98 actors，需对比 130 精选 |
| 26 | **mubeng** | 2.4k | Proxy Rotator | ✅ P0 已部署 |
| 27 | **robin** | 6.4k | Dark Web OSINT | 暗网搜索（法律边界） |

---

## 执行 TODO

### Phase 2.1: 高优先级补全 (5 repos, 预计 2h)

- [ ] **SpiderFoot** (21.2k) - 对比现有 3 endpoints，识别缺失的 OSINT 模块
- [ ] **blackbird** (7.8k) - 与 Sherlock/Maigret 对比，是否有差异化价值
- [ ] **AnyCrawl** (3.4k) - SERP 结构化提取能力 vs 现有 3 引擎
- [ ] **BestBlogs** (4k) - 技术博客聚合 + LLM 评分，与 DevTo/Juejin 对比
- [ ] **robin** (6.4k) - 暗网 OSINT 技术细节 + 法律合规性

### Phase 2.2: 中优先级补全 (5 repos, 预计 1.5h)

- [ ] **models.dev** (6.5k) - AI 模型数据库，与数据采集平台的关联度
- [ ] **TikHub-API-Python-SDK** (857) - Python SDK 封装，对比现有集成方式
- [ ] **StackPrism** (837) - 浏览器插件技术栈检测 vs Wappalyzer
- [ ] **awesome-osint-arsenal** (1.8k) - 100+ 工具清单，识别平台未覆盖的工具
- [ ] **apify/agent-skills** (2.4k) - 130 精选 actors 清单对比

### Phase 2.3: 低优先级补全 (3 repos, 预计 1h)

- [ ] **AnythingAtlas** (253) - 学习路径规划，与采集平台关联度评估
- [ ] **twscrape** (2.7k) - 已通过 TikHub 覆盖，确认无需单独集成
- [ ] **mubeng** (2.4k) - ✅ P0 已部署，补充使用统计

---

## 执行方案

### 策略 1: 并行 Web 抓取 (批量)
```bash
# 一次性抓取所有 README
repos=(
  "smicallef/spiderfoot"
  "p1ngul1n0/blackbird"
  "any4ai/AnyCrawl"
  "ginobefun/BestBlogs"
  "apurvsinghgautam/robin"
  "anomalyco/models.dev"
  "TikHub/TikHub-API-Python-SDK"
  "setube/stackprism"
  "rawfilejson/awesome-osint-arsenal"
  "Liuziyu77/AnythingAtlas"
  "vladkens/twscrape"
  "apify/agent-skills"
  "mubeng/mubeng"
)

for repo in "${repos[@]}"; do
  curl -s "https://raw.githubusercontent.com/$repo/main/README.md" > "${repo//\//-}.md"
done
```

### 策略 2: MECE 分类框架

所有 repos 按功能归类：

```
├── Infrastructure (基础设施)
│   ├── ✅ mubeng (proxy rotator) - P0 已部署
│   ├── ✅ proxifly (free proxy list)
│   └── ✅ autoscraper (smart extraction)
│
├── Browser Automation (浏览器)
│   ├── ✅ browser-use (LLM agent)
│   ├── ✅ obscura (Rust headless)
│   ├── ✅ browser-harness (self-healing)
│   └── ✅ bb-browser (login state) - P0 已部署
│
├── OSINT (情报收集)
│   ├── ✅ maigret (3000+ sites) - P0 已部署
│   ├── ✅ sherlock (400+ sites)
│   ├── ⏳ SpiderFoot (21.2k) - 待补全
│   ├── ⏳ blackbird (7.8k) - 待补全
│   ├── ⏳ robin (6.4k, dark web) - 待补全
│   └── ⏳ awesome-osint-arsenal (1.8k, toolkit) - 待补全
│
├── Social Media Crawlers (社媒爬虫)
│   ├── ✅ MediaCrawler (63k, 中文) - 已集成
│   ├── ✅ TikHub API (857, 17 platforms) - 已集成
│   ├── ✅ twscrape (2.7k, X/Twitter) - 已覆盖
│   └── ⏳ TikHub SDK (Python封装) - 待评估
│
├── Web Crawl & Extract (通用爬取)
│   ├── ✅ Firecrawl (169k) - 已集成
│   ├── ✅ anydoc (17k, doc→markdown) - 已集成
│   ├── ⏳ AnyCrawl (3.4k, SERP) - 待补全
│   └── ✅ anysearch-skill (5.7k, unified search)
│
├── Agent Orchestration (编排)
│   ├── ⏳ Agent-Reach (73k) - 待深度调研
│   ├── ✅ wigolo (4.6k, MCP)
│   └── ⏳ apify/agent-skills (2.4k, 130 actors) - 待对比
│
├── Tech Stack Detection (技术栈)
│   ├── ✅ Wappalyzer - 已集成
│   └── ⏳ StackPrism (837, 浏览器插件) - 待对比
│
├── Content Aggregation (内容聚合)
│   ├── ✅ DevTo/Juejin/Substack - 已集成
│   ├── ⏳ BestBlogs (4k, LLM评分) - 待补全
│   └── ⏳ AnythingAtlas (253, 学习路径) - 待评估
│
└── AI Models (AI 模型)
    └── ⏳ models.dev (6.5k) - 待评估关联度
```

---

## 输出目标

### 1. 补全能力矩阵 (Excel 格式)
```
| Repo | Stars | Category | 平台已有 | 差异化能力 | ROI | Priority |
|------|-------|----------|---------|-----------|-----|----------|
| ... 27 行完整对比 ... |
```

### 2. 更新融合方案
- Part II.6: 补全 OSINT 层详细对比 (SpiderFoot vs 现有)
- Part II.7: 补全 Content Aggregation 层 (BestBlogs)
- Part II.8: 补全 SERP 层 (AnyCrawl vs 现有)
- Part II.9: 补全 Tech Stack 层 (StackPrism vs Wappalyzer)

### 3. 最终 P1/P2 优先级调整
基于补全分析，重新排序 P1/P2 任务的 ROI

---

## 下一步
立即执行 Phase 2.1 高优先级补全（5 repos）
