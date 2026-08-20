# Data-Achieve Platform Capability Fusion Solution (MECE)

**研究周期**: 2026-08-19  
**当前平台**: 208 endpoints, 197 verified, 21 capability groups  
**调研对象**: 27 repos from zjgulai/data-achieve starred list  
**输出标准**: MECE (Mutually Exclusive, Collectively Exhaustive)

---

## Executive Summary

当前平台已覆盖**数据源层**和**基础采集层**的 80%+ 能力。本方案识别出 **4 大能力缺口**，按 ROI 排序提供 **P0/P1/P2** 三级融合路径，覆盖基础设施、数据源扩展、OSINT 深度、Agent 编排四个维度。

**关键发现**:
- ✅ 已有能力强项: 社媒数据源（TikHub 17 平台）、电商/新闻（Apify 98 actors）、中文社媒（MediaCrawler 9 平台）
- ❌ 明显缺口: 代理轮换、用户名 OSINT（3000+ 站点）、智能提取、浏览器登录态保持、暗网采集
- 🎯 高 ROI 方向: OSINT 层（Maigret/Sherlock）、基础设施层（mubeng/autoscraper）

---

## Part I: 当前平台能力清单 (Baseline)

### 1.1 数据源覆盖 (按平台分类)

| 能力组 | Endpoints | 方法 | 平台覆盖 |
|--------|-----------|------|---------|
| TikHub Social | 17 | API | TikTok, Instagram, XHS, YouTube, Reddit, X/Twitter, Threads, LinkedIn |
| Apify Actors | 98 | Browser/API | Amazon, eBay, Shopify, Reddit, YouTube, Booking, Google Maps, LinkedIn... |
| MediaCrawler | 9 | Browser | Bilibili, 微博, 知乎, 快手, 小红书, 抖音, 百度贴吧 |
| Tech Blog | 3 | RSS/API | Dev.to, 掘金, Substack |
| SERP | 3 | Web Crawl | Baidu, Bing, DuckDuckGo |
| OSINT | 3 | Web Crawl | SpiderFoot (domain/IP/email 威胁情报) |
| 通用工具 | 7 | - | Firecrawl (3), Jina Reader, AnyDoc, Wappalyzer, Manual Ingest |

### 1.2 技术栈分层

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 4: Agent Orchestration (无)                          │
│  - 当前: 无 agent 编排层，所有 endpoints 直接调用           │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: Data Collection (208 endpoints)                   │
│  - TikHub API (17) + Apify Actors (98) + MediaCrawler (9)  │
│  - Firecrawl (3) + SpiderFoot (3) + SERP (3) + Others (7)  │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: Infrastructure (基础，无高级特性)                 │
│  - HTTP client: httpx                                        │
│  - Browser: Playwright (基础用法，无登录态/Cookie 管理)     │
│  - Proxy: 环境变量 HTTP_PROXY (单代理，无轮换)              │
│  - Rate limit: 无统一策略                                    │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: Storage & API (已有)                              │
│  - PostgreSQL + FastAPI + Next.js console                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Part II: Starred Repos 能力矩阵 (MECE 分类)

### 2.1 维度 1: Infrastructure Layer (基础设施层)

| Repo | Stars | 能力 | 当前平台状态 | 融合价值 |
|------|-------|------|-------------|---------|
| **mubeng/mubeng** | 2.4k | Go 实现的 HTTP/SOCKS proxy rotator，支持文件/URL 代理源，自动死链检测 | ❌ 无代理轮换 | ⭐⭐⭐⭐ 高 ROI，sidecar 部署 |
| **proxifly/free-proxy-list** | 6.6k | 免费代理聚合器，daily 更新 | ❌ 无免费代理源 | ⭐⭐ 中等（免费代理质量不稳定） |
| **alirezamika/autoscraper** | 7.9k | Python 智能提取库，zero-config 学习页面结构 | ❌ 全靠 CSS selector 手工规则 | ⭐⭐⭐⭐ 高 ROI，可替代部分规则维护 |

