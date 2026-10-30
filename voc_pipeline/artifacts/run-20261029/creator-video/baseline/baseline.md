> 基线仅含 10 条锚点确证目标商品的视频。其余 31 条为品类参照（修正前口径 38 条，其中 7 条已降级为 low），不参与任何结论。

# Creator/Video 互动基线：仅 target_exact

- 商品：Momcozy Pregnancy Belly Band YB001, CozySupport Ergonest Maternity Belly Band（product_id 1729474995478630680）
- 市场：TikTok Shop 美国站
- 基线样本：10 条 target_exact 视频；medium 不进入基线。
- 数据快照：2026-10-30；本轮付费调用 0 次，花费 0 美元

## 1. 基线口径

基线只含锚点确证目标商品的视频。判定条件如下：

- `relation_type=target_exact`；`confidence=high`；`anchor_product_ids` 含 `1729474995478630680`。
- 来源：`relations/video-product-target-baseline.jsonl`。指标来源：`relations/video-product-candidates.jsonl` 的 `engagement`。
- 详情快照优先。10 条 exact 全部有 `fetch_post_detail` 快照。
- medium 品类参照 31 条单列。它们不进入基线，不参与结论。
- 分层规则：层内 n<8 时只报计数。不报中位数，不报 CI，不报结论。

## 2. 整体分布（n=10）

四分位方法：Python `statistics.quantiles(method='exclusive')`，等价于 PERCENTILE.EXC。

| 指标 | Q1 | 中位数 | Q3 | 均值 | 最小 | 最大 | 均值/中位数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 播放 | 25,300 | 172,650 | 389,675 | 305,493 | 1,025 | 1,500,000 | 1.769 |
| 点赞 | 532.5 | 1,452 | 2,163 | 2,315 | 16 | 12,400 | 1.594 |
| 评论 | 3.75 | 22 | 53 | 48.1 | 2 | 243 | 2.186 |
| 分享 | 47.5 | 134 | 305.5 | 316.3 | 0 | 1,833 | 2.36 |
| 收藏 | 47.2 | 272.5 | 369 | 439.6 | 1 | 2,467 | 1.613 |
| 互动率 | 0.63% | 1.19% | 2.63% | 1.73% | 0.46% | 4.80% | 1.453 |
| 时长（秒） | 24.8 | 32 | 40.8 | 34.2 | 11 | 68 | 1.069 |

互动率的定义沿用上游：(点赞 + 评论 + 分享 + 收藏) / 播放。

## 3. 逐条明细（10 条 exact）

| # | video_id | 播放 | 点赞 | 评论 | 分享 | 收藏 | 互动率 | 时长（秒） | 时长档 |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 7596080221900639543 | 317,200 | 1,930 | 9 | 65 | 513 | 0.79% | 11 | <=15s |
| 2 | 7613588163990129950 | 1,500,000 | 12,400 | 116 | 1,833 | 2,467 | 1.12% | 34 | 31-60s |
| 3 | 7624603263974788382 | 208,100 | 2,209 | 28 | 113 | 283 | 1.27% | 39 | 31-60s |
| 4 | 7630157203525225742 | 607,100 | 2,148 | 243 | 245 | 167 | 0.46% | 30 | 16-30s |
| 5 | 7669995620307881230 | 143,300 | 1,382 | 32 | 155 | 262 | 1.28% | 39 | 31-60s |
| 6 | 7691166964626066701 | 38,000 | 1,522 | 21 | 63 | 61 | 4.39% | 68 | >60s |
| 7 | 7692109722316475661 | 202,000 | 816 | 23 | 201 | 315 | 0.67% | 46 | 31-60s |
| 8 | 7695942452426968333 | 31,500 | 702 | 2 | 487 | 321 | 4.80% | 28 | 16-30s |
| 9 | 7700940453163699486 | 6,701 | 24 | 4 | 0 | 6 | 0.51% | 21 | 16-30s |
| 10 | 7702214491013942559 | 1,025 | 16 | 3 | 1 | 1 | 2.05% | 26 | 16-30s |

## 4. 分层计数（没有可用的分层）

下表只报计数。没有一层同时满足层 n>=8 和对照 n>=8，因此不计算分层中位数、倍数、bootstrap 或显著性检验。

