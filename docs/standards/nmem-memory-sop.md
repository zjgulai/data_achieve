---
name: nmem-memory-sop
description: Nowledge Mem 智能体记忆系统与知识图谱构建规范（本仓库收编版）：四维治理方法论、四层记忆分层、六步落地法与验收基线；Source 项目执行以文末「本仓库修正」六条裁决为准
doc_type: standard
module: M00-治理
topic: nmem 记忆系统与知识图谱
status: 已批准
created: 2026-10-31
updated: 2026-10-31
owner: Pray
source: Lody 附件 v2.0（2026-10-26，Vicky 工程与架构团队）
---

> **收编说明**：本文为 Lody 附件《SOP_Nowledge_Mem_智能体记忆系统与知识图谱构建规范》v2.0 的仓库收编版。原路径 `.lody/attachments/` 被 `.git/info/exclude` 忽略、不可复现，故收编入库。第 1-7 节保留原文；文末「八、本仓库修正」为 Source 项目强制裁决（2026-10-31 批准），执行时与正文冲突处以该节为准。

# 智能体记忆系统与知识图谱构建标准化操作规程 (SOP)
## —— 基于 Nowledge Mem 的通用 Agent 记忆底座与认知网络建设全景指南

**文档版本**：v2.0（实战沉淀与方法论升级版）  
**制定日期**：2026-10-26  
**制定团队**：Vicky（PR Agent）工程与架构团队  
**适用场景**：所有垂类业务 Agent（如 PR-Agent, SI-Agent, VOC-Agent, CS-Agent 等）的长期记忆系统冷启动、知识蒸馏治理、代码双向集成与知识图谱网络构建。

---

## 一、 核心方法论：认知智能体的四维记忆治理哲学

给智能体构建长期记忆，**绝不是机械式地把日志、对话记录或原始表格一股脑塞入向量数据库**。缺乏治理的记忆会导致严重的信息过载、语义稀释、跨业务污染以及严重的模型幻觉。

本规范提出认知智能体记忆建设的 **「四维治理方法论（4D Governance Methodology）」**：

```
                    ┌── 1. 物理隔离度 (Space Isolation) ──> 零污染与单一真源
                    ├── 2. 认知金字塔 (Cognitive Pyramid) ─> 高信噪比分层赋权
记忆治理方法论 ─────┼── 3. 实体关系网 (Ontology & Graph) ──> 从碎片事实到因果网络
                    └── 4. 读写自闭环 (Closed-loop Recall) ─> 优雅降级与即时唤醒
```

### 1. 物理隔离与单一真源原则 (Physical Isolation)
- **拒绝大杂烩**：每个独立的业务 Agent 必须享有专属的 Memory Space（如 `pr-agent`，采用 `strict` 检索模式），物理阻断跨项目干扰。
- **真源唯一性**：业务口径必须单源维护，禁止在记忆库中保留多份相互矛盾或未获批的临时结论。

### 2. 认知金字塔四层赋权模型 (Cognitive Pyramid)
记忆按生命周期与决策权重严格自顶向下分层：
- **第一层 · 核心准则 (Importance 1.0, Timeless)**：定义 Agent 的**人格设定、决策优先级金字塔与不可逾越的操作红线**。随 Context 必定注入，作为硬性守门底线。
- **第二层 · 业务口径 (Importance 0.9, Fact)**：业务统计与策略的唯一判定标准（如时间窗口、免责口径、官方 SOP）。
- **第三层 · 避坑实证 (Importance 0.85, Learning)**：来自实战的血泪教训（防无脑重试、防假绿灯计数器、多维表格批量覆盖坑）。
- **第四层 · 沉淀纪要 (Importance 0.7, Context)**：真实团队交互与大数据的归纳画像（核心用户偏好、高频诉求分布、宏观舆情模型），**坚决过滤低价值流水碎语**。

### 3. 领域本体与实体网络化 (Ontology & Entities)
- 记忆不仅是扁平的“文本切片”，必须通过定义**对象类型（Object Types）**与**语义关系（Link Types）**建立知识图谱。
- 让 Agent 能够顺着关系链进行多跳因果联想（例如：`Editor` 隶属于 `MediaChannel`，该渠道关联特定 `Brand` 的竞品 `Competitor`）。

