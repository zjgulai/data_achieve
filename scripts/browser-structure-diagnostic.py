#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import ipaddress
import json
import socket
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT_DIR = Path(__file__).resolve().parents[1]
API_SRC_DIR = ROOT_DIR / "apps" / "api" / "src"
if str(API_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(API_SRC_DIR))

from data_intelligence_hub.services.browser_structure_diagnostic import (  # noqa: E402
    build_browser_structure_diagnostic,
)

JSON_BEGIN = "BROWSER_DIAGNOSTIC_JSON_BEGIN"
JSON_END = "BROWSER_DIAGNOSTIC_JSON_END"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run an authorized read-only browser-harness structure diagnostic and "
            "write a traceable JSON evidence file."
        )
    )
    parser.add_argument("--url", required=True, help="Public HTTP/HTTPS URL to inspect.")
    parser.add_argument(
        "--authorized",
        action="store_true",
        help="Required. Confirms the URL is authorized for read-only inspection.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON path. Defaults to tmp/outputs/browser-diagnostics/...",
    )
    parser.add_argument(
        "--screenshot",
        type=Path,
        default=None,
        help="Screenshot PNG path. Defaults to the output JSON path with .png suffix.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="Page load/network timeout in seconds.",
    )
    parser.add_argument(
        "--harness-bin",
        default="browser-harness",
        help="browser-harness executable path.",
    )
    parser.add_argument(
        "--input-raw",
        type=Path,
        default=None,
        help="Build the diagnostic from a saved raw browser snapshot instead of launching Chrome.",
    )
    args = parser.parse_args()

    if not args.authorized:
        print("error: --authorized is required for browser diagnostics", file=sys.stderr)
        return 2

    try:
        asyncio.run(_assert_public_http_url(args.url))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    output_path = args.output or _default_output_path(args.url)
    screenshot_path = args.screenshot or output_path.with_suffix(".png")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)

    if args.input_raw is not None:
        with args.input_raw.open(encoding="utf-8") as file:
            raw_snapshot = json.load(file)
    else:
        raw_snapshot = _run_browser_harness(
            url=args.url,
            screenshot_path=screenshot_path,
            timeout=args.timeout,
            harness_bin=args.harness_bin,
        )

    diagnostic = build_browser_structure_diagnostic(
        raw_snapshot,
        requested_url=args.url,
        authorized=args.authorized,
        generated_at=datetime.now(UTC),
    )
    diagnostic["harness"] = {
        "binary": args.harness_bin,
        "version": _harness_version(args.harness_bin),
    }

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(diagnostic, file, ensure_ascii=False, indent=2, sort_keys=True)
        file.write("\n")
    print(json.dumps({"output": str(output_path), "final_url": diagnostic["final_url"]}))
    return 0


def _run_browser_harness(
    *,
    url: str,
    screenshot_path: Path,
    timeout: float,
    harness_bin: str,
) -> dict[str, Any]:
    harness_code = _build_harness_code(
        url=url,
        screenshot_path=screenshot_path,
        timeout=timeout,
    )
    completed = subprocess.run(
        [harness_bin],
        input=harness_code,
        text=True,
        capture_output=True,
        timeout=max(timeout + 20.0, 30.0),
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "browser-harness failed with exit code "
            f"{completed.returncode}: {completed.stderr.strip()}"
        )
    return _extract_raw_snapshot(completed.stdout)


