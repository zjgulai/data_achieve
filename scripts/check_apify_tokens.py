#!/usr/bin/env python3
"""Check Apify tokens without printing them.

Why this exists: five Apify tokens appeared in plaintext in a session. Before
rotating them, we need to know which are still valid and which account each one
belongs to. Printing tokens to a terminal or a log would make the exposure
worse.

The token file accepts one entry per line, either::

    apify_api_xxx
    t1 apify_api_xxx

Only the last whitespace-separated field is treated as the token. The optional
prefix is kept as a label for the report.

Usage:
  python3 scripts/check_apify_tokens.py
  python3 scripts/check_apify_tokens.py --file ~/.config/apify-lake/tokens.txt
  python3 scripts/check_apify_tokens.py --json

Exit codes: 0 all valid, 1 any invalid or unreadable, 2 usage error.
"""

from __future__ import annotations

import argparse
import http.client
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_FILE = Path.home() / ".config" / "apify-lake" / "tokens.txt"
API = "https://api.apify.com/v2/users/me"


def read_tokens(path: Path) -> list[tuple[str, str]]:
    if not path.is_file():
        raise SystemExit(f"token file not found: {path}")
    entries: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        token = parts[-1]
        label = " ".join(parts[:-1]) or f"#{len(entries) + 1}"
        entries.append((label, token))
    return entries


def check(token: str) -> dict[str, object]:
    # Never put the token in an exception message or a log line. The only
    # place it appears is the request URL, which is not printed.
    try:
        request = urllib.request.Request(f"{API}?token={token}")
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return {"valid": False, "status": exc.code, "account": None, "plan": None}
    except (
        urllib.error.URLError,
        TimeoutError,
        json.JSONDecodeError,
        http.client.InvalidURL,
        ValueError,
        OSError,
    ) as exc:
        return {"valid": False, "status": type(exc).__name__, "account": None, "plan": None}

    data = payload.get("data", {})
    plan = data.get("plan")
    return {
        "valid": True,
        "status": 200,
        "account": data.get("username"),
        "plan": plan.get("id") if isinstance(plan, dict) else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default=str(DEFAULT_FILE))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    entries = read_tokens(Path(args.file).expanduser())
    if not entries:
        print(f"no tokens in {args.file}", file=sys.stderr)
        return 1

    results = []
    for label, token in entries:
        result = check(token)
        result["label"] = label
        results.append(result)

    if args.json:
        print(json.dumps({"count": len(results), "results": results}, ensure_ascii=False, indent=2))
    else:
        print(f"tokens: {len(results)}")
        for result in results:
            account = result.get("account") or "-"
            print(
                f"  {result['label']}: valid={result['valid']} "
                f"status={result['status']} account={account} plan={result.get('plan') or '-'}"
            )
        unique = {r["account"] for r in results if r.get("account")}
        print(f"unique accounts: {len(unique)}")

    return 0 if all(result["valid"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
