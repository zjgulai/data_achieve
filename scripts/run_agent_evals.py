#!/usr/bin/env python3
# ─── How to run ───
# cd apps/api && uv run python ../../scripts/run_agent_evals.py
# cd apps/api && uv run python ../../scripts/run_agent_evals.py --agent shusuo
# cd apps/api && uv run python ../../scripts/run_agent_evals.py --json
# cd apps/api && uv run python ../../scripts/run_agent_evals.py --update-baseline
#
# Agent 评测运行器。只跑**确定性接缝**（纯函数、无 IO、无 LLM），
# 因此结果可比、可进 PR 门禁、零成本。
#
# 为什么只跑确定性接缝：
#   模型层用例有随机性，放进 PR 门禁会让红灯失去信号意义。
#   确定性接缝覆盖命令解析、意图回退、参数校验、安全边界——
#   这些一旦回归就是真回归，基线严格可比。
#
# 退出码：0 全部通过且不低于基线，1 有失败或相对基线退化，2 输入错误。

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api/src"))

EVALS_DIR = ROOT / "configs/agents"
REPORTS_DIR = ROOT / "reports/agents"
BASELINE_NAME = "baseline.json"

REPORT_SCHEMA_VERSION = "agent-eval-report.v1"
CASE_SCHEMA = "agent-eval-cases.v1"


class EvalConfigError(RuntimeError):
    """用例文件本身有问题（不是被测对象失败）。"""


# ── 接缝注册表 ────────────────────────────────────────────────────────────────
# 只登记纯函数。加新接缝必须确认：无 IO、无环境变量、无 DB、无网络、无 LLM。
# 这个白名单同时是安全边界：runner 不会根据用例文件执行任意代码。

def _seam_registry() -> dict[str, Any]:
    from data_intelligence_hub.agents.shusuo import commands as shusuo_commands
    from data_intelligence_hub.agents.shusuo import intents as shusuo_intents
    from data_intelligence_hub.agents.tiktok_cdo import endpoint_router, tool_router
    from data_intelligence_hub.agents.tiktok_cdo import intent as tiktok_intent
    from data_intelligence_hub.agents.tiktok_cdo.intent import TikTokIntent

    def _intent(spec: dict[str, Any]) -> TikTokIntent:
        """用例里用普通 dict 声明意图，这里构造真对象。

        适配器只做构造，不做任何归一化——否则用例就测不到真实调用了。
        """
        return TikTokIntent(**spec)

    return {
        "shusuo.build_proposal": shusuo_intents.build_proposal,
        "shusuo.proposal_reply": shusuo_intents.proposal_reply,
        "shusuo.clean_text": shusuo_commands.clean_text,
        "shusuo.parse_params": shusuo_commands.parse_params,
        "shusuo.parse_command": shusuo_commands.parse_command,
        "tiktok_cdo.fallback_intent": tiktok_intent._fallback_intent,
        "tiktok_cdo.build_tool_call": lambda spec: tool_router.build_tool_call(_intent(spec)),
        "tiktok_cdo.build_collect_params": lambda spec: endpoint_router.build_collect_params(
            _intent(spec)
        ),
        "tiktok_cdo.system_prompt": tiktok_intent._system_prompt,
    }


# ── 断言求值 ──────────────────────────────────────────────────────────────────
# 受限 DSL：用例文件只能声明这些操作，不能塞代码。

def _resolve_path(obj: Any, path: str) -> Any:
    """按 a.b.c 取值；支持 dataclass 属性、dict 键、序列下标（纯数字段）。"""
    if path in ("", "."):
        return obj
    current = obj
    for part in path.split("."):
        if isinstance(current, dict):
            current = current[part]
        elif isinstance(current, (list, tuple)) and part.lstrip("-").isdigit():
            current = current[int(part)]
        elif hasattr(current, part):
            current = getattr(current, part)
        else:
            raise KeyError(f"路径 {path} 在 {type(current).__name__} 上不存在（{part}）")
    return current