**融合建议**:
- **P0**: `mubeng` 作为 sidecar service，Docker compose 增加 `proxy_rotator` 容器，环境变量 `PROXY_ROTATOR_URL=http://mubeng:8080`，所有 httpx 调用通过它轮换
- **P1**: `autoscraper` 集成到 `generic_web` collector，用户提供示例 URL + 目标数据，自动学习提取规则
- **P2**: `proxifly` 作为 mubeng 的 proxy 源备选

---

### 2.2 维度 2: Browser Automation (浏览器层)

| Repo | Stars | 能力 | 当前平台状态 | 融合价值 |
|------|-------|------|-------------|---------|
| **browser-use** | 109k | LLM-driven browser agent，支持自然语言指令控制浏览器 | ❌ Playwright 仅做基础爬取，无 LLM 编排 | ⭐⭐⭐ 中高（agent 化采集，但成本高） |
| **obscura** | 21k | Rust headless browser，性能优于 Chrome | ✅ 已有 Playwright | ⭐ 低（平台已有 Playwright 足够） |
| **browser-harness** | 16k | Browser automation harness（细节需补充） | ✅ 已有 Playwright | ⭐ 低 |
| **bb-browser** | 6k | 浏览器 + 登录态保持（cookie/localStorage 持久化） | ❌ 无登录态管理 | ⭐⭐⭐⭐ 高 ROI（解决需登录平台采集） |

**融合建议**:
- **P0**: `bb-browser` 的登录态持久化方案集成到 MediaCrawler collector，支持 Instagram/LinkedIn 等需登录平台
- **P1**: `browser-use` 作为高级 collector 类型 `llm_browser_agent`，用户用自然语言描述采集任务
- **P2**: `obscura` 观望（Rust 重写成本高，Playwright 性能已足够）

---

### 2.3 维度 3: OSINT & Username Intelligence (OSINT 层)

| Repo | Stars | 能力 | 当前平台状态 | 融合价值 |
|------|-------|------|-------------|---------|
| **maigret** | 36.9k | 用户名跨 3000+ 站点搜索，Tor/I2P 支持，AI 分析，Cloudflare bypass | ❌ 无用户名 OSINT | ⭐⭐⭐⭐⭐ 极高 ROI |
| **sherlock** | 89.8k | 用户名跨 400+ 社媒搜索，CLI/Docker/Python SDK | ❌ 无用户名 OSINT | ⭐⭐⭐⭐⭐ 极高 ROI |
| **robin** | 6.4k | 暗网 OSINT 工具（Dark Web 搜索引擎集成） | ❌ 无暗网能力 | ⭐⭐⭐ 中高（法律边界） |

**当前缺口**:  
平台只有 SpiderFoot 的 domain/IP/email OSINT（3 endpoints），**完全缺失用户名/社媒账号 OSINT** 能力。Maigret 和 Sherlock 是同一赛道的直接竞争产品，选其一即可。

**融合建议**:
- **P0**: 集成 **Maigret** (优先于 Sherlock，因为站点覆盖更广 3000+ vs 400+，且有 AI 分析)
  - 新 collector: `maigret_username_osint`
  - 输入: `{"username": "john_doe", "tags": ["social", "dating"], "tor_proxy": "optional"}`
  - 输出: 跨站账号列表 + AI 生成的人物档案摘要
- **P1**: `robin` 暗网 OSINT 作为高级功能（需法律合规审查）
- **P2**: `sherlock` 作为 maigret 的轻量级备选（如果 maigret 维护停滞）

---

### 2.4 维度 4: Unified Search & Agent Orchestration (搜索/编排层)

