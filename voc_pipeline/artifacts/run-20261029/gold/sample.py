"""Reproducible 50-record gold-set sampler. Fixed seed, sorted pool."""
import json, random, hashlib
from pathlib import Path

RUN = Path("/Users/lute/Project/data_scrapy/voc_pipeline/artifacts/run-20261029")
SEED = 20261030

rows = [json.loads(l) for l in open(RUN / "canonical-records.jsonl")]

tt_pool = sorted(
    [r for r in rows
     if r["source"] == "tiktok_shop"
     and (r.get("source_meta") or {}).get("verified_purchase") is True
     and (r.get("text") or "").strip()],
    key=lambda r: r["canonical_id"],
)
rd_pool = sorted(
    [r for r in rows
     if r["source"] == "reddit"
     and r["product_match"] in {"exact_current_family", "category_adjacent"}],
    key=lambda r: r["canonical_id"],
)

rng = random.Random(SEED)
tt_ids = rng.sample([r["canonical_id"] for r in tt_pool], 25)
rd_ids = rng.sample([r["canonical_id"] for r in rd_pool], 25)

by_id = {r["canonical_id"]: r for r in rows}
sample = [by_id[i] for i in tt_ids + rd_ids]

manifest = {
    "seed": SEED,
    "method": "sort pool by canonical_id ascending; random.Random(seed).sample(ids, 25) per stratum",
    "tiktok_pool_n": len(tt_pool),
    "reddit_pool_n": len(rd_pool),
    "tiktok_ids": tt_ids,
    "reddit_ids": rd_ids,
}
(RUN / "gold" / "sampling-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

with open(RUN / "gold" / "gold-set-50.raw.jsonl", "w") as f:
    for r in sample:
        keep = {k: r.get(k) for k in (
            "canonical_id","source","subreddit","author","created_utc","title","text",
            "product_match","content_role","frames","url")}
        keep["source_meta"] = r.get("source_meta")
        f.write(json.dumps(keep, ensure_ascii=False) + "\n")

print("tiktok pool", len(tt_pool), "reddit pool", len(rd_pool))
print("sampled", len(sample), "tiktok", len(tt_ids), "reddit", len(rd_ids))
print("tt sample text-len min/median/max:", *sorted([len((by_id[i]['text'] or '')) for i in tt_ids])[::12])
print("rd sample empty texts:", sum(1 for i in rd_ids if not (by_id[i]['text'] or '').strip()))
print("sha256 raw:", hashlib.sha256((RUN/'gold'/'gold-set-50.raw.jsonl').read_bytes()).hexdigest()[:16])
