---
name: tikhub-tiktok-endpoint-probe-2026-10-19
description: 2026-10-19 TikHub 31 个 TikTok 端点的字段探测报告，列出可用状态、顶层键、关键字段、失败端点与替代路径。接 TikHub 端点或更新字段契约时先读这份。
---

# TikHub 31 个 TikTok 端点字段探测报告

> 日期：2026-10-19。
> 环境：本地 Python 3.12，TikHub API。
> 请求头：`Authorization: Bearer <key>`、`Accept: application/json`、`User-Agent: DataIntelligenceHub/1.0`。
> 样本：视频 `7534061113365859586`；达人 `bruniela_`；商品 `1731141296519615241`；话题 `newborn`。

## 1. 结论

1. 25 个端点返回可用数据。
2. 4 个端点返回 400，需要额外参数或改用替代路径。
3. 2 个端点返回 200 但受限：`fetch_product_detail_v3` 不回商品字段；`fetch_hot_selling_products_list` 不支持美国。
4. 评论字段证据成立：TikHub 评论端点返回 `reply_id`、`author_pin`、`is_author_digged`、`is_high_purchase_intent`。
5. 话题 ID 有两个命名空间：Web `challengeID` 与 App `ch_id` 不能混用。
6. 美国 Shop 发现用 `fetch_search_products_list_v2`；热卖榜只支持 ID、JP、MX、MY、PH、SG、TH、VN。

## 2. 端点矩阵