### 4. 运行时双向闭环与防御性工程 (Defensive Integration)
- **开机即唤醒**：通过环境变量固化，每次对话第一秒自动加载 Agent 身份与今日 Working Memory。
- **读侧轻量 Recall**：在对话主干中挂载异步语义检索，**配置严格超时控制（≤3秒）与 try...except 优雅降级**，API 或服务异常时静默回退，绝不阻塞用户交互。
- **写侧持续蒸馏**：通过自动化脚本监听真源变更，增量提取高价值事实。

---

## 二、 记忆分层标准与属性映射表

| 记忆层级 | 对应常见源文件 | Importance 权重 | Unit Type (合规枚举) | 常用标签 (Labels) | 核心价值与典型示例 |
| :--- | :--- | :---: | :--- | :--- | :--- |
| **第一层 · 核心准则** | `CLAUDE.md`, ADR 架构决议 | **1.0** (最高) | `decision` | `identity, persona, redline, boundary` | 决定 Agent “我是谁、先保什么、绝对不做什么”。如：`事实 > 信誉 > 叙事 > 安全 > 流量`、八条操作红线。 |
| **第二层 · 业务口径** | 业务确认文档、`decision_registry.md` | **0.9** | `fact` | `caliber, sop, decision, [业务关键词]` | 业务统计唯一的口径源，如时间窗口定义、免责范围、平台口播盲区。 |
| **第三层 · 避坑实证** | `坑位库.md`, `.learnings/*.md` | **0.85** | `learning` | `pitfall, harden, [平台关键词]` | 生产级教训，如飞书多维表格单选静默丢弃、禁止原样重试、本地计数器防假绿灯。 |
| **第四层 · 沉淀纪要** | 历史交互表（DuckDB/MySQL）、大数据 | **0.7 ~ 0.85** | `context` 或 `learning` | `history, analytics, narrative_model` | 经聚类归纳的真实用户画像、宏观叙事传播模型，禁止存入无意义流水对话。 |

> ⚠️ **合规枚举警示**：`unit_type` 必须严格取自 `nmem` 底层支持的 8 个合法枚举之一：  
> `fact` / `preference` / `decision` / `plan` / `procedure` / `learning` / `context` / `event`。  
> （如传入 `rule` 会报错，应映射为 `decision`；传入 `insight` 会报错，应映射为 `learning` 或 `fact`）。

---

## 三、 标准落地实施六步法（可直接照搬）

### 第 1 步：创建专属空间与身份绑定（Space & Agent Identity）

```bash
# 1.1 创建严格隔离空间
nmem spaces create "<项目显示名> Space" \
  --id <项目Slug，如 pr-agent / voc-agent / si-agent> \
  --description "<项目定位描述>" \
  --retrieval-mode strict

# 1.2 注册专属 AI 身份
nmem agents enroll <agent_id，如 vicky / emily / roy> \
  --name "<Agent显示名>" \
  --role "<角色名，如 pr_guardian / voc_analyst>" \
  --default-space <项目Slug> \
  --description "<角色定位描述>" \
  --tags "<标签1>,<标签2>"
```

### 第 2 步：注入空间常驻守门规则（Space Rules）

Space Rules 是 Context Bundle 中**随每次对话启动必定、无损注入**的硬规则：

```bash
# 2.1 注入人设与决策金字塔规则（Priority: 100）
nmem rules upsert <agent_id>_core_persona \
  --title "<Agent名> 人格内核与决策优先级" \
  --body "沟通人设：...；人格内核：...；决策优先级绝对遵从：事实 > 信誉 > 叙事 > 安全 > 流量；核心操作红线：..." \
  --scope space \
  --space <项目Slug> \
  --priority 100 \
  --tags "persona,rules,governance"

# 2.2 注入项目物理边界与数据读写纪律（Priority: 90）
nmem rules upsert <agent_id>_repo_boundary \
  --title "<项目名> 仓库物理边界与数据零读写纪律" \
  --body "仓库边界：本仓独立承载...；禁止跨项目 import 与写入；数据库为自有独占..." \
  --scope space \
  --space <项目Slug> \
  --priority 90 \
  --tags "boundary,infra"
```

