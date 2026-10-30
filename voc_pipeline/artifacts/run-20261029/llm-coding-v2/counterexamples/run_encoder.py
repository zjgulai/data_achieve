#!/usr/bin/env python3
"""Run an independent LLM encoder pass over the eight SUP counterexamples.

The prompt contains only the coding contract, taxonomy.json, and the items.
It never contains hand-judgment.json.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
LLM_CODING = HERE.parents[1] / "llm-coding"
CONTRACT = LLM_CODING / "CODING-CONTRACT.md"
TAXONOMY = LLM_CODING / "taxonomy.json"
ITEMS = HERE / "items.jsonl"


def load_contract() -> str:
    text = CONTRACT.read_text(encoding="utf-8")
    start = text.index("## 2.")
    end = text.index("## 8.")
    return text[start:end].strip()


def load_taxonomy() -> dict:
    return json.loads(TAXONOMY.read_text(encoding="utf-8"))


def taxonomy_block(tax: dict) -> str:
    lines = ["# taxonomy.json (VOC-BAND-v1.1)", "", "## resolution_rules (mandatory priority; first match wins per evidence span)"]
    for rule in tax["resolution_rules"]:
        lines.append(f"- step {rule['step']}: {rule['code']} — {rule['condition']}")
    lines += ["", "## aspects"]
    for a in tax["aspects"]:
        lines.append(f"### {a['code']} — {a['label']} (family {a['family']})")
        lines.append(f"definition: {a['definition']}")
        lines.append(f"include: {a['include']}")
        lines.append(f"exclude: {a['exclude']}")
        lines.append("")
    lines.append("## contexts")
    for c in tax["contexts"]:
        lines.append(f"- {c['code']}: {c['definition']}")
    return "\n".join(lines)


def build_messages() -> list[dict]:
    contract = load_contract()
    tax = load_taxonomy()
    items = [json.loads(line) for line in ITEMS.read_text(encoding="utf-8").splitlines() if line.strip()]
    items_block = "\n".join(json.dumps(it, ensure_ascii=False) for it in items)
    system = (
        "You are the VOC LLM coder (llm-v1). You follow the coding contract exactly. "
        "You output only JSONL: one JSON object per input record, same order, no prose, no code fences."
    )
    user = f"""# Coding contract (verbatim sections 2-7)

{contract}

{taxonomy_block(tax)}

# Input records (8 lines, JSONL)

{items_block}

# Output

Encode all 8 records under the contract above. Rules that matter for this run:
- One output object per input record, same order, exactly 8 lines.
- Fields: canonical_id, is_product_experience (legacy audit field; not a published gate after E-merge), experience_reason, experience_scope, experience_source, aspects, contexts, journey, outcome, medical_self_report, notes.
- Each aspect: code, polarity, evidence_span, confidence. evidence_span must be a verbatim substring of that record's title or text, <=120 chars, and one span may support only one aspect.
- Apply the SUP resolution_rules in step order. The first matching step is the only SUP code for that evidence span. If a clause contains two coordinated predicates about different attributes, they may be two aspects, but each needs its own distinct span.
- polarity enum: positive, qualified_positive, negative, qualified_negative, mixed, unknown.
Return only the 8 JSONL lines."""
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def call_openai_compatible(url: str, api_key: str, model: str, messages: list[dict], temperature: float = 0.0) -> dict:
    body = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 6000,
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    })
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"request failed after retries: {last}")


def extract_content(payload: dict) -> str:
    return payload["choices"][0]["message"]["content"]


def parse_jsonl(text: str) -> list[dict]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:jsonl|json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=["deepseek", "kimi"], required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    if args.provider == "deepseek":
        url = "https://api.deepseek.com/chat/completions"
        key = os.environ["DEEPSEEK_API_KEY"]
    else:
        url = "https://api.moonshot.cn/v1/chat/completions"
        key = os.environ["KIMI_API_KEY"]
    messages = build_messages()
    print(f"prompt chars: system={len(messages[0]['content'])} user={len(messages[1]['content'])}", file=sys.stderr)
    payload = call_openai_compatible(url, key, args.model, messages)
    content = extract_content(payload)
    rows = parse_jsonl(content)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    meta = {
        "provider": args.provider,
        "model": args.model,
        "temperature": 0.0,
        "prompt_chars": {"system": len(messages[0]["content"]), "user": len(messages[1]["content"])},
        "usage": payload.get("usage"),
        "rows": len(rows),
        "raw_chars": len(content),
    }
    args.out.with_suffix(".meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
