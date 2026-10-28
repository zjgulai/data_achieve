#!/usr/bin/env python3
# ─── How to run ───
# 只读探测并记账（不改生产）：
#   python3 scripts/record_release.py probe --host a
#   python3 scripts/record_release.py probe --host b
# 校验账本：
#   python3 scripts/record_release.py verify
# 手工补记（发布脚本调用或人工核对）：
#   python3 scripts/record_release.py append --host a --commit <sha> --result success
#
# 发布账本回答一个问题：「生产现在跑的是哪一版代码」。
# 在此之前这个答案只能靠现场 SSH 猜，文档则写着过时的「B = main 加一个提交」。
#
# 账本入库（docs/ops/releases.jsonl），因为它是判定回滚点的依据，不能只存在本地。
# reports/ 被 .gitignore 忽略（那是本地巡检产物），所以账本不放那里。
#
# 退出码：0 成功，1 校验失败，2 输入错误。

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs/ops/releases.jsonl"
LEDGER_SCHEMA = "release-ledger.v1"

# 两台生产的固定信息，与 scripts/deploy-p0.sh 保持一致。
# 密钥路径不进仓库，只放「默认候选」，找不到时报错而不是静默失败。
HOSTS: dict[str, dict[str, str]] = {
    "a": {
        "ssh": "ubuntu@43.163.92.244",
        "url": "https://scrapy.luteos.com",
        "branch": "main",
        "key_candidates": "zhoujian_pachong.pem",
    },
    "b": {
        "ssh": "ubuntu@101.34.52.232",
        "url": "https://scrapy.lute-tlz-dddd.top",
        "branch": "deploy/tiktok-cdo-codex",
        "key_candidates": "DDDD.pem",
    },
}

REMOTE_APP = "/opt/data-achieve-scrapy/app"
API_CONTAINER = "data_achieve_scrapy_api"

# 探测脚本：只读，不 fetch、不重启、不写任何文件。
PROBE_SCRIPT = f"""
set -euo pipefail
cd {REMOTE_APP}
echo "COMMIT=$(git rev-parse HEAD)"
echo "SHORT=$(git rev-parse --short HEAD)"
echo "BRANCH=$(git rev-parse --abbrev-ref HEAD)"
echo "SUBJECT=$(git log -1 --format=%s)"
echo "COMMITTED_AT=$(git log -1 --format=%cI)"
echo "DIRTY=$(git status --porcelain | wc -l | tr -d ' ')"
inspect() {{
  docker inspect -f "$1" {API_CONTAINER} 2>/dev/null || echo unknown
}}
echo "IMAGE=$(inspect '{{{{.Config.Image}}}}')"
echo "CONTAINER_CREATED=$(inspect '{{{{.Created}}}}')"
echo "CONTAINER_STATUS=$(inspect '{{{{.State.Status}}}}')"
"""


def _find_key(host: str) -> Path:
    info = HOSTS[host]
    name = info["key_candidates"]
    # 先在常见位置找，不把绝对路径写死进仓库。
    for candidate in (
        Path.home() / "Downloads" / name,
        Path.home() / "Project/pr-agent" / name,
        Path.home() / ".ssh" / name,
        ROOT / name,
    ):
        if candidate.is_file():
            return candidate
    raise SystemExit(
        f"输入错误：找不到 {host} 的密钥 {name}。"
        f"可用 KEY_DIR 指定目录，或手工核对后用 append 子命令记账。"
    )


