"""Ingest: read immutable raw responses and their collection ledger.

Implements SOP skill ``voc-source-pilot`` partially (G3): the reader verifies
the raw-to-ledger lineage and refuses to invent missing payloads.  It does not
perform network collection, so G5 (``voc-stratified-collection``) is only
consumed, never executed here.

Design: every reader returns ``RawResponse`` objects.  A production table
reader can be added later without changing the downstream pipeline, because
``counting`` and ``identity`` consume the normalised response objects rather
than files or SQL.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Protocol

from . import contract


@dataclass
class RawResponse:
    provider: str
    endpoint: str
    request_id: str
    frame: str
    kind: str
    subreddit: str
    query: str
    fetched_at: str
    path: str
    sha256: str
    status: str
    error: str | None
    records: list[dict[str, Any]] = field(default_factory=list)
    payload_text: str | None = None
    ledger_sha256: str | None = None
    sha256_ok: bool = True

    @property
    def record_count(self) -> int:
        return len(self.records)


@dataclass
class IngestResult:
    run_dir: Path
    responses: list[RawResponse]
    failed_requests: list[dict[str, Any]]
    ledger: dict[str, Any]
    generated_at: str
    source_notes: list[str] = field(default_factory=list)

    @property
    def raw_object_count(self) -> int:
        return sum(r.record_count for r in self.responses)

    @property
    def raw_response_count(self) -> int:
        return len(self.responses)

    @property
    def requested_response_count(self) -> int:
        return len(self.responses) + len(self.failed_requests)

    def provider_counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for r in self.responses:
            out[r.provider] = out.get(r.provider, 0) + 1
        return out


class Reader(Protocol):
    name: str

    def read(self, run_dir: Path) -> IngestResult:
        ...


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve_path(run_dir: Path, raw_path: str) -> Path | None:
    candidate = Path(raw_path)
    tries = [candidate]
    if not candidate.is_absolute():
        tries.extend(
            [
                run_dir / candidate,
                run_dir.parent.parent / candidate,
                run_dir / "raw" / Path(candidate).name,
            ]
        )
    for path in tries:
        if path.exists() and path.is_file():
            return path
    return None


def _safe_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _classify_reddit_record(rec: dict[str, Any], endpoint: str) -> str:
    if endpoint == "comments" or "body" in rec:
        return "comment"
    if "title" in rec or str(rec.get("name", "")).startswith("t3_"):
        return "post"
    return "unknown"


def _normalise_reddit_record(rec: dict[str, Any], kind: str) -> dict[str, Any]:
    if kind == "post":
        title = rec.get("title") or ""
        body = rec.get("selftext") or ""
        if body in ("[removed]", "[deleted]"):
            body = ""
        return {
            "external_id": str(rec.get("id") or ""),
            "kind": "post",
            "author": rec.get("author") or "[deleted]",
            "created_utc": int(rec.get("created_utc") or 0),
            "subreddit": rec.get("subreddit") or "",
            "title": title,
            "text": body,
            "permalink": rec.get("permalink") or "",
            "score": int(rec.get("score") or 0),
            "num_comments": int(rec.get("num_comments") or 0),
        }
    body = rec.get("body") or ""
    if body in ("[removed]", "[deleted]"):
        body = ""
    return {
        "external_id": str(rec.get("id") or ""),
        "kind": "comment",
        "author": rec.get("author") or "[deleted]",
        "created_utc": int(rec.get("created_utc") or 0),
        "subreddit": rec.get("subreddit") or "",
        "title": "",
        "text": body,
        "permalink": rec.get("permalink") or "",
        "score": int(rec.get("score") or 0),
        "num_comments": int(rec.get("num_comments") or 0),
    }


class RedditLedgerReader:
    """Read Arctic Shift raw responses listed in collection-run-ledger.json."""

    name = "reddit-ledger"

    def read(self, run_dir: Path) -> IngestResult:
        ledger_path = run_dir / "collection-run-ledger.json"
        if not ledger_path.exists():
            raise contract.ContractError(f"missing collection ledger: {ledger_path}")
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        responses: list[RawResponse] = []
        failed: list[dict[str, Any]] = []
        notes: list[str] = []
        for row in ledger.get("rows", []):
            request = row.get("request") or {}
            path = _resolve_path(run_dir, str(row.get("path") or ""))
            if path is None:
                failed.append({**row, "error": f"raw path not found: {row.get('path')}"})
                notes.append(f"missing raw payload for {row.get('raw_id')}")
                continue
            digest = _sha256_file(path)
            ledger_sha = row.get("sha256")
            if ledger_sha and ledger_sha != digest:
                notes.append(f"sha256 mismatch for {row.get('raw_id')}: ledger={ledger_sha[:12]} file={digest[:12]}")
            if row.get("status") != "success":
                failed.append({**row, "sha256_file": digest})
                continue
            payload = _safe_json(path)
            if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
                failed.append({**row, "error": "payload has no data list", "sha256_file": digest})
                continue
            kind = _classify_reddit_record(payload["data"][0] if payload["data"] else {}, request.get("kind", "posts"))
            records = [_normalise_reddit_record(r, kind) for r in payload["data"] if isinstance(r, dict)]
            records = [r for r in records if r["external_id"]]
            responses.append(
                RawResponse(
                    provider=str(row.get("provider") or "arcticshift"),
                    endpoint=str(row.get("endpoint") or request.get("kind") or "posts"),
                    request_id=str(row.get("request_id") or ""),
                    frame=str(request.get("frame") or "natural"),
                    kind=kind,
                    subreddit=str(request.get("subreddit") or ""),
                    query=str(request.get("query") or ""),
                    fetched_at=str(row.get("fetched_at") or ledger.get("generated_at") or ""),
                    path=str(row.get("path") or ""),
                    sha256=digest,
                    status="success",
                    error=None,
                    records=records,
                    ledger_sha256=ledger_sha,
                    sha256_ok=(not ledger_sha or ledger_sha == digest),
                )
            )
        return IngestResult(
            run_dir=run_dir,
            responses=responses,
            failed_requests=failed,
            ledger=ledger,
            generated_at=str(ledger.get("generated_at") or contract.now_iso()),
            source_notes=notes,
        )


class AmazonPdpReader:
    """Read Amazon PDP HTML.  The raw files are HTML, not JSON.

    The parsed ``amazon-identity-raw.json`` ledger supplies the ASIN for each
    request; the HTML is kept byte-for-byte for identity parsing.
    """

    name = "amazon-pdp"

    def read(self, run_dir: Path) -> IngestResult:
        artifact_path = run_dir / "amazon-identity-raw.json"
        ledger: dict[str, Any] = {"rows": [], "summary": {"requests": 0, "success": 0, "failed": 0}}
        if artifact_path.exists():
            try:
                ledger = json.loads(artifact_path.read_text(encoding="utf-8")).get("ledger", ledger)
            except json.JSONDecodeError:
                pass
        responses: list[RawResponse] = []
        failed: list[dict[str, Any]] = []
        notes: list[str] = []
        rows = ledger.get("rows", [])
        if not rows:
            # Fall back to scanning the raw directory when no parsed ledger exists.
            for path in sorted((run_dir / "raw" / "amazon").glob("*.json")):
                rows.append(
                    {
                        "raw_id": path.stem,
                        "request_id": path.stem,
                        "request": {"asin": None},
                        "fetched_at": "",
                        "path": str(path),
                        "sha256": None,
                        "status": "success",
                    }
                )
        for row in rows:
            path = _resolve_path(run_dir, str(row.get("path") or ""))
            if path is None:
                failed.append({**row, "error": "amazon raw path not found"})
                continue
            digest = _sha256_file(path)
            if row.get("sha256") and row["sha256"] != digest:
                notes.append(f"amazon sha256 mismatch for {row.get('raw_id')}")
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                failed.append({**row, "error": str(exc)})
                continue
            responses.append(
                RawResponse(
                    provider="amazon",
                    endpoint="pdp",
                    request_id=str(row.get("request_id") or row.get("raw_id") or ""),
                    frame="identity",
                    kind="pdp",
                    subreddit="",
                    query=str((row.get("request") or {}).get("asin") or ""),
                    fetched_at=str(row.get("fetched_at") or ""),
                    path=str(row.get("path") or ""),
                    sha256=digest,
                    status=str(row.get("status") or "success"),
                    error=row.get("error"),
                    records=[{"asin": (row.get("request") or {}).get("asin")}],
                    payload_text=text,
                    ledger_sha256=row.get("sha256"),
                    sha256_ok=(not row.get("sha256") or row["sha256"] == digest),
                )
            )
        return IngestResult(
            run_dir=run_dir,
            responses=responses,
            failed_requests=failed,
            ledger=ledger,
            generated_at=contract.now_iso(),
            source_notes=notes,
        )


class RunReader:
    """Composite reader: Reddit raw + Amazon PDP raw + frozen artifacts."""

    name = "run"

    def read(self, run_dir: Path) -> IngestResult:
        reddit = RedditLedgerReader().read(run_dir)
        responses = reddit.responses
        failed = list(reddit.failed_requests)
        notes = list(reddit.source_notes)
        if (run_dir / "raw" / "amazon").exists() or (run_dir / "amazon-identity-raw.json").exists():
            amazon = AmazonPdpReader().read(run_dir)
            responses.extend(amazon.responses)
            failed.extend(amazon.failed_requests)
            notes.extend(amazon.source_notes)
        if not responses:
            raise contract.ContractError(f"no readable raw responses under {run_dir}")
        return IngestResult(
            run_dir=run_dir,
            responses=responses,
            failed_requests=failed,
            ledger=reddit.ledger,
            generated_at=reddit.generated_at,
            source_notes=notes,
        )


def load_frozen_artifacts(run_dir: Path) -> dict[str, Any]:
    """Load the immutable G4/G5 artifacts this pipeline consumes."""
    out: dict[str, Any] = {}
    for name in ("taxonomy.json", "gate-ledger.json", "voc-research-charter.json"):
        path = run_dir / name
        if path.exists():
            try:
                out[name] = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise contract.ContractError(f"invalid JSON in {name}: {exc}") from exc
    return out


def load_run(run_dir: str | os.PathLike[str]) -> tuple[IngestResult, dict[str, Any]]:
    path = Path(run_dir).expanduser().resolve()
    if not path.is_dir():
        raise contract.ContractError(f"run directory not found: {path}")
    return RunReader().read(path), load_frozen_artifacts(path)


def iter_records(result: IngestResult) -> Iterable[tuple[RawResponse, dict[str, Any]]]:
    for response in result.responses:
        if response.provider == "amazon":
            continue
        for record in response.records:
            yield response, record


def raw_inventory(result: IngestResult) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for response in result.responses:
        rows.append(
            {
                "provider": response.provider,
                "endpoint": response.endpoint,
                "request_id": response.request_id,
                "frame": response.frame,
                "kind": response.kind,
                "subreddit": response.subreddit,
                "query": response.query,
                "fetched_at": response.fetched_at,
                "path": response.path,
                "sha256": response.sha256,
                "ledger_sha256": response.ledger_sha256,
                "sha256_ok": response.sha256_ok,
                "record_count": response.record_count,
                "status": response.status,
            }
        )
    return rows