def _build_harness_code(*, url: str, screenshot_path: Path, timeout: float) -> str:
    js_probe = r"""
(() => {
  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
  const abs = (value) => {
    try { return new URL(value, location.href).href; } catch { return String(value || ""); }
  };
  const sameOrigin = (value) => {
    try { return new URL(value, location.href).origin === location.origin; } catch { return false; }
  };
  const count = (selector) => document.querySelectorAll(selector).length;
  const text = clean(document.body ? document.body.innerText : "");
  const headings = Array.from(document.querySelectorAll("h1,h2,h3"))
    .map((element) => clean(element.innerText || element.textContent))
    .filter(Boolean)
    .slice(0, 16);
  const links = Array.from(document.querySelectorAll("a[href]")).slice(0, 40).map((element) => ({
    text: clean(element.innerText || element.textContent).slice(0, 120),
    href: abs(element.getAttribute("href")),
    same_origin: sameOrigin(element.getAttribute("href"))
  }));
  const forms = Array.from(document.querySelectorAll("form")).slice(0, 20).map((element) => ({
    name: clean(element.getAttribute("name") || element.getAttribute("aria-label") || element.id),
    method: clean(element.getAttribute("method") || "get").toLowerCase(),
    action: abs(element.getAttribute("action") || location.href),
    input_count: element.querySelectorAll("input, select, textarea").length
  }));
  const meta = {
    description: clean(document.querySelector('meta[name="description"]')?.getAttribute("content")),
    robots: clean(document.querySelector('meta[name="robots"]')?.getAttribute("content")),
    canonical_url: abs(document.querySelector('link[rel~="canonical"]')?.getAttribute("href") || "")
  };
  const jsonLdTypes = [];
  for (const script of Array
    .from(document.querySelectorAll('script[type*="ld+json"]'))
    .slice(0, 20)) {
    try {
      const parsed = JSON.parse(script.textContent || "null");
      const values = Array.isArray(parsed) ? parsed : [parsed];
      for (const value of values) {
        const type = value && value["@type"];
        if (Array.isArray(type)) jsonLdTypes.push(...type.map(String));
        else if (type) jsonLdTypes.push(String(type));
      }
    } catch {}
  }
  const resources = performance.getEntriesByType("resource").slice(0, 500).map((entry) => ({
    url: entry.name,
    initiator_type: entry.initiatorType || "other",
    duration_ms: Math.round(entry.duration || 0),
    transfer_size: Math.round(entry.transferSize || 0)
  }));
  return {
    title: document.title,
    final_url: location.href,
    visible_text_sample: text.slice(0, 1600),
    visible_text_length: text.length,
    visible_line_count: text ? text.split(/\n+/).filter((line) => clean(line)).length : 0,
    headings,
    links,
    forms,
    meta,
    json_ld_types: Array.from(new Set(jsonLdTypes)).slice(0, 24),
    counters: {
      links: count("a[href]"),
      same_origin_links: Array.from(document.querySelectorAll("a[href]"))
        .filter((a) => sameOrigin(a.getAttribute("href"))).length,
      external_links: Array.from(document.querySelectorAll("a[href]"))
        .filter((a) => !sameOrigin(a.getAttribute("href"))).length,
      forms: count("form"),
      inputs: count("input, select, textarea"),
      buttons: count("button, [role='button'], input[type='button'], input[type='submit']"),
      tables: count("table"),
      lists: count("ul, ol, [role='list']"),
      articles: count("article"),
      cards: count(
        "article, [class*='card'], [data-testid*='card'], [class*='item'], "
        + "[data-testid*='item']"
      ),
      images: count("img, picture"),
      scripts: count("script"),
      stylesheets: count("link[rel~='stylesheet']"),
      json_ld_blocks: count('script[type*="ld+json"]')
    },
    resources
  };
})()
"""
    return f"""
import json

URL = {json.dumps(url)}
SCREENSHOT_PATH = {json.dumps(str(screenshot_path))}
TIMEOUT = {json.dumps(timeout)}
errors = []
page = {{}}
dom = {{}}
accessibility = {{"total_nodes": 0, "role_counts": {{}}, "named_nodes": []}}
screenshot_output = None

def summarize_ax_tree(payload):
    nodes = payload.get("nodes", []) if isinstance(payload, dict) else []
    role_counts = {{}}
    named_nodes = []
    for node in nodes:
        role = ((node.get("role") or {{}}).get("value") or "unknown")
        name = ((node.get("name") or {{}}).get("value") or "").strip()
        role_counts[role] = role_counts.get(role, 0) + 1
        if name and len(named_nodes) < 24:
            named_nodes.append({{"role": role, "name": name[:160]}})
    return {{"total_nodes": len(nodes), "role_counts": role_counts, "named_nodes": named_nodes}}

try:
    new_tab(URL)
    wait_for_load(TIMEOUT)
    try:
        wait_for_network_idle(timeout=min(TIMEOUT, 10.0), idle_ms=600)
    except Exception as exc:
        errors.append(f"network_idle_unavailable: {{exc.__class__.__name__}}")
    page = page_info()
    dom = js({json.dumps(js_probe)})
    try:
        accessibility = summarize_ax_tree(cdp("Accessibility.getFullAXTree", {{}}))
    except Exception as exc:
        errors.append(f"accessibility_snapshot_failed: {{exc.__class__.__name__}}")
    try:
        screenshot_output = capture_screenshot(SCREENSHOT_PATH, full=True, max_dim=1800)
    except Exception as exc:
        errors.append(f"screenshot_failed: {{exc.__class__.__name__}}")
except Exception as exc:
    errors.append(f"browser_diagnostic_failed: {{exc.__class__.__name__}}: {{exc}}")
finally:
    try:
        close_tab()
    except Exception:
        pass

payload = {{
    "page": page,
    "dom": dom if isinstance(dom, dict) else {{}},
    "accessibility": accessibility,
    "evidence": {{"screenshot_path": screenshot_output}},
    "errors": errors,
}}
print({json.dumps(JSON_BEGIN)})
print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
print({json.dumps(JSON_END)})
"""


