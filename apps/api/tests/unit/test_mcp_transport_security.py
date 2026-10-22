from data_intelligence_hub.mcp_runtime.server import MCP_TRANSPORT_SECURITY


def test_transport_allowlist_contains_production_host_and_origin() -> None:
    for host in ("scrapy.luteos.com", "scrapy.lute-tlz-dddd.top"):
        assert host in MCP_TRANSPORT_SECURITY.allowed_hosts
        assert f"{host}:*" in MCP_TRANSPORT_SECURITY.allowed_hosts
        assert f"https://{host}" in MCP_TRANSPORT_SECURITY.allowed_origins


def test_transport_allowlist_excludes_unknown_host() -> None:
    assert "malicious.example" not in MCP_TRANSPORT_SECURITY.allowed_hosts