def _check(assertion: dict[str, Any], actual: Any) -> tuple[bool, str]:
    op = assertion.get("op")
    path = assertion.get("path", "")

    try:
        value = _resolve_path(actual, path)
    except (KeyError, AttributeError) as exc:
        return False, f"取值失败：{exc}"

    if op == "equals":
        expected = assertion.get("value")
        return value == expected, f"期望 {expected!r}，实际 {value!r}"

    if op == "not_equals":
        expected = assertion.get("value")
        return value != expected, f"期望不等于 {expected!r}，实际 {value!r}"

    if op == "in_set":
        allowed = assertion.get("values") or []
        return value in allowed, f"期望属于 {allowed!r}，实际 {value!r}"

    if op == "is_none":
        return value is None, f"期望 None，实际 {value!r}"

    if op == "is_not_none":
        return value is not None, f"期望非 None，实际 {value!r}"

    if op == "contains":
        needle = assertion.get("value")
        ok = isinstance(value, (str, list, tuple)) and needle in value
        return ok, f"期望包含 {needle!r}，实际 {value!r}"

    if op == "not_contains":
        needle = assertion.get("value")
        ok = not (isinstance(value, (str, list, tuple)) and needle in value)
        return ok, f"期望不包含 {needle!r}，实际 {value!r}"

    if op == "matches":
        pattern = assertion.get("value")
        ok = isinstance(value, str) and re.search(str(pattern), value) is not None
        return ok, f"期望匹配 /{pattern}/，实际 {value!r}"

    if op == "not_matches":
        pattern = assertion.get("value")
        ok = isinstance(value, str) and re.search(str(pattern), value) is None
        return ok, f"期望不匹配 /{pattern}/，实际 {value!r}"

    if op == "length_at_most":
        limit = assertion.get("value")
        ok = hasattr(value, "__len__") and len(value) <= int(limit)
        return ok, f"期望长度 <= {limit}，实际 {len(value) if hasattr(value, '__len__') else 'N/A'}"

    raise EvalConfigError(f"未知断言操作：{op!r}")


# ── 运行 ──────────────────────────────────────────────────────────────────────

