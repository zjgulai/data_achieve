"""44 个参数声明与实现不一致的采集器类型的参数契约。

本表是 2026-10-15 参数审计的后续产物。审计判定 86 个类型中 44 个存在
声明与实现不一致，并指出目录的 `config_schema` 不可直接采信。
本模块把这 44 个类型的真实约束登记为契约。

规格来源一律是各采集器的 `validate_config()` 实现与
`services/collector_catalog.py` 的服务层校验函数，不是 `config_schema`。
逐条的源码取证留在审计报告与 research 产物里，本文件只登记约束本身。

覆盖范围：

- 本模块：44 个不一致类型。
- `package_registry_specs.py`：16 个判定一致的类型。
- 合计 60 个；其余 26 个类型的规格尚未登记。

关于两处校验站点：同一参数在服务层与采集器类级各有一份校验。
标准调用路径（quick_collect / source_service / collector_service）先后经过两者，
先执行且做白名单化的那一份决定实际行为。两者判定不同时记入 `conflicts`，
不擅自选边——擅自合并会掩盖「标准路径拒绝、直连路径放行」这类缺口。

审计结论见 docs/architecture/【审计报告】DIH参数类型声明审计.md。

本模块不修改采集目录，也不触发任何执行。
"""

from data_intelligence_hub.tool_catalog.parameters import (
    ParameterConflict,
    ParameterSpec,
    ToolParameterContract,
)

