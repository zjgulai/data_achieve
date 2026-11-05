#!/usr/bin/env python3
"""Source 项目日报：一份 JSON，双落点（飞书 docx + 仓内 Markdown）。

用法：
  python3 tools/lark_daily_report.py --selftest
  python3 tools/lark_daily_report.py --file /tmp/report.json \\
      --md reports/Source-项目日报-20261105.md
  python3 tools/lark_daily_report.py --file /tmp/report.json --apply
  python3 tools/lark_daily_report.py --md reports/Source-项目日报-20261105.md --check-md
  python3 tools/lark_daily_report.py --md reports/Source-项目日报-20261105.md --fix
  python3 tools/lark_daily_report.py --readback

JSON 字段（中文键或英文键均可）：
  {"date": "2026-11-05（周四）",
   "progress": ["1. ...", "1.1 ..."],
   "verification": ["1. ..."],
   "todo": ["1. ..."]}
  中文键：日期 / 今日进展 / 验证结果 / 没做完的

红线：
  - 默认 dry-run；--apply 才写飞书。
  - 凭据只从仓外 0600 文件读，不打印。
  - 同日重跑整篇替换，不追加重复内容。
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any

import requests

BASE = "https://open.feishu.cn/open-apis"
DEFAULT_CONFIG = "~/.config/source-daily-report/feishu.json"
SECTION_TITLES = ("今日进展", "验证结果", "没做完的")
SECTION_KEYS = ("progress", "verification", "todo")

# 飞书 docx block_type：2=text，4=heading2，5=heading3
BLOCK_TEXT = 2
BLOCK_H2 = 4
BLOCK_H3 = 5
MAX_CHILDREN_PER_CALL = 50


class ReportError(RuntimeError):
    pass


# ---------------------------------------------------------------- config / auth


def load_config(path: str) -> dict[str, Any]:
    cfg_path = Path(os.path.expanduser(path))
    if not cfg_path.is_file():
        raise ReportError(f"配置文件不存在：{cfg_path}")
    mode = stat.S_IMODE(cfg_path.stat().st_mode)
    if mode & 0o077:
        print(f"WARN 配置文件权限 {oct(mode)}，应为 600", file=sys.stderr)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    for key in ("app_id", "app_secret", "doc_token"):
        if not cfg.get(key):
            raise ReportError(f"配置文件缺少字段：{key}")
    return cfg


def tenant_token(cfg: dict[str, Any]) -> str:
    resp = requests.post(
        f"{BASE}/auth/v3/tenant_access_token/internal",
        json={"app_id": cfg["app_id"], "app_secret": cfg["app_secret"]},
        timeout=20,
    )
    data = resp.json()
    if data.get("code") != 0:
        raise ReportError(f"鉴权失败 code={data.get('code')} msg={data.get('msg')}")
    return data["tenant_access_token"]


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ---------------------------------------------------------------- input


def normalize(content: dict[str, Any]) -> dict[str, Any]:
    aliases = {
        "date": ("date", "日期"),
        "progress": ("progress", "今日进展"),
        "verification": ("verification", "验证结果"),
        "todo": ("todo", "没做完的"),
    }
    out: dict[str, Any] = {}
    for key, names in aliases.items():
        value = None
        for name in names:
            if name in content:
                value = content[name]
                break
        if value is None:
            raise ReportError(f"缺少字段：{names[-1]}（或 {names[0]}）")
        if key == "date":
            if not isinstance(value, str) or not value.strip():
                raise ReportError("日期必须是非空字符串")
            out[key] = value.strip()
        else:
            if isinstance(value, str):
                value = [line for line in value.splitlines() if line.strip()]
            if not isinstance(value, list) or not value:
                raise ReportError(f"{names[-1]} 必须是非空数组")
            out[key] = [str(item).strip() for item in value if str(item).strip()]
    return out


def load_content(path: str) -> dict[str, Any]:
    return normalize(json.loads(Path(path).read_text(encoding="utf-8")))


# ---------------------------------------------------------------- render


def render_md(report: dict[str, Any]) -> str:
    lines = [f"# 项目日报 · {report['date']}", ""]
    for title, key in zip(SECTION_TITLES, SECTION_KEYS, strict=True):
        lines.append(f"## {title}")
        lines.append("")
        lines.extend(report[key])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def block(block_type: int, text: str) -> dict[str, Any]:
    node = {"elements": [{"text_run": {"content": text}}]}
    if block_type == BLOCK_H2:
        return {"block_type": BLOCK_H2, "heading2": node}
    if block_type == BLOCK_H3:
        return {"block_type": BLOCK_H3, "heading3": node}
    return {"block_type": BLOCK_TEXT, "text": {**node, "style": {}}}


def render_blocks(report: dict[str, Any]) -> list[dict[str, Any]]:
    blocks = [block(BLOCK_H2, report["date"])]
    for title, key in zip(SECTION_TITLES, SECTION_KEYS, strict=True):
        blocks.append(block(BLOCK_H3, title))
        blocks.extend(block(BLOCK_TEXT, item) for item in report[key])
    return blocks


def plain_text(item: dict[str, Any]) -> str:
    for key in ("text", "heading1", "heading2", "heading3", "heading4", "bullet", "ordered"):
        node = item.get(key)
        if node and node.get("elements"):
            return "".join(
                element.get("text_run", {}).get("content", "") for element in node["elements"]
            )
    return ""


# ---------------------------------------------------------------- feishu doc


def get_document(cfg: dict[str, Any], token: str) -> dict[str, Any]:
    resp = requests.get(
        f"{BASE}/docx/v1/documents/{cfg['doc_token']}", headers=headers(token), timeout=20
    )
    data = resp.json()
    if data.get("code") != 0:
        raise ReportError(
            f"读取文档失败 HTTP {resp.status_code} "
            f"code={data.get('code')} msg={data.get('msg')}"
        )
    return data["data"]["document"]


def list_blocks(cfg: dict[str, Any], token: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page_token = ""
    while True:
        params: dict[str, Any] = {"page_size": 500, "document_revision_id": -1}
        if page_token:
            params["page_token"] = page_token
        resp = requests.get(
            f"{BASE}/docx/v1/documents/{cfg['doc_token']}/blocks",
            headers=headers(token),
            params=params,
            timeout=30,
        )
        data = resp.json()
        if data.get("code") != 0:
            raise ReportError(
                f"读取块失败 HTTP {resp.status_code} "
                f"code={data.get('code')} msg={data.get('msg')}"
            )
        items.extend(data["data"].get("items", []))
        if not data["data"].get("has_more"):
            return items
        page_token = data["data"].get("page_token", "")
        if not page_token:
            return items


def page_block_id(blocks: list[dict[str, Any]], cfg: dict[str, Any]) -> str:
    for item in blocks:
        if item.get("block_type") == 1:
            return item["block_id"]
    return cfg["doc_token"]


def delete_children(cfg: dict[str, Any], token: str, parent: str, count: int) -> None:
    if count <= 0:
        return
    resp = requests.delete(
        f"{BASE}/docx/v1/documents/{cfg['doc_token']}/blocks/{parent}/children/batch_delete",
        headers=headers(token),
        json={"start_index": 0, "end_index": count},
        timeout=30,
    )
    data = resp.json()
    if data.get("code") != 0:
        raise ReportError(
            f"清空文档失败 HTTP {resp.status_code} "
            f"code={data.get('code')} msg={data.get('msg')}"
        )


def create_children(
    cfg: dict[str, Any], token: str, parent: str, blocks: list[dict[str, Any]]
) -> None:
    for start in range(0, len(blocks), MAX_CHILDREN_PER_CALL):
        chunk = blocks[start : start + MAX_CHILDREN_PER_CALL]
        resp = requests.post(
            f"{BASE}/docx/v1/documents/{cfg['doc_token']}/blocks/{parent}/children",
            headers=headers(token),
            json={"children": chunk, "index": start},
            timeout=30,
        )
        data = resp.json()
        if data.get("code") != 0:
            raise ReportError(
                f"写入文档失败 HTTP {resp.status_code} "
                f"code={data.get('code')} msg={data.get('msg')}"
            )


def readback(cfg: dict[str, Any], token: str) -> dict[str, Any]:
    blocks = list_blocks(cfg, token)
    parent = page_block_id(blocks, cfg)
    direct = [item for item in blocks if item.get("parent_id") == parent]
    sections: dict[str, int] = {}
    current = None
    for item in direct:
        text = plain_text(item)
        if item.get("block_type") == BLOCK_H3 and text in SECTION_TITLES:
            current = text
            sections[current] = 0
        elif current and item.get("block_type") == BLOCK_TEXT and text:
            sections[current] += 1
    return {
        "title": get_document(cfg, token).get("title"),
        "direct_children": len(direct),
        "sections": sections,
        "first_lines": [plain_text(item)[:80] for item in direct[:6] if plain_text(item)],
    }


# ---------------------------------------------------------------- markdown check


def check_md(path: Path) -> list[str]:
    problems: list[str] = []
    if not path.is_file():
        return [f"文件不存在：{path}"]
    data = path.read_bytes()
    if not data:
        return [f"文件为空：{path}"]
    nul = data.find(b"\x00")
    if nul >= 0:
        tail = data[nul:]
        if tail.strip(b"\x00"):
            problems.append(f"文件中间出现 NUL 字节（偏移 {nul}），不是尾部填充，需人工处理")
        else:
            problems.append(f"尾部有 {len(tail)} 字节 NUL 填充（偏移 {nul}），跑 --fix")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        problems.append(f"不是合法 UTF-8：{exc}")
    return problems


def fix_md(path: Path) -> int:
    data = path.read_bytes()
    nul = data.find(b"\x00")
    if nul < 0:
        print(f"OK 无需修复：{path}")
        return 0
    if data[nul:].strip(b"\x00"):
        raise ReportError("NUL 字节不在文件尾部，拒绝截断，请人工处理")
    cleaned = data[:nul]
    cleaned.decode("utf-8")  # 截断后必须仍是合法 UTF-8
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(cleaned)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    print(f"FIXED 去掉 {len(data) - len(cleaned)} 字节 NUL 填充：{path}")
    return 0


# ---------------------------------------------------------------- commands


def cmd_selftest(cfg_path: str, sample: Path | None) -> int:
    checks: list[tuple[str, bool, str]] = []

    def run(name: str, fn) -> None:
        try:
            detail = fn()
            checks.append((name, True, str(detail)))
        except Exception as exc:  # noqa: BLE001 - selftest 要收集所有失败
            checks.append((name, False, str(exc)))

    cfg = load_config(cfg_path)
    checks.append(("config", True, f"app_id={cfg['app_id'][:8]}… doc={cfg['doc_token'][:6]}…"))
    token = tenant_token(cfg)
    checks.append(("auth", True, "tenant_access_token ok"))
    doc = get_document(cfg, token)
    checks.append(
        ("document", True, f"title={doc.get('title')!r} revision={doc.get('revision_id')}")
    )
    blocks = list_blocks(cfg, token)
    checks.append(("blocks", True, f"{len(blocks)} blocks"))
    sample_report = {
        "date": "2026-01-01（周四）",
        "progress": ["1. selftest"],
        "verification": ["1. selftest"],
        "todo": ["1. selftest"],
    }
    rendered = render_blocks(sample_report)
    expected_blocks = 1 + len(SECTION_TITLES) * 2  # 日期 + 每个板块 1 标题 + 1 条目
    checks.append(("render", len(rendered) == expected_blocks, f"{len(rendered)} blocks"))
    if sample:
        problems = check_md(sample)
        checks.append(("markdown", not problems, "; ".join(problems) or "ok"))

    failed = [name for name, ok, _ in checks if not ok]
    for name, ok, detail in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")
    passed = len(checks) - len(failed)
    print(f"SELFTEST {'PASS' if not failed else 'FAIL'} ({passed}/{len(checks)})")
    return 0 if not failed else 1


def write_md(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Source 项目日报双落点工具")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="飞书凭据配置（仓外 0600）")
    parser.add_argument("--file", help="日报内容 JSON")
    parser.add_argument("--md", help="仓内 Markdown 路径")
    parser.add_argument("--apply", action="store_true", help="写入飞书（默认 dry-run）")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不写飞书（默认）")
    parser.add_argument("--selftest", action="store_true", help="自检：配置/鉴权/文档/渲染")
    parser.add_argument("--readback", action="store_true", help="回读飞书文档并打印板块条目数")
    parser.add_argument("--check-md", action="store_true", help="检查 Markdown 是否有 NUL 填充")
    parser.add_argument("--fix", action="store_true", help="修掉 Markdown 尾部 NUL 填充")
    parser.add_argument("--sample", help="selftest 时附带检查的 Markdown 路径")
    args = parser.parse_args(argv)

    if args.selftest:
        return cmd_selftest(args.config, Path(args.sample) if args.sample else None)

    if args.fix:
        if not args.md:
            parser.error("--fix 需要 --md")
        return fix_md(Path(args.md))

    if args.check_md:
        if not args.md:
            parser.error("--check-md 需要 --md")
        problems = check_md(Path(args.md))
        if problems:
            for problem in problems:
                print(f"FAIL  {problem}")
            return 1
        print(f"PASS  {args.md}: 无 NUL 填充，UTF-8 合法")
        return 0

    if args.readback:
        cfg = load_config(args.config)
        token = tenant_token(cfg)
        result = readback(cfg, token)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        expected = {"今日进展", "验证结果", "没做完的"}
        missing = expected - set(result["sections"])
        return 0 if not missing else 1

    if not args.file:
        parser.error("需要 --file 或 --selftest/--readback/--check-md/--fix")

    report = load_content(args.file)
    markdown = render_md(report)
    blocks = render_blocks(report)

    print(f"日期：{report['date']}")
    for title, key in zip(SECTION_TITLES, SECTION_KEYS, strict=True):
        print(f"{title}：{len(report[key])} 条")
    print(f"飞书块数：{len(blocks)}（写入时按 {MAX_CHILDREN_PER_CALL} 个一批）")

    md_problems: list[str] = []
    if args.md:
        write_md(Path(args.md), markdown)
        md_problems = check_md(Path(args.md))
        print(f"MD  {args.md}: {'OK' if not md_problems else '; '.join(md_problems)}")
        if md_problems:
            return 1

    if not args.apply:
        print("\n----- dry-run 预览 -----")
        print(markdown)
        print("----- 未写飞书；加 --apply 才写入 -----")
        return 0

    cfg = load_config(args.config)
    token = tenant_token(cfg)
    doc = get_document(cfg, token)
    blocks_before = list_blocks(cfg, token)
    parent = page_block_id(blocks_before, cfg)
    direct = [item for item in blocks_before if item.get("parent_id") == parent]
    print(f"目标文档：{doc.get('title')!r}（{len(direct)} 个直接子块）")
    delete_children(cfg, token, parent, len(direct))
    create_children(cfg, token, parent, blocks)
    result = readback(cfg, token)
    print("APPLIED " + json.dumps(result, ensure_ascii=False))
    expected = {
        "今日进展": len(report["progress"]),
        "验证结果": len(report["verification"]),
        "没做完的": len(report["todo"]),
    }
    if result["sections"] != expected:
        raise ReportError(f"回读不一致：期望 {expected}，实际 {result['sections']}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except ReportError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        sys.exit(1)
