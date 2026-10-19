"""SpiderFoot purpose-built collectors for high-value OSINT use cases.

Each collector wraps the generic SpiderFootDomainCollector with a
curated module set targeting a specific intelligence objective.

Module names are verified against smicallef/spiderfoot `modules/`. SpiderFoot
ignores names it does not know without failing the scan, so a typo silently
reduces coverage instead of raising. Several modules below need their own API
key inside SpiderFoot (e.g. sfp_shodan, sfp_censys, sfp_virustotal); without it
they contribute nothing. Per-scan module errors are reported in the collected
record's `module_errors`, which is how a key-gated module becomes visible.

Environment variables:
    SPIDERFOOT_BASE_URL   Required — self-hosted SpiderFoot URL
    SPIDERFOOT_TIMEOUT    Total scan timeout in seconds (default 300)
"""
from __future__ import annotations

from typing import Any

from data_intelligence_hub.collectors.spiderfoot_collector import (
    _SpiderFootCollector,
)

_SF_MODULES_SUBDOMAIN = [
    "sfp_dnsbrute", "sfp_dnsdumpster", "sfp_virustotal",
    "sfp_threatcrowd", "sfp_certspotter", "sfp_crt",
    "sfp_hackertarget", "sfp_shodan",
]

_SF_MODULES_THREAT = [
    "sfp_virustotal", "sfp_threatcrowd", "sfp_alienvault",
    "sfp_greynoise", "sfp_ipinfo", "sfp_abuseipdb",
    "sfp_blocklistde", "sfp_spamhaus",
]

_SF_MODULES_BREACH = [
    "sfp_haveibeenpwned", "sfp_dehashed",
    "sfp_hunter", "sfp_emailrep",
]

_SF_MODULES_CERT = [
    "sfp_crt", "sfp_certspotter", "sfp_circllu",
    "sfp_googlesafebrowsing",
]

_SF_MODULES_DARKWEB = [
    "sfp_ahmia", "sfp_onionsearchengine",
    "sfp_torch",
]

_SF_MODULES_ATTACK_SURFACE = [
    "sfp_shodan", "sfp_censys", "sfp_binaryedge",
    "sfp_hackertarget", "sfp_dnsbrute", "sfp_portscan_tcp",
    "sfp_tool_nmap", "sfp_crt", "sfp_dnsdumpster",
    "sfp_virustotal", "sfp_robtex",
]


class SpiderFootSubdomainCollector(_SpiderFootCollector):
    collector_type = "spiderfoot_subdomain_enum"
    allow_empty = True
    _target_type = "domain"

    def validate_config(self) -> dict[str, Any]:
        config = super().validate_config()
        config["modules"] = _SF_MODULES_SUBDOMAIN
        return config


class SpiderFootThreatIntelCollector(_SpiderFootCollector):
    collector_type = "spiderfoot_threat_intel"
    allow_empty = True
    _target_type = "ip"

    def validate_config(self) -> dict[str, Any]:
        config = super().validate_config()
        config["modules"] = _SF_MODULES_THREAT
        return config


class SpiderFootBreachCollector(_SpiderFootCollector):
    collector_type = "spiderfoot_breach_check"
    allow_empty = True
    _target_type = "email"

    def validate_config(self) -> dict[str, Any]:
        config = super().validate_config()
        config["modules"] = _SF_MODULES_BREACH
        return config


class SpiderFootCertCollector(_SpiderFootCollector):
    collector_type = "spiderfoot_cert_transparency"
    allow_empty = True
    _target_type = "domain"

    def validate_config(self) -> dict[str, Any]:
        config = super().validate_config()
        config["modules"] = _SF_MODULES_CERT
        return config


class SpiderFootDarkWebCollector(_SpiderFootCollector):
    collector_type = "spiderfoot_dark_web"
    allow_empty = True
    _target_type = "domain"

    def validate_config(self) -> dict[str, Any]:
        config = super().validate_config()
        config["modules"] = _SF_MODULES_DARKWEB
        return config


class SpiderFootAttackSurfaceCollector(_SpiderFootCollector):
    collector_type = "spiderfoot_attack_surface"
    allow_empty = True
    _target_type = "domain"

    def validate_config(self) -> dict[str, Any]:
        config = super().validate_config()
        config["modules"] = _SF_MODULES_ATTACK_SURFACE
        return config