| 维度 | 层 | n | 对照 n | 层 n>=8 | 状态 |
| --- | --- | ---: | ---: | --- | --- |
| 时长档 | <=15s | 1 | 9 | 否 | insufficient_sample |
| 时长档 | 16-30s | 4 | 6 | 否 | insufficient_sample |
| 时长档 | 31-60s | 4 | 6 | 否 | insufficient_sample |
| 时长档 | >60s | 1 | 9 | 否 | insufficient_sample |
| 是否对比测评 | true | 0 | 0 | 否 | insufficient_sample |
| 是否对比测评 | false | 0 | 0 | 否 | insufficient_sample |
| 是否对比测评 | unknown | 10 | — | 是 | 未归类 |
| 是否演示 | true | 0 | 0 | 否 | insufficient_sample |
| 是否演示 | false | 0 | 0 | 否 | insufficient_sample |
| 是否演示 | unknown | 10 | — | 是 | 未归类 |
| 是否有购买链接 | true | 10 | 0 | 是 | insufficient_sample |
| 是否有购买链接 | false | 0 | 10 | 否 | insufficient_sample |
| 是否有购买链接 | unknown | 0 | — | 否 | 未归类 |
| 是否有广告披露 | true | 10 | 0 | 是 | insufficient_sample |
| 是否有广告披露 | false | 0 | 10 | 否 | insufficient_sample |
| 是否有广告披露 | unknown | 0 | — | 否 | 未归类 |
| 平台广告标记 | true | 9 | 1 | 是 | insufficient_sample |
| 平台广告标记 | false | 1 | 9 | 否 | insufficient_sample |
| 平台广告标记 | unknown | 0 | — | 否 | 未归类 |

has_link 和 ad_disclosure 在 10 条 exact 中只有一个取值，对照 n=0。platform_is_ad 的 false 只有 1 条，true 的对照 n=1。这些维度没有可比的对照层。

### 4.1 bootstrap

bootstrap 未运行。10 条 exact 中没有任何一层同时满足层 n>=8 和对照 n>=8。按规则，n<8 或对照 n<8 的层只给计数，不给 CI。bootstrap 只对 exact 做；本轮没有可做的 exact 分层比较。

## 5. 高表现视频（仅 10 条 exact）

定义：互动率 >= 10 条 exact 互动率中位数的 2 倍。中位数为 1.19%，门槛为 2.39%。

没有时长档达到 n>=8，因此倍数分母用 10 条 exact 的整体中位数，不用时长档中位数。

结果：2 条 exact 视频的互动率达到 10 条 exact 中位数的 2 倍。

| # | video_id | 互动率 | 倍数 | 播放 | 时长（秒） | 时长档 | 链接 | 广告披露 |
| ---: | --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| 1 | 7695942452426968333 | 4.80% | 4.023x | 31,500 | 28 | 16-30s | true | true |
| 2 | 7691166964626066701 | 4.39% | 3.677x | 38,000 | 68 | >60s | true | true |

这 2 条的播放都低于 10 条 exact 的播放中位数 172,650。互动率高不等于触达高。

提问帖 `7696910923616881951` 不在 exact 总体，也不在高表现集合。它的 `content_tag=consideration`，已排除出所有表现统计。

## 6. 品类参照（medium，not baseline eligible）

数量：31 条。relation_type：duplicate_listing_anchor 19、text_brand_and_category 12。confidence：medium 31。content_tag：consideration 1、material_candidate 1、unknown 29。

中位数口径：30 条，不含 consideration 1 条。consideration 已排除出表现统计。

| 指标 | n | 中位数 |
| --- | ---: | ---: |
| 播放 | 30 | 16,350 |
| 点赞 | 30 | 161.5 |
| 评论 | 30 | 6 |
| 分享 | 30 | 6.5 |
| 收藏 | 30 | 19 |
| 互动率 | 30 | 1.61% |
| 时长（秒） | 30 | 33.5 |

**not baseline eligible**。本节只作品类参照。不与 exact 合并，不与 exact 比较，不出「哪类跑赢」的结论。

- consideration：`7696910923616881951`，播放 551，互动率 9.44%，`low_denominator_flag=true`。已排除出表现统计。

## 7. 未归类

- low confidence：36 条。relation_type：hashtag_category_only 7、non_target_subline 7、other_brand_category_anchor 6、sibling_product_anchor 2、text_category_only 14。
- no_signal：64 条。
- 以上 100 条不进入任何统计。video_id 清单见 `baseline.json` 的 `unclassified`。

## 8. 证据缺口与注意事项

