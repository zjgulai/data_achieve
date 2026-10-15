"""26 个采集器类型的参数契约（审计判定实现与声明一致的一组）。

这是 2026-10-15 参数审计的第三批登记。审计判定的分布是：

- 44 个声明与实现不一致 → `collector_specs.py`
- 16 个包注册类判定一致 → `package_registry_specs.py`
- 本模块：其余 26 个（判定一致或未被逐条核验）

三批合计 86 个，即全部已注册的 collector_type。

规格来源是各采集器的 `validate_config()` 实现与
`services/collector_catalog.py` 的服务层校验函数。
这一批里多数类型走服务层 passthrough，实际约束全在类级，
因此每条 `standard_path_validation_site` 都注明了这一点。

关于执行可达性：本模块的多个类型在出口策略层被拒绝
（`assert_collector_allowed` 先于类级校验执行），
所以规格描述的是实现约束，不等于该类型当前可执行。
可达性单独可查，见 `tool_catalog/reachability.py`。
本模块只登记约束，不宣称可执行。

本模块不修改采集目录，也不触发任何执行。
"""

from data_intelligence_hub.tool_catalog.parameters import (
    ParameterConflict,
    ParameterSpec,
    ToolParameterContract,
)

CONTRACTS: dict[str, ToolParameterContract] = {
    # ── aliens_eye ──
    "aliens_eye_basic": ToolParameterContract(
        tool_id="aliens_eye_basic",
        specs=(
    ParameterSpec(
        name="username",
        value_type="string",
        required=True,
        source="collector_validation",
        description=(
        "非空字符串，strip 后使用；非字符串、空串或纯空白抛 CollectorError； "
        "无长度与字符集校验。服务层 passthrough 不查， "
        "违反只在采集期拒绝（失败 TaskRun，非 400）。"
        ),
    ),
        ),
    ),
    "aliens_eye_correlate": ToolParameterContract(
        tool_id="aliens_eye_correlate",
        specs=(
    ParameterSpec(
        name="username",
        value_type="string",
        required=True,
        source="collector_validation",
        description=(
        "非空字符串，strip 后使用；非字符串、空串或纯空白抛 CollectorError； "
        "无长度与字符集校验。服务层 passthrough 不查， "
        "违反只在采集期拒绝（失败 TaskRun，非 400）。"
        ),
    ),
        ),
    ),
    "aliens_eye_domain": ToolParameterContract(
        tool_id="aliens_eye_domain",
        specs=(
    ParameterSpec(
        name="username",
        value_type="string",
        required=True,
        source="collector_validation",
        description=(
        "非空字符串，strip 后使用；非字符串、空串或纯空白抛 CollectorError； "
        "无长度与字符集校验。服务层 passthrough 不查， "
        "违反只在采集期拒绝（失败 TaskRun，非 400）。"
        ),
    ),
        ),
    ),
    "aliens_eye_selfcheck": ToolParameterContract(
        tool_id="aliens_eye_selfcheck",
        notes=(
        "无参数：类级校验返回空，采集命令固定。执行层仍会读取 run_timeout_seconds "
        "作为预算，本类型有 1200 秒的端点级默认。"
        ),
    ),
    # ── spiderfoot ──
    "spiderfoot_domain_osint": ToolParameterContract(
        tool_id="spiderfoot_domain_osint",
        specs=(
    ParameterSpec(
        name="target",
        value_type="string",
        required=True,
        source="collector_validation",
        description=(
        "必填非空字符串：isinstance(str) 检查、strip 后为空即抛 CollectorError， "
        "返回 strip 后的值使用；不做域名格式校验（`_target_type = \"domain\"` 是类属性、 "
        "非配置参数，collectors/spiderfoot_collector.py:365）。"
        ),
    ),
    ParameterSpec(
        name="modules",
        value_type="list",
        required=False,
        source="collector_validation",
        default=[
        "sfp_dnsresolve",
        "sfp_whois",
        "sfp_sslcert",
        "sfp_crt",
        "sfp_webserver",
        "sfp_webframework",
        "sfp_webanalytics",
        ],
        description=(
        "可选；仅 isinstance(list) 检查，元素零校验（错误文案称 'module name strings' "
        "但无对应实现）。非空列表整体替换默认模块表并作为 modulelist 实参； "
        "空列表或缺省回落 _FAST_DOMAIN_MODULES（:218 `modules or "
        "self._default_modules`）。"
        ),
    ),
        ),
    ),
    "spiderfoot_email_osint": ToolParameterContract(
        tool_id="spiderfoot_email_osint",
        specs=(
    ParameterSpec(
        name="target",
        value_type="string",
        required=True,
        source="collector_validation",
        description=(
        "必填非空字符串：isinstance(str) 检查、strip 后为空即抛 CollectorError， "
        "返回 strip 后的值使用；不做邮箱格式校验（`_target_type = \"email\"` 是类属性、 "
        "非配置参数，collectors/spiderfoot_collector.py:379）。"
        ),
    ),
    ParameterSpec(
        name="modules",
        value_type="list",
        required=False,
        source="collector_validation",
        default=["sfp_emailformat", "sfp_accounts"],
        description=(
        "可选；仅 isinstance(list) 检查，元素零校验（错误文案称 'module name strings' "
        "但无对应实现）。非空列表整体替换默认模块表并作为 modulelist 实参； "
        "空列表或缺省回落 _FAST_EMAIL_MODULES（:218 `modules or "
        "self._default_modules`）。"
        ),
    ),
        ),
    ),
    "spiderfoot_ip_osint": ToolParameterContract(
        tool_id="spiderfoot_ip_osint",
        specs=(
    ParameterSpec(
        name="target",
        value_type="string",
        required=True,
        source="collector_validation",
        description=(
        "必填非空字符串：isinstance(str) 检查、strip 后为空即抛 CollectorError， "
        "返回 strip 后的值使用；不做 IP 格式校验（`_target_type = \"ip\"` 是类属性、 "
        "非配置参数，collectors/spiderfoot_collector.py:372）。"
        ),
    ),
    ParameterSpec(
        name="modules",
        value_type="list",
        required=False,
        source="collector_validation",
        default=["sfp_dnsresolve", "sfp_whois", "sfp_arin", "sfp_webframework"],
        description=(
        "可选；仅 isinstance(list) 检查，元素零校验（错误文案称 'module name strings' "
        "但无对应实现）。非空列表整体替换默认模块表并作为 modulelist 实参； "
        "空列表或缺省回落 _FAST_IP_MODULES（:218 `modules or "
        "self._default_modules`）。"
        ),
    ),
        ),
    ),
    # ── hackernews ──
    "hackernews_front_page": ToolParameterContract(
        tool_id="hackernews_front_page",
        specs=(
    ParameterSpec(
        name="max_items",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=30,
        minimum=1,
        maximum=500,
        description=(
        "返回条数上限，整数 1 到 500。类级默认 30；经 quick_collect 时入口注入 10， "
        "故该路径缺省为 10。服务层是 passthrough 不做校验，非法值在执行期由类级拒绝。"
        ),
    ),
        ),
    ),
    "hackernews_search": ToolParameterContract(
        tool_id="hackernews_search",
        specs=(
    ParameterSpec(
        name="query",
        value_type="string",
        required=True,
        source="collector_validation",
        description=(
        "必填非空字符串。经 quick_collect 时入口注入默认值 python， "
        "故该路径缺省时不报错；经建源路径缺失则在采集期被拒。"
        ),
    ),
    ParameterSpec(
        name="max_items",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=30,
        minimum=1,
        maximum=500,
        description=(
        "返回条数上限，整数 1 到 500。类级默认 30；经 quick_collect 时入口注入 10。 "
        "服务层是 passthrough 不做校验，非法值在执行期由类级拒绝。"
        ),
    ),
        ),
    ),
    "hackernews_user": ToolParameterContract(
        tool_id="hackernews_user",
        specs=(
    ParameterSpec(
        name="username",
        value_type="string",
        required=True,
        source="collector_validation",
        description=(
        "必填非空字符串。经 quick_collect 时入口注入默认值 pg， "
        "故该路径缺省时不报错；经建源路径缺失则在采集期被拒。"
        ),
    ),
    ParameterSpec(
        name="max_items",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=30,
        minimum=1,
        maximum=500,
        description=(
        "返回条数上限，整数 1 到 500。类级默认 30；经 quick_collect 时入口注入 10。 "
        "服务层是 passthrough 不做校验，非法值在执行期由类级拒绝。"
        ),
    ),
        ),
    ),
    # ── mediacrawler ──
    "bilibili_video_search": ToolParameterContract(
        tool_id="bilibili_video_search",
        specs=(
    ParameterSpec(
        name="keyword",
        value_type="string",
        required=True,
        source="collector_validation",
        description=(
        "必填；须为非空字符串（返回 strip 后的值）；非 str（含缺失、 "
        "数字）或 strip 后为空均抛 CollectorError。"
        ),
    ),
    ParameterSpec(
        name="max_items",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=20,
        minimum=1,
        maximum=200,
        description=(
        "返回条数上限，整数 1 到 200，默认 20。实现用 int() 强转， "
        "故数字字符串与浮点被接受。True 被当作 1 通过；False 变 0，不满足下界 1， "
        "抛错。"
        ),
    ),
        ),
        notes=(
        "实现只读 keyword 与 max_items，与目录声明、端点元数据三方一致。 "
        "服务层对该类型零拦截，布尔与浮点等边界值只在执行期由类级处理。"
        ),
    ),
    "weibo_trending_topics": ToolParameterContract(
        tool_id="weibo_trending_topics",
        notes="无参数：实现不读任何配置键，与目录声明和端点元数据一致。",
    ),
    "zhihu_hot_list": ToolParameterContract(
        tool_id="zhihu_hot_list",
        notes="无参数：实现不读任何配置键，与目录声明和端点元数据一致。",
    ),
    # ── web-basics ──
    "generic_web": ToolParameterContract(
        tool_id="generic_web",
        specs=(
    ParameterSpec(
        name="url",
        value_type="string",
        required=True,
        source="collector_validation",
        description=(
        "必须是非空 str（strip 后非空），且解析后 scheme 为 http 或 https、 "
        "netloc 非空；strip 后的值被持久化并用于请求。"
        ),
    ),
    ParameterSpec(
        name="extract_mode",
        value_type="enum",
        required=False,
        source="collector_validation",
        default="main_content",
        allowed_values=("main_content", "full_html",),
        description=(
        "枚举 main_content / full_html，默认 main_content；集合成员判定， "
        "非成员值（数字、布尔等）被拒；不可哈希值（list/dict）在判定处抛 TypeError。"
        ),
    ),
        ),
    ),
    "github_topic": ToolParameterContract(
        tool_id="github_topic",
        specs=(
    ParameterSpec(
        name="topic",
        value_type="string",
        required=True,
        source="collector_validation",
        description="必须是非空 str（strip 后非空）；无正则、无 topic 字符集校验。",
    ),
    ParameterSpec(
        name="max_results",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=30,
        minimum=1,
        maximum=100,
        description=(
        "整数 1–100（含端点），默认 30；严格 isinstance(int)， "
        "数字字符串与浮点被拒；True 通过（isinstance(True, int)）并随后以 str(True) "
        "作为 per_page 发出，False 被下界拒绝。"
        ),
    ),
        ),
        conflicts=(
    ParameterConflict(
        param="max_items/max_results",
        standard_path_site=(
        "端点元数据：src/data_intelligence_hub/api/routes/collectors.py:2195-21 "
        "96 `required_params=[\"topic\"],`、 "
        "`optional_params=[\"max_items\"],`（github_topic 唯一元数据条目）"
        ),
        other_site=(
        "服务层 "
        "_validate_github_topic_config（src/data_intelligence_hub/services/collector_ca "
        "talog.py:955 只读 max_results）与类级 "
        "GitHubTopicCollector.validate_config（src/data_intelligence_hub/collectors/git "
        "hub_topic.py:27 只读 max_results…"
        ),
        difference=(
        "按元数据公告传 max_items 不报错也不生效：服务层白名单只返回 topic 与 "
        "max_results（:960 `out = {\"topic\": topic, \"max_results\": max_results}`）， "
        "max_items 被静默丢弃、max_results 回落默认 30；实现全文件零读取 max_items。"
        ),
        impact=(
        "对外契约需人工裁决（本输出不代选）：把端点元数据 optional_params 改为 "
        "max_results，或让服务层与类级接受 max_items 并映射到 max_results。 "
        "规格已按实现实际读取键 max_results 登记。"
        ),
    ),
        ),
        notes=(
        "端点元数据公告的 max_items 在实现中零读取，见分歧记录。 "
        "run_timeout_seconds 由服务层透传、执行层消费，目录未声明它。"
        ),
    ),
    "public_feed": ToolParameterContract(
        tool_id="public_feed",
        specs=(
    ParameterSpec(
        name="url",
        value_type="string",
        required=True,
        source="collector_validation",
        description=(
        "必须是非空 str（strip 后非空），且解析后 scheme 为 http 或 https、 "
        "netloc 非空。"
        ),
    ),
    ParameterSpec(
        name="feed_type",
        value_type="enum",
        required=False,
        source="collector_validation",
        default="auto",
        allowed_values=("auto", "rss", "atom",),
        description="枚举 auto / rss / atom，默认 auto；集合成员判定，非成员值（含非字符串）被拒。",
    ),
    ParameterSpec(
        name="max_items",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=20,
        minimum=1,
        maximum=100,
        description=(
        "整数 1–100（含端点），默认 20；严格 isinstance(int)， "
        "数字字符串与浮点被拒；True 通过（isinstance(True, int)）并按 1 参与条目截取， "
        "False 被下界拒绝。"
        ),
    ),
        ),
        notes=(
        "端点元数据未公告实现读取的 feed_type 与 max_items，但这三项实现确实读取， "
        "本契约照实现登记。"
        ),
    ),
    "jina_reader": ToolParameterContract(
        tool_id="jina_reader",
        specs=(
    ParameterSpec(
        name="url",
        value_type="string",
        required=True,
        source="collector_validation",
        description=(
        "必须是非空 str（strip 后非空）；不校验 URL 格式（无 scheme/netloc 检查）， "
        "任意字符串通过，后续直接拼接到 https://r.jina.ai/ 前缀。"
        ),
    ),
    ParameterSpec(
        name="return_format",
        value_type="enum",
        required=False,
        source="collector_validation",
        default="markdown",
        allowed_values=("markdown", "text", "html",),
        description=(
        "枚举 markdown / text / html，默认 markdown；集合成员判定， "
        "非成员值（含非字符串）被拒。"
        ),
    ),
        ),
        notes="运行需要环境变量 JINA_API_KEY。端点元数据公告的 optional_params 与实现一致。",
    ),
    # ── ecommerce ──
    "ecommerce_product_page": ToolParameterContract(
        tool_id="ecommerce_product_page",
        specs=(
    ParameterSpec(
        name="url",
        value_type="string",
        required=True,
        source="collector_validation",
        description=(
        "非空字符串，strip 后使用；须为绝对 http/https URL（scheme ∈ {http,https} 且 "
        "netloc 非空），否则拒绝。两处站点判定相同。"
        ),
    ),
    ParameterSpec(
        name="fields",
        value_type="string_list",
        required=False,
        source="collector_validation",
        default=[
        "title",
        "price",
        "price_min",
        "price_max",
        "currency",
        "availability",
        "availability_detail",
        "sku",
        "variant",
        "brand",
        "category",
        "description",
        "image_url",
        "canonical_url",
        ],
        description=(
        "可选，缺省为全部 14 个字段（仅键缺省时；显式 null 被拒）；须为非空 list， "
        "元素限固定 14 "
        "值枚举：title/price/price_min/price_max/currency/availability/availability_de "
        "tail/sku/variant/brand/category/description/image_url/canonical_url。 "
        "枚举外元素两处均拒；重复允许、条数无上限。"
        ),
    ),
    ParameterSpec(
        name="platform_hint",
        value_type="enum",
        required=False,
        source="collector_validation",
        default="auto",
        allowed_values=("auto", "shopify", "independent_ecommerce",),
        description=(
        "三值枚举，缺省 auto（仅键缺省时；显式 null 被拒）。 "
        "判定为集合成员测试、无 isinstance：数组/对象等不可哈希值抛未包装 TypeError "
        "而非 CollectorError。该参数仅参与校验，采集逻辑不消费其值；两处判定相同。"
        ),
    ),
        ),
    ),
    "ecommerce_product_discovery": ToolParameterContract(
        tool_id="ecommerce_product_discovery",
        specs=(
    ParameterSpec(
        name="url",
        value_type="string",
        required=True,
        source="collector_validation",
        description=(
        "非空字符串，strip 后使用；须为绝对 http/https URL（scheme ∈ {http,https} 且 "
        "netloc 非空），否则拒绝。两处站点判定相同。"
        ),
    ),
    ParameterSpec(
        name="max_products",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=50,
        minimum=1,
        maximum=200,
        description=(
        "严格 isinstance(int)，无 int() 强转：浮点与数字字符串被拒。 "
        "范围 1-200（含端点），缺省 50（仅键缺省时；显式 null 被拒）。 "
        "布尔是 int 子类：true 通过并当 1 使用（[:max_products]）， "
        "false 因 0<1 被拒。两处站点判定相同。"
        ),
    ),
    ParameterSpec(
        name="platform_hint",
        value_type="enum",
        required=False,
        source="collector_validation",
        default="auto",
        allowed_values=("auto", "shopify", "independent_ecommerce",),
        description=(
        "三值枚举，缺省 auto（仅键缺省时；显式 null 被拒）。 "
        "判定为集合成员测试、无 isinstance：数组/对象等不可哈希值抛未包装 TypeError "
        "而非 CollectorError。该参数仅参与校验，采集逻辑不消费其值；两处判定相同。"
        ),
    ),
        ),
    ),
    # ── osint-misc ──
    "sherlock": ToolParameterContract(
        tool_id="sherlock",
        specs=(
    ParameterSpec(
        name="username",
        value_type="string",
        required=True,
        source="collector_validation",
        description=(
        "必填非空字符串：isinstance(str) 且 strip() 后非空， "
        "否则抛 CollectorError；返回 strip 后的值。数字/布尔因类型检查被拒； "
        "无长度、字符集或格式约束。"
        ),
    ),
    ParameterSpec(
        name="sites",
        value_type="list",
        required=False,
        source="collector_validation",
        default=[],
        description=(
        "可选，默认 []；仅校验 isinstance(list)， "
        "非 list 抛 CollectorError。元素不校验：非字符串元素通过校验， "
        "在 subprocess 参数组装时抛 TypeError，由执行层兜底为失败任务。空 list 合法， "
        "等于不加 --site、扫全量站点。"
        ),
    ),
        ),
        notes=(
        "实现只读 username 与 sites，与两份声明一致。sites 的容器类型有校验， "
        "元素内容不校验。"
        ),
    ),
    "blackbird_email_osint": ToolParameterContract(
        tool_id="blackbird_email_osint",
        specs=(
    ParameterSpec(
        name="email",
        value_type="string",
        required=True,
        source="collector_validation",
        description=(
        "必填非空字符串：isinstance(str) 且 strip() 后非空， "
        "否则抛 CollectorError；另要求字面包含 \"@\"（子串检查而非正则/格式校验， "
        "\"@\" 自身也通过），否则抛 CollectorError；返回 strip 后的值，无长度上限。"
        ),
    ),
        ),
        notes=(
        "实现只读 email，与两份声明一致。校验只检查是否含 @ 字符， "
        "不是邮箱格式校验。运行需要环境变量 BLACKBIRD_BASE_URL。"
        ),
    ),
    "blackbird_username_osint": ToolParameterContract(
        tool_id="blackbird_username_osint",
        specs=(
    ParameterSpec(
        name="username",
        value_type="string",
        required=True,
        source="collector_validation",
        description=(
        "必填非空字符串：isinstance(str) 且 strip() 后非空， "
        "否则抛 CollectorError；返回 strip 后的值。无长度、字符集或格式约束。"
        ),
    ),
        ),
        notes=(
        "实现只读 username，与两份声明一致，除非空检查外无附加约束。 "
        "运行需要环境变量 BLACKBIRD_BASE_URL。"
        ),
    ),
    # ── misc-single ──
    "anydoc_file_to_markdown": ToolParameterContract(
        tool_id="anydoc_file_to_markdown",
        specs=(
    ParameterSpec(
        name="file_url",
        value_type="string",
        required=True,
        source="collector_validation",
        description=(
        "必填；须为 str 且 strip 后非空（require_text，base.py:96-100）， "
        "返回去首尾空白后的值；数字/布尔/null 等非字符串一律拒绝。服务层零校验， "
        "缺失或非法到采集期才失败（failed TaskRun，非建源 400）。"
        ),
    ),
    ParameterSpec(
        name="file_type",
        value_type="string",
        required=False,
        source="collector_validation",
        default="",
        description=(
        "文件类型提示，默认空字符串。实现直接对其调用字符串方法， "
        "传入非字符串会抛属性错误，由执行层兜底为失败任务。"
        ),
    ),
        ),
        notes=(
        "实现只读 file_url 与 file_type，与两份声明一致。file_type 非字符串会抛裸属性错误， "
        "属实现事实。"
        ),
    ),
    "firecrawl_batch_scrape": ToolParameterContract(
        tool_id="firecrawl_batch_scrape",
        specs=(
    ParameterSpec(
        name="urls",
        value_type="string_list",
        required=True,
        source="collector_validation",
        max_length=100,
        description=(
        "必填。必须是 str 组成的非空 list；非 list、空 list、 "
        "元素非字符串或 strip 后为空都抛 CollectorError， "
        "返回值为逐项 strip 后的列表。条目数上限 100， "
        "超出即拒（max_length=100 指条目数）。.get(\"urls\", []) 的缺省 [] 同被拒， "
        "故不可省略。"
        ),
    ),
        ),
        notes=(
        "实现只读 urls。目录声明只写元素为数组，长度上限与元素非空约束在目录中不可见。 "
        "quick_collect 路径会注入示例地址，故该路径下必填性不显现。"
        ),
    ),
    "twscrape_trends": ToolParameterContract(
        tool_id="twscrape_trends",
        specs=(
    ParameterSpec(
        name="category",
        value_type="enum",
        required=False,
        source="collector_validation",
        default="news",
        allowed_values=("news", "sport", "entertainment", "trending",),
        description=(
        "可选，缺省 news（:322）。四值封闭枚举（:36）， "
        "区分大小写、无 strip/lower 归一；任意非成员值（含数字、 "
        "布尔）抛 CollectorError；list/dict 等不可哈希值在集合成员判定处抛裸 "
        "TypeError。目录与端点元数据仅把它声明为 string，枚举只存在于实现。"
        ),
    ),
        ),
        notes=(
        "实现允许四类取值（含 trending），而端点元数据描述文案只列三类。差异照实登记， "
        "收敛方式留待人工裁决。"
        ),
    ),
    "tech_stack_detect": ToolParameterContract(
        tool_id="tech_stack_detect",
        specs=(
    ParameterSpec(
        name="url",
        value_type="string",
        required=True,
        source="collector_validation",
        description=(
        "必填；非空 str（strip 后非空，base.py:96-100）， "
        "返回去空白后的值。urlparse 后的 scheme 必须是 http 或 https， "
        "否则 CollectorError；不校验主机名（\"http://\" 之类空 netloc 也通过校验， "
        "httpx 在采集期才失败）。报错文案写 start with，实际判定是解析后的 scheme。"
        ),
    ),
        ),
        notes=(
        "实现只读 url，与两份声明一致。仅接受 http 与 https 协议这一约束只存在于实现， "
        "两份声明均未体现。"
        ),
    ),
}


def build_baseline_contracts() -> dict[str, ToolParameterContract]:
    """返回这 26 个类型的参数契约。

    每次调用返回新的字典，避免调用方修改共享状态。
    契约对象本身是冻结的，可以安全共享。
    """
    return dict(CONTRACTS)
