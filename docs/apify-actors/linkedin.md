# Apify 采集方案卡 — LinkedIn

日期：2026-10-14。数据来源同总说明。

## 主题矩阵

| 主题 | 覆盖 | 主力 | 降级① | 降级② |
|---|---|---|---|---|
| 个人档案（全量段） | ● | harvestapi/linkedin-profile-scraper | apimaestro/linkedin-profile-posts（帖子维度替代） | curious_coder/linkedin-profile-scraper（要 cookie，最后手段） |
| 档案搜索（按关键词/过滤条件找人） | ● | harvestapi/linkedin-profile-search | apimaestro/linkedin-company-employees-scraper-no-cookies（公司维度） | — |
| 公司员工名录 | ● | apimaestro/linkedin-company-employees-scraper-no-cookies | harvestapi/linkedin-profile-search（company 过滤） | — |
| 职位 | ● | curious_coder/linkedin-jobs-scraper | bebity/linkedin-jobs-scraper | freshdata/linkedin-job-scraper |
| 公司帖子 | ● | harvestapi/linkedin-company-posts | apimaestro/linkedin-profile-posts | — |
| 个人帖子 | ● | apimaestro/linkedin-profile-posts | harvestapi/linkedin-profile-scraper（featured 字段） | — |

**淘汰决定：curious_coder/linkedin-profile-scraper 不进任何主力位。** 输入强制要求 cookie + userAgent（schema required 四项），会话失效即整批失败，且 30 天月活仅 13 人。

## 主力 actor 详情

### harvestapi/linkedin-profile-scraper — 档案主力
- 稳定性：ok **100%**（12146 用户/30 天），免 cookie
- 计费：PAY_PER_EVENT，profile $0.004/份；带邮箱版本 profile_with_email $0.01/份（profileScraperMode 切换）
- 输入 5 项（无必填）：queries / urls / publicIdentifiers / profileIds 四入口；profileScraperMode 选带不带邮箱
- 输出 53 字段（实测）：id, publicIdentifier, linkedinUrl, firstName, lastName, headline, about, emails, websites, location, industry, openToWork, hiring, premium, influencer, creator, verified, connectionsCount, followerCount, registeredAt, currentPosition, profileTopEducation, topSkills, skills, experience, education, certifications, projects, volunteering, receivedRecommendations, publications, courses, patents, honorsAndAwards, languages, organizations, causes, featured, sectionTotals, profilePicture, coverPicture, primaryLocale, multiLocaleHeadline, services, interests, originalQuery
- 职业画像最完整：经历/教育/证书/专利/荣誉/语言 12 个段全量

### harvestapi/linkedin-profile-search — 搜索主力
- 稳定性：ok 99.6%（6499 用户）
- 输入 41 项：关键词 + 职位/公司/学校/地点/行业等全部过滤维度
- 输出 10 字段（搜索结果列表形）：档案卡摘要。深挖靠 profile-scraper 二段接力

### apimaestro/linkedin-company-employees-scraper-no-cookies — 员工名录主力
- 稳定性：ok 99.9%（1267 用户）
- 输入 3 项：company_url + limit，最简输入
- 输出 20 字段（实测）：company_url, profile_url, fullname, first_name, last_name, headline, public_identifier, location, is_creator, is_influencer, is_premium, open_to_work, is_top_voice, urn, current_company_urn
- 定位：员工花名册场景（快、便宜、字段够），个体深挖交给 profile-scraper

### curious_coder/linkedin-jobs-scraper — 职位主力
- 稳定性：ok 98.7%，**16481 用户/30 天（LinkedIn 类第一）**
- 计费：$0.00075/条 + $0.00005/run
- 输入 13 项：关键词/地点/职位级别/远程/发布时间/公司黑名单等
- 输出 25 字段：id, link, title, companyName, companyLinkedinUrl, companyLogo, location, salaryInfo, postedAt, benefits, applicantsCount, applyUrl, descriptionHtml, descriptionText, jobPosterName, jobPosterTitle, jobPosterProfileUrl

### harvestapi/linkedin-company-posts — 公司帖子主力
- 稳定性：ok **100%**（4387 用户）
- 输出 48 字段：type, id, linkedinUrl, content, author(公司卡), postedAt, timestamp, interaction 计数、media 等

### apimaestro/linkedin-profile-posts — 个人帖子
- 稳定性：ok 98.3%（2054 用户）
- 输出信封形（实测）：success, message, data → posts[]（urn, posted_at, text, url, post_type, author, stats, media, pagination_token）。解析器要剥 success/message 信封

## 降级链

1. **档案**：profile-scraper 是唯一免 cookie 全量段方案；它失败时用 employees-scraper 拿摘要，或 profile-posts 拿内容侧写。
2. **职位**：bebity（99.1%，45 字段含 companyWebsite/workType/contractType）→ freshdata（100%，但 157 用户规模小、字段浅——项目现有端点已注明"响应信封、字段较浅"）。
3. **搜索**：harvestapi 搜索失败 → apimaestro 员工名录（已知公司时等价）。

## 坑点

| 症状 | 原因 | 规避 |
|---|---|---|
| cookie 型 actor 批量 401 | 会话过期 | 已淘汰 cookie 型；存量 curious_coder/linkedin-profile-scraper 端点应标记 deprecated |
| apimaestro 帖子 0 条 | 信封 data 层没剥 | 提取器加 success/message 分支 |
| freshdata 响应信封 | 同上，字段浅 | 仅作第三降级 |
| harvestapi 邮箱版贵 2.5 倍 | profile_with_email $0.01 | 默认不带邮箱，按需切 mode |

## 与现有 catalog 对照

| 现有端点 | 本卡结论 |
|---|---|
| freshdata/linkedin-job-scraper | 降为第三降级（字段浅） |
| apimaestro/linkedin-company-employees-scraper-no-cookies | 保留，升员工名录主力 |
| — | 新增建议：harvestapi/linkedin-profile-scraper（档案全量缺口）、linkedin-jobs-scraper（职位主力）、linkedin-company-posts（公司内容缺口） |
