"""SpiderFoot purpose-built collectors for high-value OSINT use cases.

Each collector wraps the generic SpiderFootDomainCollector with a
curated module set targeting a specific intelligence objective.

Environment variables:
    SPIDERFOOT_BASE_URL   Required — self-hosted SpiderFoot URL
    SPIDERFOOT_TIMEOUT    Total scan timeout in seconds (default 300)
"""
from __future__ import annotations

from typing import Any

from data_intelligence_hub.collectors.spiderfoot_collector import (
    _SpiderFootCollector,
    require_text,
)

_SF_MODULES_SUBDOMAIN = [
    "sfp_dnsbrute", "sfp_dnsdumpster", "sfp_virustotal",
    "sfp_threatcrowd", "sfp_certspotter", "sfp_crt",
    "sfp_hackertarget", "sfp_shodan",
]

_SF_MODULES_THREAT = [
    "sfp_virustotal", "sfp_threatcrowd", "sfp_alienvault",
    "sfp_greynoise", "sfp_ipinfo", "sfp_abuseipdb",
    "sfp_blocklist_de", "sfp_spamhaus", "sfp_sans",
]

_SF_MODULES_BREACH = [
    "sfp_haveibeenpwned", "sfp_dehashed", "sfp_leakcheck",
    "sfp_hunterio", "sfp_emailrep",
]

_SF_MODULES_CERT = [
    "sfp_crt", "sfp_certspotter", "sfp_circl",
    "sfp_googlesafe", "sfp_ssltools",
]

_SF_MODULES_DARKWEB = [
    "sfp_ahmia", "sfp_onionscan", "sfp_darksearch",
    "sfp_torch",
]

_SF_MODULES_ATTACK_SURFACE = [
    "sfp_shodan", "sfp_censys", "sfp_binaryedge",
    "sfp_hackertarget", "sfp_dnsbrute", "sfp_portscan_tcp",
    "sfp_nmap", "sfp_crt", "sfp_dnsdumpster",
    "sfp_virustotal", "sfp_robtex",
]


class SpiderFootSubdomainCollector(_SpiderFootCollector):
    collector_type = "spiderfoot_subdomain_enum"
    _target_type = "domain"

    def validate_config(self) -> dict[str, Any]:
        target = require_text(self.config, "target")
        return {"target": target, "modules": _SF_MODULES_SUBDOMAIN}


class SpiderFootThreatIntelCollector(_SpiderFootCollector):
    collector_type = "spiderfoot_threat_intel"
    _target_type = "ip"

    def validate_config(self) -> dict[str, Any]:
        target = require_text(self.config, "target")
        return {"target": target, "modules": _SF_MODULES_THREAT}


class SpiderFootBreachCollector(_SpiderFootCollector):
    collector_type = "spiderfoot_breach_check"
    _target_type = "email"

    def validate_config(self) -> dict[str, Any]:
        target = require_text(self.config, "target")
        return {"target": target, "modules": _SF_MODULES_BREACH}


class SpiderFootCertCollector(_SpiderFootCollector):
    collector_type = "spiderfoot_cert_transparency"
    _target_type = "domain"

    def validate_config(self) -> dict[str, Any]:
        target = require_text(self.config, "target")
        return {"target": target, "modules": _SF_MODULES_CERT}


class SpiderFootDarkWebCollector(_SpiderFootCollector):
    collector_type = "spiderfoot_dark_web"
    _target_type = "domain"

    def validate_config(self) -> dict[str, Any]:
        target = require_text(self.config, "target")
        return {"target": target, "modules": _SF_MODULES_DARKWEB}


class SpiderFootAttackSurfaceCollector(_SpiderFootCollector):
    collector_type = "spiderfoot_attack_surface"
    _target_type = "domain"

    def validate_config(self) -> dict[str, Any]:
        target = require_text(self.config, "target")
        return {"target": target, "modules": _SF_MODULES_ATTACK_SURFACE}