### 第 3 步：初始化每日工作记忆（Working Memory）与资料库（Library）

#### 3.1 注入 Working Memory
Working Memory 是动态交互焦点，必须包含 `## Focus Areas` 和 `## Briefing` 两大标准段落：

```bash
nmem working-memory edit --space <项目Slug> -m "## Focus Areas
- **当前工程分支**：<Git当前分支>，正在推进的核心重构或业务特性。
- **重点关注任务**：任务1、任务2、任务3。
- **日常基线维护**：巡检健康度、数据对齐状态。

## Briefing
- **项目角色**：<Agent身份及守门职责>。
- **核心准则**：决策底线与红线。
- **近期动态**：最新业务发布或看板同步状态。"
```

#### 3.2 权威真源文档归档进 Library（避坑红线！）
> ⚠️ **致命避坑提示（MIME 解析陷阱）**：  
> `nmem-server` 当前版本的文档解析器存在 MIME 类型判定缺陷：若直接传入扩展名为 `.md` 的文件，服务器会识别为 `application/octet-stream` 二进制流，并报错：  
> `Nowledge Mem recorded 'xxx.md', but this file did not look like readable text and no parser is available for its format yet.`  
> **标准化解法**：在调用 `nmem library add` 时，将文件复制为 `.markdown` 或 `.txt` 后缀传入，解析器即可百分之百识别为 `text/markdown` 并完成切片索引（State: `indexed`）！

```bash
# 示例：以 .markdown 格式归档真源
python3 -c "
import subprocess, shutil
from pathlib import Path
files = [
    ('decision_registry.markdown', 'kb/pr/knowledge-system/decision_registry.md', ['decision'], '业务口径唯一真源'),
    ('坑位库.markdown', 'skills/Vicky项目总控/references/坑位库.md', ['pitfall'], '实证避坑库'),
]
for name, src, labels, comment in files:
    tmp = Path('/tmp') / name
    shutil.copy(src, tmp)
    cmd = ['nmem', 'library', 'add', '--space', '<项目Slug>', '-c', comment]
    for l in labels: cmd.extend(['-l', l])
    cmd.append(str(tmp))
    subprocess.run(cmd, check=True)
    tmp.unlink()
"
```

### 第 4 步：编写并执行四层记忆批量蒸馏脚本

在项目 `tools/dev/` 目录下建立模板脚本 `distill_memories_to_nmem.py`（完整模版见附录 A），直接运行完成入库：

```bash
python3 tools/dev/distill_memories_to_nmem.py
```

### 第 5 步：构建领域知识图谱本体（Ontology Patch）

在项目 `artifacts/<agent>_ontology_patch.json` 中定义该领域的对象类型（Object Types）与关系类型（Link Types），并应用到图谱：

```json
{
  "objectTypes": [
    { "key": "Brand", "displayName": "品牌", "description": "母婴及消费品品牌实体" },
    { "key": "Competitor", "displayName": "竞品", "description": "出海竞品品牌" },
    { "key": "MediaChannel", "displayName": "传播媒体/渠道", "description": "公关传播渠道与社媒平台" },
    { "key": "KeyPerson", "displayName": "核心成员/联系人", "description": "团队核心接口人、达人、媒体主编" }
  ],
  "linkTypes": [
    { "key": "MONITORS", "displayName": "监控" },
    { "key": "COMPETES_WITH", "displayName": "竞争" },
    { "key": "COLLABORATES_WITH", "displayName": "合作" }
  ]
}
```

应用本体：
```bash
nmem ontology apply --file artifacts/<agent>_ontology_patch.json
nmem ontology show
```

### 第 6 步：环境永久固化与代码运行时双向打通

#### 6.1 环境变量固化（免切换，开机自启）
在项目的 `.claude/settings.local.json`（已加入 `.gitignore`）中注入环境变量：
```json
{
  "env": {
    "NMEM_SPACE": "<项目Slug>",
    "NMEM_AGENT_ID": "<agent_id>"
  }
}
```