def _extract_raw_snapshot(stdout: str) -> dict[str, Any]:
    begin = stdout.find(JSON_BEGIN)
    end = stdout.find(JSON_END)
    if begin == -1 or end == -1 or end <= begin:
        raise RuntimeError("browser-harness output did not contain diagnostic JSON markers")
    body = stdout[begin + len(JSON_BEGIN) : end].strip()
    parsed = json.loads(body)
    if not isinstance(parsed, dict):
        raise RuntimeError("browser-harness diagnostic payload must be a JSON object")
    return parsed


def _harness_version(harness_bin: str) -> str | None:
    try:
        completed = subprocess.run(
            [harness_bin, "--version"],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def _default_output_path(url: str) -> Path:
    parsed = urlparse(url)
    host = (parsed.hostname or "unknown").replace(".", "-")
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return ROOT_DIR / "tmp" / "outputs" / "browser-diagnostics" / f"{host}-{timestamp}.json"


async def _assert_public_http_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
        raise ValueError("url must be an absolute HTTP or HTTPS URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("url_userinfo_not_allowed")
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname in {"localhost", "localhost.localdomain"}:
        raise ValueError("url_host_not_public")
    addresses = _parse_ip_literal(hostname)
    if addresses is None:
        addresses = await _resolve_host_ips(hostname)
    if any(not _is_public_address(address) for address in addresses):
        raise ValueError("url_host_not_public")


def _parse_ip_literal(hostname: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address] | None:
    try:
        return [ipaddress.ip_address(hostname)]
    except ValueError:
        return None


async def _resolve_host_ips(hostname: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    loop = asyncio.get_running_loop()
    try:
        address_info = await loop.run_in_executor(
            None,
            socket.getaddrinfo,
            hostname,
            None,
            socket.AF_UNSPEC,
            socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise ValueError("url_host_unresolvable") from exc
    addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for entry in address_info:
        sockaddr = entry[4]
        try:
            addresses.append(ipaddress.ip_address(str(sockaddr[0])))
        except ValueError as exc:
            raise ValueError("url_host_invalid") from exc
    if not addresses:
        raise ValueError("url_host_unresolvable")
    return addresses


def _is_public_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        address.is_global
        and not address.is_loopback
        and not address.is_link_local
        and not address.is_multicast
        and not address.is_private
        and not address.is_reserved
        and not address.is_unspecified
    )


if __name__ == "__main__":
    raise SystemExit(main())
