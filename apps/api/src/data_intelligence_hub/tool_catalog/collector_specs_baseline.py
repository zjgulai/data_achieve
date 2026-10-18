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
        "必填。用户名，不能为空；首尾空白自动去掉。"
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
        "必填。用户名，不能为空；首尾空白自动去掉。"
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
        "必填。用户名，不能为空；首尾空白自动去掉。"
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
        "必填。目标域名，不能为空。"
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
        "模块列表，可选。留空时使用默认模块；填非空列表则替换默认模块。"
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
        "必填。目标邮箱地址，不能为空。"
        ),
    ),
    ParameterSpec(
        name="modules",
        value_type="list",
        required=False,
        source="collector_validation",
        default=["sfp_emailformat", "sfp_accounts"],
        description=(
        "模块列表，可选。留空时使用默认模块；填非空列表则替换默认模块。"
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
        "必填。目标 IP 地址，不能为空。"
        ),
    ),
    ParameterSpec(
        name="modules",
        value_type="list",
        required=False,
        source="collector_validation",
        default=["sfp_dnsresolve", "sfp_whois", "sfp_arin", "sfp_webframework"],
        description=(
        "模块列表，可选。留空时使用默认模块；填非空列表则替换默认模块。"
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
        "返回条数上限，可选。整数 1 到 500，默认 30；快速采集未填时为 10。"
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
        "必填。搜索关键词，不能为空；快速采集未填时使用默认值 python。"
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
        "返回条数上限，可选。整数 1 到 500，默认 30；快速采集未填时为 10。"
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
        "必填。Hacker News 用户名，不能为空；快速采集未填时使用默认值 pg。"
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
        "返回条数上限，可选。整数 1 到 500，默认 30；快速采集未填时为 10。"
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
        "必填。搜索关键词，不能为空。"
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
        "返回条数上限，可选。整数 1 到 200，默认 20。"
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
        "必填。要抓取的网页地址，必须是完整的 http 或 https 地址。"
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
        "内容提取方式，可选。可选值：main_content、full_html；默认 main_content。"
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
        description="必填。GitHub 话题名称，不能为空。",
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
        "返回仓库数上限，可选。整数 1 到 100，默认 30。"
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
        "必填。订阅源地址，必须是完整的 http 或 https 地址。"
        ),
    ),
    ParameterSpec(
        name="feed_type",
        value_type="enum",
        required=False,
        source="collector_validation",
        default="auto",
        allowed_values=("auto", "rss", "atom",),
        description="订阅源类型，可选。可选值：auto、rss、atom；默认 auto。",
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
        "返回条目数上限，可选。整数 1 到 100，默认 20。"
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
        "必填。要读取的网页地址，不能为空；请填完整网址。"
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
        "返回格式，可选。可选值：markdown、text、html；默认 markdown。"
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
        "必填。商品详情页地址，必须是完整的 http 或 https 地址。"
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
        "要提取的字段，可选。默认提取全部 14 个字段。"
        "可选值：title、price、price_min、price_max、currency、"
        "availability、availability_detail、sku、variant、brand、"
        "category、description、image_url、canonical_url。"
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
        "平台类型提示，可选。可选值：auto、shopify、"
        "independent_ecommerce；默认 auto。该参数不影响采集行为。"
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
        "必填。商品列表页地址，必须是完整的 http 或 https 地址。"
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
        "最多发现的商品数，可选。整数 1 到 200，默认 50。"
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
        "平台类型提示，可选。可选值：auto、shopify、"
        "independent_ecommerce；默认 auto。该参数不影响采集行为。"
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
        "必填。要查询的用户名，不能为空。"
        ),
    ),
    ParameterSpec(
        name="sites",
        value_type="list",
        required=False,
        source="collector_validation",
        default=[],
        description=(
        "站点列表，可选。留空表示查询全部站点。"
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
        "必填。要查询的邮箱地址，不能为空，且必须包含 @。"
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
        "必填。要查询的用户名，不能为空。"
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
        "必填。要转换的文件地址，不能为空。"
        ),
    ),
    ParameterSpec(
        name="file_type",
        value_type="string",
        required=False,
        source="collector_validation",
        default="",
        description=(
        "文件类型提示，可选。默认空字符串，由系统自行判断。"
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
        "必填。要抓取的网页地址列表，1 到 100 条，每条不能为空。"
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
        "趋势分类，可选。可选值：news、sport、entertainment、"
        "trending；默认 news。区分大小写。"
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
        "必填。要检测的网页地址，必须是 http 或 https 地址。"
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