#### 6.2 运行时 Recall 插件实现（轻量、低延迟、优雅降级）
在 Agent 的上下文构建模块（如 `vicky_context.py`）中增加读取逻辑：
```python
def recall_durable_memories(query: str, limit: int = 2, min_score: float = 0.5,
                            space: str = "<项目Slug>") -> str:
    """从 Nowledge Mem 检索与当前用户问题强相关的持久决策、业务口径与避坑经验。

    失败、离线或无匹配时静默返回空串（优雅降级，绝对不阻塞问答主链路）。
    """
    if not query or not query.strip():
        return ""
    try:
        import json, os, subprocess
        cli = os.environ.get("NMEM_CLI_PATH", "nmem")
        target_space = os.environ.get("NMEM_SPACE", space)
        cmd = [cli, "--json", "memories", "search", query.strip()[:100],
               "--space", target_space, "-n", str(limit)]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        if res.returncode != 0:
            return ""
        data = json.loads(res.stdout)
        items = data if isinstance(data, list) else data.get("items", data.get("memories", []))
        blocks = []
        for m in items:
            score = float(m.get("score") or 0.0)
            if score < min_score:
                continue
            title = m.get("title", "").strip()
            content = (m.get("content") or m.get("snippet") or "").strip()
            if title and content:
                blocks.append(f"• 【{title}】(匹配度 {score:.2f})\n{content}")
        if not blocks:
            return ""
        return "【Nowledge Mem 专属记忆检索（核心口径/红线/避坑经验）】\n" + "\n\n".join(blocks)
    except Exception:
        return ""
```

---

## 四、 桌面端（Nowledge Mem.app）图谱可视化查验指南

很多同学在初次使用桌面端时容易找不到知识图谱，请按以下指引查验：
1. **开启专业模式**：在 App 界面左侧边栏的最底部，打开 **「专业模式 (Pro Mode)」** 开关，侧边栏将完整展开 9 大菜单。
2. **快捷键直达**：在 App 窗口激活状态下，直接按下 **`⌘ + 5`**（Windows 下为 `Ctrl + 5`），即可一键切换至 WebGL 全景知识图谱。
3. **切换专属空间**：点击左上角空间切换器，选择你的专属 Space（如 `PR Agent Space`），即可看到由数十乃至数百个实体节点相互联结而成的知识星空网络。

---

## 五、 全流程复盘与经验总结 (Lessons Learned)

在本次 `pr-agent` 的完整落地战役中，我们经历并攻克了以下关键问题，特此沉淀为标准经验：

### 1. 规避全量灌入，坚持“实体聚合与高频打标”
- **教训**：飞书多维表格有 523 条编辑记录，如果粗暴地按单行逐条插入 Mem，不仅会产生 500 多条低质碎片，而且会稀释搜索相关度。
- **最佳解法**：采用“按机构聚合 + 业务核心字段打标”策略，聚合为 207 家核心决策媒体人脉画像，打上 `tier_s`、`priority_p0`、`traffic_tier1` 标签，单条记忆置信度直接飙升至 **0.99**。

### 2. 攻克底层文件解析器的 MIME 陷阱
- **教训**：`nmem-server` 对标准 `.md` 文件误判为二进制流拒绝解析。
- **最佳解法**：在 SOP 中确立硬性规范——所有送入 Library 的 Markdown 文档统一在传输时转为 `.markdown`，实现 100% 成功解析切片。

### 3. 严格遵循 `unit_type` 标准枚举
- **教训**：随意使用自定义字符串（如 `rule`, `insight`, `guide`）会导致 CLI 报错退出。
- **最佳解法**：严格规范映射（规则类映射为 `decision`，洞察经验映射为 `learning`，实操指引映射为 `procedure`）。

### 4. 读侧集成的“生命线原则”
- **教训**：如果在主问答链路中强依赖外部记忆检索，一旦 Mem 服务离线或卡顿，会直接导致整个对话挂起或白屏。
- **最佳解法**：加装 3 秒超时限制与全捕获 try...except 兜底。记忆是“如虎添翼”，绝不成为单点故障阻碍主链路。

---

## 六、 验收基线 Checklist

每个项目执行完毕后，对照以下 8 条硬标准逐一核验打卡：

