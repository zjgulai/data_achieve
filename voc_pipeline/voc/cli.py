"""Command line entry point for the VOC pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import build as build_mod
from . import deliver
from . import collect
from . import counting
from . import evidence
from . import gates
from . import reachability
from . import skills
from . import spec_report
from . import validate_report
from .contracts import forbidden_conclusions_payload

ROOT = Path(__file__).resolve().parent.parent


DEFAULT_PLAN = [
    {"frame": "natural", "kind": "posts", "subreddit": "BabyBumps", "query": "belly band", "pages": 3},
    {"frame": "natural", "kind": "posts", "subreddit": "pregnant", "query": "belly band", "pages": 3},
    {"frame": "natural", "kind": "posts", "subreddit": "fitpregnancy", "query": "belly band", "pages": 2},
    {"frame": "natural", "kind": "comments", "subreddit": "BabyBumps", "query": "belly band", "pages": 3},
    {"frame": "natural", "kind": "comments", "subreddit": "pregnant", "query": "belly band", "pages": 3},
    {"frame": "qualitative_seed", "kind": "posts", "subreddit": "BabyBumps", "query": "Momcozy", "pages": 2},
    {"frame": "qualitative_seed", "kind": "comments", "subreddit": "BabyBumps", "query": "Momcozy", "pages": 2},
]


def cmd_collect(args: argparse.Namespace) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    plan = DEFAULT_PLAN
    if args.plan:
        plan = json.loads(Path(args.plan).read_text())
    manifest = collect.run_reddit_collection(
        out,
        plan,
        fetcher=collect.Fetcher(min_interval=args.interval),
        ledger_name=args.ledger_name,
    )
    print(json.dumps(manifest["summary"], ensure_ascii=False))
    return 0


def cmd_identity(args: argparse.Namespace) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    identity = collect.collect_amazon_identity(out, args.asins)
    print(json.dumps(identity["ledger"]["summary"], ensure_ascii=False))
    return 0


def cmd_collect_tiktok(args: argparse.Namespace) -> int:
    out = Path(args.out)
    if args.from_ledger:
        from . import tiktok_shop

        stats = tiktok_shop.rebuild_outputs(out / args.run)
    else:
        stats = collect.run_tiktok_collection(
            out / args.run,
            product_id=args.product_id,
            max_pages=args.pages,
            budget_usd=args.budget_usd,
            min_interval=args.interval,
        )
    print(json.dumps(stats, ensure_ascii=False, indent=1))
    return 0


def cmd_spec(args: argparse.Namespace) -> int:
    spec_dir = Path(args.out)
    spec_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "gates": gates.gate_spec(),
        "skills": skills.skill_spec(),
        "automation": skills.automation_summary(),
        "counting": counting.counting_spec(),
        "evidence": evidence.evidence_spec(),
        "reachability": reachability.build_reachability(),
        "forbidden_conclusions": forbidden_conclusions_payload(),
    }
    (spec_dir / "voc-method-spec.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    for key in ("gates", "skills", "counting", "evidence", "reachability", "forbidden_conclusions"):
        (spec_dir / f"{key}.json").write_text(json.dumps(payload[key], ensure_ascii=False, indent=1))
    print(f"wrote {spec_dir / 'voc-method-spec.json'}")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    run_dir = ROOT / "artifacts" / args.run
    source_run_dir = ROOT / "artifacts" / args.source_run if args.source_run else None
    try:
        result = build_mod.build(
            run_dir,
            coder_mode=args.coder,
            min_confidence=args.min_confidence,
            source_run_dir=source_run_dir,
        )
    except validate_report.ForbiddenConclusionError as exc:
        print(f"[FAIL] forbidden-conclusion gate: {exc}", file=sys.stderr)
        return 1
    spec_report.render(ROOT / "spec", ROOT / "spec" / "spec.html", run_summary=result)
    print(json.dumps(result, ensure_ascii=False))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    run_dir = ROOT / "artifacts" / args.run
    report_suite = validate_report.validate_report(run_dir / "report.html", run_dir / "claims.json")
    spec_suite = validate_report.validate_spec(ROOT / "spec")
    payload = {
        "report": report_suite.to_dict(),
        "spec": spec_suite.to_dict(),
    }
    (run_dir / "validation-result.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    ledger = json.loads((run_dir / "gate-ledger.json").read_text())
    statuses = {g["gate_id"]: g["status"] for g in ledger["gates"]}
    deliver.write_manifest(run_dir, statuses)
    print(json.dumps({
        "report": payload["report"]["status"],
        "report_checks": f"{payload['report']['passed']}/{payload['report']['checks']}",
        "spec": payload["spec"]["status"],
        "spec_checks": f"{payload['spec']['passed']}/{payload['spec']['checks']}",
    }, ensure_ascii=False))
    if not (report_suite.passed and spec_suite.passed):
        for label, suite in (("report", report_suite), ("spec", spec_suite)):
            for check in suite.checks:
                if not check.passed:
                    print(f"[FAIL] {label}.{check.name}: {check.detail}", file=sys.stderr)
    return 0 if report_suite.passed and spec_suite.passed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="voc")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("collect", help="run the approved Reddit collection plan")
    p.add_argument("--out", required=True)
    p.add_argument("--plan")
    p.add_argument("--interval", type=float, default=12.0)
    p.add_argument("--ledger-name", default="collection-run-ledger.json")
    p.set_defaults(func=cmd_collect)

    p = sub.add_parser("identity", help="collect Amazon PDP identity evidence")
    p.add_argument("--out", required=True)
    p.add_argument("--asins", nargs="+", required=True)
    p.set_defaults(func=cmd_identity)

    p = sub.add_parser("collect-tiktok", help="collect TikTok Shop verified-purchase reviews")
    p.add_argument("--run", default="run-20261029")
    p.add_argument("--out", default=str(ROOT / "artifacts"))
    p.add_argument("--product-id", default=None)
    p.add_argument("--pages", type=int, default=14)
    p.add_argument("--budget-usd", type=float, default=0.10)
    p.add_argument("--interval", type=float, default=1.2)
    p.add_argument("--from-ledger", action="store_true")
    p.set_defaults(func=cmd_collect_tiktok)

    p = sub.add_parser("spec", help="serialise the method spec")
    p.add_argument("--out", default=str(ROOT / "spec"))
    p.set_defaults(func=cmd_spec)

    p = sub.add_parser("build", help="build run artifacts and report")
    p.add_argument("--run", default="run-20261029")
    p.add_argument(
        "--source-run",
        default=None,
        help="frozen input run directory; defaults to --run",
    )
    p.add_argument(
        "--coder",
        choices=["llm", "llm-v2", "rule"],
        default=None,
        help="single coder to use; default llm, VOC_CODER overrides when omitted",
    )
    p.add_argument(
        "--min-confidence",
        choices=["high", "medium", "all"],
        default=None,
        help=(
            "LLM aspect confidence gate; default high, "
            "VOC_MIN_CONFIDENCE overrides when omitted"
        ),
    )
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("validate", help="validate report and spec")
    p.add_argument("--run", default="run-20261029")
    p.set_defaults(func=cmd_validate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
