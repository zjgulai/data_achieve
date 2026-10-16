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
        description="非空字符串，strip 后使用（:303 → :310 返回值）。",
    ),
    ParameterSpec(
        name="sites",
        value_type="string",
        required=False,
        source="collector_validation",
        default="",
        enforced=False,
        description=(
            "零运行时校验：仅真值原样透传为 --site 实参， "
            "非字符串只会在 subprocess 参数组装阶段报 TypeError。 "
            "此规格按 argv 消费语义与 catalog :482 声明登记为 string； "
            "实现没有任何额外断言。"
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
            "strip().lower() 归一后比对枚举，非法值抛 CollectorError； "
            "缺省/空值回落 intermediate。catalog config_schema 未声明（属 "
            "undeclared_but_read）；端点元数据已公告（src/data_intelligence_hub/api/ro "
            "utes/collectors.py:3478 `optional_params=[\"sites\", \"level\"],`）。"
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
        description="非空字符串，strip 后使用。",
    ),
    ParameterSpec(
        name="depth",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=1,
        maximum=3,
        description=(
            "int() 强转后仅校验上限 3：接受数值字符串、浮点、布尔（\"2\"→2、2.9→2、 "
            "True→1），不可解析字符串抛未包装的 ValueError； "
            "无下限（0、负数通过校验并透传 --recurse-depth）。"
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
            "逗号分隔字符串为官方用法（str 分支按 \",\" 拆分并 strip）； "
            "字符串数组/任意可迭代同样接受（else 分支逐项 str() 归一）； "
            "解析后为空报错；上限 10 个。value_type 记 string， "
            "数组可用性见 description。"
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
            "非空字符串，strip 后使用；不做 domain/ip/email 格式校验（`_target_type` "
            "是类属性、非配置参数：spiderfoot_extended_collectors.py:62 `_target_type "
            "= \"domain\"`）。"
            ),
    ),
    ParameterSpec(
        name="modules",
        value_type="string_list",
        required=False,
        source="collector_validation",
        default=[],
        description="用户值仅过 list 类型检查，随后被固定模块表整体覆盖，对实际扫描模块零影响。",
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
            "非空字符串，strip 后使用；不做 IP 格式校验（`_target_type = "
            "\"ip\"`：spiderfoot_extended_collectors.py:72，类属性、非参数）。"
            ),
    ),
    ParameterSpec(
        name="modules",
        value_type="string_list",
        required=False,
        source="collector_validation",
        default=[],
        description="用户值仅过 list 类型检查，随后被固定模块表整体覆盖，对实际扫描模块零影响。",
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
            "非空字符串，strip 后使用；不做邮箱格式校验（`_target_type = "
            "\"email\"`：spiderfoot_extended_collectors.py:82，类属性、非参数）。"
            ),
    ),
    ParameterSpec(
        name="modules",
        value_type="string_list",
        required=False,
        source="collector_validation",
        default=[],
        description="用户值仅过 list 类型检查，随后被固定模块表整体覆盖，对实际扫描模块零影响。",
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
            "非空字符串，strip 后使用；不做 domain 格式校验（`_target_type = "
            "\"domain\"`：spiderfoot_extended_collectors.py:92，类属性、非参数）。"
            ),
    ),
    ParameterSpec(
        name="modules",
        value_type="string_list",
        required=False,
        source="collector_validation",
        default=[],
        description="用户值仅过 list 类型检查，随后被固定模块表整体覆盖，对实际扫描模块零影响。",
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
            "非空字符串，strip 后使用；不做 domain 格式校验（`_target_type = "
            "\"domain\"`：spiderfoot_extended_collectors.py:102，类属性、非参数）。"
            ),
    ),
    ParameterSpec(
        name="modules",
        value_type="string_list",
        required=False,
        source="collector_validation",
        default=[],
        description="用户值仅过 list 类型检查，随后被固定模块表整体覆盖，对实际扫描模块零影响。",
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
            "非空字符串，strip 后使用；不做 domain 格式校验（`_target_type = "
            "\"domain\"`：spiderfoot_extended_collectors.py:112，类属性、非参数）。"
            ),
    ),
    ParameterSpec(
        name="modules",
        value_type="string_list",
        required=False,
        source="collector_validation",
        default=[],
        description="用户值仅过 list 类型检查，随后被固定模块表整体覆盖，对实际扫描模块零影响。",
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
        description="非空字符串，strip 后使用。",
    ),
    ParameterSpec(
        name="max_results",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=20,
        maximum=100,
        description=(
            "int() 强转（接受 \"50\"/浮点）后仅做上限截断 min(x, 100)； "
            "无下限（0/负数通过校验）。"
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
        description="非空字符串，strip 后使用。",
    ),
    ParameterSpec(
        name="max_results",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=20,
        maximum=100,
        description="int() 强转后仅做上限截断 min(x, 100)；无下限。",
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
        description="仅非空字符串，不校验 '@'（审计复核成立）。",
    ),
    ParameterSpec(
        name="max_results",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=20,
        maximum=100,
        description="int() 强转后仅做上限截断 min(x, 100)；无下限。",
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
        description="非空字符串，strip 后使用。",
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
            "整数 1 到 3000（含端点）。仅命令行路径生效；sidecar 路径不接收该参数， "
            "且在值不等于默认 500 时记一条 warning——显式传 500 时同样被忽略但不记录。"
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
        description="必填。必须为非空字符串（strip 后非空）；返回值去除首尾空白。",
    ),
    ParameterSpec(
        name="search_type",
        value_type="enum",
        required=False,
        source="collector_validation",
        default="auto",
        allowed_values=(            "instant",
            "fast",
            "auto",
            "deep-lite",
            "deep",
            "deep-reasoning",
            ),
        description="六值枚举，默认 auto。deep-lite/deep/deep-reasoning 为深搜类型。",
    ),
    ParameterSpec(
        name="num_results",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=10,
        minimum=1,
        description=(
            "整数，下界 1。上界随 search_type 变化：深搜类（deep-lite / deep / "
            "deep-reasoning）为 25，其余为 10， "
            "故不设 maximum。默认 10。True 是 int 的子类会被当作 1 通过；False 变 0， "
            "被下界拒绝。"
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
        description="六值枚举，默认未设置（None）。仅真值参与校验：None 与空串直接放行。",
    ),
    ParameterSpec(
        name="contents_mode",
        value_type="enum",
        required=False,
        source="collector_validation",
        default="highlights",
        allowed_values=("highlights", "text", "summary", "none",),
        description="四值枚举，默认 highlights；none 表示不取内容。",
    ),
    ParameterSpec(
        name="include_domains",
        value_type="list",
        required=False,
        source="collector_validation",
        default=[],
        description=(
            "只校验容器必须是 list，元素内容不校验，原样成为请求的 includeDomains。 "
            "因此 [1, 2] 这类非字符串元素会被放行。"
            ),
    ),
    ParameterSpec(
        name="exclude_domains",
        value_type="list",
        required=False,
        source="collector_validation",
        default=[],
        description=(
            "只校验容器必须是 list，元素内容不校验，原样成为请求的 excludeDomains。 "
            "因此 [1, 2] 这类非字符串元素会被放行。"
            ),
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
        description="必填。非空字符串即可；实现不做 URL 格式校验。",
    ),
    ParameterSpec(
        name="num_results",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=10,
        minimum=1,
        maximum=25,
        description="整数 1–25，默认 10。",
    ),
    ParameterSpec(
        name="exclude_source_domain",
        value_type="boolean",
        required=False,
        source="collector_validation",
        default=True,
        description=(
            "布尔，默认 true（排除种子 URL 同域结果）；严格 isinstance(bool) 检查， "
            "字符串 \"true\" 会被拒绝。"
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
            "必填。非空 list，至多 100 项，每项为非空字符串； "
            "max_length=100 指条目数上限（非字符数）。"
            ),
    ),
    ParameterSpec(
        name="contents_mode",
        value_type="enum",
        required=False,
        source="collector_validation",
        default="highlights",
        allowed_values=("highlights", "text", "summary", "none",),
        description="四值枚举，默认 highlights。",
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
            "整数 0–100，默认 0；仅当大于 0 时才写入请求 "
            "subpages（exa_collector.py:552-555）。"
            ),
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
        description="必填。必须为非空字符串（strip 后非空）。",
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
        description="B站 UP 主 uid；必须是非空 str（strip 后非空），数字等非字符串类型会被拒。",
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
            "采集条数上限；默认 30，范围 1..200（含边界）；int() 强转口径见 notes； "
            "出站作为 MediaCrawler 查询参数 limit 发送。"
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
        description="B站视频 bvid；必须是非空 str（strip 后非空），数字等非字符串类型会被拒。",
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
            "采集条数上限；默认 50，范围 1..500（含边界）；int() 强转口径见 notes； "
            "出站作为 MediaCrawler 查询参数 limit 发送。"
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
        description="微博搜索关键词；必须是非空 str（strip 后非空），数字等非字符串类型会被拒。",
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
            "采集条数上限；默认 20，范围 1..200（含边界）；int() 强转口径见 notes； "
            "出站作为 MediaCrawler 查询参数 limit 发送。"
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
            "微博用户 uid（注意：不是声明中的 user_id， "
            "见 conflicts）；必须是非空 str（strip 后非空）， "
            "数字等非字符串类型会被拒。"
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
            "采集条数上限；默认 30，范围 1..200（含边界）；int() 强转口径见 notes； "
            "出站作为 MediaCrawler 查询参数 limit 发送。"
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
        description="知乎问题 id；必须是非空 str（strip 后非空），数字等非字符串类型会被拒。",
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
            "采集条数上限；默认 20，范围 1..200（含边界）；int() 强转口径见 notes； "
            "出站作为 MediaCrawler 查询参数 limit 发送。"
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
        description="知乎搜索关键词；必须是非空 str（strip 后非空），数字等非字符串类型会被拒。",
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
            "采集条数上限；默认 20，范围 1..200（含边界）；int() 强转口径见 notes； "
            "出站作为 MediaCrawler 查询参数 limit 发送。"
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
        description="快手搜索关键词；必须是非空 str（strip 后非空），数字等非字符串类型会被拒。",
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
            "采集条数上限；默认 20，范围 1..200（含边界）；int() 强转口径见 notes； "
            "出站作为 MediaCrawler 查询参数 limit 发送。"
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
            "快手用户 user_id；必须是非空 str（strip 后非空）， "
            "数字等非字符串类型会被拒。此键名与目录声明及实现一致（同族对照项）。"
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
            "采集条数上限；默认 30，范围 1..200（含边界）；int() 强转口径见 notes； "
            "出站作为 MediaCrawler 查询参数 limit 发送。"
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
            "服务层：非空字符串且必须 http/https 绝对 URL（:954-958）； "
            "类级：只要求非空字符串（:53）。协议判定两站不一致， "
            "见 conflicts；标准路径上服务层先生效。"
            ),
    ),
    ParameterSpec(
        name="wanted_list",
        value_type="string_list",
        required=True,
        source="collector_validation",
        enforced=False,
        description=(
            "两站一致：必填、非空 list；元素类型未校验（注解 list[str]， "
            "无元素 isinstance）。声明（collector_catalog.py:755）required 含本键。"
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
            "声明（collector_catalog.py:756）只写 string；实现是封闭枚举， "
            "两站集合与默认值一致。"
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
            "unchecked：两站均无类型校验；任意值原样持久化并按真值使用——字符串 "
            "\"false\" 也是真值、会被当作开启落盘。"
            ),
    ),
    ParameterSpec(
        name="rules_path",
        value_type="string",
        required=False,
        source="collector_validation",
        enforced=False,
        description=(
            "unchecked：无类型校验；非字符串在采集期按类型抛不同异常（dict 在 "
            "os.path.exists 处 TypeError）。"
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
            "两站不一致：服务层只查非空字符串（:1219），http(s)/私网检查只在类级、 "
            "采集期才拒绝（见 conflicts）。"
            ),
    ),
    ParameterSpec(
        name="wait_for",
        value_type="enum",
        required=False,
        source="collector_validation",
        default="load",
        allowed_values=("load", "networkidle", "domcontentloaded",),
        description="两站同一集合与默认值；声明（collector_catalog.py:135）只写 string。",
    ),
    ParameterSpec(
        name="extract_mode",
        value_type="enum",
        required=False,
        source="collector_validation",
        default="text",
        allowed_values=("text", "html", "screenshot",),
        description="两站同一集合与默认值；声明（collector_catalog.py:136）只写 string。",
    ),
    ParameterSpec(
        name="wait_selector",
        value_type="string",
        required=False,
        source="collector_validation",
        description=(
            "服务层（标准路径生效站）：None/non-str/空白串拒绝，strip 后持久化， "
            "未传归一 None；类级：只拒 non-str，空白串放行且不 "
            "strip——两站对空白串判定不一致（见 conflicts）。"
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
            "必填非空字符串。服务层不校验，采集期才拒绝。建源路径可缺键； "
            "quick_collect 路径有默认值，故表现为可以传 null 或非法串，而不是缺键。"
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
            "整数 1 到 500（含端点）。实现用 int() 强转而非类型检查， "
            "因此数字字符串与浮点被接受、True 变 1。无法转换时抛裸异常：字符串抛 "
            "ValueError，null 或字典抛 TypeError，两者都由执行层兜底为失败任务。"
            ),
    ),
    ParameterSpec(
        name="include_paths",
        value_type="string_list",
        required=False,
        source="collector_validation",
        default=[],
        description=(
            "无类型/元素校验，真值即原样转发（传非空字符串也照发）。 "
            "未声明于 COLLECTOR_CATALOG.config_schema（:344-347）， "
            "但端点元数据已公告（collectors.py:3131）。"
            ),
    ),
    ParameterSpec(
        name="exclude_paths",
        value_type="string_list",
        required=False,
        source="collector_validation",
        default=[],
        description=(
            "同 include_paths：无校验、真值即原样转发； "
            "未声明于 config_schema 但端点元数据已公告（collectors.py:3131）。"
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
        description="服务层 passthrough 不查；采集期才拒绝（失败任务运行，非 400）。",
    ),
    ParameterSpec(
        name="prompt",
        value_type="string",
        required=False,
        source="collector_validation",
        default="",
        description=(
            "未声明于 config_schema（:353），但实现读取、转发， "
            "端点元数据已公告（collectors.py:3147）。 "
            "与 schema 至少提供其一（:237-240）。 "
            "`.strip()` 仅对 str 有效：键存在且为 JSON null/数字时抛 "
            "AttributeError（未包装非 CollectorError）。"
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
            "Apify Actor 标识，必须是 owner/name 形态。服务层只要求非空字符串， "
            "类级还强制该形态，标准路径上以更严的类级为准。经 quick_collect 时 95 "
            "个已登记端点由服务端注入常量、调用方无法覆盖；apify_tiktok_shop_search_v2 "
            "不在该表内，须由调用方提供。"
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
            "抓取条数上限，整数 1 到 1000，默认 20，标准路径以服务层严格校验为准。 "
            "经 quick_collect 时入口总提供该键，未传为 10， "
            "并接受别名 maxItems；该别名只对已登记端点有效。 "
            "类级的宽松分支在标准路径上不可达，见分歧记录。"
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
            "Actor 运行计费上限，必须严格大于 0。服务层默认 1.0， "
            "类级与 quick_collect 入口默认 3.0， "
            "两处不一致。它不是限流开关：触顶会让按事件计费的 Actor 直接中止。"
            ),
    ),
    ParameterSpec(
        name="run_timeout_seconds",
        value_type="number",
        required=False,
        source="collector_validation",
        default=600.0,
        description=(
            "Actor 运行等待上限（秒）。目录声明 integer（collector_catalog.py:123）， "
            "但唯一支持它的类级实现经 float() 强转接受 int/float/数值字符串、 "
            "无范围检查（结果 float），故按实现登记为 number。"
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
            "可选。非空字符串且按 / 切分至少 2 段时，owner/repo 取最后两段且跳过 "
            "owner/repo 校验；实现不校验域名必须是 github.com。 "
            "非字符串值被忽略并回落 owner/repo 必填。 "
            "服务层返回值被持久化为 source/task.config，url 键本身被丢弃。"
            ),
    ),
    ParameterSpec(
        name="owner",
        value_type="string",
        required=True,
        source="collector_validation",
        description=(
            "strip 后非空的字符串。服务层仅在未提供可用 url 时必填；类层无条件必填， "
            "视为恒定必填。"
            ),
    ),
    ParameterSpec(
        name="repo",
        value_type="string",
        required=True,
        source="collector_validation",
        description="同 owner 的约束与条件。",
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
        description="strip 后非空字符串；两处判定相同。",
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
            "严格 isinstance(int)：浮点与数字字符串被拒绝（与 twscrape "
            "的强转模式相反）。"
            ),
    ),
    ParameterSpec(
        name="site",
        value_type="string",
        required=False,
        source="collector_validation",
        description="可选字符串；None 合法。",
    ),
    ParameterSpec(
        name="tag",
        value_type="string",
        required=False,
        source="collector_validation",
        description=(
            "可选字符串，无枚举限制（ANYSEARCH_KNOWN_TAGS 定义于 "
            "anysearch_collector.py:24-26， "
            "全仓库无其他引用）。catalog 未声明；透传上游 payload（:45-46）。"
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
        description="strip 后非空字符串（require_text 定义于 collectors/base.py:96-100）。",
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
            "int() 强转后再查范围：数字字符串（\"50\"）与浮点（截断）都被接受； "
            "非法值（如 \"abc\"）抛裸 ValueError/TypeError 而非 CollectorError。 "
            "审计类型不符成立。"
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
            "大小写敏感，仅三个值；catalog 只声明为 "
            "string（collector_catalog.py:190），枚举仅存在于实现。"
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
        description="strip 后非空字符串。",
    ),
    ParameterSpec(
        name="limit",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=50,
        minimum=1,
        maximum=3200,
        description="int() 强转，接受数字字符串/浮点；范围检查在转换之后。审计类型不符成立。",
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
        description="strip 后非空字符串；两处判定相同。",
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
            "strip 并转小写后匹配；空字符串合法，等于不过滤， "
            "也是默认值。传入非字符串会在调用 strip 时抛属性错误， "
            "由执行层兜底为失败任务。"
            ),
    ),
    ParameterSpec(
        name="lang",
        value_type="enum",
        required=False,
        source="collector_validation",
        default="all",
        allowed_values=("zh", "en", "all",),
        description="空串会被拒绝（不在集合内）。",
    ),
    ParameterSpec(
        name="min_score",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=70,
        minimum=0,
        maximum=100,
        description="int() 强转，接受数字字符串/浮点；0 合法。审计类型不符成立。",
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
            "int() 强转。此类型 catalog 声明的 limit 与实现一致（audit 中 name "
            "问题不适用于它），问题仅在强转。"
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
            "可选；但 tag/username/keyword 三者至少一个 strip 后非空（三选一组合必填， "
            "任一单参数都不单独必填）。.strip() 无 isinstance 检查：非字符串抛 "
            "AttributeError。"
            ),
    ),
    ParameterSpec(
        name="username",
        value_type="string",
        required=False,
        source="collector_validation",
        default="",
        description="参与三选一必填组合；catalog 未声明。",
    ),
    ParameterSpec(
        name="keyword",
        value_type="string",
        required=False,
        source="collector_validation",
        default="",
        description="参与三选一必填组合；透传为 Dev.to API 的 search 参数。",
    ),
    ParameterSpec(
        name="max_items",
        value_type="integer",
        required=False,
        source="collector_validation",
        default=20,
        minimum=1,
        maximum=100,
        description="int() 强转，接受 \"20\"/浮点；实际分页参数（per_page，:114）。",
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
            "硬必填（非空字符串），却是 catalog 未声明参数：catalog required=[] 且 "
            "properties 只有 "
            "category/limit（src/data_intelligence_hub/services/collector_catalog.py:3 "
            "71-374）。注意经 quick_collect 会先注入默认 "
            "keyword=python（api/routes/quick_collect.py:358）， "
            "故快采路径不传也能通过。"
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
        description="int() 强转；catalog 未声明（声明的是从不被读的 limit）。",
    ),
    ParameterSpec(
        name="category",
        value_type="string",
        required=False,
        source="collector_validation",
        default="",
        description=(
            "任意字符串，无枚举检查（_CATE_MAP 定义于 :164-172， "
            "全仓库仅此定义处被命中，未参与校验或请求）。被读取但不影响行为：collect() "
            "的 payload 只含 key_word/search_type（:196-199）。 "
            "非字符串抛 AttributeError。"
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
            "必填非空字符串。会被清洗为裸 publication 名——去掉协议前缀、 "
            "斜杠与 .substack.com 后缀，再拼成订阅源地址。 "
            "目录声明的 publication_url 从不被读取。"
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
        description="int() 强转；catalog 未声明。RSS item 截取上限（:320）。",
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
            "硬必填；catalog 声明的 query（collector_catalog.py:299-302）从不被读。 "
            "经 quick_collect 时 keyword 有默认值 "
            "python（api/routes/quick_collect.py:354）， "
            "且用户传 query 不会报错——只会被忽略并按默认 keyword 采集。"
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
        description="int() 强转；catalog 声明的 limit 从不被读。",
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
            "硬必填；catalog 声明的 query（collector_catalog.py:308-311）从不被读。 "
            "quick_collect 默认注入 "
            "keyword=python（api/routes/quick_collect.py:355）， "
            "传 query 会被静默忽略。"
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
        description="int() 强转；catalog 声明的 limit 从不被读。",
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
            "硬必填；catalog 声明的 query（collector_catalog.py:317-320）从不被读。 "
            "quick_collect 默认注入 "
            "keyword=python（api/routes/quick_collect.py:356）。"
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
        description="int() 强转；catalog 声明的 limit 从不被读。",
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
        description="strip 后非空字符串（自然语言任务描述）。",
    ),
    ParameterSpec(
        name="url",
        value_type="string",
        required=False,
        source="collector_validation",
        default="",
        description=(
            "可选；非空时必须是绝对 http/https URL， "
            "且主机不得为 localhost/127.0.0.1/::1/192.168.* 段。 "
            ".strip() 无 isinstance 检查：非字符串抛 AttributeError。"
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
        description="int() 强转：接受 \"10\"/浮点；范围检查在转换之后。审计类型不符成立。",
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
            "必填、非空 string、62 值封闭枚举；两处站点判定一致。 "
            "枚举在四处重复（collector_catalog.py:1091-1154、tikhub_social.py:39、 "
            "quick_collect.py:32-93、_build_params 分支 :1394-1625）， "
            "AST 核对为同一集合、无共享常量。"
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
            "标准路径：int 且 1–100，缺省 20，否则 API 层 400。 "
            "边角：isinstance(True, int) 为真， "
            "JSON true 两层均按 1 放行。类层较松的 str 分支只影响绕过服务层的路径（见 "
            "conflicts）。"
            ),
    ),
    ParameterSpec(
        name="keyword",
        value_type="string",
        required=False,
        source="collector_validation",
        enforced=False,
        description=(
            "unchecked：任一校验站点都不做类型检查，任意 JSON 值（如 "
            "keyword=123）原样到达 _build_params 并作为上游参数发出； "
            "空值经 `or \"\"` 兜底为空串。多数端点实际强依赖 keyword（空串上游 "
            "400/422），校验不拦。"
            ),
    ),
    ParameterSpec(
        name="unique_id",
        value_type="string",
        required=False,
        source="collector_validation",
        enforced=False,
        description=(
            "unchecked（同 keyword）：无类型/非空校验， "
            "空值 `or \"\"` 兜底；读取处带 username 回退。"
            ),
    ),
    ParameterSpec(
        name="ch_id",
        value_type="string",
        required=False,
        source="collector_validation",
        enforced=False,
        description=(
            "unchecked。回退键 hashtag_id 同样未在 config_schema 声明（见 "
            "undeclared_but_read）。"
            ),
    ),
    ParameterSpec(
        name="user_id",
        value_type="string",
        required=False,
        source="collector_validation",
        enforced=False,
        description=(
            "unchecked。:1510 的 camelCase 回退 `config.get(\"userId\")` "
            "在标准路径不可达（userId 不在白名单、入库前即被丢弃， "
            "见 conflicts 第 2 项）。"
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
