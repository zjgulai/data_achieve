"""Frozen taxonomy v1 for the maternity support band category.

The code set is adapted from the prior BumpEase G4 taxonomy (same product
category) and trimmed to codes that this corpus can actually support.  Every
code carries a definition, include and exclude rules.  The version string is
part of every annotation, so a later taxonomy change cannot silently rewrite
history.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

TAXONOMY_VERSION = "VOC-BAND-v1.1"
TAXONOMY_FROZEN_AT = "2026-10-30T12:00:00+08:00"
TAXONOMY_SUPERSEDES = "VOC-BAND-v1.0"

# The frozen LLM artifact ``llm-coding/coded/ALL.jsonl`` was produced under
# v1.0.  Decision B changes only the SUP boundary rules and keeps every code,
# so the artifact is not re-coded; its annotations stay stamped v1.0.
CODED_ARTIFACT_TAXONOMY_VERSION = "VOC-BAND-v1.0"

TAXONOMY_REVISION_NOTE = (
    "裁决 B（support 族）：四个 SUP code 全部保留，include/exclude 重写为互斥规则，"
    "并增加强制优先级：BELLY_LIFT > weight PRESSURE_OFFLOAD > BACK > "
    "relief PRESSURE_OFFLOAD > GENERAL。code 集合不变；现有 coded/ALL.jsonl "
    "是 v1.0 产物，未重新编码。"
)

LANGUAGES = {"en"}

# SUP family lexicons.  These are also consumed by the rule coder and by
# tools/check_support_exclusivity.py, so the priority rules and the code
# definitions cannot drift apart.
_SUP_GENERAL_LEXICON = ("support", "supportive")
_SUP_BACK_LEXICON = ("back pain", "backache", "lower back", "back support", "my back")
_SUP_WEIGHT_LEXICON = (
    "weight off",
    "weight is lifted",
    r"take(?:s|n)? (?:the )?weight",
    "pressure off",
)
_SUP_RELIEF_LEXICON = (
    r"reliev(?:e|es|ed|ing)",
    "relief",
    r"eas(?:e|es|ed|ing)",
    r"take(?:s|n)? away",
)
_SUP_PRESSURE_LEXICON = _SUP_WEIGHT_LEXICON + _SUP_RELIEF_LEXICON
_SUP_BELLY_LIFT_LEXICON = (
    r"lift(?:s|ing|ed)?(?: and support)? (?:that |my |your |the )?(?:big )?(?:belly|bump|bundle|baby)",
    r"hold(?:s|ing)? up (?:my |the |her )?(?:little )?(?:bump|belly|bundle|baby)",
    "belly lift",
    "托起肚子",
)

# Decision B §3.1: apply these rules in order.  The first rule that matches
# the evidence span wins; later rules do not also fire.  Step 2 deliberately
# precedes step 3, so "the weight off my pelvis and lower back" is PRESSURE,
# not BACK, even though it contains the literal "lower back".
SUP_RESOLUTION_ORDER = [
    {
        "step": 1,
        "code": "SUP.BELLY_LIFT",
        "condition": "lift / hold up + belly / bump / bundle / baby",
        "lexicon": _SUP_BELLY_LIFT_LEXICON,
    },
    {
        "step": 2,
        "code": "SUP.PRESSURE_OFFLOAD",
        "condition": "weight or load transfer: weight off, takes the weight, weight is lifted, pressure off",
        "lexicon": _SUP_WEIGHT_LEXICON,
    },
    {
        "step": 3,
        "code": "SUP.BACK",
        "condition": "explicit back or waist reference, and no step-2 weight/load transfer",
        "lexicon": _SUP_BACK_LEXICON,
    },
    {
        "step": 4,
        "code": "SUP.PRESSURE_OFFLOAD",
        "condition": "relief / ease / take away + pain or pressure, and no back reference",
        "lexicon": _SUP_RELIEF_LEXICON,
    },
    {
        "step": 5,
        "code": "SUP.GENERAL",
        "condition": "generic support only: no body part, weight/load, or belly lift",
        "lexicon": _SUP_GENERAL_LEXICON,
    },
]


@dataclass(frozen=True)
class Code:
    code: str
    axis: str  # aspect | context | journey | outcome | gap | medical
    label: str
    definition: str
    include: str
    exclude: str
    lexicon: tuple[str, ...]


ASPECTS: list[Code] = [
    Code("SUP.GENERAL", "aspect", "总体支撑", "对支撑效果的评价；仅在没有部位、没有重量转移、没有托起肚子语义时使用。", "support, supportive, holds me（兜底）", "back pain / lower back / back support / my back → BACK；weight off / take the weight / weight is lifted → PRESSURE；lift my belly / hold up bump / holding up her bundle → BELLY_LIFT；comfortable / soft → COM.*", _SUP_GENERAL_LEXICON),
    Code("SUP.BACK", "aspect", "背部支撑", "对下背、腰部支撑或该部位疼痛缓解的评价。", "back pain, backache, lower back, back support, my back", "weight off / take the weight / weight is lifted（即使同句有 lower back）→ PRESSURE；无背部指向的 support → GENERAL；姿势/运动", _SUP_BACK_LEXICON),
    Code("SUP.PRESSURE_OFFLOAD", "aspect", "压力卸载", "对重量被卸掉、负载/压力被转移，或疼痛/压力得到缓解的评价。", "weight off, takes the weight, weight is lifted, pressure off, relieve/ease/take away pain or pressure", "仅描述松紧；单纯 support → GENERAL/BACK；点名 lower back/back pain 且无 weight/load 语义 → BACK；lift/hold up belly → BELLY_LIFT；weightless 仅描述带子本身轻 → APP.LOW_PROFILE/COM.*；缓解来自其他物品/行为 → 不标", _SUP_PRESSURE_LEXICON),
    Code("SUP.BELLY_LIFT", "aspect", "腹部托举", "明确描述把肚子托起来、兜住或托举。", "lift my belly, lift your belly, hold up bump, holding up her little bundle, 托起肚子", "仅说 support → GENERAL；仅说 weightless → PRESSURE/COM.*", _SUP_BELLY_LIFT_LEXICON),
    Code("FIT.SIZE_ACCURACY", "aspect", "尺码准确", "尺码是否与标注/预期一致。", "true to size, runs small/large, size up/down", "只问该买哪个码", ("true to size", "runs? (?:small|large|big)", "size up", "size down", "sizing", "size chart", "my size", "medium", "large", "small")),
    Code("FIT.BODY_SHAPE", "aspect", "体型适配", "腹型、躯干、身高、plus size 对适配的影响。", "short/long torso, plus size, body shape", "泛指尺码", ("body shape", "torso", "plus size", "curvy", "petite", "tall")),
    Code("FIT.GROWTH_RANGE", "aspect", "孕期增长区间", "随孕周/肚子增长是否仍可用。", "as bump grows, later pregnancy, third trimester", "单次静态穿着", ("as (?:my )?bump grows", "grow(?:s|ing)?", "later (?:in )?pregnancy", "third trimester", "weeks? (?:3[0-9]|4[0-2])")),
    Code("FIT.COVERAGE", "aspect", "覆盖范围", "支撑带覆盖面积是否足够。", "coverage, wide enough, covers", "颜色覆盖", ("coverage", "covers?", "wide enough", "too narrow")),
    Code("ADJ.STRAP_DESIGN", "aspect", "带体/绑带设计", "绑带、魔术贴、扣件等结构。", "strap, band, velcro, hook", "整体支撑评价", ("strap", "velcro", "hook", "band design", "waistband")),
    Code("ADJ.DONNING", "aspect", "穿脱难度", "穿上、脱下、调整的难易。", "put on, take off, get on", "首次购买", ("put(?:ting)? (?:it )?on", "take (?:it )?off", "get it on", "on and off")),
    Code("ADJ.RANGE_TENSION", "aspect", "松紧调节", "可调节范围与张力是否合适。", "adjust, tighten, loosen, tension", "不可调结构", ("adjust", "tighten", "loosen", "tension", "too tight", "too loose")),
    Code("STB.STAY_IN_PLACE", "aspect", "保持位置", "是否下滑、卷边、移位。", "slip, slide, roll down, bunch", "支撑不足", ("slip", "slides?", "roll(?:s|ed)? down", "roll(?:s|ed)? up", "bunch", "stay in place", "move around", "shift")),
    Code("STB.STRAP_POSITION", "aspect", "绑带位置", "绑带是否压到不合适的位置。", "dig into, strap position", "单纯紧", ("dig(?:s|ging)? into", "strap position", "rides up")),
    Code("COM.SOFTNESS", "aspect", "柔软触感", "面料柔软、亲肤。", "soft, cozy, gentle", "支撑", ("soft", "cozy", "gentle", "comfortable fabric")),
    Code("COM.BREATHABILITY_HEAT", "aspect", "透气与发热", "闷热、出汗、透气性。", "breathable, hot, sweat", "环境温度", ("breathable", "air flow", "ventilat", "sweat", "sweaty", "too hot", "warm")),
    Code("COM.SKIN_CHAFE", "aspect", "皮肤摩擦", "摩擦、红印、瘙痒、皮疹。", "chafe, rub, rash, itch", "压力痛", ("chafe", "chafing", "rub(?:s|bing)?", "rash", "itch", "red marks?")),
    Code("COM.PRESSURE_DIGGING", "aspect", "局部压迫", "局部压痛、勒痕、digging。", "dig, cut into, pressure point", "皮肤摩擦", ("dig(?:s|ging)?", "cut(?:s|ting)? into", "pressure point", "leave marks")),
    Code("COM.WEAR_TOLERANCE", "aspect", "长时间穿着", "能否全天或长时间穿着。", "all day, for hours, long wear", "单次短时", ("all day", "for hours", "long(?:er)? wear", "every day")),
    Code("COM.GENERAL", "aspect", "总体舒适", "整体舒适度评价。", "comfortable, comfort", "具体部位", ("comfortable", "comfort", "uncomfortable")),
    Code("APP.UNDER_CLOTHING", "aspect", "衣下表现", "穿在衣服下是否可见、是否臃肿。", "under clothes, invisible, not visible", "外穿", ("under (?:my )?clothes", "under clothing", "invisible", "not visible", "show through", "under a shirt")),
    Code("APP.LOW_PROFILE", "aspect", "轻薄低体积", "体积小、不臃肿、低调。", "low profile, slim, thin, discreet", "面料厚薄本身", ("low profile", "slim", "thin", "discreet", "bulky", "bulk")),
    Code("APP.COLOR_AESTHETIC", "aspect", "颜色外观", "颜色、外观是否喜欢。", "color, cute, looks", "功能", ("color", "cute", "looks", "aesthetic")),
    Code("MAT.FABRIC", "aspect", "面料", "面料材质本身。", "fabric, material", "舒适评价", ("fabric", "material")),
    Code("MAT.DURABILITY", "aspect", "耐用性", "洗后/长期使用是否损坏。", "durable, fell apart, after washes", "单次", ("durable", "fell apart", "wore out", "after (?:a few )?wash", "falling apart")),
    Code("MAT.ELASTICITY_RETENTION", "aspect", "弹性保持", "是否被撑松、失去弹性。", "stretched out, lost elasticity", "初始弹性", ("stretch(?:ed)? out", "lost (?:its )?elasticity", "elastic")),
    Code("MAT.THICKNESS", "aspect", "厚薄", "厚薄程度。", "thick, thin", "体积", ("thick", "thin")),
    Code("MAT.CARE", "aspect", "清洗护理", "清洗、晾干、护理要求。", "wash, dryer, care", "耐用性", ("wash", "washing", "dryer", "laundry")),
    Code("VAL.PRICE_VALUE", "aspect", "价格价值", "价格是否值、性价比。", "price, expensive, worth, cheap", "赠品", ("price", "expensive", "cheap", "worth", "money", "cost", "overpriced")),
    Code("CX.RETURN_EXCHANGE", "aspect", "退换", "退货、换货、退款体验。", "return, exchange, refund", "犹豫是否买", ("return", "returned", "exchange", "refund")),
    Code("FUL.PRODUCT_CONDITION", "aspect", "到货状态", "包装、到货、二手痕迹。", "arrived, package, damaged", "物流时效", ("arrived", "package", "damaged", "used")),
    Code("GEN.OVERALL_EVALUATION", "aspect", "总体评价", "对产品的整体好恶。", "overall, love it, hate it, recommend", "单一属性", ("overall", "love it", "hate it", "would recommend", "recommend")),
    Code("USE.LAYERING", "aspect", "穿着方式", "内穿/外穿/叠穿方式。", "over clothes, under shirt, layering", "衣下可见性", ("over (?:my )?clothes", "under (?:a )?shirt", "layering", "over a dress")),
    Code("ACT.COMPATIBILITY", "aspect", "活动兼容", "走路、跑步、工作、站立、坐着、睡觉时的可用性。", "walking, running, work, standing, sitting, sleeping", "静态合身", ("walking", "walk", "running", "run", "work", "standing", "sit(?:ting)?", "sleep", "exercise", "chase")),
    Code("SAF.PRESSURE_PLACEMENT", "aspect", "受力位置安全", "对腹部受力位置的安全担忧。", "pressure on belly, too much pressure", "一般不适", ("pressure on (?:my )?belly", "too much pressure", "unsafe")),
]

CONTEXTS: list[Code] = [
    Code("CTX.PREGNANCY_T2", "context", "孕中期", "孕 13–27 周。", "second trimester, week 14-27", "产后", ("second trimester", "trimester 2", "weeks? 1[3-9]", "weeks? 2[0-7]")),
    Code("CTX.PREGNANCY_T3", "context", "孕晚期", "孕 28 周以后。", "third trimester, week 28+", "孕中期", ("third trimester", "trimester 3", "weeks? (?:2[8-9]|3[0-9]|4[0-2])")),
    Code("CTX.BODY_PLUS_SIZE", "context", "plus size", "自述 plus size 或大码需求。", "plus size, curvy, 2x", "一般体型", ("plus size", "curvy", "2x", "3x", "bigger body")),
    Code("CTX.BODY_TALL_LONG_TORSO", "context", "高个/长躯干", "自述高个或长躯干。", "tall, long torso", "短躯干", ("tall", "long torso")),
    Code("CTX.BODY_SHORT_TORSO", "context", "矮个/短躯干", "自述矮个或短躯干。", "short torso, petite", "长躯干", ("short torso", "petite")),
    Code("CTX.MULTIPLES", "context", "多胎", "双胞胎/多胎。", "twins, multiples", "单胎", ("twins", "multiples")),
    Code("CTX.ACTIVITY_WORK", "context", "工作场景", "上班/职业场景。", "at work, desk, nurse, teacher", "休闲", ("at work", "desk job", "nurse", "teacher", "on my feet")),
    Code("CTX.ACTIVITY_EXERCISE", "context", "运动场景", "跑步、健身、瑜伽等。", "running, gym, yoga, exercise", "日常走路", ("running", "gym", "yoga", "exercise", "workout")),
    Code("CTX.DURATION_ALL_DAY", "context", "全天佩戴", "全天或接近全天。", "all day, 8 hours", "短时", ("all day", "8 hours", "whole day")),
    Code("CTX.PURCHASE_GIFT", "context", "他人购买", "作为礼物或替他人买。", "gift, for my wife, bought for", "自购", ("gift", "for my wife", "for my daughter", "bought for")),
    Code("CTX.SENSITIVE_SKIN", "context", "敏感肌", "自述皮肤敏感。", "sensitive skin, eczema", "普通皮肤", ("sensitive skin", "eczema")),
    Code("CTX.POSTPARTUM", "context", "产后", "产后使用。", "postpartum, after birth", "孕期", ("postpartum", "after birth", "post partum")),
]

JOURNEYS: list[Code] = [
    Code("JNY.CONSIDERATION", "journey", "考虑比较", "选购前的比较与求推荐。", "looking for, recommend, which one, vs", "已购买", ("looking for", "recommend", "which one", "vs", "any suggestions")),
    Code("JNY.SIZE_SELECTION", "journey", "选码", "选码阶段的疑问或失误。", "what size, size chart", "使用后", ("what size", "which size", "size chart", "size up")),
    Code("JNY.FIRST_FITTING", "journey", "首次穿戴", "刚收到、第一次试穿。", "just got, first time, tried on", "长期使用", ("just got", "first time", "tried (?:it )?on", "arrived today")),
    Code("JNY.USE", "journey", "使用体验", "日常使用中的体验。", "wearing, used it", "选购", ("wearing", "wore", "used it", "using it")),
    Code("JNY.CARE", "journey", "护理耐用", "清洗与长期耐用。", "washed, after weeks", "首次", ("washed", "after (?:a few )?weeks", "laundry")),
    Code("JNY.RETURN", "journey", "退换", "退货换货阶段。", "returned, refund", "使用中", ("returned", "refund", "exchange")),
    Code("JNY.RECOMMEND", "journey", "推荐复购", "推荐他人或复购。", "recommend, buy again", "首次购买", ("recommend", "buy again", "repurchase")),
]

OUTCOMES: list[Code] = [
    Code("OUT.RELIEF", "outcome", "缓解", "疼痛或不适得到缓解。", "relief, helped", "无变化", ("relief", "relieved", "helped", "helps")),
    Code("OUT.ACTIVITY_ENABLED", "outcome", "恢复活动", "能继续走路/工作/运动。", "able to walk, can move", "仍受限", ("able to (?:walk|move|work)", "can walk", "kept walking")),
    Code("OUT.NO_BENEFIT", "outcome", "无感", "没有感觉到帮助。", "didn't help, no difference, useless", "轻微帮助", ("didn'?t help", "no difference", "useless", "did nothing", "no relief")),
    Code("OUT.LIMITED_USE", "outcome", "受限使用", "只能短时或特定场景使用。", "only wear, can't wear all day", "全天可用", ("only (?:wear|use)", "can'?t wear", "couldn'?t wear", "too uncomfortable to wear")),
    Code("OUT.RETURN_INTENT", "outcome", "退货意向", "打算或已经退货。", "returning, sent back", "继续使用", ("returning", "sent it back", "send it back")),
    Code("OUT.RECOMMEND", "outcome", "推荐", "愿意推荐给他人。", "recommend, told my friend", "不推荐", ("recommend", "told my", "recommended")),
    Code("OUT.REGRET", "outcome", "后悔", "后悔购买。", "regret, waste of money", "满意", ("regret", "waste of money", "wish I")),
    Code("OUT.CONTINUED_USE", "outcome", "继续使用", "仍在使用/每天使用。", "still wearing, every day", "已弃用", ("still wear", "still using", "every day")),
]

GAPS: list[Code] = [
    Code("GAP.FIT_MISMATCH", "gap", "适配落差", "预期合身但实际不合身。", "didn't fit, too small/large", "无预期", ("didn'?t fit", "doesn'?t fit", "too small", "too big", "too tight", "too loose")),
    Code("GAP.SUPPORT_MISMATCH", "gap", "支撑落差", "预期更强支撑但未兑现。", "not supportive enough, expected more support", "无预期", ("not supportive enough", "expected more support", "not enough support", "support was lacking")),
    Code("GAP.VALUE_MISMATCH", "gap", "价值落差", "价格与体验不匹配。", "not worth, overpriced", "无价格提及", ("not worth", "overpriced", "waste of money")),
    Code("GAP.MATCHED", "gap", "符合预期", "明确说符合或超出预期。", "exactly what I needed, as expected", "无预期", ("exactly what i needed", "as expected", "lived up to")),
]

MEDICAL: list[Code] = [
    Code("MED.PAIN_SELF_REPORT", "medical", "疼痛自述", "自述疼痛或不适（只记录，不判断）。", "pain, hurt, ache, sciatica", "一般不适", ("pain", "hurt", "ache", "sciatica", "pelvic pain")),
    Code("MED.MEDICAL_HISTORY", "medical", "病史自述", "自述疾病或状况。", "SPD, PGP, pubic symphysis, polyhydramnios", "无", ("spd", "pgp", "pubic symphysis", "polyhydramnios", "placenta")),
    Code("MED.PRESSURE_SAFETY", "medical", "受力安全信号", "担心压迫腹部或胎儿。", "pressure on baby, unsafe", "无", ("pressure on (?:my )?baby", "unsafe for (?:the )?baby", "too much pressure")),
]

ALL_CODES: list[Code] = ASPECTS + CONTEXTS + JOURNEYS + OUTCOMES + GAPS + MEDICAL


def taxonomy_dict() -> dict[str, Any]:
    return {
        "taxonomy_id": TAXONOMY_VERSION,
        "supersedes": TAXONOMY_SUPERSEDES,
        "frozen_at": TAXONOMY_FROZEN_AT,
        "revision_note": TAXONOMY_REVISION_NOTE,
        "resolution_rules": [
            {
                "step": rule["step"],
                "code": rule["code"],
                "condition": rule["condition"],
                "lexicon": list(rule["lexicon"]),
            }
            for rule in SUP_RESOLUTION_ORDER
        ],
        "languages": sorted(LANGUAGES),
        "axes": {
            "aspect": [c.code for c in ASPECTS],
            "context": [c.code for c in CONTEXTS],
            "journey": [c.code for c in JOURNEYS],
            "outcome": [c.code for c in OUTCOMES],
            "gap": [c.code for c in GAPS],
            "medical": [c.code for c in MEDICAL],
        },
        "codes": [
            {
                "code": c.code,
                "axis": c.axis,
                "label": c.label,
                "definition": c.definition,
                "include": c.include,
                "exclude": c.exclude,
                "lexicon": list(c.lexicon),
            }
            for c in ALL_CODES
        ],
        "polarity_enum": ["positive", "qualified_positive", "negative", "qualified_negative", "mixed", "unknown"],
        "rules": [
            "unknown 不等于 negative",
            "mixed 保留正负两个 component；正负同等 material 且同一子句拆不开时用 mixed",
            "没有 polarity cue 时记 unknown，不默认负向",
            "qualified_positive：总体正向，且同一属性上带实质性程度/条件保留（almost / mostly / some / somewhat / just enough / only / not fully / compared with X it is less）；保留必须可引用、不能拆成独立负向 aspect，总体仍归 positive family",
            "qualified_negative：总体负向，且同一属性上带实质性程度/条件保留（hedge 或让步）；保留必须可引用、不能拆成独立正向 aspect，总体仍归 negative family。与 qualified_positive 对称",
            "polarity family：positive + qualified_positive 同族；negative + qualified_negative 同族；mixed / unknown 不进方向统计的分子或分母",
            "medical code 只记录 self-report，不形成功效或安全判断",
        ],
    }