| # | 端点 | 方法 | 状态 | data 顶层键 | 关键字段与备注 |
|---|---|---|---|---|---|
| 1 | `web/get_sec_user_id` | GET | 200 | `data` 是字符串 | 直接返回 sec_uid。 |
| 2 | `web/get_user_id` | GET | 200 | `data` 是字符串 | 直接返回数字 uid。 |
| 3 | `app/v3/get_user_id_and_sec_user_id_by_username` | GET | 200 | `user_id`、`sec_user_id` | 一次拿 uid 与 sec_uid。 |
| 4 | `web/fetch_post_detail` | GET | 200 | `extra`、`itemInfo`、`shareMeta` | 单视频详情。 |
| 5 | `web/fetch_user_post` | GET | 200 | `itemList`、`cursor`、`hasMore` | 作品字段：`id`、`desc`、`createTime`、`author`、`authorStats`、`stats`、`statsV2`、`music`、`video`、`textExtra`、`isAd`。 |
| 6 | `web/fetch_general_search` | GET | 200 | `data` 是列表 | 每项 `type`、`item`、`common`；`item.id` 是视频 ID。 |
| 7 | `web/fetch_search_video` | GET | 400 | — | 需要额外参数。用 `fetch_general_search` 替代。 |
| 8 | `app/v3/fetch_one_video` | GET | 200 | `aweme_detail` | `aweme_id`、`desc`、`author`、`statistics`、`video`、`music`、`cha_list`。 |
| 9 | `web/fetch_post_comment` | GET | 200 | `comments`、`total`、`has_more` | `cid`、`reply_id`、`author_pin`、`is_author_digged`、`comment_language`、`digg_count`、`reply_comment_total`、`is_high_purchase_intent`。 |
| 10 | `web/fetch_post_comment_reply` | GET | 400 | — | 参数正确仍失败。用 `app/v3/fetch_video_comment_replies`。 |
| 11 | `app/v3/fetch_video_comments` | GET | 200 | `comments`、`total`、`has_more` | 评论字段与 #9 同构。 |
| 12 | `app/v3/fetch_video_comment_replies` | GET | 200 | `comments`、`total`、`has_more` | 回复树可用。 |
| 13 | `web/fetch_tag_detail` | GET | 200 | `challengeInfo`、`shareMeta` | `challengeInfo.challenge.id` 是 Web challengeID；`statsV2` 有视频数与播放量。 |
| 14 | `web/fetch_tag_post` | GET | 200 | `itemList`、`cursor`、`hasMore` | 只认 Web `challengeID`。 |
| 15 | `web/fetch_trending_searchwords` | GET | 200 | `trending_search_words` | 每项 `trendingSearchWord`、`trendingSearchWordType`。 |
| 16 | `app/v3/fetch_hashtag_detail` | GET | 200 | `ch_info`、`dynamic_list`、`rec_list` | `ch_info` 有 `cid`、`cha_name`、`use_count`、`user_count`、`view_count`。只认 App `ch_id`。 |
| 17 | `web/fetch_user_profile` | GET | 200 | `userInfo` | `user` 有 `id`、`uniqueId`、`secUid`、`signature`、`verified`、`ttSeller`；`stats` 有粉丝、关注、获赞、作品数。 |
| 18 | `web/fetch_user_fans` | GET | 200 | `userList`、`total`、`hasMore` | 每项 `user`、`stats`、`statsV2`。 |
| 19 | `web/fetch_user_follow` | GET | 400 | — | 参数正确仍失败。用 App 关注列表或 Apify。 |
| 20 | `web/fetch_search_user` | GET | 400 | — | 参数正确仍失败。用 Apify 用户搜索。 |
| 21 | `app/v3/fetch_music_detail` | GET | 200 | `music_info` | `id`、`title`、`author`、`duration`、`play_url`、`is_commercial`、`is_original`。 |
| 22 | `app/v3/fetch_music_video_list` | GET | 200 | `aweme_list` | 音乐下视频列表。 |
| 23 | `app/v3/fetch_music_chart_list` | GET | 200 | `music_list`、`chart_info` | 每项 `id`、`music_info`、`trend`。 |
| 24 | `shop/web/fetch_hot_selling_products_list` | GET | 200 | `data.productList`、`hasMore` | 支持地区：ID、JP、MX、MY、PH、SG、TH、VN。US 不支持。 |
| 25 | `shop/web/fetch_search_products_list_v2` | GET | 200 | `data.data.component_data.products` | `product_id`、`title`、`product_price_info`、`rate_info`、`sold_info`、`seller_info`、`seo_url`、`brand_info`、`sku_info`。 |
| 26 | `shop/web/fetch_product_detail_v3` | GET | 200 | `product_data.ab_test`、`product_data.page_config` | 只回页面配置，不回商品字段。不要当详情源。 |
| 27 | `shop/web/fetch_product_reviews_v2` | GET | 200 | `data.product_reviews`、`review_ratings` | `review_id`、`product_id`、`sku_id`、`review_rating`、`review_time`、`is_verified_purchase`、`is_incentivized_review`、`review_text`、`review_images`、`sku_specification`、`review_country`。 |
| 28 | `shop/web/fetch_search_word_suggestion_v2` | GET | 200 | `data` 是字符串列表 | 搜索词建议。 |
| 29 | `analytics/detect_fake_views` | GET | 200 | `video_metrics`、`creator_metrics`、`content_metrics`、`fake_view_analysis`、`traffic_pool`、`suspicious_features`、`detailed_analysis`、`view_pattern_type`、`mcn_report`、`recommendations` | 假流量检测。 |
| 30 | `analytics/fetch_comment_keywords` | GET | 200 | `item_id`、`key_words.comment_key_words` | 每项 `key_word`、`comments`。 |
| 31 | `ads/get_trends_hashtag_list` | POST | 200 | `items`、`pagination`、`BaseResp` | `hashtagID`、`hashtagName`、`publishCnt`、`rankIndex`、`topCreators`、`vv`、`popularityCurve`。 |

## 3. 失败与替代

| 端点 | 现象 | 替代 |
|---|---|---|
| `web/fetch_search_video` | 400，参数正确 | `web/fetch_general_search`。 |
| `web/fetch_post_comment_reply` | 400，评论有回复 | `app/v3/fetch_video_comment_replies`。 |
| `web/fetch_user_follow` | 400，sec_uid 正确 | App 关注列表或 Apify。 |
| `web/fetch_search_user` | 400，keyword 正确 | Apify 用户搜索。 |
| `shop/web/fetch_product_detail_v3` | 200，但只有页面配置 | `pratikdani/tiktok-shop-scraper` 或商品搜索列表。 |
| `shop/web/fetch_hot_selling_products_list` | US 不支持 | 美国用 `fetch_search_products_list_v2`。 |