def _load_cases(agent: str) -> list[dict[str, Any]]:
    path = EVALS_DIR / agent / "evals" / "p0.json"
    if not path.is_file():
        raise EvalConfigError(f"找不到用例文件 {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != CASE_SCHEMA:
        raise EvalConfigError(
            f"{path} 的 schema_version 应为 {CASE_SCHEMA}，实际 {payload.get('schema_version')!r}"
        )
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise EvalConfigError(f"{path} 里没有 cases")
    return cases


def _call(seams: dict[str, Any], target: str, arguments: Any) -> Any:
    if target not in seams:
        raise EvalConfigError(
            f"未知接缝 {target!r}。可用的有：{', '.join(sorted(seams))}"
        )
    fn = seams[target]
    if isinstance(arguments, list):
        return fn(*arguments)
    if arguments is None:
        return fn()
    return fn(**arguments)


def run_agent(agent: str, seams: dict[str, Any]) -> dict[str, Any]:
    cases = _load_cases(agent)
    results: list[dict[str, Any]] = []

    for case in cases:
        case_id = case.get("id") or "<无 id>"
        target = case.get("target")
        expected_error = case.get("expect_error")
        try:
            actual = _call(seams, target, case.get("input"))
            if expected_error is not None:
                # 期望抛异常但没抛：这也是回归（本该拒绝的输入被接受了）。
                results.append(
                    {
                        "id": case_id,
                        "target": target,
                        "status": "fail",
                        "failures": [
                            f"期望抛出含 {expected_error!r} 的异常，实际正常返回 {actual!r}"
                        ],
                        "known_bug": bool(case.get("known_bug")),
                        "note": case.get("note", ""),
                    }
                )
                continue
            failures = []
            for assertion in case.get("assert") or []:
                ok, detail = _check(assertion, actual)
                if not ok:
                    failures.append(detail)
            results.append(
                {
                    "id": case_id,
                    "target": target,
                    "status": "pass" if not failures else "fail",
                    "failures": failures,
                    "known_bug": bool(case.get("known_bug")),
                    "note": case.get("note", ""),
                }
            )
        except Exception as exc:  # noqa: BLE001 - 被测代码抛异常也是有效结果
            if expected_error is not None:
                ok = expected_error in str(exc)
                results.append(
                    {
                        "id": case_id,
                        "target": target,
                        "status": "pass" if ok else "fail",
                        "failures": [] if ok else [
                            f"异常文案不含 {expected_error!r}，实际 {type(exc).__name__}: {exc}"
                        ],
                        "known_bug": bool(case.get("known_bug")),
                        "note": case.get("note", ""),
                    }
                )
                continue
            results.append(
                {
                    "id": case_id,
                    "target": target,
                    "status": "error",
                    "failures": [f"{type(exc).__name__}: {exc}"],
                    "known_bug": bool(case.get("known_bug")),
                    "note": case.get("note", ""),
                }
            )

    passed = [r for r in results if r["status"] == "pass"]
    # known_bug 的用例允许失败，但仍要计数，便于看到"已知问题还没修"。
    unexpected = [
        r for r in results if r["status"] != "pass" and not r["known_bug"]
    ]
    known = [r for r in results if r["status"] != "pass" and r["known_bug"]]

    return {
        "agent": agent,
        "total": len(results),
        "passed": len(passed),
        "known_bug_failing": len(known),
        "unexpected_failing": len(unexpected),
        "ok": not unexpected,
        "results": results,
    }


def _baseline_path(agent: str) -> Path:
    return EVALS_DIR / agent / "evals" / BASELINE_NAME


def _compare_baseline(report: dict[str, Any]) -> list[str]:
    """与基线比较：通过数不得下降。基线不存在时不比较。"""
    path = _baseline_path(report["agent"])
    if not path.is_file():
        return []
    baseline = json.loads(path.read_text(encoding="utf-8"))
    previous = int(baseline.get("passed", 0))
    current = report["passed"]
    if current < previous:
        return [
            f"{report['agent']}: 通过数从基线 {previous} 降到 {current}"
            f"（改了行为就更新 baseline.json，别让基线悄悄过期）"
        ]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description="运行 Agent 确定性评测集")
    parser.add_argument("--agent", help="只跑指定 Agent")
    parser.add_argument("--json", action="store_true", help="输出 JSON 报告")
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="把本次通过数写为基线（确认行为变更是有意的才用）",
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="把报告写入 reports/agents/<id>/<date>-eval.json",
    )
    args = parser.parse_args()

    seams = _seam_registry()
    agents = [args.agent] if args.agent else sorted(
        p.name for p in EVALS_DIR.iterdir() if (p / "evals" / "p0.json").is_file()
    )
    if not agents:
        raise SystemExit("输入错误：configs/agents/*/evals/p0.json 一个都没有")

    reports = []
    problems: list[str] = []
    for agent in agents:
        report = run_agent(agent, seams)
        report["baseline_problems"] = _compare_baseline(report)
        problems.extend(report["baseline_problems"])
        if not report["ok"]:
            problems.append(
                f"{agent}: {report['unexpected_failing']} 条用例出现非预期失败"
            )
        reports.append(report)

        if args.update_baseline:
            _baseline_path(agent).write_text(
                json.dumps(
                    {
                        "schema_version": "agent-eval-baseline.v1",
                        "passed": report["passed"],
                        "total": report["total"],
                        "updated": date.today().isoformat(),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

        if args.write_report:
            out_dir = REPORTS_DIR / agent
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / f"{date.today().isoformat()}-eval.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

    if args.json:
        print(json.dumps(
            {"schema_version": REPORT_SCHEMA_VERSION, "reports": reports, "problems": problems},
            ensure_ascii=False,
            indent=2,
        ))
    else:
        for report in reports:
            print(
                f"{report['agent']}: {report['passed']}/{report['total']} 通过"
                + (
                    f"，已知缺陷未修 {report['known_bug_failing']} 条"
                    if report["known_bug_failing"]
                    else ""
                )
            )
            for item in report["results"]:
                if item["status"] == "pass":
                    continue
                tag = "已知缺陷" if item["known_bug"] else "失败"
                print(f"  [{tag}] {item['id']} → {item['target']}")
                for failure in item["failures"]:
                    print(f"      {failure}")
                if item["note"]:
                    print(f"      备注：{item['note']}")
        if problems:
            print(f"\n问题 {len(problems)} 项：")
            for item in problems:
                print(f"  - {item}")
        else:
            print("\n检查结果：通过")

    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
