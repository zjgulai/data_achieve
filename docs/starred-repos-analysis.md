# Data-Achieve Starred Repos 深度分析

> 生成时间：2026-09-03  
> 来源：https://github.com/stars/zjgulai/lists/data-achieve  
> 仓库总数：31  
> 当前平台端点：218 (162 可用 / 56 配置依赖)

---

## 一、仓库分类概览

### 🕵️ OSINT 工具（7个）
| 仓库 | Stars | 核心能力 | 集成状态 |
|---|---|---|---|
| smicallef/spiderfoot | 21.7k | 自动化 OSINT 威胁情报 | ✅ 已集成 9端点 |
| sherlock-project/sherlock | 90.9k | 跨平台用户名搜索 | ✅ 已集成 1端点 |
| soxoj/maigret | 37.3k | 3000+站点用户画像 | ✅ 已集成 1端点 |
| p1ngul1n0/blackbird | 7.9k | 用户名/邮箱 OSINT | ✅ 已集成 2端点 |
| apurvsinghgautam/robin | 7.0k | AI 暗网 OSINT | ❌ 未集成 |
| arxhr007/Aliens_eye | 3.8k | 840+社交账号猎杀 | ❌ 未集成 |
| rawfilejson/awesome-osint-arsenal | 2.7k | OSINT 工具集合 | ❌ 工具集 |

### 🌐 浏览器自动化（5个）
| 仓库 | Stars | 核心能力 | 集成状态 |
|---|---|---|---|
| browser-use/browser-use | 112.1k | AI agent 浏览器自动化 | ❌ 未集成 |
| browser-use/browser-harness | 17.3k | 自愈式 LLM 任务执行 | ❌ 未集成 |
| epiral/bb-browser | 6.2k | Chrome MCP server | ❌ 未集成 |
| citrolabs/ego-lite | 14.7k | AI agent 浏览器状态共享 | ❌ 未集成 |
| h4ckf0r0day/obscura | 24.2k | 无头浏览器 (Rust) | ❌ 未集成 |

### 🚀 数据采集框架（5个）
| 仓库 | Stars | 核心能力 | 集成状态 |
|---|---|---|---|
| firecrawl/firecrawl | 175.8k | Web 搜索/爬取/交互 | ✅ 已集成 3端点 |
| Panniantong/Agent-Reach | 77.6k | 零 API 费用全网搜索 | ❌ 未集成 |
| KnockOutEZ/wigolo | 4.9k | AI 编码 agent 本地搜索 | ❌ 未集成 |
| anysearch-ai/anysearch-skill | 6.0k | 统一实时搜索引擎 | ✅ 已集成 2端点 |
| alirezamika/autoscraper | 7.9k | 智能自动学习爬虫 | ✅ 已集成 1端点 |

### 📱 社交媒体（4个）
| 仓库 | Stars | 核心能力 | 集成状态 |
|---|---|---|---|
| TikHub/TikHub-API-Python-SDK | 874 | 抖音/TikTok/小红书/快手/微博/Instagram/YouTube/X | ✅ 已集成 61端点 |
| NanmiCoder/MediaCrawler | 64.3k | 小红书/抖音/快手/B站/微博/百度贴吧/知乎 | ✅ 已集成 11端点 |
| vladkens/twscrape | 2.7k | X/Twitter 多账号轮换 | ✅ 已集成 3端点 |
| any4ai/AnyCrawl | 3.4k | Google/Bing/Baidu SERP | ✅ 已集成 3端点 |

### 📄 文档处理（2个）
| 仓库 | Stars | 核心能力 | 集成状态 |
|---|---|---|---|
| firecrawl/anydoc | 20.1k | Word/PDF/Excel→Markdown | ❌ 未集成 |
| ginobefun/BestBlogs | 4.0k | AI 精选技术博客 | ✅ 已集成 1端点 |

### 🔧 代理/网络（2个）
| 仓库 | Stars | 核心能力 | 集成状态 |
|---|---|---|---|
| proxifly/free-proxy-list | 6.7k | 免费代理列表 API | ❌ 未集成 |
| mubeng/mubeng | 2.5k | Go 代理轮换器 | ❌ 未集成 |

### 🤖 AI/Agent（3个）
| 仓库 | Stars | 核心能力 | 集成状态 |
|---|---|---|---|
| apify/agent-skills | 2.4k | Apify agent 技能集合 | ⚠️ 部分集成 (75端点) |
| anomalyco/models.dev | 6.7k | AI 模型开源数据库 | ❌ 未集成 |
| Liuziyu77/AnythingAtlas | 256 | 主题学习路径规划 | ❌ 未集成 |

### 🛠️ 其他工具（3个）
| 仓库 | Stars | 核心能力 | 集成状态 |
|---|---|---|---|
| setube/stackprism | 843 | 技术栈检测浏览器插件 | ⚠️ 类似功能已有 (wappalyzer) |
| itshen/source-reading-methodology | 130 | AI 精读大型开源仓库方法论 | ❌ 方法论 |

---

## 二、集成现状统计

### 已集成端点分布
```
✅ 已完全集成：15/31 (48.4%)
  - TikHub: 61 端点
  - Apify: 75 端点  
  - MediaCrawler: 11 端点
  - SpiderFoot: 9 端点
  - AnyCrawl: 3 端点
  - twscrape: 3 端点
  - firecrawl: 3 端点
  - anysearch: 2 端点
  - blackbird: 2 端点
  - sherlock/maigret: 各1端点
  - autoscraper/bestblogs: 各1端点

⚠️ 部分集成：1/31 (3.2%)
  - Apify agent-skills: 仅通用 actor 调用，未专项集成

❌ 未集成：15/31 (48.4%)
```

### 集成优先级评估（基于 stars + 独特价值）