## 4. 关键字段证据

### 4.1 评论

`web/fetch_post_comment` 首条评论实测字段：

1. `cid`。
2. `reply_id`。顶层为 `"0"`。
3. `reply_to_reply_id`。
4. `author_pin`。
5. `is_author_digged`。
6. `is_high_purchase_intent`。
7. `comment_language`。
8. `digg_count`。
9. `reply_comment_total`。
10. `create_time`。

结论：飞书文档里的 `parent_comment_id`、`is_pinned`、`creator_interacted` 可以由 TikHub 评论端点落地。`clockworks/tiktok-comments-scraper` 不能。

### 4.2 达人作品

`web/fetch_user_post` 的 `itemList` 每项有：

`id`、`desc`、`createTime`、`author`、`authorStats`、`authorStatsV2`、`stats`、`statsV2`、`music`、`video`、`textExtra`、`isAd`、`effectStickers`。

### 4.3 话题

1. Web `fetch_tag_detail` 的 `challengeInfo.challenge.id` 是 Web challengeID，例如 `newborn` 为 `40393`。
2. App `fetch_hashtag_detail` 的 `ch_info.cid` 是 App `ch_id`，例如视频里的 `comeramabanana` 为 `7513253515507007493`。
3. 两个 ID 不能混用。`fetch_tag_post` 只认 Web challengeID；`fetch_hashtag_detail` 只认 App ch_id。

### 4.4 Shop

`fetch_search_products_list_v2` 的 `component_data.products` 每项有：

`product_id`、`title`、`image`、`product_price_info`、`rate_info`、`sold_info`、`seller_info`、`seo_url`、`product_marketing_info`、`brand_info`、`sku_info`。

`fetch_product_reviews_v2` 的 `product_reviews` 每项有：

`review_id`、`product_id`、`sku_id`、`reviewer_id`、`review_rating`、`review_time`、`is_verified_purchase`、`is_incentivized_review`、`product_name`、`reviewer_name`、`reviewer_avatar_url`、`review_text`、`display_image_url`、`review_images`、`sku_specification`、`review_country`。

### 4.5 分析

`detect_fake_views` 返回：

`video_metrics`、`creator_metrics`、`content_metrics`、`fake_view_analysis`、`traffic_pool`、`suspicious_features`、`detailed_analysis`、`view_pattern_type`、`mcn_report`、`recommendations`。

`fetch_comment_keywords` 返回：

`key_words.comment_key_words[].key_word` 与 `comments`。

### 4.6 趋势

`ads/get_trends_hashtag_list` 的 `items` 每项有：

`hashtagID`、`hashtagName`、`industryIDs`、`popularityCurve`、`publishCnt`、`rankIndex`、`topCreators`、`vv`。

## 5. 对 R1 的影响

1. **评论模块**：主链改为 TikHub `app/v3/fetch_video_comments` + `fetch_video_comment_replies`；`clockworks` 只做量大补充。
2. **Shop 详情**：主链保留 `pratikdani/tiktok-shop-scraper`；TikHub `fetch_product_detail_v3` 不作为详情源。
3. **Shop 发现**：美国用 `fetch_search_products_list_v2`；热卖榜只用于东南亚市场。
4. **身份解析**：`get_sec_user_id`、`get_user_id`、`get_user_id_and_sec_user_id_by_username` 可用，优先使用。
5. **达人作品**：`fetch_user_post` 可用，字段完整。
6. **粉丝**：`fetch_user_fans` 可用；`fetch_user_follow` 不可用。
7. **话题**：Web 与 App ID 分离，采集器必须显式区分。
8. **假流量与评论关键词**：可直接接入达人风控与 VOC。

## 6. 复现与成本

1. 探测调用 41 次，其中 10 次返回 400，2 次区域不支持。
2. 按 TikHub 按次计费，成本约几美分。
3. 没有保存原始响应到仓库。原始响应在本地临时目录。
4. 请求头必须带 `User-Agent` 与 `Accept`。缺这两个头会返回 403。
5. 400 请求不扣费；200 请求按次计费。