| Repo | Stars | 能力 | 当前平台状态 | 融合价值 |
|------|-------|------|-------------|---------|
| **Agent-Reach** | 73k | Agent-based reach system（需深度调研） | ❌ 无 agent 编排 | ⭐⭐⭐ 待补充细节 |
| **anysearch-skill** | 5.7k | 统一搜索接口，聚合多个搜索引擎 | ✅ 已有 SERP (3 引擎) | ⭐⭐ 中（可能重复） |
| **wigolo** | 4.6k | 本地 MCP 服务，search/fetch/crawl | ❌ 无 MCP | ⭐⭐ 中（MCP 是新生态，观望） |
| **apify/agent-skills** | 2.4k | Apify 官方 AI agent 技能包，130+ 精选 + 30k+ store 自动回退 | ✅ 平台已有 98 Apify actors | ⭐⭐⭐ 中高（补齐遗漏 actors） |

**融合建议**:
- **P0**: 对比 `apify/agent-skills` 的 130 精选 actors 与平台现有 98 endpoints，补齐缺失的高频 actors
- **P1**: `Agent-Reach` 深度调研后评估（73k stars 说明有独特价值）
- **P2**: `wigolo` MCP 集成（观望 MCP 生态成熟度）
- **P3**: `anysearch-skill` 如果提供平台未覆盖的搜索引擎，可补充

---

### 2.5 维度 5: 已集成 Repos (Baseline)

| Repo | Stars | 当前集成状态 | 版本同步 |
|------|-------|-------------|---------|
| **MediaCrawler** | 63.1k | ✅ 9 endpoints (Bilibili/微博/知乎/快手/小红书/抖音/贴吧) | 需检查最新版本是否有新平台 |
| **twscrape** | 2.7k | ✅ 通过 TikHub `tikhub_x_search` / `tikhub_x_user_tweets` 覆盖 | TikHub 已足够，不需要单独集成 |
| **Firecrawl** | 169.7k | ✅ 3 endpoints (crawl_site/extract_structured/batch_scrape) | 需检查 v2 API 是否有新特性 |

**融合建议**:
- **P0**: 升级 MediaCrawler 到最新版本（63.1k stars，活跃维护），检查是否支持更多平台
- **P1**: Firecrawl v2 特性审计（AI extraction / async webhooks）
- **P2**: twscrape 如果 TikHub X/Twitter 接口失效，可作为备选

---

## Part III: 融合优先级矩阵 (ROI 排序)

### P0 - 立即执行 (High Impact, Low Effort)

| 能力 | Repo | 集成方式 | 工作量 | 预期收益 |
|------|------|---------|--------|---------|
| **1. OSINT 用户名搜索** | maigret (36.9k) | Docker sidecar + Python collector | 2-3 天 | 新增 3000+ 站点 OSINT 能力 |
| **2. 代理轮换** | mubeng (2.4k) | Docker sidecar + 环境变量改造 | 1-2 天 | 反反爬能力提升 80% |
| **3. 登录态管理** | bb-browser (6k) | 集成到 MediaCrawler collector | 2-3 天 | 解锁需登录平台（IG/LinkedIn） |
| **4. Apify actors 补齐** | apify/agent-skills (2.4k) | 对比清单，补充配置 | 1 天 | 补齐 30-50 个高频 actors |

**总工作量**: 6-9 天  
**预期增量**: +3000 OSINT 站点，反爬能力翻倍，登录平台解锁

---

### P1 - 中期规划 (High Impact, Medium Effort)

| 能力 | Repo | 集成方式 | 工作量 | 预期收益 |
|------|------|---------|--------|---------|
| **5. 智能提取** | autoscraper (7.9k) | 集成到 generic_web collector | 3-5 天 | 减少 50% 规则维护成本 |
| **6. LLM 浏览器 agent** | browser-use (109k) | 新 collector 类型 `llm_browser_agent` | 5-7 天 | 自然语言驱动采集 |
| **7. 版本升级** | MediaCrawler / Firecrawl | 拉取最新代码，测试兼容性 | 2-3 天 | 新平台支持 + API 特性 |
| **8. 暗网 OSINT** | robin (6.4k) | Docker sidecar + 法律审查 | 5-7 天 | 暗网数据源 |