#### 🔴 P0 - 高价值待集成（3个）
1. **browser-use** (112k★) - AI agent 浏览器自动化框架  
   - 独特价值：支持 AI agent 视觉识别 + 自然语言操作  
   - 集成复杂度：中  
   - 预期端点：5-8个 (导航/点击/提取/截图/表单填充)

2. **Agent-Reach** (77.6k★) - 零 API 费用全网搜索  
   - 独特价值：Twitter/Reddit/YouTube/GitHub/Bilibili/小红书统一读取  
   - 集成复杂度：中  
   - 预期端点：10-15个 (各平台搜索+内容提取)

3. **obscura** (24.2k★) - Rust 无头浏览器  
   - 独特价值：高性能 + AI agent 专用  
   - 集成复杂度：高 (Rust FFI)  
   - 预期端点：3-5个 (爬取/渲染/反检测)

#### 🟡 P1 - 中等价值待集成（4个）
4. **anydoc** (20.1k★) - 文档转 Markdown  
   - 独特价值：支持 Word/PPT/Excel/OpenDocument/RTF/EPUB  
   - 集成复杂度：低 (Node.js/Python bindings)  
   - 预期端点：1个 (万能文档转换)

5. **browser-harness** (17.3k★) - 自愈式浏览器任务  
   - 独特价值：LLM 驱动的自修复  
   - 集成复杂度：中  
   - 预期端点：2-3个 (任务执行/状态监控)

6. **ego-lite** (14.7k★) - AI agent 浏览器状态共享  
   - 独特价值：与 Codex/Claude Code 共享登录态  
   - 集成复杂度：中  
   - 预期端点：3-5个 (状态获取/会话管理)

7. **robin** (7.0k★) - AI 暗网 OSINT  
   - 独特价值：暗网 + AI 增强  
   - 集成复杂度：高 (Tor 依赖)  
   - 预期端点：2-3个 (暗网搜索/情报收集)

#### 🟢 P2 - 低优先级（8个）
- proxifly/free-proxy-list (6.7k★) - 基础设施支持  
- bb-browser (6.2k★) - 与 ego-lite 功能重叠  
- wigolo (4.9k★) - 本地优先搜索  
- Aliens_eye (3.8k★) - 与 maigret/blackbird 重叠  
- mubeng (2.5k★) - 代理轮换工具  
- awesome-osint-arsenal (2.7k★) - 工具集合  
- stackprism (843★) - 已有 wappalyzer  
- AnythingAtlas (256★) - 方法论项目  

---

## 三、技术债务与改进方向

### 当前痛点
1. **MediaCrawler 11 端点全 fail** - cookies 未配置  
2. **Apify 30+ 端点月度额度耗尽** - 成本控制问题  
3. **TikHub 10+ 端点订阅等级不足** - 需升级订阅  
4. **firecrawl 3 端点需 API key** - 配置缺失  
5. **baidu/bing SERP 需 ANYCRAWL_BASE_URL** - 服务未部署  

### 技术栈空白
1. **浏览器自动化层** - 缺少 AI agent 级别的视觉+交互能力  
2. **文档解析层** - 仅支持 PDF，缺 Word/PPT/Excel  
3. **暗网情报层** - 无暗网数据源  
4. **会话管理层** - 无登录态共享机制  
5. **代理基础设施** - 手动管理，无轮换池  

### 架构优化建议
1. **分层集成策略**  
   ```
   L4 智能层: browser-use, browser-harness (AI 驱动)
   L3 自动化层: ego-lite, bb-browser (会话管理)
   L2 采集层: 现有 218 端点 (数据获取)
   L1 基础设施层: proxifly, mubeng (代理/网络)
   ```

2. **成本优化方案**  
   - Apify: 优先使用免费 actors, 月度配额告警  
   - TikHub: 按需升级订阅，非核心端点降级处理  
   - 自建服务: AnyCrawl SERP 服务容器化部署  

3. **配置管理改进**  
   - MediaCrawler cookies 定期更新机制  
   - 敏感配置迁移至 `/data/scrapy/configs/.env.production`  
   - 健康检查增加配置缺失检测  

---

## 四、待调研结果汇总

### 🔄 进行中的并行调研任务

#### Task 1: bg_bb8c0881 (librarian)
- SpiderFoot, MediaCrawler, Blackbird, maigret, sherlock
- 预期产出：5个仓库的深度技术分析

#### Task 2: bg_2acabab2 (librarian)
- TikHub, browser-use, firecrawl, AnyCrawl, twscrape  
- 预期产出：5个仓库的深度技术分析

#### Task 3: bg_83c02d59 (librarian)
- mubeng, proxifly, browser-harness, wigolo + 9个杂项工具  
- 预期产出：13个仓库的轻量级评估

---

## 五、下一步行动

### 短期（1-2周）
1. ✅ 修复 218 端点映射问题 (已完成)  
2. 🔄 等待 3 个并行调研任务完成  
3. 📝 基于调研结果补充技术细节  
4. 🎯 制定 P0 工具集成方案 (browser-use, Agent-Reach, obscura)  

### 中期（1-2月）
1. 🔧 解决 MediaCrawler cookies 配置  
2. 💰 Apify/TikHub 成本优化  
3. 🚀 部署 AnyCrawl SERP 服务  
4. 📦 集成 anydoc 文档转换  

### 长期（3-6月）
1. 🏗️ 构建四层架构 (智能/自动化/采集/基础设施)  
2. 🤖 接入 browser-use/browser-harness  
3. 🌐 建立代理轮换池  
4. 🔒 添加暗网情报源  

---

**生成工具**: Claude Opus 4.7 (Sisyphus)  
**数据来源**: GitHub starred list + 本地代码扫描  
**更新频率**: 调研任务完成后追加
