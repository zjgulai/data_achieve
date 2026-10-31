#!/usr/bin/env python3
"""KG-07 知识图谱 seed 脚本。

实测结论（2026-10-31，nmem 0.10.111）：
- CLI 与 REST 均无实体 create 端点；实体只能由 extraction 产生，而全局 extraction.active=false
  （gate=fallback_one_shot_model_not_tool_capable），identity/extract 对单条记忆执行后 identity=[]，是 no-op。
- 因此本期（P2 第一阶段）seed 的是「记忆显式关系链」（memories link add），已验证进图
  （graph expand 可见 edges，⌘5 全景图 source-agent 节点 11）。
- relation_type 落库会转小写（RELATES_TO → relates_to），与本体 key 大小写不同属预期。
- 端点约束（from→to）不入本体 patch（S1 裁决），以 linkType labels.zh 承载；建链时人工保证两端语义。

等 extraction 开启后（P2 第二阶段）再补实体抽取；到时用 ontology retype 把默认类型折叠进 26 声明类型。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

SPACE = "source-agent"

LINKS = [
    # 红线簇
    ("ds-l1-01", "ds-l2-04", "RELATES_TO", "身份红线与能力口径关联"),
    ("ds-l1-04", "ds-l3-05", "SUPPORTS_CLAIM", "发布红线与 edge 502 坑互证"),
    ("ds-l1-04", "ds-l3-07", "SUPPORTS_CLAIM", "发布红线与 git 纪律坑互证"),
    ("ds-l1-02", "ds-l3-06", "SUPPORTS_CLAIM", "密钥红线与 compose env 坑互证"),
    ("ds-l1-03", "ds-l1-05", "RELATES_TO", "基础设施红线与双生产纪律关联"),
    # 口径簇
    ("ds-l2-04", "ds-l2-05", "RELATES_TO", "能力计数与端点状态语义关联"),
    ("ds-l2-05", "ds-l3-01", "SUPPORTS_CLAIM", "verified 语义与假绿灯坑互证"),
    ("ds-l2-05", "ds-l3-02", "SUPPORTS_CLAIM", "端点六态与 config-gated 判据互证"),
    ("ds-l2-09", "ds-l2-04", "RELATES_TO", "MCP 工具数与能力计数同属口径"),
    ("ds-l2-06", "ds-l4-05", "RELATES_TO", "证据等级与 VOC 管线边界关联"),
    ("ds-l2-12", "ds-l3-12", "SUPPORTS_CLAIM", "ABI 契约与 ABI 暗坑互证"),
    ("ds-l2-07", "ds-l3-04", "SUPPORTS_CLAIM", "外访约束与 quick-collect 计费坑互证"),
    # 画像簇
    ("ds-l4-01", "ds-l4-02", "RELATES_TO", "能力画像与里程碑关联"),
    ("ds-l4-01", "ds-l2-04", "GROUNDS_IN_RECORD", "画像以能力口径为据"),
    ("ds-l4-07", "ds-l4-06", "RELATES_TO", "报告约定与发布事实关联"),
    ("ds-l4-09", "ds-l2-10", "SUPPORTS_CLAIM", "产品方向与首期不做边界互证"),
    ("ds-l4-03", "ds-l4-04", "RELATES_TO", "32 仓库结论与 Apify 选型关联"),
    ("ds-l4-05", "ds-l4-08", "RELATES_TO", "VOC 边界与历史快照裁决关联"),
]


def existing_links() -> set[tuple[str, str, str]]:
    """收集已建 (source, target, relation) 集，幂等跳过。"""
    seen: set[tuple[str, str, str]] = set()
    ids = {l[0] for l in LINKS} | {l[1] for l in LINKS}
    for mid in sorted(ids):
        r = subprocess.run(["nmem", "--json", "memories", "link", "list", mid, "--space", SPACE],
                           capture_output=True, text=True)
        try:
            d = json.loads(r.stdout)
        except json.JSONDecodeError:
            continue
        for rel in d.get("relations", []):
            seen.add((rel.get("source_memory_id"), rel.get("target_memory_id"),
                      (rel.get("relation_type") or "").lower()))
    return seen


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    have = existing_links()
    ok = skip = fail = 0
    for src, dst, rel, reason in LINKS:
        if (src, dst, rel.lower()) in have:
            print(f"  [skip] {src} -{rel}-> {dst} (已存在)")
            skip += 1
            continue
        if args.dry_run:
            print(f"  [dry] {src} -{rel}-> {dst}")
            continue
        r = subprocess.run(["nmem", "--json", "memories", "link", "add", src, dst,
                            "--type", rel, "--reason", reason, "--space", SPACE],
                           capture_output=True, text=True)
        try:
            d = json.loads(r.stdout)
            if d.get("id"):
                ok += 1
                print(f"  [ok] {src} -{rel}-> {dst}")
            else:
                fail += 1
                print(f"  [fail] {src} -{rel}-> {dst}: {json.dumps(d, ensure_ascii=False)[:100]}")
        except json.JSONDecodeError:
            fail += 1
            print(f"  [fail] {src} -{rel}-> {dst}: {r.stdout[:80]}")
    print(f"DONE ok={ok} skip={skip} fail={fail}")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
