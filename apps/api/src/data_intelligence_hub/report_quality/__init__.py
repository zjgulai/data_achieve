"""Business-report language and number gate.

One rule catalog, one owner, one allowlist. The gate is intentionally
dependency-free so the API importer, the insight-report validator, the daily
report script, and CI can all call the same implementation.

Checks:
- banned plain-language terms, with a narrow allowlist for explicit negations
  and existing structural labels;
- every percentage has a denominator in its text block, exhibit container, or
  (for a section heading) the next exhibit;
- every chart figure declares a source and a scope;
- every report declares an evidence grade or a descriptive-archive status.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, cast

RULES_PATH = Path(__file__).with_name("rules.json")

BLOCK_TAGS = frozenset(
    {
        "p",
        "li",
        "td",
        "th",
        "figcaption",
        "caption",
        "blockquote",
        "dt",
        "dd",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
    }
)
CONTAINER_TAGS = frozenset({"figure", "table"})
CONTAINER_CLASS_HINTS = ("kpi", "answer", "takeaways", "chart-wrap", "hero")
SKIP_TAGS = frozenset({"script", "style", "noscript", "template"})
HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
CHART_TAGS = frozenset({"svg", "img"})
TEXT_ATTRIBUTES = ("title", "alt", "aria-label")
PERCENT_RE = re.compile(r"\d+(?:\.\d+)?\s*%")
DATE_RE = re.compile(r"\b20\d{2}-\d{2}-\d{2}\b")


@dataclass(frozen=True)
class Hit:
    """One failed check, with a source line and a short visible snippet."""

    kind: str
    message: str
    line: int
    snippet: str
    term: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "message": self.message,
            "line": self.line,
            "snippet": self.snippet,
            "term": self.term,
        }


@dataclass
class GateResult:
    """Result of one report scan."""

    hits: list[Hit] = field(default_factory=list)
    checked_percentages: int = 0
    checked_figures: int = 0
    evidence: str = "missing"

    @property
    def ok(self) -> bool:
        return not self.hits

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "hits": [hit.to_dict() for hit in self.hits],
            "checked_percentages": self.checked_percentages,
            "checked_figures": self.checked_figures,
            "evidence": self.evidence,
        }


def load_rules(path: Path | None = None) -> dict[str, Any]:
    """Load the single rule catalog."""

    rules_path = path or RULES_PATH
    return cast(dict[str, Any], json.loads(rules_path.read_text(encoding="utf-8")))


class _ReportParser(HTMLParser):
    """Collect visible text with its block and exhibit context."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tokens: list[dict[str, Any]] = []
        self.blocks: dict[int, dict[str, Any]] = {}
        self.containers: dict[int, dict[str, Any]] = {}
        self.stack: list[dict[str, Any]] = []
        self._next_id = 0
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key: value or "" for key, value in attrs}
        if tag in SKIP_TAGS:
            self._skip_depth += 1

        node: dict[str, Any] = {
            "tag": tag,
            "block_id": None,
            "container_id": None,
            "in_skip": tag in SKIP_TAGS,
        }
        if tag in BLOCK_TAGS:
            block_id = self._new_id()
            self.blocks[block_id] = {
                "tag": tag,
                "line": self.getpos()[0],
                "text": [],
            }
            node["block_id"] = block_id
        if tag in CONTAINER_TAGS or self._is_container(attributes):
            container_id = self._new_id()
            self.containers[container_id] = {
                "tag": tag,
                "line": self.getpos()[0],
                "class": attributes.get("class", ""),
                "text": [],
                "has_chart": False,
            }
            node["container_id"] = container_id

        self.stack.append(node)
        if tag in CHART_TAGS:
            for active in reversed(self.stack):
                container_id = active["container_id"]
                if container_id is not None and self.containers[container_id]["tag"] == "figure":
                    self.containers[container_id]["has_chart"] = True
                    break
        for attribute in TEXT_ATTRIBUTES:
            value = attributes.get(attribute, "").strip()
            if value:
                self._emit(value, self.getpos()[0])

    def handle_endtag(self, tag: str) -> None:
        while self.stack:
            node = self.stack.pop()
            if node["tag"] == tag:
                break
        if tag in SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if data.strip():
            self._emit(data, self.getpos()[0])

    def _emit(self, text: str, line: int) -> None:
        block_id = next(
            (node["block_id"] for node in reversed(self.stack) if node["block_id"] is not None),
            None,
        )
        container_ids = [
            node["container_id"] for node in self.stack if node["container_id"] is not None
        ]
        self.tokens.append(
            {
                "text": text,
                "line": line,
                "block_id": block_id,
                "container_ids": container_ids,
            }
        )
        if block_id is not None:
            self.blocks[block_id]["text"].append(text)
        for container_id in container_ids:
            self.containers[container_id]["text"].append(text)

    def _new_id(self) -> int:
        self._next_id += 1
        return self._next_id

    @staticmethod
    def _is_container(attributes: dict[str, str]) -> bool:
        class_name = attributes.get("class", "")
        return any(hint in class_name for hint in CONTAINER_CLASS_HINTS)


