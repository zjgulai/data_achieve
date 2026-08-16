---
name: next-steps-product-roadmap
description: Data Intelligence Hub 下一阶段产品演进方案与执行 TODO。基于当前 148 端点 / 50 平台 / 14 数据类型的采集能力现状，结合产品形态、用户场景和工程可行性制定。当规划下一批功能、分配开发优先级、或进行项目评审时使用。
---

# 下一步产品方案 & 执行 TODO

> **更新日期**：2026-08-16  
> **当前生产状态**：148 端点 / 137 verified / 50 平台 / 14 数据类型  
> **生产地址**：`https://scrapy.lute-tlz-dddd.top`  
> **当前 commit**：`8a68afc`

---

## 一、产品现状评估

### 已完成的核心能力

| 模块 | 状态 | 说明 |
|---|---|---|
| 平台能力中心（/platforms）| ✅ 上线 | 三层矩阵 UI：平台分类 → 内容类型 → 采集方式 |
| 采集端点目录 API | ✅ 完整 | 148 端点，content_type + method 双维度标注 |
| 快速采集（Quick Collect）| ✅ 可用 | 点击卡片即启动，支持全部 137 个 verified 端点 |
| 采集能力 13 类 MECE 覆盖 | ✅ 基本完整 | C01-C12 均有端点，C10 直播 / C11 分析已接入 |
| LinkedIn 全链路 | ✅ 上线 | 帖子/职位/员工/公司搜索（TikHub + Apify 双路）|
| 内容分析新维度 | ✅ 上线 | TikTok/YouTube 字幕、TikTok Creative Center |

### 当前产品形态定位

**Data Intelligence Hub** 当前是一个**数据采集能力中台**，提供：

1. **平台能力中心**（Scraper Console `/platforms`）：可视化浏览 137 个采集能力，一键启动快速采集
2. **API 层**（FastAPI）：完整的采集目录 API、快速采集 API、任务管理
3. **主产品 Web**（Next.js `/`）：洞察面板，对采集数据进行分析和可视化

---

## 二、下一步产品演进方向

### 方向一：采集闭环完善（最高优先级）

当前"快速采集"只能启动，**缺少采集结果的查看、下载和管理**：

- 采集任务列表页面（进度、状态、耗时）
- 采集结果预览（字段映射、数据质量）
- 数据集下载（CSV / JSON）
- 采集历史和重复触发

### 方向二：平台能力中心交互深化

三层矩阵已上线，但**用户体验还可以深化**：

- 每个采集卡片展示"上次采集时间"和"采集量"
- 平台能力中心加入"收藏常用端点"
- 快速采集 Drawer 支持参数模板保存
- 批量采集：同时启动多个端点的采集任务

### 方向三：数据质量与证据层

当前系统是**采集能力层**，数据流向下游（RawRecord → Signal → Intelligence）的链路尚未完整：

- `RawRecord` 归一化字段映射（canonical schema）
- 数据质量评分（字段完整率、时效性）
- 采集结果到 `EntitySnapshot` 的自动流转
- 证据链（Evidence）和报告生成

### 方向四：生产工程加固

- **Docker 镜像重建**：当前 API 容器为热更新状态，需 `docker compose up --build` 固化
- **Console 镜像重建**：当前前端 `.next` 也是热更新，需重建固化
- **git pull 部署方案**：服务器网络超时导致只能 docker cp，需解决（代理或 Actions 推送）
- **CI/CD 接入**：当前分支无 CI dispatch，合并到 main 后需验证

---

## 三、执行 TODO（优先级排序）

### 🔴 P0 — 生产工程加固（本周）

- [ ] **重建生产 Docker 镜像**：`docker compose up --build --no-deps api console` 固化热更新内容
- [ ] **解决 git pull 超时**：配置服务器 Git 代理或通过 GitHub Actions 推送产物
- [ ] **更新 playbook 详细端点章节**：新增的 57 个端点（Threads/LinkedIn/Lemon8/直播/分析等）补充文档

