"""Explicit isolation for legacy adapter unit tests, never for policy/route tests."""

from __future__ import annotations

import asyncio
import importlib
import socket
import subprocess
from collections.abc import Iterator

import pytest

# These suites exercise parsing and mocked transport handling behind the entry
# gate. The public entry gate is tested without this fixture in outbound suites.
_LEGACY_ADAPTERS = {
    "test_anycrawl_collector.py": "anycrawl_collector",
    "test_anydoc_collector.py": "anydoc_collector",
    "test_browser_use_collector.py": "browser_use_collector",
    "test_firecrawl_collector.py": "firecrawl_collector",
    "test_mediacrawler_collector.py": "mediacrawler_collector",
    "test_osint_collector.py": "osint_collector",
    "test_spiderfoot_collector.py": "spiderfoot_collector",
    "test_tech_blog_collector.py": "tech_blog_collector",
    "test_twscrape_collector.py": "twscrape_collector",
    "test_wappalyzer_collector.py": "wappalyzer_collector",
}


@pytest.fixture()
def isolated_adapter_transport(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    name = request.path.name
    module_name = _LEGACY_ADAPTERS.get(name)
    if module_name is None:
        pytest.fail("adapter-only fixture cannot be used by policy or integration suites")
    module = importlib.import_module(f"data_intelligence_hub.collectors.{module_name}")

    def no_external_activity(*args: object, **kwargs: object) -> None:
        pytest.fail("legacy adapter unit test attempted real network or subprocess activity")

    monkeypatch.setattr(socket.socket, "connect", no_external_activity)
    monkeypatch.setattr(socket.socket, "connect_ex", no_external_activity)
    monkeypatch.setattr(socket, "getaddrinfo", no_external_activity)
    monkeypatch.setattr(subprocess, "Popen", no_external_activity)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", no_external_activity)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", no_external_activity)
    monkeypatch.setattr(module, "assert_collector_allowed", lambda _collector_type: None)
    yield
