from __future__ import annotations

import json
from pathlib import Path

from data_intelligence_hub.report_quality import check_html_report
from data_intelligence_hub.report_quality.cli import main as gate_main

TESTS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
FIXTURE_63 = TESTS_DIR / "fixtures" / "report_language_63.html"
REPORT_DIR = REPO_ROOT / "tools" / "insight-reports" / "tiktok-viral-topic" / "2026-10-31"


def _archive_manifest() -> dict[str, str]:
    return {
        "source_status": "snapshot_only",
        "generated_at": "2026-11-03T00:00:00Z",
    }


def _scan(html: str, *, manifest: dict[str, str] | None = None, strict: bool = False):
    return check_html_report(html, manifest=manifest, strict=strict)


def test_fixture_has_exactly_63_term_hits() -> None:
    result = _scan(
        FIXTURE_63.read_text(encoding="utf-8"),
        manifest=_archive_manifest(),
        strict=True,
    )

    term_hits = [hit for hit in result.hits if hit.kind == "banned_term"]
    assert not result.ok
    assert len(term_hits) == 63


def test_current_report_passes_with_allowlist() -> None:
    result = _scan(
        (REPORT_DIR / "report.html").read_text(encoding="utf-8"),
        manifest=json.loads((REPORT_DIR / "manifest.json").read_text(encoding="utf-8")),
        strict=True,
    )

    assert result.ok, [hit.to_dict() for hit in result.hits]
    assert result.checked_figures == 6
    assert result.evidence == "descriptive_archive"


def test_bare_percentage_fails() -> None:
    result = _scan("<html><body><p>增长 40%。</p></body></html>", manifest=_archive_manifest())

    kinds = [hit.kind for hit in result.hits]
    assert kinds == ["percent_without_denominator"]


def test_percentage_with_denominator_passes() -> None:
    result = _scan(
        "<html><body><p>288 条里增长 40%。</p></body></html>",
        manifest=_archive_manifest(),
    )

    assert result.ok


def test_banned_term_fails() -> None:
    result = _scan("<html><body><p>这里用归因。</p></body></html>", manifest=_archive_manifest())

    assert [hit.kind for hit in result.hits] == ["banned_term"]
    assert result.hits[0].term == "归因"


def test_negated_extrapolation_is_allowed() -> None:
    result = _scan(
        "<html><body><p>不能往外推到 11 月。</p></body></html>",
        manifest=_archive_manifest(),
    )

    assert result.ok


def test_missing_evidence_fails() -> None:
    result = _scan("<html><body><p>288 条里增长 40%。</p></body></html>")

    assert [hit.kind for hit in result.hits] == ["missing_evidence"]


def test_chart_without_source_or_scope_fails() -> None:
    html = (
        "<html><body><figure><svg aria-label='图'></svg>"
        "<figcaption>图 1</figcaption></figure></body></html>"
    )
    result = _scan(html, manifest=_archive_manifest())

    assert [hit.kind for hit in result.hits] == [
        "chart_without_source",
        "chart_without_scope",
    ]


def test_strict_requires_as_of() -> None:
    result = _scan(
        "<html><body><p>本报告为描述性归档。</p></body></html>",
        strict=True,
    )

    assert [hit.kind for hit in result.hits] == ["missing_as_of"]


def test_cli_exit_codes(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(_archive_manifest()), encoding="utf-8")
    passing = tmp_path / "pass.html"
    passing.write_text("<html><body><p>288 条里增长 40%。</p></body></html>", encoding="utf-8")
    failing = tmp_path / "fail.html"
    failing.write_text("<html><body><p>增长 40%。</p></body></html>", encoding="utf-8")

    assert gate_main(["--html", str(passing), "--manifest", str(manifest_path)]) == 0
    assert gate_main(["--html", str(failing), "--manifest", str(manifest_path)]) == 1