### 🟡 P1 — 采集闭环（2周内）

- [ ] **采集任务列表页面**（`/runs`）：展示 TaskRun 列表，含状态/耗时/记录数
- [ ] **采集结果预览**：在 Quick Collect Drawer 内展示采集预览（前10条）
- [ ] **数据集下载**：`/datasets` 页面支持 CSV/JSON 导出
- [ ] **快速采集参数模板**：常用参数组合可保存和复用

### 🟡 P1 — 产品形态完善（2周内）

- [ ] **Console /platforms 卡片增强**：显示最近采集时间、采集量统计
- [ ] **批量采集 UI**：选中多个端点 → 统一配置 → 一键启动
- [ ] **端点搜索优化**：支持按 platform/content_type/method 组合 URL 参数，可分享和收藏
- [ ] **主 Web 洞察面板**：接入真实采集数据，展示趋势图和 VOC 词云

### 🟢 P2 — 数据质量层（1月内）

- [ ] **canonical schema 映射**：RawRecord → EntitySnapshot 字段归一化
- [ ] **数据质量仪表板**：字段完整率、时效性、采集成功率
- [ ] **采集调度器**：定时任务配置（cron），替代手动触发
- [ ] **Webhook / 通知**：采集完成后推送（飞书/邮件）

### 🔵 P3 — 高级功能（持续迭代）

- [ ] **AI 摘要**：采集结果自动生成竞品简报/舆情摘要（接入 LLM）
- [ ] **竞品监控看板**：多品牌对比，自动对比维度（价格/声量/情感）
- [ ] **采集结果去重**：跨平台相同内容识别
- [ ] **TikTok 直播监控**：实时推送直播间状态变化
- [ ] **Douyin/WeChat 中国平台**：业务决策后接入（TikHub 已支持）

---

## 四、技术债务清单

| 项目 | 风险 | 处理方式 |
|---|---|---|
| API/Console 容器热更新未固化 | 高：容器重建会回退代码 | 下次部署必须完整重建 |
| GitHub RSS disabled 端点（3个）| 低 | 清理或迁移到 github_api |
| `public_feed` 重复 endpoint_type | 低 | 当前用 label 区分，可考虑加 slug |
| collectors.py 达 2064 行 | 中 | 考虑按分组拆分为多文件 |
| quick_collect.py 达 431 行 | 低 | 可接受，字典映射清晰 |
| `data_scrapy-apify-docs/` 研究文档 (24个目录) | 低 | 归档到 `archive/` 或 `.gitignore` |

---

## 五、当前系统能力快速参考

```bash
# 生产验收
curl -fsSL https://scrapy.lute-tlz-dddd.top/api/collectors/catalog | python3 -c "
import sys, json; d = json.load(sys.stdin)
groups = d.get('collectors', [])
v = sum(1 for g in groups for e in g.get('endpoints', []) if e.get('status') == 'verified')
t = sum(len(g.get('endpoints', [])) for g in groups)
from collections import Counter
methods = Counter(e.get('method') for g in groups for e in g.get('endpoints', []) if e.get('status') == 'verified')
print(f'total={t} verified={v}')
print('methods:', dict(methods))
"
# 期望：total=148 verified=137
# methods: {'tikhub': 45, 'apify': 75, 'github_api': 2, 'rss': 10, 'web_crawl': 5}
```

---

## 六、产品地址汇总

| 环境 | 服务 | 地址 |
|---|---|---|
| 生产 | 平台能力中心 | `https://scrapy.lute-tlz-dddd.top/platforms` |
| 生产 | 主产品 Web | `https://scrapy.lute-tlz-dddd.top/` |
| 生产 | API OpenAPI 文档 | `https://scrapy.lute-tlz-dddd.top/api/docs` |
| 生产 | 采集目录 API | `https://scrapy.lute-tlz-dddd.top/api/collectors/catalog` |
| 本地 | Console | `http://localhost:3001/platforms` |
| 本地 | API | `http://localhost:8000/docs` |