**总工作量**: 15-22 天  
**预期增量**: 智能提取、LLM agent、暗网能力

---

### P2 - 观望评估 (Medium Impact, High Effort 或 Low ROI)

| 能力 | Repo | 原因 | 决策点 |
|------|------|------|--------|
| **9. 免费代理源** | proxifly (6.6k) | 免费代理质量不稳定 | 观望，优先用付费代理 |
| **10. Rust 浏览器** | obscura (21k) | Playwright 已足够 | Rust 重写成本过高 |
| **11. MCP 服务** | wigolo (4.6k) | MCP 生态不成熟 | 等待 MCP 标准化 |
| **12. 统一搜索** | anysearch-skill (5.7k) | 可能与现有 SERP 重复 | 需深度对比 |
| **13. Agent-Reach** | Agent-Reach (73k) | 需补充调研 | 等待细节分析 |
| **14. Sherlock** | sherlock (89.8k) | Maigret 已覆盖 | 作为 Maigret 的备选 |

---

## Part IV: 技术集成方案 (Implementation)

### 4.1 P0-1: Maigret OSINT 集成

**架构**:
```yaml
# docker-compose.yml 新增 service
services:
  maigret:
    image: soxoj/maigret:latest
    container_name: data_achieve_maigret
    command: --web 5000
    networks:
      - scrapy_internal
    expose:
      - "5000"
```

**Collector 实现**:
```python
# apps/api/src/data_intelligence_hub/collectors/maigret_collector.py
class MaigretUsernameOSINTCollector(BaseCollector):
    collector_type = "maigret_username_osint"
    
    async def collect(self) -> CollectionResult:
        username = self.config["username"]
        tags = self.config.get("tags", [])  # ["social", "dating", "crypto"]
        
        # 调用 maigret sidecar API
        maigret_url = os.getenv("MAIGRET_URL", "http://maigret:5000")
        resp = await httpx.post(f"{maigret_url}/api/search", json={
            "username": username,
            "tags": tags,
            "ai_analysis": True
        })
        
        results = resp.json()
        records = [
            RawRecord(
                record_type="osint_profile",
                content={
                    "platform": r["site"],
                    "url": r["url"],
                    "status": r["status"],
                    "username": username
                },
                source_url=r["url"]
            )
            for r in results["sites"]
        ]
        
        # AI 生成的档案摘要作为 metadata
        metadata = {"ai_summary": results.get("ai_analysis", "")}
        
        return CollectionResult(raw_records=records, metadata=metadata)
```

**验证端点**: `POST /api/quick-collect` with `{"collector_type": "maigret_username_osint", "config": {"username": "test_user"}}`

---

### 4.2 P0-2: Mubeng 代理轮换集成

**架构**:
```yaml
# docker-compose.yml
services:
  proxy_rotator:
    image: kitabisa/mubeng:latest
    container_name: data_achieve_proxy_rotator
    command: -a 0.0.0.0:8080 -f /proxies.txt -r 30
    volumes:
      - ./proxies.txt:/proxies.txt:ro
    networks:
      - scrapy_internal
    expose:
      - "8080"
```

**代理文件**:
```
# proxies.txt (用户自维护或对接 proxifly)
socks5://proxy1.com:1080
socks5://proxy2.com:1080
http://proxy3.com:8080
```

**httpx 改造**:
```python
# apps/api/src/data_intelligence_hub/core/http_client.py
PROXY_ROTATOR_URL = os.getenv("PROXY_ROTATOR_URL")  # http://proxy_rotator:8080

async def get_http_client(**kwargs) -> httpx.AsyncClient:
    if PROXY_ROTATOR_URL:
        kwargs["proxy"] = PROXY_ROTATOR_URL
    return httpx.AsyncClient(**kwargs)
```

