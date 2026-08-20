# Apify Skill 集成分析报告

## 1. 现有架构发现

### Apify 在当前系统中的使用情况
- **collectors.py** 已集成 75 个 Apify actors
- **endpoint_type="apify_*"** 命名模式
- 通过 `_create_apify_endpoint` 统一创建端点
- 依赖 `ApifyCollector` 基础类

### 官方 Apify Agent Skills 结构
- **5 个独立 skills**：
  1. apify-ultimate-scraper (数据抓取)
  2. apify-actor-development (Actor 开发)
  3. apify-actorization (项目迁移)
  4. apify-generate-output-schema (Schema 生成)
  5. apify-sdk-integration (SDK 集成)

- **覆盖 14 大平台类别**：
  - Instagram (13 actors)
  - Facebook (16 actors)
  - TikTok (13 actors)
  - YouTube (7 actors)
  - X/Twitter (5 actors)
  - LinkedIn (20+ actors)
  - Google Maps (7 actors)
  - Google Search/Trends (3 actors)
  - Reviews (8 actors)
  - Real Estate (9 actors)
  - SEO Tools (6 actors)
  - Content Crawling (8 actors)
  - Other Platforms (7 actors)
  - Enrichment (5 actors)

## 2. 集成策略设计

### 方案 A：分平台多 Collector 模式（推荐）
**优势**：
- ✅ 结构清晰，每个平台独立维护
- ✅ 符合现有 SpiderFoot/BestBlogs/Blackbird 模式
- ✅ catalog 分组自然对应平台
- ✅ 利于增量迁移和测试

**实施**：
```python
# collectors/apify/instagram_collector.py
class ApifyInstagramCollector(BaseCollector):
    """Instagram 数据采集（13 actors）"""
    
# collectors/apify/facebook_collector.py  
class ApifyFacebookCollector(BaseCollector):
    """Facebook 数据采集（16 actors）"""
    
# collectors/apify/linkedin_collector.py
class ApifyLinkedInCollector(BaseCollector):
    """LinkedIn OSINT（20+ actors）"""
```

## 3. 推荐实施路径

### Phase 1：高优先级平台（P0）
1. **LinkedIn** (20+ actors) - 职业背景、公司情报、人脉网络
2. **Instagram** (13 actors) - 社交足迹、兴趣画像
3. **Google Maps** (7 actors) - 地理位置、商业信息

### Phase 2：通用工具（P1）
4. **SEO Tools** (6 actors) - 网站情报
5. **Content Crawling** (8 actors) - 网页抓取、RAG 数据源
6. **Enrichment** (5 actors) - 邮箱挖掘、联系人扩充

## 4. 与现有 75 个 Apify endpoints 的关系

### 迁移策略
1. **保持向后兼容**：现有 75 个端点继续工作
2. **渐进式重构**：新增分平台 collectors，逐步迁移端点
3. **双轨运行期**：旧端点标记 deprecated
4. **最终收敛**：完成迁移后移除旧端点

## 5. 下一步行动

### 立即可做
1. 创建 `collectors/apify/` 目录结构
2. 实现 `ApifyLinkedInCollector` MVP
3. 测试单个 actor 调用链路

### 本周完成
4. 实现 Instagram + Google Maps collectors
5. 完善错误处理和认证流程
6. 更新 catalog 分组展示