CONTRACTS: dict[str, ToolParameterContract] = {
    # ── osint ──
    "aliens_eye_advanced": ToolParameterContract(
        tool_id="aliens_eye_advanced",
        specs=(
    ParameterSpec(
        name="username",
        value_type="string",
        required=True,
        source="collector_validation",
        description="必填。用户名，不能为空；首尾空白自动去掉。",
    ),
    ParameterSpec(
        name="sites",
        value_type="string",
        required=False,
        source="collector_validation",
        default="",
        enforced=False,
        description=(
            "目标站点，可选。填站点名；留空则不限定站点。"
            ),
    ),
    ParameterSpec(
        name="level",
        value_type="enum",
        required=False,
        source="collector_validation",
        default="intermediate",
        allowed_values=("basic", "intermediate", "advanced",),
        description=(
            "扫描深度，可选。可选值：basic、intermediate、advanced；"
            "默认 intermediate。留空时也按 intermediate 处理。"
            ),
    ),
        ),
    ),
    "aliens_eye_recurse": ToolParameterContract(
        tool_id="aliens_eye_recurse",
        specs=(
    ParameterSpec(
        name="username",
        value_type="string",
        required=True,
        source="collector_validation",
        description="必填。用户名，不能为空；首尾空白自动去掉。",
    ),
    ParameterSpec(
        name="depth",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=1,
        maximum=3,
        description=(
            "递归层数，可选。整数，最大 3，默认 1；超过 3 按 3 处理。"
            ),
    ),
        ),
    ),
    "aliens_eye_batch": ToolParameterContract(
        tool_id="aliens_eye_batch",
        specs=(
    ParameterSpec(
        name="usernames",
        value_type="string",
        required=True,
        source="collector_validation",
        description=(
            "必填。要查询的用户名。多个用逗号分隔，最多 10 个；也可直接传字符串数组。"
            ),
    ),
        ),
    ),
    "spiderfoot_subdomain_enum": ToolParameterContract(
        tool_id="spiderfoot_subdomain_enum",
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
        value_type="string_list",
        required=False,
        source="collector_validation",
        default=[],
        description="模块列表，可选。该采集器使用固定模块，传入值不改变扫描范围。",
    ),
        ),
    ),
    "spiderfoot_threat_intel": ToolParameterContract(
        tool_id="spiderfoot_threat_intel",
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
        value_type="string_list",
        required=False,
        source="collector_validation",
        default=[],
        description="模块列表，可选。该采集器使用固定模块，传入值不改变扫描范围。",
    ),
        ),
    ),
    "spiderfoot_breach_check": ToolParameterContract(
        tool_id="spiderfoot_breach_check",
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
        value_type="string_list",
        required=False,
        source="collector_validation",
        default=[],
        description="模块列表，可选。该采集器使用固定模块，传入值不改变扫描范围。",
    ),
        ),
    ),
    "spiderfoot_cert_transparency": ToolParameterContract(
        tool_id="spiderfoot_cert_transparency",
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
        value_type="string_list",
        required=False,
        source="collector_validation",
        default=[],
        description="模块列表，可选。该采集器使用固定模块，传入值不改变扫描范围。",
    ),
        ),
    ),
    "spiderfoot_dark_web": ToolParameterContract(
        tool_id="spiderfoot_dark_web",
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
        value_type="string_list",
        required=False,
        source="collector_validation",
        default=[],
        description="模块列表，可选。该采集器使用固定模块，传入值不改变扫描范围。",
    ),
        ),
    ),
    "spiderfoot_attack_surface": ToolParameterContract(
        tool_id="spiderfoot_attack_surface",
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
        value_type="string_list",
        required=False,
        source="collector_validation",
        default=[],
        description="模块列表，可选。该采集器使用固定模块，传入值不改变扫描范围。",
    ),
        ),
    ),
    "robin_darkweb_search": ToolParameterContract(
        tool_id="robin_darkweb_search",
        specs=(
    ParameterSpec(
        name="keyword",
        value_type="string",
        required=True,
        source="collector_validation",
        description="必填。搜索关键词，不能为空；首尾空白自动去掉。",
    ),
    ParameterSpec(
        name="max_results",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=20,
        maximum=100,
        description=(
            "返回结果数上限，可选。整数，默认 20；超过 100 按 100 处理。"
            ),
    ),
        ),
    ),
    "robin_darkweb_username": ToolParameterContract(
        tool_id="robin_darkweb_username",
        specs=(
    ParameterSpec(
        name="username",
        value_type="string",
        required=True,
        source="collector_validation",
        description="必填。要查询的用户名，不能为空；首尾空白自动去掉。",
    ),
    ParameterSpec(
        name="max_results",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=20,
        maximum=100,
        description="返回结果数上限，可选。整数，默认 20；超过 100 按 100 处理。",
    ),
        ),
    ),
    "robin_darkweb_email": ToolParameterContract(
        tool_id="robin_darkweb_email",
        specs=(
    ParameterSpec(
        name="email",
        value_type="string",
        required=True,
        source="collector_validation",
        description="必填。邮箱地址，不能为空；必须包含 @。",
    ),
    ParameterSpec(
        name="max_results",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=20,
        maximum=100,
        description="返回结果数上限，可选。整数，默认 20；超过 100 按 100 处理。",
    ),
        ),
    ),
    "maigret": ToolParameterContract(
        tool_id="maigret",
        specs=(
    ParameterSpec(
        name="username",
        value_type="string",
        required=True,
        source="collector_validation",
        description="必填。要查询的用户名，不能为空；首尾空白自动去掉。",
    ),
    ParameterSpec(
        name="max_sites",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=500,
        minimum=1,
        maximum=3000,
        description=(
            "最多查询的站点数，可选。整数 1 到 3000，默认 500。仅在命令行采集模式下生效。"
            ),
    ),
        ),
    ),
    # ── exa ──
    "exa_search": ToolParameterContract(
        tool_id="exa_search",
        specs=(
    ParameterSpec(
        name="query",
        value_type="string",
        required=True,
        source="collector_validation",
        description="必填。搜索查询词，不能为空；首尾空白自动去掉。",
    ),
    ParameterSpec(
        name="search_type",
        value_type="enum",
        required=False,
        source="collector_validation",
        default="auto",
        allowed_values=(            "lite",
            "instant",
            "fast",
            "auto",
            "deep-lite",
            "deep",
            "deep-reasoning",
            ),
        description=(
            "搜索类型，可选。可选值：lite、instant、fast、auto、deep-lite、"
            "deep、deep-reasoning；默认 auto。lite 只读缓存，单价最低。"
            "后三项为深度搜索。"
        ),
    ),
    ParameterSpec(
        name="num_results",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=10,
        minimum=1,
        description=(
            "返回结果数，可选。整数，最小 1，最大 100，默认 10。"
            ),
    ),
    ParameterSpec(
        name="category",
        value_type="enum",
        required=False,
        source="collector_validation",
        allowed_values=(            "company",
            "people",
            "publication",
            "news",
            "personal site",
            "financial report",
            ),
        description=(
            "结果分类，可选。可选值：company、people、publication、"
            "news、personal site、financial report；默认不限制。"
        ),
    ),
    ParameterSpec(
        name="contents_mode",
        value_type="enum",
        required=False,
        source="collector_validation",
        default="highlights",
        allowed_values=("highlights", "text", "summary", "none",),
        description=(
            "内容返回方式，可选。可选值：highlights、text、summary、"
            "none；默认 highlights。none 表示不返回正文。"
        ),
    ),
    ParameterSpec(
        name="include_domains",
        value_type="list",
        required=False,
        source="collector_validation",
        default=[],
        description=(
            "只在这些域名内搜索，可选。填域名列表；默认空。"
            ),
    ),
    ParameterSpec(
        name="exclude_domains",
        value_type="list",
        required=False,
        source="collector_validation",
        default=[],
        description=(
            "排除这些域名，可选。填域名列表；默认空。"
            ),
    ),
    ParameterSpec(
        name="objective",
        value_type="string",
        required=False,
        source="collector_validation",
        description=(
            "研究目标，可选。用一句话说明这次搜索要回答什么问题，"
            "上游会用它优化结果排序。"
        ),
    ),
    ParameterSpec(
        name="snapshot_as_of",
        value_type="string",
        required=False,
        source="collector_validation",
        description=(
            "时间快照，可选。ISO-8601 时间字符串；填后按该时刻的缓存复现"
            "检索结果，用于审计与回归对比。"
        ),
    ),
    ParameterSpec(
        name="user_identifier",
        value_type="string",
        required=False,
        source="collector_validation",
        description="调用方标识，可选。填一个稳定的调用方名字，便于上游计费与审计。",
    ),
    ParameterSpec(
        name="user_location",
        value_type="string",
        required=False,
        source="collector_validation",
        description="用户位置，可选。填 ISO 国家码（如 US、CN），用于本地化结果。",
    ),
        ),
    ),
    "exa_find_similar": ToolParameterContract(
        tool_id="exa_find_similar",
        specs=(
    ParameterSpec(
        name="url",
        value_type="string",
        required=True,
        source="collector_validation",
        description="必填。要查找相似内容的网页地址，不能为空。",
    ),
    ParameterSpec(
        name="num_results",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=10,
        minimum=1,
        maximum=25,
        description="返回结果数，可选。整数 1 到 25，默认 10。",
    ),
    ParameterSpec(
        name="exclude_source_domain",
        value_type="boolean",
        required=False,
        source="collector_validation",
        default=True,
        description=(
            "是否排除与原始网页同域的结果，可选。填 true 或 false；默认 true。"
            ),
    ),
        ),
    ),
    "exa_contents": ToolParameterContract(
        tool_id="exa_contents",
        specs=(
    ParameterSpec(
        name="urls",
        value_type="string_list",
        required=True,
        source="collector_validation",
        max_length=100,
        description=(
            "必填。要读取内容的网页地址列表，1 到 100 条，每条不能为空。"
            ),
    ),
    ParameterSpec(
        name="contents_mode",
        value_type="enum",
        required=False,
        source="collector_validation",
        default="highlights",
        allowed_values=("highlights", "text", "summary", "none",),
        description=(
            "内容返回方式，可选。可选值：highlights、text、summary、"
            "none；默认 highlights。"
        ),
    ),
    ParameterSpec(
        name="subpages",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=0,
        minimum=0,
        maximum=100,
        description=(
            "每个网页额外读取的子页数，可选。整数 0 到 100，默认 0。"
            ),
    ),
    ParameterSpec(
        name="summary_query",
        value_type="string",
        required=False,
        source="collector_validation",
        description="摘要检索词，可选。contents_mode=summary 时用于生成页面摘要。",
    ),
    ParameterSpec(
        name="extras_image_links",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=0,
        minimum=0,
        maximum=10,
        description="返回图片链接数量，可选。整数 0 到 10，默认 0。",
    ),
    ParameterSpec(
        name="livecrawl_timeout",
        value_type="integer",
        required=False,
        source="collector_validation",
        minimum=1000,
        maximum=60000,
        description="实时抓取超时，可选。毫秒，1000 到 60000。",
    ),
    ParameterSpec(
        name="include_sections",
        value_type="list",
        required=False,
        source="collector_validation",
        default=[],
        description="只保留这些页面区块，可选。填区块名列表；默认空。",
    ),
    ParameterSpec(
        name="exclude_sections",
        value_type="list",
        required=False,
        source="collector_validation",
        default=[],
        description="排除这些页面区块，可选。填区块名列表；默认空。",
    ),
        ),
    ),
    "exa_answer": ToolParameterContract(
        tool_id="exa_answer",
        specs=(
    ParameterSpec(
        name="query",
        value_type="string",
        required=True,
        source="collector_validation",
        description="必填。要回答的问题，不能为空；首尾空白自动去掉。",
    ),
        ),
    ),
    "exa_agent": ToolParameterContract(
        tool_id="exa_agent",
        specs=(
    ParameterSpec(
        name="query",
        value_type="string",
        required=True,
        source="collector_validation",
        description="必填。研究问题，不能为空。",
    ),
    ParameterSpec(
        name="effort",
        value_type="enum",
        required=False,
        source="collector_validation",
        default="medium",
        allowed_values=(
            "minimal", "low", "medium", "high", "xhigh", "auto", "ultra",
        ),
        description=(
            "研究投入档位，可选。默认 medium；auto 与 ultra 按用量计费，"
            "固定档位按次计费。"
        ),
    ),
    ParameterSpec(
        name="output_schema",
        value_type="string",
        required=False,
        source="collector_validation",
        description=(
            "输出 JSON Schema，可选。填 JSON 对象字符串；"
            "填后返回结构化结果与字段级引用。"
        ),
    ),
    ParameterSpec(
        name="system_prompt",
        value_type="string",
        required=False,
        source="collector_validation",
        description="系统提示词，可选。用于约束研究风格与输出语言。",
    ),
    ParameterSpec(
        name="max_cost_dollars",
        value_type="number",
        required=False,
        source="collector_validation",
        default=5,
        minimum=1,
        maximum=100,
        description="单次研究成本上限，可选。美元，1 到 100，默认 5。",
    ),
    ParameterSpec(
        name="timeout_seconds",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=600,
        minimum=30,
        maximum=1800,
        description="等待研究完成的秒数，可选。30 到 1800，默认 600。",
    ),
        ),
    ),
    # ── social-cn ──
    "bilibili_user_videos": ToolParameterContract(
        tool_id="bilibili_user_videos",
        specs=(
    ParameterSpec(
        name="uid",
        value_type="string",
        required=True,
        source="collector_validation",
        description="必填。B 站 UP 主 uid，不能为空；请按字符串填写。",
    ),
    ParameterSpec(
        name="max_items",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=30,
        minimum=1,
        maximum=200,
        description=(
            "采集条数上限，可选。整数 1 到 200，默认 30。"
            ),
    ),
        ),
        conflicts=(
    ParameterConflict(
        param="limit/max_items",
        standard_path_site=(
            "COLLECTOR_CATALOG config_schema "
            "声明（src/data_intelligence_hub/services/collector_catalog.py:233- "
            "236，limit 在 :235 `\"properties\": {\"uid\": \"string\", \"limit\": "
            "\"integer\"}`）：limit 被声明为可选 integer， "
            "无任何运行时校验消费者，仅入库并经 GET /collectors 对外公告。"
            ),
        other_site=(
            "端点元数据（src/data_intelligence_hub/api/routes/collectors.py:2934-2935 "
            "`required_params=[\"uid\"]`、`optional_params=[\"max_items\"]`）与类级 "
            "validate_config（src/data_intelligence_hub/collectors/mediacrawler_collect "
            "or.py:181-186 只读 max_items）——两者一致，并与 c…"
            ),
        difference=(
            "按声明传 limit 不报错也不生效：服务层 passthrough 把 limit 原样存入 "
            "source/task config（collector_catalog.py:902 → :1403-1404）， "
            "采集期类级校验完全不读 limit，静默回落默认 30； "
            "limit 在整个采集器文件中仅作为出站 HTTP "
            "查询参数名出现（mediacrawler_collector.py:206）。"
            ),
        impact=(
            "规格已按实现实际读取键登记为 max_items；两处声明互相矛盾， "
            "对外契约需人工裁决（本输出不代选）：把 config_schema 及 UI/文档消费面统一改为 "
            "max_items，或在实现中接受 limit 并映射到 max_items 以兼容旧配置。"
            ),
    ),
        ),
    ),
    "bilibili_video_comments": ToolParameterContract(
        tool_id="bilibili_video_comments",
        specs=(
    ParameterSpec(
        name="bvid",
        value_type="string",
        required=True,
        source="collector_validation",
        description="必填。B 站视频 bvid，不能为空；请按字符串填写。",
    ),
    ParameterSpec(
        name="max_items",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=50,
        minimum=1,
        maximum=500,
        description=(
            "采集条数上限，可选。整数 1 到 500，默认 50。"
            ),
    ),
        ),
        conflicts=(
    ParameterConflict(
        param="limit/max_items",
        standard_path_site=(
            "COLLECTOR_CATALOG config_schema "
            "声明（src/data_intelligence_hub/services/collector_catalog.py:242- "
            "245，limit 在 :244 `\"properties\": {\"bvid\": \"string\", \"limit\": "
            "\"integer\"}`）：limit 被声明为可选 integer， "
            "无任何运行时校验消费者，仅入库并经 GET /collectors 对外公告。"
            ),
        other_site=(
            "端点元数据（src/data_intelligence_hub/api/routes/collectors.py:2947-2948 "
            "`required_params=[\"bvid\"]`、 "
            "`optional_params=[\"max_items\"]`）与类级 "
            "validate_config（src/data_intelligence_hub/collectors/mediacrawler_collect "
            "or.py:228-233 只读 max_items）——两者一致，并与 …"
            ),
        difference=(
            "按声明传 limit 不报错也不生效：服务层 passthrough 把 limit 原样存入 "
            "source/task config（collector_catalog.py:902 → :1403-1404）， "
            "采集期类级校验完全不读 limit，静默回落默认 50； "
            "limit 仅作为出站 HTTP 查询参数名出现（mediacrawler_collector.py:253）。"
            ),
        impact=(
            "规格已按实现实际读取键登记为 max_items；两处声明互相矛盾， "
            "对外契约需人工裁决：把 config_schema/UI 统一改为 max_items， "
            "或在实现中接受 limit 并映射到 max_items。"
            ),
    ),
        ),
    ),
    "weibo_keyword_search": ToolParameterContract(
        tool_id="weibo_keyword_search",
        specs=(
    ParameterSpec(
        name="keyword",
        value_type="string",
        required=True,
        source="collector_validation",
        description="必填。微博搜索关键词，不能为空；请按字符串填写。",
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
            "采集条数上限，可选。整数 1 到 200，默认 20。"
            ),
    ),
        ),
        conflicts=(
    ParameterConflict(
        param="limit/max_items",
        standard_path_site=(
            "COLLECTOR_CATALOG config_schema "
            "声明（src/data_intelligence_hub/services/collector_catalog.py:251- "
            "254，limit 在 :253 `\"properties\": {\"keyword\": \"string\", \"limit\": "
            "\"integer\"}`）：limit 被声明为可选 integer， "
            "无任何运行时校验消费者，仅入库并经 GET /collectors 对外公告。"
            ),
        other_site=(
            "端点元数据（src/data_intelligence_hub/api/routes/collectors.py:2963-2964 "
            "`required_params=[\"keyword\"]`、 "
            "`optional_params=[\"max_items\"]`）与类级 "
            "validate_config（src/data_intelligence_hub/collectors/mediacrawler_collect "
            "or.py:280-285 只读 max_items）——两者一致，…"
            ),
        difference=(
            "按声明传 limit 不报错也不生效：服务层 passthrough 把 limit 原样存入 "
            "source/task config（collector_catalog.py:902 → :1403-1404）， "
            "采集期类级校验完全不读 limit，静默回落默认 20； "
            "limit 仅作为出站 HTTP 查询参数名出现（mediacrawler_collector.py:305）。"
            ),
        impact=(
            "规格已按实现实际读取键登记为 max_items；两处声明互相矛盾， "
            "对外契约需人工裁决：把 config_schema/UI 统一改为 max_items， "
            "或在实现中接受 limit 并映射到 max_items。"
            ),
    ),
        ),
    ),
    "weibo_user_posts": ToolParameterContract(
        tool_id="weibo_user_posts",
        specs=(
    ParameterSpec(
        name="uid",
        value_type="string",
        required=True,
        source="collector_validation",
        description=(
            "必填。微博用户 uid，不能为空；请按字符串填写。"
            ),
    ),
    ParameterSpec(
        name="max_items",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=30,
        minimum=1,
        maximum=200,
        description=(
            "采集条数上限，可选。整数 1 到 200，默认 30。"
            ),
    ),
        ),
        conflicts=(
    ParameterConflict(
        param="user_id/uid",
        standard_path_site=(
            "COLLECTOR_CATALOG config_schema "
            "声明（src/data_intelligence_hub/services/collector_catalog.py:260- "
            "263：`\"required\": [\"user_id\"]`、 "
            ":262 `\"properties\": {\"user_id\": \"string\", \"limit\": "
            "\"integer\"}`）：必填键声明为 user_id。"
            ),
        other_site=(
            "端点元数据（src/data_intelligence_hub/api/routes/collectors.py:2976 "
            "`required_params=[\"uid\"]`）与类级 "
            "validate_config（src/data_intelligence_hub/collectors/mediacrawler_collect "
            "or.py:328 `uid = require_text(self.config, \"uid\")`）：必填检查落在 uid。"
            ),
        difference=(
            "只传声明里的 user_id 时：服务层 passthrough 不报错（可建源/入库， "
            "quick_collect.py:902、source_service.py:45/120）， "
            "采集期直接抛 CollectorError('Collector config field is required: uid')； "
            "声明为必填的 user_id 在实现中零读取。"
            ),
        impact=(
            "规格已按实际读取键 uid "
            "登记；对外契约需人工裁决（本输出不代选）：把实现与端点元数据统一改回 "
            "user_id（并保留声明），或确认 uid 为唯一合法键并修正 config_schema， "
            "避免调用方按声明传参后到运行期才失败。"
            ),
    ),
    ParameterConflict(
        param="limit/max_items",
        standard_path_site=(
            "COLLECTOR_CATALOG config_schema "
            "声明（src/data_intelligence_hub/services/collector_catalog.py:260- "
            "263，limit 在 :262）：limit 被声明为可选 integer， "
            "无任何运行时校验消费者，仅入库并经 GET /collectors 对外公告。"
            ),
        other_site=(
            "端点元数据（src/data_intelligence_hub/api/routes/collectors.py:2976-2977 "
            "`required_params=[\"uid\"]`、`optional_params=[\"max_items\"]`）与类级 "
            "validate_config（src/data_intelligence_hub/collectors/mediacrawler_collect "
            "or.py:327-332 只读 max_items）——两者一致，并与 c…"
            ),
        difference=(
            "按声明传 limit 不报错也不生效：服务层 passthrough 把 limit 原样存入 "
            "source/task config（collector_catalog.py:902 → :1403-1404）， "
            "采集期类级校验完全不读 limit，静默回落默认 30； "
            "limit 仅作为出站 HTTP 查询参数名出现（mediacrawler_collector.py:352）。"
            ),
        impact=(
            "规格已按实现实际读取键登记为 max_items；对外契约需人工裁决：把 "
            "config_schema/UI 统一改为 max_items， "
            "或在实现中接受 limit 并映射到 max_items。"
            ),
    ),
        ),
    ),
    "zhihu_question_answers": ToolParameterContract(
        tool_id="zhihu_question_answers",
        specs=(
    ParameterSpec(
        name="question_id",
        value_type="string",
        required=True,
        source="collector_validation",
        description="必填。知乎问题 id，不能为空；请按字符串填写。",
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
            "采集条数上限，可选。整数 1 到 200，默认 20。"
            ),
    ),
        ),
        conflicts=(
    ParameterConflict(
        param="limit/max_items",
        standard_path_site=(
            "COLLECTOR_CATALOG config_schema "
            "声明（src/data_intelligence_hub/services/collector_catalog.py:275- "
            "278，limit 在 :277 `\"properties\": {\"question_id\": \"string\", "
            "\"limit\": \"integer\"}`）：limit 被声明为可选 integer， "
            "无任何运行时校验消费者，仅入库并经 GET /collectors 对外公告。"
            ),
        other_site=(
            "端点元数据（src/data_intelligence_hub/api/routes/collectors.py:3005-3006 "
            "`required_params=[\"question_id\"]`、 "
            "`optional_params=[\"max_items\"]`）与类级 "
            "validate_config（src/data_intelligence_hub/collectors/mediacrawler_collect "
            "or.py:418-423 只读 max_items）——两…"
            ),
        difference=(
            "按声明传 limit 不报错也不生效：服务层 passthrough 把 limit 原样存入 "
            "source/task config（collector_catalog.py:902 → :1403-1404）， "
            "采集期类级校验完全不读 limit，静默回落默认 20； "
            "limit 仅作为出站 HTTP 查询参数名出现（mediacrawler_collector.py:445）。 "
            "对抗性复核裁定：limit 属「声明了但代码零读取」，真 mismatch 在参数名层。"
            ),
        impact=(
            "规格已按实现实际读取键登记为 max_items；两处声明互相矛盾， "
            "对外契约需人工裁决：把 config_schema/UI 统一改为 max_items， "
            "或在实现中接受 limit 并映射到 max_items。"
            ),
    ),
        ),
    ),
    "zhihu_keyword_search": ToolParameterContract(
        tool_id="zhihu_keyword_search",
        specs=(
    ParameterSpec(
        name="keyword",
        value_type="string",
        required=True,
        source="collector_validation",
        description="必填。知乎搜索关键词，不能为空；请按字符串填写。",
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
            "采集条数上限，可选。整数 1 到 200，默认 20。"
            ),
    ),
        ),
        conflicts=(
    ParameterConflict(
        param="limit/max_items",
        standard_path_site=(
            "COLLECTOR_CATALOG config_schema "
            "声明（src/data_intelligence_hub/services/collector_catalog.py:284- "
            "287，limit 在 :286 `\"properties\": {\"keyword\": \"string\", \"limit\": "
            "\"integer\"}`）：limit 被声明为可选 integer， "
            "无任何运行时校验消费者，仅入库并经 GET /collectors 对外公告。"
            ),
        other_site=(
            "端点元数据（src/data_intelligence_hub/api/routes/collectors.py:3018-3019 "
            "`required_params=[\"keyword\"]`、 "
            "`optional_params=[\"max_items\"]`）与类级 "
            "validate_config（src/data_intelligence_hub/collectors/mediacrawler_collect "
            "or.py:468-473 只读 max_items）——两者一致，…"
            ),
        difference=(
            "按声明传 limit 不报错也不生效：服务层 passthrough 把 limit 原样存入 "
            "source/task config（collector_catalog.py:902 → :1403-1404）， "
            "采集期类级校验完全不读 limit，静默回落默认 20； "
            "limit 仅作为出站 HTTP 查询参数名出现（mediacrawler_collector.py:493）。 "
            "对抗性复核裁定：limit 属「声明了但代码零读取」，真 mismatch 在参数名层。"
            ),
        impact=(
            "规格已按实现实际读取键登记为 max_items；两处声明互相矛盾， "
            "对外契约需人工裁决：把 config_schema/UI 统一改为 max_items， "
            "或在实现中接受 limit 并映射到 max_items。"
            ),
    ),
        ),
    ),
    "kuaishou_video_search": ToolParameterContract(
        tool_id="kuaishou_video_search",
        specs=(
    ParameterSpec(
        name="keyword",
        value_type="string",
        required=True,
        source="collector_validation",
        description="必填。快手搜索关键词，不能为空；请按字符串填写。",
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
            "采集条数上限，可选。整数 1 到 200，默认 20。"
            ),
    ),
        ),
        conflicts=(
    ParameterConflict(
        param="limit/max_items",
        standard_path_site=(
            "COLLECTOR_CATALOG config_schema "
            "声明（src/data_intelligence_hub/services/collector_catalog.py:326- "
            "329，limit 在 :328 `\"properties\": {\"keyword\": \"string\", \"limit\": "
            "\"integer\"}`）：limit 被声明为可选 integer， "
            "无任何运行时校验消费者，仅入库并经 GET /collectors 对外公告。"
            ),
        other_site=(
            "端点元数据（src/data_intelligence_hub/api/routes/collectors.py:3095-3096 "
            "`required_params=[\"keyword\"]`、 "
            "`optional_params=[\"max_items\"]`）与类级 "
            "validate_config（src/data_intelligence_hub/collectors/mediacrawler_collect "
            "or.py:559-564 只读 max_items）——两者一致，…"
            ),
        difference=(
            "按声明传 limit 不报错也不生效：服务层 passthrough 把 limit 原样存入 "
            "source/task config（collector_catalog.py:902 → :1403-1404）， "
            "采集期类级校验完全不读 limit，静默回落默认 20； "
            "limit 仅作为出站 HTTP 查询参数名出现（mediacrawler_collector.py:584）。 "
            "对抗性复核裁定：limit 属「声明了但代码零读取」，真 mismatch 在参数名层。"
            ),
        impact=(
            "规格已按实现实际读取键登记为 max_items；两处声明互相矛盾， "
            "对外契约需人工裁决：把 config_schema/UI 统一改为 max_items， "
            "或在实现中接受 limit 并映射到 max_items。"
            ),
    ),
        ),
    ),
    "kuaishou_user_videos": ToolParameterContract(
        tool_id="kuaishou_user_videos",
        specs=(
    ParameterSpec(
        name="user_id",
        value_type="string",
        required=True,
        source="collector_validation",
        description=(
            "必填。快手用户 user_id，不能为空；请按字符串填写。"
            ),
    ),
    ParameterSpec(
        name="max_items",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=30,
        minimum=1,
        maximum=200,
        description=(
            "采集条数上限，可选。整数 1 到 200，默认 30。"
            ),
    ),
        ),
        conflicts=(
    ParameterConflict(
        param="limit/max_items",
        standard_path_site=(
            "COLLECTOR_CATALOG config_schema "
            "声明（src/data_intelligence_hub/services/collector_catalog.py:335- "
            "338，limit 在 :337 `\"properties\": {\"user_id\": \"string\", \"limit\": "
            "\"integer\"}`）：limit 被声明为可选 integer， "
            "无任何运行时校验消费者，仅入库并经 GET /collectors 对外公告。"
            ),
        other_site=(
            "端点元数据（src/data_intelligence_hub/api/routes/collectors.py:3111-3112 "
            "`required_params=[\"user_id\"]`、 "
            "`optional_params=[\"max_items\"]`）与类级 "
            "validate_config（src/data_intelligence_hub/collectors/mediacrawler_collect "
            "or.py:606-611 只读 max_items）——两者一致，…"
            ),
        difference=(
            "按声明传 limit 不报错也不生效：服务层 passthrough 把 limit 原样存入 "
            "source/task config（collector_catalog.py:902 → :1403-1404）， "
            "采集期类级校验完全不读 limit，静默回落默认 30； "
            "limit 仅作为出站 HTTP 查询参数名出现（mediacrawler_collector.py:631）。"
            ),
        impact=(
            "规格已按实现实际读取键登记为 max_items；两处声明互相矛盾， "
            "对外契约需人工裁决：把 config_schema/UI 统一改为 max_items， "
            "或在实现中接受 limit 并映射到 max_items。"
            ),
    ),
        ),
    ),
    # ── web-and-extract ──
    "autoscraper_enhanced_web": ToolParameterContract(
        tool_id="autoscraper_enhanced_web",
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
        name="wanted_list",
        value_type="string_list",
        required=True,
        source="collector_validation",
        enforced=False,
        description=(
            "必填。要提取的字段名列表，至少填一项。"
            ),
    ),
    ParameterSpec(
        name="mode",
        value_type="enum",
        required=False,
        source="collector_validation",
        default="exact",
        allowed_values=("exact", "similar",),
        description=(
            "匹配模式，可选。可选值：exact、similar；默认 exact。"
            ),
    ),
    ParameterSpec(
        name="save_rules",
        value_type="boolean",
        required=False,
        source="collector_validation",
        default=False,
        enforced=False,
        description=(
            "是否保存提取规则，可选。填 true 或 false；默认 false。"
            ),
    ),
    ParameterSpec(
        name="rules_path",
        value_type="string",
        required=False,
        source="collector_validation",
        enforced=False,
        description=(
            "规则文件路径，可选。填文件路径字符串。"
            ),
    ),
        ),
        conflicts=(
    ParameterConflict(
        param="url",
        standard_path_site=(
            "服务层 "
            "_validate_autoscraper_enhanced_web_config（src/data_intelligence_h "
            "ub/services/collector_catalog.py:954-958）：非 http/https 或无 "
            "netloc 即拒（CollectorConfigError）"
            ),
        other_site=(
            "类级 "
            "AutoScraperEnhancedWebCollector.validate_config（src/data_intelligence_hub "
            "/collectors/autoscraper_collector.py:53）：只查非空字符串，协议不限"
            ),
        difference=(
            "同一 url（如 \"ftp://example.com\"、\"example.com\"）：服务层判非法， "
            "类级判合法——绕过服务层的直连路径会放行，采集期再以 httpx 错误收场； "
            "标准路径上服务层先拒绝，分歧只在非标准路径可见"
            ),
        impact=(
            "选定唯一事实源：把协议检查下沉到类级共享，或删除服务层协议检查； "
            "不擅自选一。当前标准路径由服务层判定（更严）。"
            ),
    ),
        ),
    ),
    "playwright_browser": ToolParameterContract(
        tool_id="playwright_browser",
        specs=(
    ParameterSpec(
        name="url",
        value_type="string",
        required=True,
        source="collector_validation",
        description=(
            "必填。要打开的网页地址，必须是完整的 http 或 https 地址。"
            ),
    ),
    ParameterSpec(
        name="wait_for",
        value_type="enum",
        required=False,
        source="collector_validation",
        default="load",
        allowed_values=("load", "networkidle", "domcontentloaded",),
        description=(
            "页面加载等待方式，可选。可选值：load、networkidle、"
            "domcontentloaded；默认 load。"
        ),
    ),
    ParameterSpec(
        name="extract_mode",
        value_type="enum",
        required=False,
        source="collector_validation",
        default="text",
        allowed_values=("text", "html", "screenshot",),
        description="内容提取方式，可选。可选值：text、html、screenshot；默认 text。",
    ),
    ParameterSpec(
        name="wait_selector",
        value_type="string",
        required=False,
        source="collector_validation",
        description=(
            "等待出现的页面元素，可选。填 CSS 选择器；留空则不等待特定元素。"
            ),
    ),
        ),
        conflicts=(
    ParameterConflict(
        param="url",
        standard_path_site=(
            "服务层 "
            "_validate_playwright_browser_config（src/data_intelligence_hub/ser "
            "vices/collector_catalog.py:1219）：仅非空字符串，协议/私网不查"
            ),
        other_site=(
            "类级 "
            "PlaywrightBrowserCollector.validate_config（src/data_intelligence_hub/coll "
            "ectors/playwright_browser.py:76 → :62-68）：_assert_public_url 拒绝非 "
            "http/https 与 localhost/127.0.0.1/::1/192.168.*"
            ),
        difference=(
            "同一 url（如 \"http://localhost:8000/\"、 "
            "\"ftp://example.com\"）：服务层放行并持久化， "
            "类级在采集期拒绝（CollectorError → 失败 TaskRun，不是建源 400）"
            ),
        impact=(
            "决定私网/非 http(s) 在哪一层拦：把 _assert_public_url 上移到服务层（建源即 "
            "400），或明确只在采集期拒绝。标准路径两站都跑、结果不一致，不擅自选一。"
            ),
    ),
    ParameterConflict(
        param="wait_selector",
        standard_path_site=(
            "服务层 "
            "_validate_playwright_browser_config（src/data_intelligence_hub/ser "
            "vices/collector_catalog.py:1231-1234、 "
            ":1239）：非 str 或空白串即拒；strip 后持久化；未传归一 None"
            ),
        other_site=(
            "类级 "
            "PlaywrightBrowserCollector.validate_config（src/data_intelligence_hub/coll "
            "ectors/playwright_browser.py:87-89、:94）：只拒非 str； "
            "空白串放行并原样返回（:176 真值判断随后静默忽略）"
            ),
        difference=(
            "空白串（\"\" 或全空白）：服务层判非法，类级判合法（等价未配置）； "
            "`strip` 归一也只做在服务层"
            ),
        impact=(
            "空字符串在类级为假值，被静默忽略，等价未配置；但非空的全空白串（如三个空格）是 "
            "真值，会原样传给选择器等待，在采集期报错，并不等于未配置。"
            ),
    ),
        ),
    ),
    "firecrawl_crawl": ToolParameterContract(
        tool_id="firecrawl_crawl",
        specs=(
    ParameterSpec(
        name="url",
        value_type="string",
        required=True,
        source="collector_validation",
        description=(
            "必填。要抓取的起始网页地址。"
            ),
    ),
    ParameterSpec(
        name="max_pages",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=10,
        minimum=1,
        maximum=500,
        description=(
            "最多抓取的页面数，可选。整数 1 到 500，默认 10。"
            ),
    ),
    ParameterSpec(
        name="include_paths",
        value_type="string_list",
        required=False,
        source="collector_validation",
        default=[],
        description=(
            "只抓取这些路径，可选。填路径列表；留空则不限制。"
            ),
    ),
    ParameterSpec(
        name="exclude_paths",
        value_type="string_list",
        required=False,
        source="collector_validation",
        default=[],
        description=(
            "不抓取这些路径，可选。填路径列表；留空则不排除。"
            ),
    ),
        ),
    ),
    "firecrawl_extract": ToolParameterContract(
        tool_id="firecrawl_extract",
        specs=(
    ParameterSpec(
        name="url",
        value_type="string",
        required=True,
        source="collector_validation",
        description="必填。要提取内容的网页地址。",
    ),
    ParameterSpec(
        name="prompt",
        value_type="string",
        required=False,
        source="collector_validation",
        default="",
        description=(
            "提取要求，可选。用自然语言描述要提取的内容；与提取结构至少填一项。"
            ),
    ),
        ),
    ),
    # ── apify ──
    "apify_actor": ToolParameterContract(
        tool_id="apify_actor",
        specs=(
    ParameterSpec(
        name="actor_id",
        value_type="string",
        required=True,
        source="collector_validation",
        pattern="^(?!\\.)(?!.*\\.\\.)[A-Za-z0-9][A-Za-z0-9._-]*/(?!\\.)[A-Za-z0-9][A-Za-z0-9._-]*$",
        description=(
            "必填。Apify Actor 标识，格式为 owner/name。"
            ),
    ),
    ParameterSpec(
        name="max_items",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=20,
        minimum=1,
        maximum=1000,
        description=(
            "抓取条数上限，可选。整数 1 到 1000，默认 20。也可用别名 maxItems。"
            ),
    ),
    ParameterSpec(
        name="max_total_charge_usd",
        value_type="number",
        required=False,
        source="collector_validation",
        default=1.0,
        minimum=0,
        description=(
            "单次运行的费用上限，单位美元。填大于 0 的数值，"
            "默认 1.0。达到上限会中止按事件计费的运行。"
            ),
    ),
    ParameterSpec(
        name="run_timeout_seconds",
        value_type="number",
        required=False,
        source="collector_validation",
        default=600.0,
        description=(
            "运行等待上限，单位秒。填数值，默认 600。"
            ),
    ),
        ),
        conflicts=(
    ParameterConflict(
        param="run_timeout_seconds",
        standard_path_site=(
            "services/collector_catalog.py:1191-1213（服务层专用函数：完全不读 "
            "取该键；:1208-1213 返回白名单不含 → 值被静默剥离）"
            ),
        other_site=(
            "collectors/apify_actor.py:359-364（类级：float() 强转接受 "
            "int/float/数值字符串、无范围检查、缺省 600.0；:408/:452 消费）"
            ),
        difference=(
            "同一参数一个站点丢弃、一个站点支持：quick_collect.py:898 构造的值在 :902 "
            "校验时被剥除，collector_service.py:357 `value = "
            "config.get(\"run_timeout_seconds\")` 永远拿不到 → 回落 :362 的 300.0 "
            "全局缺省（SLOW_ENDPOINT_TIMEOUT_SECONDS :51-62 无 apify 键）， "
            "而类级内层仍按 600.0 自等（审计报告 §4.2：内层 600 会被外…"
            ),
        impact=(
            "需人决策二选一：服务层白名单透传该键并纳入 collector_service 预算链（修复 "
            "§4.2），或从类级支持与文档（apify_actor.py:330）中移除。 "
            "登记默认值 600.0 取类级实现；标准路径实际缺省为 300.0。"
            ),
    ),
    ParameterConflict(
        param="max_items",
        standard_path_site=(
            "services/collector_catalog.py:1198-1202（严格：必须 int 且 "
            "1<=x<=1000，否则拒绝）"
            ),
        other_site=(
            "collectors/apify_actor.py:354-357（宽松：int() 强转收数字字符串、 "
            "无下界 0/负数通过、上界 min() 静默裁剪 1000、非 int/str 类型静默回落 20）"
            ),
        difference=(
            "同一输入判定不同：'50'（数字字符串）、0、-1、5000 在 A 被 400 拒绝， "
            "在 B 分别被接受/接受/接受/裁剪到 1000。标准路径 A 先执行且白名单化， "
            "B 只收到 1..1000 的 int，宽松分支经 quick_collect/source_service "
            "不可达（审计推断成立），但两站点契约语义未收敛（B "
            "亦为绕过服务层的直达类实例路径的实际契约）。"
            ),
        impact=(
            "标准路径上服务层先执行并做白名单化，类级的宽松分支收不到越界值， "
            "该分歧只在绕过服务层的直连路径可见。"
            ),
    ),
    ParameterConflict(
        param="max_total_charge_usd",
        standard_path_site=(
            "services/collector_catalog.py:1203-1207,1212（仅 int|float 且 >0， "
            "否则拒绝；缺省 1.0；返回 float）"
            ),
        other_site=(
            "collectors/apify_actor.py:365-366（float() 强转收数字字符串、 "
            "不检查正值 0/负数通过、缺省 3.0，常量 :40）"
            ),
        difference=(
            "接受面不同：'1.5' 字符串与负数在 A 被拒、在 B 通过； "
            "缺省值不同：A 1.0 vs B 3.0（quick_collect 入口 :895-897 用 3.0、 "
            "与 B 一致）。标准路径经 quick_collect 时入口恒供给该键、A 缺省不触发； "
            "经 source_service 直建 source 且调用方省略时缺省为 A 的 1.0。"
            ),
        impact=(
            "标准路径上服务层负责校验与默认值，两处默认值之差（1.0 与 "
            "3.0）只在绕过服务层的路径可见。"
            ),
    ),
    ParameterConflict(
        param="actor_id",
        standard_path_site=(
            "services/collector_catalog.py:1192 → :909-915（只要求非空字符串， "
            "去首尾空白）"
            ),
        other_site=(
            "collectors/apify_actor.py:346-349 + :339-341（追加 owner/name "
            "正则：拒绝无斜杠值、含 '..'、段首为点）"
            ),
        difference=(
            "同一输入判定不同：'foo'、'a/..'、'.a/b' 等非空字符串在 A 通过、在 B 拒绝。 "
            "标准路径两站点都执行且顺序固定（A 先于 B）：经 quick_collect 时 actor_id "
            "恒为服务端端点常量（quick_collect.py:889）故差异不显现； "
            "经 source_service 自建 source 时 A 放行、运行期 B 失败（failed TaskRun， "
            "非 400）。"
            ),
        impact=(
            "两处都执行且顺序固定，服务层先于类级。经 quick_collect 时 95 "
            "个已登记端点的值由服务端注入、调用方无法覆盖；apify_tiktok_shop_search_v2 "
            "不在该表内，形状错误会在采集期暴露。"
            ),
    ),
        ),
    ),
    # ── misc ──
    "github_repo": ToolParameterContract(
        tool_id="github_repo",
        specs=(
    ParameterSpec(
        name="url",
        value_type="string",
        required=False,
        source="collector_validation",
        default="",
        description=(
            "仓库地址，可选。可填完整仓库链接；留空时必须填 owner 和 repo。"
            ),
    ),
    ParameterSpec(
        name="owner",
        value_type="string",
        required=True,
        source="collector_validation",
        description=(
            "仓库所有者。未填仓库地址时必填。"
            ),
    ),
    ParameterSpec(
        name="repo",
        value_type="string",
        required=True,
        source="collector_validation",
        description="仓库名称。未填仓库地址时必填。",
    ),
        ),
        conflicts=(
    ParameterConflict(
        param="url（连带 owner/repo 的必填性）",
        standard_path_site=(
            "服务层 "
            "_validate_github_repo_config（services/collector_catalog.py:918-92 "
            "4）：接受 url，可由 url 推导 owner/repo， "
            "此时完全不校验 owner/repo"
            ),
        other_site=(
            "类层 "
            "GitHubRepoCollector.validate_config（collectors/github_repo.py:25-30）：不 "
            "识别 url，无条件 require_text owner/repo； "
            "url-only config 在直构路径必失败"
            ),
        difference=(
            "同一类型的合法入参集合不一致：服务层认 url，类层只认 owner/repo。 "
            "标准路径靠服务层先归一化（quick_collect.py:902 → 持久化）才无实际冲突； "
            "绕过服务层直接用 url 构造类实例会失败"
            ),
        impact=(
            "人类决策：url "
            "是否保留为受支持入口。保留则以服务层为归一化权威并把该事实写入契约（或让类层同 "
            "样接受 url）；废弃则删服务层 url 分支。不要两处各写一半。"
            ),
    ),
        ),
    ),
    "anysearch": ToolParameterContract(
        tool_id="anysearch",
        specs=(
    ParameterSpec(
        name="query",
        value_type="string",
        required=True,
        source="collector_validation",
        description="必填。搜索查询词，不能为空；首尾空白自动去掉。",
    ),
    ParameterSpec(
        name="num_results",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=10,
        minimum=1,
        maximum=50,
        description=(
            "返回结果数，可选。整数 1 到 50，默认 10。"
            ),
    ),
    ParameterSpec(
        name="site",
        value_type="string",
        required=False,
        source="collector_validation",
        description="限定站点，可选。填站点标识；留空则不限定。",
    ),
    ParameterSpec(
        name="tag",
        value_type="string",
        required=False,
        source="collector_validation",
        description=(
            "标签过滤，可选。填上游支持的标签；留空则不传。"
            ),
    ),
        ),
    ),
    "twscrape_search": ToolParameterContract(
        tool_id="twscrape_search",
        specs=(
    ParameterSpec(
        name="query",
        value_type="string",
        required=True,
        source="collector_validation",
        description="必填。搜索查询词，不能为空。",
    ),
    ParameterSpec(
        name="limit",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=20,
        minimum=1,
        maximum=1000,
        description=(
            "返回条数上限，可选。整数 1 到 1000，默认 20。"
            ),
    ),
    ParameterSpec(
        name="product",
        value_type="enum",
        required=False,
        source="collector_validation",
        default="Latest",
        allowed_values=("Latest", "Top", "Media",),
        description=(
            "搜索范围，可选。可选值：Latest、Top、Media；默认 Latest。区分大小写。"
            ),
    ),
        ),
    ),
    "twscrape_user_tweets": ToolParameterContract(
        tool_id="twscrape_user_tweets",
        specs=(
    ParameterSpec(
        name="username",
        value_type="string",
        required=True,
        source="collector_validation",
        description="必填。要查询的 X 用户名，不能为空。",
    ),
    ParameterSpec(
        name="limit",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=50,
        minimum=1,
        maximum=3200,
        description="返回条数上限，可选。整数 1 到 3200，默认 50。",
    ),
        ),
    ),
    "manual_json": ToolParameterContract(
        tool_id="manual_json",
        specs=(
    ParameterSpec(
        name="entity_type",
        value_type="string",
        required=True,
        source="collector_validation",
        description="必填。实体类型标识，不能为空。",
    ),
        ),
    ),
    "bestblogs_articles": ToolParameterContract(
        tool_id="bestblogs_articles",
        specs=(
    ParameterSpec(
        name="category",
        value_type="enum",
        required=False,
        source="collector_validation",
        default="",
        allowed_values=(            "",
            "ai",
            "design",
            "devops",
            "product",
            "programming",
            "security",
            ),
        description=(
            "文章分类，可选。可选值：ai、design、devops、product、"
            "programming、security；留空表示不过滤，也是默认值。"
            ),
    ),
    ParameterSpec(
        name="lang",
        value_type="enum",
        required=False,
        source="collector_validation",
        default="all",
        allowed_values=("zh", "en", "all",),
        description="文章语言，可选。可选值：zh、en、all；默认 all。",
    ),
    ParameterSpec(
        name="min_score",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=70,
        minimum=0,
        maximum=100,
        description="最低评分，可选。整数 0 到 100，默认 70。",
    ),
    ParameterSpec(
        name="limit",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=20,
        minimum=1,
        maximum=100,
        description=(
            "文章条数上限，可选。整数 1 到 100，默认 20。"
            ),
    ),
        ),
    ),
    "devto_articles": ToolParameterContract(
        tool_id="devto_articles",
        specs=(
    ParameterSpec(
        name="tag",
        value_type="string",
        required=False,
        source="collector_validation",
        default="",
        description=(
            "标签，可选。tag、username、keyword 三项至少填一项。"
            ),
    ),
    ParameterSpec(
        name="username",
        value_type="string",
        required=False,
        source="collector_validation",
        default="",
        description="用户名，可选。与 tag、keyword 组成三选一必填。",
    ),
    ParameterSpec(
        name="keyword",
        value_type="string",
        required=False,
        source="collector_validation",
        default="",
        description="搜索关键词，可选。与 tag、username 组成三选一必填。",
    ),
    ParameterSpec(
        name="max_items",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=20,
        minimum=1,
        maximum=100,
        description="文章条数上限，可选。整数 1 到 100，默认 20。",
    ),
        ),
    ),
    "juejin_articles": ToolParameterContract(
        tool_id="juejin_articles",
        specs=(
    ParameterSpec(
        name="keyword",
        value_type="string",
        required=True,
        source="collector_validation",
        description=(
            "搜索关键词，必填。不能为空；快速采集未填时使用默认值 python。"
            ),
    ),
    ParameterSpec(
        name="max_items",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=20,
        minimum=1,
        maximum=100,
        description="文章条数上限，可选。整数 1 到 100，默认 20。",
    ),
    ParameterSpec(
        name="category",
        value_type="string",
        required=False,
        source="collector_validation",
        default="",
        description=(
            "文章分类，可选。当前采集流程不使用该值；传入不影响结果。"
            ),
    ),
        ),
    ),
    "substack_posts": ToolParameterContract(
        tool_id="substack_posts",
        specs=(
    ParameterSpec(
        name="publication",
        value_type="string",
        required=True,
        source="collector_validation",
        description=(
            "必填。Substack 出版物名称或地址，不能为空。系统会从地址中取出出版物名。"
            ),
    ),
    ParameterSpec(
        name="max_items",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=20,
        minimum=1,
        maximum=100,
        description="文章条数上限，可选。整数 1 到 100，默认 20。",
    ),
        ),
    ),
    "baidu_search": ToolParameterContract(
        tool_id="baidu_search",
        specs=(
    ParameterSpec(
        name="keyword",
        value_type="string",
        required=True,
        source="collector_validation",
        description=(
            "搜索关键词，必填。不能为空；快速采集未填时使用默认值 python。"
            ),
    ),
    ParameterSpec(
        name="max_items",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=10,
        minimum=1,
        maximum=100,
        description="返回条数上限，可选。整数 1 到 100，默认 10。",
    ),
        ),
    ),
    "bing_search": ToolParameterContract(
        tool_id="bing_search",
        specs=(
    ParameterSpec(
        name="keyword",
        value_type="string",
        required=True,
        source="collector_validation",
        description=(
            "搜索关键词，必填。不能为空；快速采集未填时使用默认值 python。"
            ),
    ),
    ParameterSpec(
        name="max_items",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=10,
        minimum=1,
        maximum=100,
        description="返回条数上限，可选。整数 1 到 100，默认 10。",
    ),
        ),
    ),
    "duckduckgo_search": ToolParameterContract(
        tool_id="duckduckgo_search",
        specs=(
    ParameterSpec(
        name="keyword",
        value_type="string",
        required=True,
        source="collector_validation",
        description=(
            "搜索关键词，必填。不能为空；快速采集未填时使用默认值 python。"
            ),
    ),
    ParameterSpec(
        name="max_items",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=10,
        minimum=1,
        maximum=100,
        description="返回条数上限，可选。整数 1 到 100，默认 10。",
    ),
        ),
    ),
    "browser_use_task": ToolParameterContract(
        tool_id="browser_use_task",
        specs=(
    ParameterSpec(
        name="task",
        value_type="string",
        required=True,
        source="collector_validation",
        description="必填。用自然语言描述要完成的任务，不能为空。",
    ),
    ParameterSpec(
        name="url",
        value_type="string",
        required=False,
        source="collector_validation",
        default="",
        description=(
            "起始网页地址，可选。填写时必须是完整的 http 或 https 地"
            "址，且不能指向本机或内网地址。"
            ),
    ),
    ParameterSpec(
        name="max_steps",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=10,
        minimum=1,
        maximum=50,
        description="最大执行步数，可选。整数 1 到 50，默认 10。",
    ),
        ),
    ),
    # ── tikhub ──
    "tikhub_social": ToolParameterContract(
        tool_id="tikhub_social",
        specs=(
    ParameterSpec(
        name="endpoint_type",
        value_type="enum",
        required=True,
        source="collector_validation",
        allowed_values=(            "tikhub_tiktok_video_search",
            "tikhub_tiktok_user_posts",
            "tikhub_tiktok_hashtag_posts",
            "tikhub_instagram_user_posts",
            "tikhub_instagram_search",
            "tikhub_xiaohongshu_search",
            "tikhub_youtube_search",
            "tikhub_youtube_channel_videos",
            "tikhub_reddit_search",
            "tikhub_reddit_subreddit_posts",
            "tikhub_x_search",
            "tikhub_x_user_tweets",
            "tikhub_douyin_video_search",
            "tikhub_douyin_user_posts",
            "tikhub_douyin_hot_search",
            "tikhub_douyin_comments",
            "tikhub_bilibili_video_search",
            "tikhub_bilibili_user_videos",
            "tikhub_bilibili_comments",
            "tikhub_weibo_search",
            "tikhub_weibo_user_posts",
            "tikhub_kuaishou_search",
            "tikhub_kuaishou_user_posts",
            "tikhub_wechat_search",
            "tikhub_wechat_channels_video",
            "tikhub_zhihu_search",
            "tikhub_zhihu_question_answers",
            "tikhub_douyin_brand_hot_search",
            "tikhub_youtube_video_search",
            "tikhub_threads_search",
            "tikhub_threads_user_posts",
            "tikhub_threads_post_comments",
            "tikhub_linkedin_user_posts",
            "tikhub_linkedin_company_profile",
            "tikhub_linkedin_company_posts",
            "tikhub_linkedin_search_jobs",
            "tikhub_linkedin_job_detail",
            "tikhub_linkedin_post_comments",
            "tikhub_lemon8_search",
            "tikhub_lemon8_user_posts",
            "tikhub_lemon8_trending",
            "tikhub_tiktok_ads_search",
            "tikhub_tiktok_top_ads",
            "tikhub_tiktok_ads_detail",
            "tikhub_tiktok_ads_keyword_suggest",
            "tikhub_tiktok_shop_products",
            "tikhub_tiktok_creator_info",
            "tikhub_tiktok_creator_insights",
            "tikhub_tiktok_creator_insights_trend",
            "tikhub_tiktok_creator_account_health",
            "tikhub_tiktok_live_search",
            "tikhub_tiktok_live_room_detail",
            "tikhub_tiktok_live_user",
            "tikhub_youtube_trending",
            "tikhub_reddit_trending",
            "tikhub_x_trending",
            "tikhub_tiktok_user_followers",
            "tikhub_instagram_user_followers",
            "tikhub_x_user_followers",
            "tikhub_instagram_post_comments",
            "tikhub_youtube_video_comments",
            "tikhub_reddit_post_comments",
            ),
        description=(
            "必填。目标端点，从受支持的 62 个平台端点中选择一个。"
            ),
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
            "返回条数上限，可选。整数 1 到 100，默认 20。"
            ),
    ),
    ParameterSpec(
        name="keyword",
        value_type="string",
        required=False,
        source="collector_validation",
        enforced=False,
        description=(
            "搜索关键词，可选。多数端点必须提供；留空时发送空字符串，上游可能报错。"
            ),
    ),
    ParameterSpec(
        name="unique_id",
        value_type="string",
        required=False,
        source="collector_validation",
        enforced=False,
        description=(
            "用户或内容唯一标识，可选。部分端点必填；留空时发送空字符串。"
            ),
    ),
    ParameterSpec(
        name="ch_id",
        value_type="string",
        required=False,
        source="collector_validation",
        enforced=False,
        description=(
            "频道标识，可选。也可改用 hashtag_id 传入。"
            ),
    ),
    ParameterSpec(
        name="user_id",
        value_type="string",
        required=False,
        source="collector_validation",
        enforced=False,
        description=(
            "用户标识，可选。部分端点必填；留空时发送空字符串。"
            ),
    ),
        ),
        conflicts=(
    ParameterConflict(
        param="max_items",
        standard_path_site=(
            "服务层 "
            "_validate_tikhub_social_config（services/collector_catalog.py:1157 "
            "-1188；标准路径入口 quick_collect.py:902、 "
            "source_service.py:45,85,120）"
            ),
        other_site=(
            "类层 "
            "TikHubSocialCollector.validate_config（collectors/tikhub_social.py:1646-16 "
            "58；运行期 collector_service.py:117）"
            ),
        difference=(
            "服务层：非 isinstance(int) 或不在 [1,100] "
            "即拒绝（collector_catalog.py:1163-1167）——数字字符串、浮点、负数均 400。"
            ),
        impact=(
            "收敛两处为同一语义；建议以服务层 isinstance(int)+[1,100] "
            "为准（拒绝数字字符串），类层改为同约束检查。bool 边角需一并明确：True "
            "两层均按 1 放行。"
            ),
    ),
    ParameterConflict(
        param="oid",
        standard_path_site=(
            "端点元数据 api/routes/collectors.py:729-741（:735 "
            "`required_params=[\"oid\"],`）"
            ),
        other_site=(
            "服务层白名单 collector_catalog.py:1171-1187（无 oid）； "
            "实现 collectors/tikhub_social.py:1491-1494（:1493 `\"bvid\": "
            "config.get(\"bvid\") or config.get(\"video_id\") or \"\"`）"
            ),
        difference=(
            "元数据声明 tikhub_bilibili_comments 必填 oid；白名单无 oid（传入即丢弃）， "
            "实现实际消费 bvid/video_id（二者未在元数据声明）。 "
            "按元数据传 oid 的用户得到上游 bvid=\"\" → 400/422。"
            ),
        impact=(
            "二选一：把 oid 加入白名单并在 :1493 回退链中支持， "
            "或把元数据 required_params 改为 bvid/video_id。"
            ),
    ),
        ),
    ),
}


def build_collector_contracts() -> dict[str, ToolParameterContract]:
    """返回 44 个不一致类型的参数契约。

    每次调用返回新的字典，避免调用方修改共享状态。
    契约对象本身是冻结的，可以安全共享。
    """
    return dict(CONTRACTS)
