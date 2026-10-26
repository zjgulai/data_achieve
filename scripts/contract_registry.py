#!/usr/bin/env python3
"""Extract, validate, generate, and compare the DIH contract registry.

The Markdown contract is authoritative. The registry JSON block lives inside
the contract. This script never writes the Markdown.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

BEGIN = "<!-- contract-registry:begin -->"
END = "<!-- contract-registry:end -->"
FENCE_OPEN = "```json"
FENCE_CLOSE = "```"


class RegistryError(ValueError):
    """A deterministic registry error. The message is the error code."""


def extract_registry_block(markdown: str) -> dict[str, Any]:
    if markdown.count(BEGIN) == 0 or markdown.count(END) == 0:
        raise RegistryError("registry_block_missing")
    if markdown.count(BEGIN) != 1 or markdown.count(END) != 1:
        raise RegistryError("registry_block_duplicate")
    start = markdown.find(BEGIN)
    end = markdown.find(END)
    if end <= start:
        raise RegistryError("registry_block_order")
    body = markdown[start + len(BEGIN):end].strip()
    if not body.startswith(FENCE_OPEN) or not body.endswith(FENCE_CLOSE):
        raise RegistryError("registry_block_fence_invalid")
    payload = body[len(FENCE_OPEN):-len(FENCE_CLOSE)].strip()
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RegistryError(
            f"registry_block_json_invalid:{exc.lineno}:{exc.colno}"
        ) from exc
    if not isinstance(value, dict):
        raise RegistryError("registry_block_not_object")
    return value


def canonical_dump(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def _resolve_ref(ref: str, root: dict[str, Any]) -> dict[str, Any]:
    prefix = "#/$defs/"
    if not ref.startswith(prefix):
        raise RegistryError(f"unsupported_ref:{ref}")
    name = ref.removeprefix(prefix)
    definitions = root.get("$defs")
    if not isinstance(definitions, dict) or name not in definitions:
        raise RegistryError(f"missing_def:{name}")
    target = definitions[name]
    if not isinstance(target, dict):
        raise RegistryError(f"def_not_object:{name}")
    return target


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    return False


def _validate_value(
    value: Any,
    schema: dict[str, Any],
    root: dict[str, Any],
    path: str,
) -> list[str]:
    errors: list[str] = []
    if "$ref" in schema:
        return _validate_value(value, _resolve_ref(str(schema["$ref"]), root), root, path)
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}:const")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}:enum")
    expected_type = schema.get("type")
    if expected_type is not None and not _type_matches(value, str(expected_type)):
        errors.append(f"{path}:type")
        return errors
    if isinstance(value, str):
        if "minLength" in schema and len(value) < int(schema["minLength"]):
            errors.append(f"{path}:minLength")
        if "maxLength" in schema and len(value) > int(schema["maxLength"]):
            errors.append(f"{path}:maxLength")
        pattern = schema.get("pattern")
        # JSON Schema ``pattern`` is an unanchored regular expression: it
        # matches when the pattern occurs anywhere in the string. Use
        # ``re.search`` and let schemas anchor with ``^`` / ``$`` themselves.
        if pattern is not None and re.search(str(pattern), value) is None:
            errors.append(f"{path}:pattern")
    is_number = isinstance(value, (int, float)) and not isinstance(value, bool)
    if is_number:
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}:minimum")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}:maximum")
    if isinstance(value, list):
        if "minItems" in schema and len(value) < int(schema["minItems"]):
            errors.append(f"{path}:minItems")
        if "maxItems" in schema and len(value) > int(schema["maxItems"]):
            errors.append(f"{path}:maxItems")
        if schema.get("uniqueItems") is True:
            encoded = [json.dumps(item, ensure_ascii=False, sort_keys=True) for item in value]
            if len(encoded) != len(set(encoded)):
                errors.append(f"{path}:uniqueItems")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(
                    _validate_value(item, item_schema, root, f"{path}[{index}]")
                )
    if isinstance(value, dict):
        required = schema.get("required", [])
        if isinstance(required, list):
            for key in required:
                if key not in value:
                    errors.append(f"{path}:required:{key}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False and isinstance(properties, dict):
            for key in value:
                if key not in properties:
                    errors.append(f"{path}:additional:{key}")
        if isinstance(properties, dict):
            for key, child_schema in properties.items():
                if key in value and isinstance(child_schema, dict):
                    errors.extend(
                        _validate_value(value[key], child_schema, root, f"{path}.{key}")
                    )
    return errors


def validate_registry(
    registry: dict[str, Any],
    schema: dict[str, Any],
) -> list[str]:
    errors = _validate_value(registry, schema, schema, "$")
    errors.extend(check_semantics(registry))
    return errors


def check_semantics(registry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    phases = [str(item.get("id")) for item in registry.get("phases", [])]
    expected_phases = [f"C{index}" for index in range(2, 15)]
    if phases != expected_phases:
        errors.append("phase_sequence_invalid")

    tables = registry.get("tables", [])
    table_names = [str(item.get("name")) for item in tables]
    if len(table_names) != len(set(table_names)):
        errors.append("duplicate_table")
    for table in tables:
        columns = [str(item.get("name")) for item in table.get("columns", [])]
        if len(columns) != len(set(columns)):
            errors.append(f"duplicate_column:{table.get('name')}")

    enums = registry.get("enums", [])
    enum_names = [str(item.get("name")) for item in enums]
    if len(enum_names) != len(set(enum_names)):
        errors.append("duplicate_enum")
    for item in enums:
        values = [str(value) for value in item.get("values", [])]
        banned = {str(value) for value in item.get("banned_values", [])}
        if banned.intersection(values):
            errors.append(f"banned_enum_value:{item.get('name')}")

    paths = registry.get("paths", [])
    path_keys = [(str(item.get("method")), str(item.get("path"))) for item in paths]
    if len(path_keys) != len(set(path_keys)):
        errors.append("duplicate_path")
    path_ids = [str(item.get("id")) for item in paths]
    if len(path_ids) != len(set(path_ids)):
        errors.append("duplicate_path_id")
    for item in paths:
        idempotency = item.get("idempotency")
        if not isinstance(idempotency, dict):
            continue
        if item.get("idempotent") is not True:
            errors.append(f"idempotency_path_not_idempotent:{item.get('id')}")
        path_codes = {str(code) for code in item.get("error_codes", [])}
        if str(idempotency.get("conflict_error")) not in path_codes:
            errors.append(f"idempotency_conflict_unbound:{item.get('id')}")

    page_routes = registry.get("page_routes", [])
    page_paths = [str(item.get("path")) for item in page_routes]
    if len(page_paths) != 11:
        errors.append("page_route_count")
    if len(page_paths) != len(set(page_paths)):
        errors.append("duplicate_page_route")
    if any(path.startswith("/api/") for path in page_paths):
        errors.append("page_route_is_api_path")
    enabled_routes = [item for item in page_routes if item.get("enabled") is True]
    disabled_routes = [item for item in page_routes if item.get("enabled") is False]
    if len(enabled_routes) != 10:
        errors.append("page_route_enabled_count")
    if [str(item.get("path")) for item in disabled_routes] != [
        "/reports/public/[id]"
    ]:
        errors.append("page_route_disabled_set")
    for item in page_routes:
        kind = item.get("kind")
        segment = item.get("dynamic_segment")
        if kind == "dynamic":
            if not isinstance(segment, str) or f"[{segment}]" not in str(
                item.get("path")
            ):
                errors.append(f"page_route_dynamic_segment:{item.get('id')}")
        elif kind == "static" and "dynamic_segment" in item:
            errors.append(f"page_route_static_has_segment:{item.get('id')}")

    primary_nav = registry.get("primary_nav", [])
    nav_paths = [str(item.get("path")) for item in primary_nav]
    nav_ids = [str(item.get("id")) for item in primary_nav]
    if len(nav_paths) != 4:
        errors.append("primary_nav_count")
    if nav_ids != ["workbench", "reports", "connectors", "settings"]:
        errors.append("primary_nav_ids")
    if nav_paths != ["/workbench", "/reports", "/connectors", "/settings"]:
        errors.append("primary_nav_paths")
    if [item.get("order") for item in primary_nav] != [1, 2, 3, 4]:
        errors.append("primary_nav_order")
    if not set(nav_paths).issubset(
        {str(item.get("path")) for item in enabled_routes}
    ):
        errors.append("primary_nav_not_page_route")

    audit_actions = registry.get("audit_actions", {}).get("actions", [])
    action_names = [str(item.get("name")) for item in audit_actions]
    if len(action_names) != len(set(action_names)):
        errors.append("duplicate_audit_action")
    for action_name in action_names:
        if len(action_name) > 80:
            errors.append(f"audit_action_too_long:{action_name}")

    deferred_names = {str(item.get("name")) for item in registry.get("deferred", [])}
    if deferred_names.intersection(table_names):
        errors.append("deferred_object_registered")

    tools = registry.get("mcp", {}).get("tools", [])
    tool_names = [str(item.get("name")) for item in tools]
    if len(tool_names) != 8:
        errors.append("mcp_tool_count")
    if len(tool_names) != len(set(tool_names)):
        errors.append("duplicate_mcp_tool")

    errors.extend(check_schema_refs_exist(registry))
    return errors


def check_schema_refs_exist(registry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    root = Path(__file__).resolve().parents[1]
    for item in registry.get("schemas", []):
        path = root / str(item.get("path"))
        if not path.exists():
            errors.append(f"schema_file_missing:{item.get('path')}")
    for tool in registry.get("mcp", {}).get("tools", []):
        for key in ("input_ref", "output_ref"):
            ref = str(tool.get(key, ""))
            if "#/$defs/" not in ref:
                errors.append(f"mcp_ref_invalid:{tool.get('name')}:{key}")
    return errors


def build(doc: Path, schema_path: Path, out: Path) -> int:
    registry = extract_registry_block(doc.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = validate_registry(registry, schema)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    out.write_text(canonical_dump(registry), encoding="utf-8")
    print(f"registry built: {out}")
    return 0


def check(doc: Path, schema_path: Path, registry_path: Path) -> int:
    registry = extract_registry_block(doc.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = validate_registry(registry, schema)
    if registry_path.read_text(encoding="utf-8") != canonical_dump(registry):
        errors.append("registry_out_of_date")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"registry check OK: {registry_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--doc", type=Path, required=True)
    build_parser.add_argument("--schema", type=Path, required=True)
    build_parser.add_argument("--out", type=Path, required=True)

    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("--doc", type=Path, required=True)
    check_parser.add_argument("--schema", type=Path, required=True)
    check_parser.add_argument("--registry", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.command == "build":
        return build(args.doc, args.schema, args.out)
    if args.command == "check":
        return check(args.doc, args.schema, args.registry)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