def _text_of(entity: dict[str, Any]) -> str:
    return " ".join(part.strip() for part in entity["text"] if part.strip())


class _Scanner:
    def __init__(
        self,
        *,
        rules: dict[str, Any],
        manifest: dict[str, Any] | None,
        strict: bool,
    ) -> None:
        self.rules = rules
        self.manifest = manifest or {}
        self.strict = strict
        self.result = GateResult()
        self.denominator_re = self._compile_denominator_re()

    def scan(self, html: str) -> GateResult:
        parser = _ReportParser()
        parser.feed(html)
        parser.close()

        block_texts = {key: _text_of(value) for key, value in parser.blocks.items()}
        container_texts = {
            key: _text_of(value) for key, value in parser.containers.items()
        }
        ordered_containers = sorted(
            parser.containers.items(), key=lambda item: item[1]["line"]
        )
        full_text = " ".join(token["text"] for token in parser.tokens)

        for token in parser.tokens:
            text = token["text"]
            block_id = token["block_id"]
            block_text = block_texts.get(block_id, "") if block_id is not None else ""
            contexts = [container_texts[cid] for cid in token["container_ids"]]
            self._scan_banned_terms(text, token["line"], block_text, contexts)
            self._scan_percentages(
                text,
                token["line"],
                block_id,
                block_text,
                contexts,
                parser.blocks,
                ordered_containers,
            )

        self._scan_figures(parser.containers, container_texts)
        self._check_evidence(full_text)
        if self.strict:
            self._check_as_of(full_text)
        return self.result

    def _compile_denominator_re(self) -> re.Pattern[str]:
        terms = [re.escape(term) for term in self.rules.get("denominator_terms", [])]
        return re.compile(r"(?:" + "|".join(terms) + r"|\d+\s*/\s*\d+)")

    def _scan_banned_terms(
        self,
        text: str,
        line: int,
        block_text: str,
        contexts: list[str],
    ) -> None:
        for rule in self.rules.get("banned_terms", []):
            term = rule["term"]
            start = 0
            while True:
                index = text.find(term, start)
                if index < 0:
                    break
                start = index + len(term)
                window = text[max(0, index - 40) : index + len(term) + 40]
                allow_context = " ".join([window, block_text, *contexts])
                if self._is_allowed(term, allow_context):
                    continue
                snippet = _snippet(text, index, len(term))
                self.result.hits.append(
                    Hit(
                        kind="banned_term",
                        term=term,
                        line=line,
                        snippet=snippet,
                        message=(
                            f"禁用词「{term}」；改为：{rule.get('suggestion', '改用读者的话')}"
                        ),
                    )
                )

    def _is_allowed(self, term: str, context: str) -> bool:
        for rule in self.rules.get("allowlist", []):
            if rule.get("term") != term:
                continue
            if re.search(rule["regex"], context):
                return True
        return False

    def _scan_percentages(
        self,
        text: str,
        line: int,
        block_id: int | None,
        block_text: str,
        contexts: list[str],
        blocks: dict[int, dict[str, Any]],
        ordered_containers: list[tuple[int, dict[str, Any]]],
    ) -> None:
        window = int(self.rules.get("denominator_window", 20))
        block = blocks.get(block_id, {}) if block_id is not None else {}
        next_exhibit = ""
        if block.get("tag") in HEADING_TAGS and self.rules.get(
            "allow_percent_in_heading_with_next_exhibit", True
        ):
            next_exhibit = self._next_exhibit_text(
                int(block.get("line", 0)), ordered_containers
            )
        allow_context = " ".join([block_text, *contexts])
        for match in PERCENT_RE.finditer(text):
            self.result.checked_percentages += 1
            local = text[max(0, match.start() - window) : match.end() + window]
            candidates = [local, block_text, *contexts]
            if next_exhibit:
                candidates.append(next_exhibit)
            if any(
                re.search(rule["regex"], allow_context)
                for rule in self.rules.get("percent_allowlist", [])
            ):
                continue
            if any(self.denominator_re.search(candidate) for candidate in candidates):
                continue
            self.result.hits.append(
                Hit(
                    kind="percent_without_denominator",
                    line=line,
                    snippet=_snippet(text, match.start(), len(match.group())),
                    message=(
                        f"百分比「{match.group().strip()}」在 20 字内没有分母；"
                        "补条数、样本、记录或总数"
                    ),
                )
            )

    @staticmethod
    def _next_exhibit_text(
        line: int, ordered_containers: list[tuple[int, dict[str, Any]]]
    ) -> str:
        for _, container in ordered_containers:
            if (
                container["line"] > line
                and container["line"] - line <= 12
                and container["tag"] in {"figure", "table"}
            ):
                return _text_of(container)
        return ""

    def _scan_figures(
        self,
        containers: dict[int, dict[str, Any]],
        container_texts: dict[int, str],
    ) -> None:
        source_markers = self.rules.get("chart_source_markers", [])
        scope_markers = self.rules.get("chart_scope_markers", [])
        for container_id, container in containers.items():
            if container["tag"] != "figure" or not container["has_chart"]:
                continue
            self.result.checked_figures += 1
            text = container_texts.get(container_id, "")
            if not any(marker in text for marker in source_markers):
                self.result.hits.append(
                    Hit(
                        kind="chart_without_source",
                        line=int(container["line"]),
                        snippet=text[:120],
                        message="图表没有写数据来源",
                    )
                )
            if not any(marker in text for marker in scope_markers):
                self.result.hits.append(
                    Hit(
                        kind="chart_without_scope",
                        line=int(container["line"]),
                        snippet=text[:120],
                        message="图表没有写统计范围或分母",
                    )
                )

    def _check_evidence(self, full_text: str) -> None:
        status = str(self.manifest.get("source_status", ""))
        if status in self.rules.get("archive_statuses", []):
            self.result.evidence = "descriptive_archive"
            return
        markers = self.rules.get("evidence_markers", [])
        if any(marker in full_text for marker in markers):
            self.result.evidence = "evidence_grade"
            return
        self.result.hits.append(
            Hit(
                kind="missing_evidence",
                line=1,
                snippet="",
                message=(
                    "报告没有证据等级，也没有声明描述性归档；"
                    "在 manifest 写 source_status=snapshot_only 或在正文标注"
                ),
            )
        )

    def _check_as_of(self, full_text: str) -> None:
        generated_at = self.manifest.get("generated_at")
        if generated_at:
            return
        if DATE_RE.search(full_text):
            return
        self.result.hits.append(
            Hit(
                kind="missing_as_of",
                line=1,
                snippet="",
                message="strict 模式要求 manifest 的 generated_at 或正文日期",
            )
        )


def _snippet(text: str, index: int, length: int) -> str:
    start = max(0, index - 30)
    end = min(len(text), index + length + 30)
    return re.sub(r"\s+", " ", text[start:end]).strip()


def check_html_report(
    html: str,
    *,
    manifest: dict[str, Any] | None = None,
    rules: dict[str, Any] | None = None,
    strict: bool = False,
) -> GateResult:
    """Scan one HTML report and return all gate failures."""

    return _Scanner(
        rules=rules or load_rules(),
        manifest=manifest,
        strict=strict,
    ).scan(html)


def check_text_report(
    text: str,
    *,
    manifest: dict[str, Any] | None = None,
    rules: dict[str, Any] | None = None,
    strict: bool = False,
) -> GateResult:
    """Scan plain text or Markdown after removing HTML tags."""

    stripped = re.sub(r"<[^>]+>", " ", text)
    return check_html_report(
        stripped,
        manifest=manifest,
        rules=rules,
        strict=strict,
    )


__all__ = [
    "GateResult",
    "Hit",
    "RULES_PATH",
    "check_html_report",
    "check_text_report",
    "load_rules",
]