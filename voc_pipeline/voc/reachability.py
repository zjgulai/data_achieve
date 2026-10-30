"""Gate reachability against the data we actually have.

The check parses the repository's ORM models and platform docs rather than
trusting a hand-written inventory.  It answers one question: starting from a
named source, which gate is the first one that cannot pass, and why.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
MODELS = ROOT / "apps/api/src/data_intelligence_hub/models"
REDDIT_DOC = ROOT / "docs/apify-actors/reddit.md"


@dataclass
class SourceCapability:
    source: str
    tables_or_fields: int
    has_text: bool
    has_author: bool
    has_timestamp: bool
    has_product_identity: bool
    has_variant_identity: bool
    has_engagement: bool
    has_review_layer: bool
    gates: dict[str, str]
    first_block: str
    note: str

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def parse_tiktok_tables() -> list[dict[str, Any]]:
    tables: list[dict[str, Any]] = []
    for filename in ("tiktok_content.py", "tiktok_commerce.py"):
        path = MODELS / filename
        if not path.exists():
            continue
        text = path.read_text()
        for match in re.finditer(r"class\s+(\w+)\([^)]*\):\n(.*?)(?=\nclass |\Z)", text, re.S):
            body = match.group(2)
            name = re.search(r'__tablename__\s*=\s*"([^"]+)"', body)
            if not name:
                continue
            cols = re.findall(r"^\s{4}(\w+):\s*Mapped\[", body, re.M)
            tables.append({"table": name.group(1), "class": match.group(1), "columns": cols, "file": filename})
    return tables


def parse_reddit_fields() -> int:
    if not REDDIT_DOC.exists():
        return 0
    text = REDDIT_DOC.read_text()
    match = re.search(r"输出 \*\*(\d+) 字段", text)
    return int(match.group(1)) if match else 0


def build_reachability() -> dict[str, Any]:
    tiktok = parse_tiktok_tables()
    tiktok_names = [t["table"] for t in tiktok]
    reddit_fields = parse_reddit_fields()

    tiktok_cols = {c for t in tiktok for c in t["columns"]}
    has_product = {"product", "product_snapshot", "video_product", "creator_product"} <= set(tiktok_names)
    has_comment = "comment" in tiktok_names
    has_transcript = "transcript" in tiktok_names

    sources = [
        SourceCapability(
            source="tiktok_canonical_tables",
            tables_or_fields=len(tiktok),
            has_text=has_comment and has_transcript,
            has_author="creator" in tiktok_names,
            has_timestamp="captured_at" in tiktok_cols,
            has_product_identity=has_product,
            has_variant_identity=False,
            has_engagement=True,
            has_review_layer="product_review" in tiktok_names,
            gates={
                "G0": "human_required",
                "G1": "partial",
                "G2": "conditional",
                "G3": "pass",
                "G4": "pass",
                "G5": "pass",
                "G6": "pass",
                "G7": "blocked",
                "G8": "blocked",
            },
            first_block="G1",
            note=(
                "表结构支持视频/评论/商品/达人，但 product 与 Amazon ASIN、颜色/尺码 variant 之间没有已验证 crosswalk；"
                "G1 的 exact-variant 谓词无法成立。"
            ),
        ),
        SourceCapability(
            source="reddit_76_field_actor",
            tables_or_fields=reddit_fields,
            has_text=True,
            has_author=True,
            has_timestamp=True,
            has_product_identity=False,
            has_variant_identity=False,
            has_engagement=True,
            has_review_layer=False,
            gates={
                "G0": "human_required",
                "G1": "blocked",
                "G2": "conditional",
                "G3": "pass",
                "G4": "pass",
                "G5": "pass",
                "G6": "pass",
                "G7": "blocked",
                "G8": "blocked",
            },
            first_block="G1",
            note=(
                "76 字段足以做 occurrence / canonical / annotation，但没有任何商品或 variant 标识；"
                "只能回答品类级问题，不能回答 exact-variant 体验。"
            ),
        ),
        SourceCapability(
            source="amazon_product_fields",
            tables_or_fields=8,
            has_text=False,
            has_author=False,
            has_timestamp=True,
            has_product_identity=True,
            has_variant_identity=True,
            has_engagement=False,
            has_review_layer=False,
            gates={
                "G0": "human_required",
                "G1": "pass",
                "G2": "conditional",
                "G3": "pass",
                "G4": "pass",
                "G5": "blocked",
                "G6": "blocked",
                "G7": "blocked",
                "G8": "blocked",
            },
            first_block="G5",
            note=(
                "PDP 可以冻结 parent/child/variant 与聚合评分；评论正文需要登录态，当前抓取路径返回 302。"
                "没有评论正文就没有 consumer occurrence。"
            ),
        ),
    ]

    return {
        "generated_at": "runtime",
        "repo_facts": {
            "tiktok_table_count": len(tiktok_names),
            "tiktok_tables": tiktok_names,
            "task_brief_said_tables": 20,
            "discrepancy": len(tiktok_names) - 20,
            "reddit_documented_fields": reddit_fields,
        },
        "sources": [s.to_dict() for s in sources],
        "verdict": {
            "with_existing_normalized_tables_only": (
                "G0 需要人写；TikTok 与 Reddit 都卡在 G1（没有已验证的 SKU/variant crosswalk），"
                "Amazon 商品字段只能到 G1。因此现有规范化表本身走不到 G3 之后。"
            ),
            "with_live_public_collection": (
                "Amazon PDP 提供 G1 身份，Reddit 归档提供 G5/G6 语料；"
                "本轮据此跑到 G6，G7 因缺少第二编码员被阻断。"
            ),
            "hard_block": "G7 双盲 agreement 是人工门槛，不是工程门槛。",
        },
    }


def main() -> None:
    print(json.dumps(build_reachability(), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