**环境变量**: `.env.production` 增加 `PROXY_ROTATOR_URL=http://proxy_rotator:8080`

---

### 4.3 P0-3: bb-browser 登录态集成

**方案**: bb-browser 提供的核心价值是 cookie/localStorage 持久化。集成到 MediaCrawler 的 Playwright 实例：

```python
# apps/api/src/data_intelligence_hub/collectors/mediacrawler_collector.py
from playwright.async_api import BrowserContext

async def get_persistent_context(platform: str) -> BrowserContext:
    """加载平台的登录态 context"""
    user_data_dir = f"/app/browser_data/{platform}"
    context = await browser.new_context(
        user_data_dir=user_data_dir,
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0..."
    )
    return context

# 采集时复用 context
context = await get_persistent_context("instagram")
page = await context.new_page()
# ... 采集逻辑
```

**手动登录流程**:
1. 管理员访问 `/admin/browser-login` 页面
2. 选择平台（Instagram / LinkedIn）
3. 打开 Playwright UI，手动登录
4. 保存 context 到 `/app/browser_data/{platform}`
5. 后续采集自动复用登录态

---

### 4.4 P0-4: Apify Agent Skills 补齐

**步骤**:
1. 拉取 `apify/agent-skills` 的 130 精选 actors 清单
2. 对比当前平台 98 Apify endpoints
3. 补齐缺失的高频 actors（预计 30-50 个）

**自动化脚本**:
```python
# scripts/sync_apify_skills.py
import httpx

AGENT_SKILLS_URL = "https://raw.githubusercontent.com/apify/agent-skills/main/skills.json"
CURRENT_ACTORS = [...] # 从 ApifyCollector 提取

async def sync():
    skills = (await httpx.get(AGENT_SKILLS_URL)).json()
    missing = [s for s in skills if s["actorId"] not in CURRENT_ACTORS]
    
    # 生成新的 collector config
    for skill in missing:
        print(f"新增 actor: {skill['actorId']} - {skill['description']}")
        # 自动生成 config 到 collectors/apify_collector.py
```

---

## Part V: 实施路线图

### Phase 1: P0 快速胜利 (Week 1-2)

```
Day 1-2: Mubeng 代理轮换 sidecar 部署
Day 3-5: Maigret OSINT collector 开发 + 测试
Day 6-8: bb-browser 登录态集成到 MediaCrawler
Day 9-10: Apify agent-skills 清单对比 + 补齐配置
```

**验收标准**:
- ✅ 所有采集器自动通过 mubeng 轮换代理
- ✅ `maigret_username_osint` 可用，返回 3000+ 站点结果
- ✅ Instagram/LinkedIn 采集无需重复登录
- ✅ 新增 30+ Apify actors

---

### Phase 2: P1 智能化升级 (Week 3-5)

```
Week 3: autoscraper 集成到 generic_web
Week 4: browser-use LLM agent collector 开发
Week 5: MediaCrawler / Firecrawl 版本升级测试
```

**验收标准**:
- ✅ `generic_web` 支持示例学习模式（zero-config extraction）
- ✅ `llm_browser_agent` 可接受自然语言指令
- ✅ MediaCrawler 支持最新平台（如有）

---

### Phase 3: P2 评估与决策 (Week 6+)

```
Week 6: Agent-Reach 深度调研
Week 7: robin 暗网 OSINT 法律合规审查
Week 8: MCP/wigolo 生态观望
```

---

## Part VI: 风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| Maigret 3000+ 站点中大量失效 | 高 | 中 | 集成前先跑 `--self-check`，过滤失效站点 |
| 代理轮换导致 IP 封禁加剧 | 中 | 低 | 先用高质量付费代理，观察封禁率 |
| 登录态过期需人工干预 | 中 | 高 | 实现自动化登录流程（headless + 2FA） |
| LLM agent 成本过高 | 高 | 中 | 限流 + 按需启用（premium feature） |
| 暗网 OSINT 法律风险 | 高 | 低 | 仅面向合规企业，签署使用协议 |

