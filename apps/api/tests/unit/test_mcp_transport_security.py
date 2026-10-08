from data_intelligence_hub.mcp_runtime.server import MCP_TRANSPORT_SECURITY


def test_transport_allowlist_contains_production_host_and_origin() -> None:
    assert "scrapy.luteos.com" in MCP_TRANSPORT_SECURITY.allowed_hosts
    assert "scrapy.luteos.com:*" in MCP_TRANSPORT_SECURITY.allowed_hosts
    assert "https://scrapy.luteos.com" in MCP_TRANSPORT_SECURITY.allowed_origins


def test_transport_allowlist_excludes_unknown_host() -> None:
    assert "malicious.example" not in MCP_TRANSPORT_SECURITY.allowed_hosts