def probe(host: str) -> dict[str, Any]:
    info = HOSTS[host]
    key = _find_key(host)
    result = subprocess.run(
        [
            "ssh", "-i", str(key),
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=15",
            "-o", "BatchMode=yes",
            info["ssh"],
            PROBE_SCRIPT,
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"探测 {host} 失败（exit {result.returncode}）：{result.stderr.strip()[:400]}"
        )
    observed = {}
    for line in result.stdout.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            observed[k.strip()] = v.strip()

    required = ("COMMIT", "BRANCH", "SUBJECT", "CONTAINER_CREATED")
    missing = [k for k in required if not observed.get(k)]
    if missing:
        raise SystemExit(f"探测 {host} 的输出缺少字段：{missing}")

    return {
        "schema_version": LEDGER_SCHEMA,
        "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "host": host,
        "url": info["url"],
        "commit": observed["COMMIT"],
        "short_commit": observed.get("SHORT", observed["COMMIT"][:7]),
        "branch": observed["BRANCH"],
        "subject": observed["SUBJECT"],
        "committed_at": observed.get("COMMITTED_AT", ""),
        "dirty_files": int(observed.get("DIRTY", "0") or 0),
        "image": observed.get("IMAGE", "unknown"),
        "container_created": observed["CONTAINER_CREATED"],
        "container_status": observed.get("CONTAINER_STATUS", "unknown"),
        "source": "probe",
    }


def append_record(record: dict[str, Any]) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_ledger() -> list[dict[str, Any]]:
    if not LEDGER.is_file():
        return []
    records = []
    for lineno, line in enumerate(LEDGER.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"输入错误：{LEDGER}:{lineno} 不是合法 JSON（{exc}）") from exc
    return records


def latest_by_host(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for record in records:
        host = record.get("host")
        if host in HOSTS:
            latest[host] = record  # 后写的覆盖先写的，jsonl 天然按时间序
    return latest


def verify(records: list[dict[str, Any]]) -> list[str]:
    problems: list[str] = []
    if not records:
        return ["账本为空：每个生产主机至少应有一条记录"]

    seen_hosts = set()
    for index, record in enumerate(records, 1):
        if record.get("schema_version") != LEDGER_SCHEMA:
            problems.append(
                f"第 {index} 条 schema_version 应为 {LEDGER_SCHEMA}，"
                f"实际 {record.get('schema_version')!r}"
            )
        host = record.get("host")
        if host not in HOSTS:
            problems.append(f"第 {index} 条 host={host!r} 不是 a 或 b")
            continue
        seen_hosts.add(host)
        commit = record.get("commit") or ""
        if len(commit) != 40:
            problems.append(f"第 {index} 条 commit 应为 40 位，实际 {commit!r}")
        if record.get("branch") and record["branch"] != HOSTS[host]["branch"]:
            # 不判失败，只提示：分支收敛前这就是需要知道的事实。
            problems.append(
                f"第 {index} 条 {host} 的 branch={record['branch']!r}，"
                f"与脚本配置的 {HOSTS[host]['branch']!r} 不一致"
            )
        if record.get("dirty_files"):
            problems.append(
                f"第 {index} 条 {host} 有 {record['dirty_files']} 个未提交改动；"
                f"生产工作区应保持干净"
            )

    for host in HOSTS:
        if host not in seen_hosts:
            problems.append(f"{host} 没有任何记录")

    return problems


def cmd_probe(args: argparse.Namespace) -> int:
    record = probe(args.host)
    if args.dry_run:
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return 0
    append_record(record)
    print(
        f"已记账 {args.host}：{record['short_commit']} "
        f"[{record['branch']}] {record['subject'][:60]}"
    )
    print(f"  容器创建于 {record['container_created']}")
    return 0


def cmd_append(args: argparse.Namespace) -> int:
    info = HOSTS[args.host]
    record = {
        "schema_version": LEDGER_SCHEMA,
        "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "host": args.host,
        "url": info["url"],
        "commit": args.commit,
        "short_commit": args.commit[:7],
        "branch": args.branch or info["branch"],
        "subject": args.subject or "",
        "committed_at": "",
        "dirty_files": 0,
        "image": args.image or "unknown",
        "container_created": args.container_created or "",
        "container_status": "unknown",
        "source": args.source,
        "result": args.result,
    }
    if args.dry_run:
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return 0
    append_record(record)
    print(f"已追加 {args.host} 记录：{args.commit[:7]} result={args.result}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    records = read_ledger()
    problems = verify(records)
    latest = latest_by_host(records)

    if args.json:
        print(json.dumps(
            {
                "schema_version": "release-ledger-report.v1",
                "records": len(records),
                "latest": latest,
                "problems": problems,
                "ok": not problems,
            },
            ensure_ascii=False,
            indent=2,
        ))
    else:
        print(f"账本：{LEDGER.relative_to(ROOT)}，{len(records)} 条记录")
        for host in sorted(latest):
            rec = latest[host]
            print(
                f"  {host.upper()}: {rec['short_commit']} [{rec['branch']}] "
                f"容器 {rec['container_created'] or '未知'}"
            )
            if rec.get("subject"):
                print(f"      {rec['subject'][:70]}")
        if problems:
            print(f"\n问题 {len(problems)} 项：")
            for item in problems:
                print(f"  - {item}")
        else:
            print("\n检查结果：通过")

    return 0 if not problems else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="生产发布账本：只读探测、追加与校验")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_probe = sub.add_parser("probe", help="SSH 只读探测生产状态并记账")
    p_probe.add_argument("--host", required=True, choices=sorted(HOSTS))
    p_probe.add_argument("--dry-run", action="store_true", help="只打印，不写账本")
    p_probe.set_defaults(func=cmd_probe)

    p_append = sub.add_parser("append", help="手工追加一条发布记录")
    p_append.add_argument("--host", required=True, choices=sorted(HOSTS))
    p_append.add_argument("--commit", required=True)
    p_append.add_argument("--branch")
    p_append.add_argument("--subject")
    p_append.add_argument("--image")
    p_append.add_argument("--container-created")
    p_append.add_argument(
        "--result", default="success", choices=["success", "rolled_back", "failed"]
    )
    p_append.add_argument(
        "--source", default="deploy-p0.sh", help="记录来源，如 deploy-p0.sh 或人工核对"
    )
    p_append.add_argument("--dry-run", action="store_true")
    p_append.set_defaults(func=cmd_append)

    p_verify = sub.add_parser("verify", help="校验账本格式与一致性")
    p_verify.add_argument("--json", action="store_true")
    p_verify.set_defaults(func=cmd_verify)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