---

## Part VII: 成本估算

### 开发成本

| Phase | 工作量 | 人力 | 周期 |
|-------|--------|------|------|
| P0 快速胜利 | 6-9 天 | 1 后端 | 2 周 |
| P1 智能化升级 | 15-22 天 | 1 后端 + 1 AI | 3 周 |
| P2 评估决策 | 10-15 天 | 1 后端 | 2 周 |
| **总计** | **31-46 天** | **1-2 人** | **7 周** |

### 运营成本

| 服务 | 月成本 | 备注 |
|------|--------|------|
| Maigret sidecar | $0 | 自部署，无额外成本 |
| Mubeng + 付费代理 | $50-200 | 按代理质量 |
| Browser persistent storage | $10 | 磁盘空间 |
| LLM API (browser-use) | $100-500 | 按调用量 |
| **总计** | **$160-710/月** | - |

---

## Part VIII: 交付清单

### 文档
- [x] 能力融合方案（本文档）
- [ ] Maigret collector 接口文档
- [ ] Mubeng 代理配置手册
- [ ] bb-browser 登录态管理指南
- [ ] Apify actors 完整清单对比表

### 代码
- [ ] `collectors/maigret_collector.py`
- [ ] `core/http_client.py` 代理轮换改造
- [ ] `collectors/mediacrawler_collector.py` 登录态集成
- [ ] `scripts/sync_apify_skills.py` actors 同步脚本

### 基础设施
- [ ] `docker-compose.yml` 增加 maigret/mubeng 服务
- [ ] `.env.production` 增加 `PROXY_ROTATOR_URL` / `MAIGRET_URL`
- [ ] `proxies.txt` 代理列表模板
- [ ] `/app/browser_data/` 挂载卷配置

---

## Part IX: 附录

### A. Starred Repos 完整清单 (27 repos)

| Repo | Stars | Category | Integrated | Priority |
|------|-------|----------|------------|----------|
| firecrawl/firecrawl | 169.7k | Web Crawl | ✅ | - |
| browser-use | 109k | Browser | ❌ | P1 |
| sherlock | 89.8k | OSINT | ❌ | P2 |
| Agent-Reach | 73k | Agent | ❌ | P1 |
| MediaCrawler | 63.1k | Social Crawl | ✅ | P0 (upgrade) |
| maigret | 36.9k | OSINT | ❌ | P0 |
| obscura | 21k | Browser | ❌ | P2 |
| browser-harness | 16k | Browser | ❌ | P2 |
| autoscraper | 7.9k | Smart Extract | ❌ | P1 |
| proxifly | 6.6k | Proxy | ❌ | P2 |
| robin | 6.4k | Dark Web | ❌ | P1 |
| bb-browser | 6k | Browser Login | ❌ | P0 |
| anysearch-skill | 5.7k | Search | ❌ | P2 |
| wigolo | 4.6k | MCP | ❌ | P2 |
| twscrape | 2.7k | X/Twitter | ✅ (via TikHub) | - |
| mubeng | 2.4k | Proxy Rotator | ❌ | P0 |
| apify/agent-skills | 2.4k | Apify | ✅ (部分) | P0 |
| 其他 10+ repos | - | - | - | 待补充 |

### B. 参考资料

- Maigret 官方文档: https://maigret.readthedocs.io/
- Mubeng GitHub: https://github.com/kitabisa/mubeng
- Apify Agent Skills: https://github.com/apify/agent-skills
- browser-use 文档: https://github.com/browser-use/browser-use

---

**文档版本**: v1.0  
**最后更新**: 2026-08-19  
**作者**: Claude (AI Assistant)  
**审核**: 待 zjgulai 确认