- [ ] **Space 校验**：`nmem spaces list` 显式列出该 Space，Mode 为 `strict`。
- [ ] **Identity 校验**：`nmem agents list` 存在该 Agent，默认 Space 正确。
- [ ] **Context Bundle 校验**：`nmem context --space <项目Slug>` 完整输出 Space、Rules、Working Memory。
- [ ] **Library 切片校验**：`nmem library list --space <项目Slug>` 状态全为 `indexed`，错误数为 0。
- [ ] **实体图谱化校验**：按 `⌘5` 能够呈现立体的实体与关系网络。
- [ ] **语义检索高置信度**：执行 `nmem memories search "<关键词>" --space <项目Slug>`，Top 1 匹配度通常需 ≥ 0.70。
- [ ] **单元测试通过**：编写对应的 `test_<agent>_nmem_recall.py`，包含真实检索与超时降级测试，全绿通过。
- [ ] **规范化 Git Commit**：遵循约定式提交（`feat`/`docs`）归档所有代码与台账。

---

## 七、 附录：通用蒸馏脚本模板代码

可直接将本仓库 `tools/dev/distill_memories_to_nmem.py` 复制到目标 Agent 项目，只需修改开头的配置常量与 `MEMORIES` 列表中的领域知识，即可一键批量落地：

```python
# tools/dev/distill_memories_to_nmem.py 核心结构示例
SPACE = "your-agent-space"
AGENT = "your-agent-id"

MEMORIES = [
    # 第一层 (Importance 1.0, unit_type: decision)
    {"title": "人设与核心底线", "importance": 1.0, "unit_type": "decision", "when": "timeless", "labels": "identity", "content": "..."},
    # 第二层 (Importance 0.9, unit_type: fact)
    {"title": "核心业务口径", "importance": 0.9, "unit_type": "fact", "when": "timeless", "labels": "caliber", "content": "..."},
    # 第三层 (Importance 0.85, unit_type: learning)
    {"title": "工程避坑教训", "importance": 0.85, "unit_type": "learning", "when": "timeless", "labels": "pitfall", "content": "..."},
    # 第四层 (Importance 0.7, unit_type: context)
    {"title": "业务画像与偏好", "importance": 0.7, "unit_type": "context", "when": "past", "labels": "history", "content": "..."},
]
```


---

## 八、本仓库修正（Source 项目执行裁决，2026-10-31 批准）

以下六条来自 `docs/plans/nmem-memory-knowledge-graph.md` §3，执行时覆盖正文对应条款：

1. **L1 红线双写**（修正第 1、4 步）：实测 context bundle 只注入 rule_stack 与 working_memory，不注入 memories。核心准则必须同时写 Space Rules（随会话必定注入）与 memories 的 decision 副本（供语义检索），二者内容一致、规则为权威源。
2. **存量单一真源**（补充第 1 步）：default 空间已有本项目相关记忆（cf515aec、fc8f5b4a、2047b5da 等）。新建空间时用 `memories move` 迁移有效条目、merge 后归档过时条目，禁止复制出第二份。
3. **本体必须 space scope**（修正第 5 步）：`nmem ontology apply --file` 默认 scope=global，会污染 pr-agent、si-agent 等全部共享空间。必须显式 `--scope space --space-id <id>`；且 space scope 是整体替换不是合并，patch 必须自含全部要用的 objectTypes 与 linkTypes。
4. **本体 key 规范**（修正第 5 步）：统一 UPPER_SNAKE + 领域前缀，以方案 §5 定稿表（26 objectTypes + 27 linkTypes）为准；禁用裸 Task/Report/Platform/Provider/Dataset/Claim/Gate/Source 等通用词。
5. **数字口径纪律**（修正第 4 步）：所有数字带「口径日期 + digest + 计数类型」；冲突值不合并，写「代码 X / 契约 Y，待同步」或标注实测快照。
6. **图谱分两期**（修正验收第 5 条）：本机 extraction.active=false，只 apply 本体不产生实体。P1 交付本体词汇表与记忆检索验收；图谱节点验收须在显式 seed（KG-07）之后。

另有 nmem 0.10.111 CLI 实测差异七条（详见方案 §7 R1），写路径命令以 `tmp/nmem-plan/smoke-report.md` 实测为准，不照抄本文示例。