- 10 条 exact 中没有任何一层同时满足层 n>=8 和对照 n>=8。时长档为 <=15s 1 条、16-30s 4 条、31-60s 4 条、>60s 1 条；has_link 和 ad_disclosure 只有一个取值；platform_is_ad 的 false 只有 1 条。分层基线不成立。
- comparison 与 demo 在 10 条 exact 中全部 unknown。没有字幕、音轨或视频帧，无法判断画面是否对比或演示。
- 31 条 medium 只作品类参照。19 条 duplicate_listing_anchor 锚到同品牌 YB001 系列的其他 listing；product_id 不同，标题相似但不相同。12 条 text_brand_and_category 没有商品锚点。
- 关键词搜索样本不是概率样本。141 条视频中只有 10 条锚点确证目标商品，不能代表品类普查。
- 所有指标是 2026-10-30 的单次快照。播放和互动会继续增长，快照之间不可直接比较寿命周期表现。
- 第三方视频的 GMV、成交、转化、受众画像和字幕不可得；本轮不涉及达人受众或达人层级基线。
- is_estimated 字段在所有返回中不存在；产物记 null，未当作实测值。

- 中位数和四分位数描述典型视频。均值受长尾影响，表中同时给出 mean/median 比值。
- 本轮不做分层基线。任何按内容形态的比较都没有样本支撑。
- 高表现视频只做计数和倍数描述，不做因果解释。10 条 exact 里只有少量高表现，不能代表总体。
- category_reference 是品类参照，不是基线。不要把它与 exact 基线合并、比较或用于「哪类跑赢」的结论。
- 分层表之间会重叠；同一视频出现在多个维度中，不能相加。
- 本轮未写数据库，未修改 canonical-records.jsonl，未修改 gold-set-50.jsonl。

## 9. 方法与可复现

- 脚本：`/Users/lute/Project/data_scrapy/tools/creator_video_baseline.py`
- 付费端点调用：0 次；花费：0 美元；未做余额探测。上一次已知余额 37.316 美元（collect-summary.json cost.balance_after_usd）。
- 四分位方法：Python `statistics.quantiles(method='exclusive')`，等价于 PERCENTILE.EXC。
- bootstrap：未运行。10 条 exact 中没有任何一层同时满足层 n>=8 和对照 n>=8。
- 金标集与 canonical-records.jsonl 未修改。

输入文件与 SHA-256：

| 文件 | SHA-256 |
| --- | --- |
| /Users/lute/Project/data_scrapy/voc_pipeline/artifacts/run-20261029/creator-video/relations/video-product-target-baseline.jsonl | `a89ee777291c9b6babae088e30afb1a8c1c155041b82474907eef9d0c9baf9de` |
| /Users/lute/Project/data_scrapy/voc_pipeline/artifacts/run-20261029/creator-video/features/video-features.jsonl | `c96986355fa276a09eeed11bd887ae795a39ad3c3461d3f478903e8cbcf4d060` |
| /Users/lute/Project/data_scrapy/voc_pipeline/artifacts/run-20261029/creator-video/relations/video-product-candidates.jsonl | `8c5da94832f64cb0ff44bfd3ae7aca0045e272a97773d93a62ddc39cbe1b1bd9` |
| /Users/lute/Project/data_scrapy/voc_pipeline/artifacts/run-20261029/creator-video/relations/video-product.jsonl | `9f549357152b2c5576ebd812e2a679106a9d070f1340c1fce4e03caf7099a132` |
| /Users/lute/Project/data_scrapy/voc_pipeline/artifacts/run-20261029/creator-video/relations/coverage.json | `5aa476089af0a0e80152c19ae32550439a0bd7f14cef6a4b71af80a33fc7e2eb` |
| /Users/lute/Project/data_scrapy/voc_pipeline/artifacts/run-20261029/canonical-records.jsonl | `88ee4402c4055bf113984dd849c2af3ae35c6c3f4b13be2532286f289582cfae` |
| /Users/lute/Project/data_scrapy/voc_pipeline/artifacts/run-20261029/gold-set-50.jsonl | `e1dcc693d7c832dc10f878129efc45b1018ecfb278a1e9674508a64267e5e65e` |

校验：

- 基线样本数：10
- 唯一 video_id 数：10
- 分维度层计数合计均为 10：True
- 原始计数 n>=8 的组：['has_link:true', 'ad_disclosure:true', 'platform_is_ad:true']
- 可用的层（层 n>=8 且对照 n>=8）：无
- 计算了中位数的层：无
- bootstrap 检验数：0
- 高表现视频数：2
- 提问帖在 exact 总体：False
- 提问帖在高表现集合：False
- category_reference 数量：31
- category_reference 与 exact 交集：0
- category_reference 全为 medium：True
- canonical-records.jsonl SHA-256 未变：True
- gold-set-50.jsonl SHA-256 未变：True
- 写数据库：0
