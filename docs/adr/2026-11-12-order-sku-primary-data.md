# ADR · order_id / sku_id 主键与 468 品类漂移处理

- 状态:已接受(2026-11-12,Plan C D7 交付;**落库执行在 12 月批次**)
- 关联:Plan C §4(pmo 行 33 延期项)、PMO Cap#82、NB-2026-11-15
- 裁决人:架构槽位;签字:用户已确认(2026-11-06)

## 1 背景

PMO Cap#82 要求「11-15 前完成 order_id/sku_id 主键(含 468 品类漂移修正)」,
支撑 6 大 Agent 同源取数。11-05 差距分析实测:order_id 在 ABI 内 0 实现、
sku_id 存在但非主键(product_review 的主键是 review_id)、468 品类漂移
0 定义、product_catalog 仅 222 品类。Plan C 把「落库」延期到 12-15,
本冲刺只交付 ADR(设计决策)。

## 2 现状与约束

- ABI 三个 schema(meta/raw/abi)已 48 表定稿(见 abi-schema-manifest.md),
  生产 42 实体表在线。加主数据表 = 新增迁移,动 schema 冻结面。
- sku_id 已有事实:`product_review.sku_id`(可空,非主键)、
  `tikhub_social.py` 与 `tiktok_content_ingestion.py` 的归一化字段。
  即 sku_id 是**采集层事实**,不是主数据。
- 「468 品类漂移」在仓库内 0 定义;product_catalog 222 品类、3,036 行
  空品类——468 的出处是业务侧(Shopify/BrandOS),不在本仓库。
- 6 大 Agent 同源取数的契约是 RawRecord→EntitySnapshot→DatasetVersion→
  DatasetDriftEvent(PMO 交接协议),ABI 当前不读写这四类契约表。

## 3 决策

### D1 · order_id/sku_id 做「主数据映射层」,不做「主键重造」

- **不动既有事实表的主键。** product_review 的主键仍是 review_id;
  把 sku_id 提成主键会破坏 review_id 粒度(一条 review 一个 sku 视角,
  但同一 review 可跨 sku 变体)。
- 新增 `meta.product_order_map`(order_id ↔ platform ↔ sku_id ↔
  product_id 的映射表,业务键唯一约束),由 ETL 从订单源(Shopify 导出/
  BrandOS)填充。ABI 的角色是**映射与对账**,不是订单系统。
- 好处:schema 冻结面只增不改;回填可重跑(幂等 upsert);漂移可观测
  (map 行数 vs 订单源行数 = DatasetDriftEvent 的天然信号)。

### D2 · sku_id 的规范化规则(采集层,立即生效)

- 归一化:去空白、大小写保留原样(业务键比对时 lower)、变体后缀
  (如 `-US-L`)保留并在 map 表单列 `variant` 字段。
- 空值语义:sku_id 为空 = 未变体(父商品),不是未知——用 `variant`
  区分,不引入第三态。

### D3 · 468 品类漂移:对账驱动,不做批量自动改写

- 468 清单由业务 owner(Shopify/BrandOS 侧)导出为 CSV,ABI 侧建
  `meta.category_drift_log`(old_category → new_category → source →
  decided_by),**只记录裁决,不自动改写 product_catalog**。
- 理由:品类漂移的语义是业务裁决,ETL 自动改写会把错误固化到全链路
  (Echo 的 VOC 分类、Market 的 TAM 都按品类聚合)。改写必须是显式的、
  可审计的、按批次执行的动作。
- 对账节奏:每周(与 Apify 例行同步同窗口),漂移行 > 阈值(默认 5%)
  触发 DatasetDriftEvent,进 DriftEvent → 通知 → 人工批次改写。

### D4 · 6 Agent 同源取数:一个试点,不做大爆炸

- 试点对象:**Echo**(它已依赖 Reddit/VOC 数据,数据血缘最短)。
- 试点范围:Echo 通过 ABI 的 saved_query + dataset 授权(已有的
  access_grant 体系)读数,**不新建服务账号**,不做实时 API——
  Agent 拿到的是 DatasetVersion 的快照引用,不是直连库。
- 全接 6 Agent 的前提:试点跑通一个完整周期(含一次 drift 事件演练)。

## 4 后果

- **12 月批次工作量(估)**:map 表迁移+ETL 4-6 人日;drift_log+对账
  3-4 人日;Echo 试点 5 人日;468 CSV 对接另计(依赖业务导出)。
- **本冲刺零落库**:48 表冻结面不变;生产取证(54 物理/42 实体)不因
  本 ADR 失真。
- **风险**:业务侧 468 清单的 owner 与格式未定——NB 里必须先钉 owner,
  否则 12-15 的「468 修正」还会滑期。
- 采集层 D2(规范化规则)可立即生效,不等迁移。

## 5 不做的事

- 不把 order_id/sku_id 加进 raw 层事实表的主键。
- 不自动改写 product_catalog 的品类。
- 不为 6 Agent 建实时查询 API(走 saved_query + 授权)。
- 不在本仓库定义 468 清单的内容(业务资产,ABI 只做映射与对账)。
