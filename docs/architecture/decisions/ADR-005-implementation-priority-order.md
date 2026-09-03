---
name: adr-005-implementation-priority-order
description: 本批次研发优先级排序决策。记录 E1~E10 各工作项的执行顺序和依据，以及永久取消项的原因。当下一批研发启动、需要对齐优先级时使用。
---

# ADR-005: 研发优先级排序（2026-09-03 批次）

**状态**: 已采纳  
**日期**: 2026-09-03  
**决策者**: lute

---

## 背景

基于对 31 个 starred repos 的 MECE 分析，识别出 10 个候选工作项，需要排序执行。

---

## 决策

### 已执行（本批）

| 优先级 | 工作项 | 依据 | 结果 |
|---|---|---|---|
| P0 | E1: MediaCrawler cookies | 激活 11 个已实现但挂起的端点，ROI 最高 | ⏳ 等用户提供 cookies |
| P0 | E2: Twitter 多账号 | twscrape 3 端点稳定性提升 | ⏳ 等用户提供 JSON |
| P1 | E4: Aliens Eye 集成 | ML-OSINT，填补检测精度缺口，代码工作不依赖外部凭证 | ✅ 7 端点已上线 |
| P1 | E6: Robin 暗网 OSINT | 暗网维度完全空白，唯一覆盖路径 | ✅ 3 端点已注册 |
| P1 | E3: Obscura + browser-use | 浏览器反检测提升 + AI 采集新能力 | ✅ 已实现 |
| P2 | E5: 优先级文档 / ADR | 决策记录，团队对齐 | ✅ 本文件 |

### 未执行（下一批）

| 优先级 | 工作项 | 前置条件 | 预计工程量 |
|---|---|---|---|
| P3 | E7: ego-lite cookie 自动刷新 | MediaCrawler 手动 cookies 验证可用后 | 3-4 天 |
| P3 | E8: mubeng 代理轮换层 | 当前 IP 封禁问题严重时触发 | 3 天 |
| P4 | E9: CollectorCatalog 路由架构升级 | 触发条件：5+ 组 endpoint 需多后端 | 5 天 |
| P4 | E10: Agent-Reach 平台路由集成 | E9 完成后 | 3 天 |

### 永久取消项

| 工作项 | 原因 |
|---|---|
| B1: Reddit collector | 用户明确要求不做 |
| B2: YouTube collector | 用户明确要求不做 |
| D2: Shopee collector | 服务器 IP 被封（HTTP 403），技术上不可行 |

---

## 优先级决策原则

1. **已实现但挂起 > 新建**：修复 cookie 让已有端点工作，比新增端点 ROI 更高
2. **不依赖外部凭证的代码工作 > 依赖凭证**：Aliens Eye/Robin/Obscura/browser-use 可立即执行
3. **填补空白维度 > 加强已有能力**：暗网 OSINT、AI 浏览器是完全新的维度
4. **基础设施升级延后**：代理层、路由架构等基础设施改造等规模达到触发阈值再做

---

## 后果

- 本批次 verified 端点从 207 增至 218（+11）
- 剩余阻塞项（cookies、LLM key、Tor）全部记录在 AGENTS.md 待办
- 下一批优先级已明确，新 session 可直接从 ADR-005 恢复上下文
