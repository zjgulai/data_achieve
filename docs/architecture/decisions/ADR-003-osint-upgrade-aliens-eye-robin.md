---
name: adr-003-osint-upgrade-aliens-eye-robin
description: OSINT 能力升级决策。记录为何在现有 Sherlock/Maigret/Blackbird/SpiderFoot 基础上，选择集成 Aliens Eye（ML-OSINT）和 Robin（暗网情报），而非替换现有工具。当调整 OSINT 工具链、新增社会工程学采集能力时使用。
---

# ADR-003: OSINT 能力升级（Aliens Eye + Robin，补充而非替换）

**状态**: 已采纳  
**日期**: 2026-09-03  
**决策者**: lute

---

## 背景

现有 OSINT 工具链：
- **Sherlock**（500+ 平台，HTTP 状态码检测）
- **Maigret**（3000+ 平台，详细报告）
- **Blackbird**（574 站点，邮箱/用户名 OSINT）
- **SpiderFoot**（9 个端点，模块化 OSINT 框架）

**差距分析**：
- Sherlock/Maigret 依赖 HTTP 状态码，误报率高（~15%）
- 无跨站关联能力（无法判断多个账号是否同一人）
- 无暗网情报层（泄露数据、凭证市场、论坛）
- 无变化监控

---

## 决策

**集成 Aliens Eye（ML-OSINT）+ Robin（暗网 OSINT），不替换现有工具**。

### Aliens Eye（7 个新端点）

| 端点 | 能力 |
|---|---|
| `aliens_eye_basic` | 840+ 平台，ML + 30维启发式检测 |
| `aliens_eye_advanced` | 带前缀/后缀变体的全量扫描 |
| `aliens_eye_correlate` | 跨站聚类（头像哈希 + Bio + 共享链接） |
| `aliens_eye_recurse` | 递归追踪 Bio 中发现的其他用户名 |
| `aliens_eye_domain` | 域名变体注册检测 |
| `aliens_eye_batch` | 最多 10 个用户名批量扫描 |
| `aliens_eye_selfcheck` | 精确率/召回率/F1 自检报告 |

**选择理由**：ML 检测比纯 HTTP 状态码准确，跨站关联是现有工具完全没有的能力。

### Robin（3 个新端点）

| 端点 | 能力 |
|---|---|
| `robin_darkweb_search` | 关键词在 8 个暗网搜索引擎检索 |
| `robin_darkweb_username` | 用户名在暗网泄露/市场记录检索 |
| `robin_darkweb_email` | 邮箱在暗网凭证列表检索 |

**实现方式**：直接实现 Robin 核心的 Tor SOCKS5 + BeautifulSoup 解析逻辑，不包装其 Streamlit UI。

**选择理由**：唯一覆盖暗网的工具，与现有明网 OSINT 完全互补。

---

## 后果

**正面**：
- OSINT 总端点从 9 增至 19（+10）
- ML 检测层补充现有 HTTP 状态码方案的弱点
- 首次覆盖暗网情报维度

**负面**：
- Aliens Eye 扫描耗时 2~5 分钟（ML 推理），不适合实时请求
- Robin 需要 Tor 守护进程，增加服务器运维复杂度

**部署依赖**：
- `pip install aliens-eye`（已写入 pyproject.toml）
- `pip install 'httpx[socks]' beautifulsoup4`（Robin 依赖，已写入 pyproject.toml）
- `apt install tor` + Tor 守护进程运行在 `127.0.0.1:9050`（新服务器待配置）
