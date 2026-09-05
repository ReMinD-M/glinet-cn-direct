#!/usr/bin/env python3
from __future__ import annotations

import ipaddress
import json
import re
import urllib.request
from pathlib import Path

OUT_FULL = Path("glinet-cn-direct.txt")
OUT_LITE = Path("glinet-cn-direct-lite.txt")
STATUS = Path("status.json")
EXTRA = Path("extra_domains.txt")

SOURCES = {
    "chnroute": "https://raw.githubusercontent.com/mayaxcn/china-ip-list/master/chnroute.txt",
    "china": "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/China/China.list",
    "tencent": "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Tencent/Tencent.list",
}

DOMAIN_RE = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", re.I)

def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "glinet-cn-direct-builder/1.0"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8", errors="replace")

def clean_domain(s: str) -> str | None:
    s = s.strip().lower().rstrip(".").lstrip(".")
    if not s or " " in s or "/" in s:
        return None

    # GL.iNet VPN Dashboard rejects domains beginning with a digit.
    if not s[0].isalpha():
        return None

    return s if DOMAIN_RE.fullmatch(s) else None

def parse_ip_lines(text: str) -> set[ipaddress.IPv4Network]:
    out = set()
    for raw in text.splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        try:
            net = ipaddress.ip_network(s, strict=False)
            if isinstance(net, ipaddress.IPv4Network):
                out.add(net)
        except ValueError:
            pass
    return out

def parse_clash(text: str):
    domains: set[str] = set()
    ipv4: set[ipaddress.IPv4Network] = set()
    for raw in text.splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        parts = [p.strip() for p in s.split(",")]
        kind = parts[0].upper()
        if kind in ("DOMAIN-SUFFIX", "DOMAIN") and len(parts) >= 2:
            d = clean_domain(parts[1])
            if d:
                domains.add(d)
        elif kind == "IP-CIDR" and len(parts) >= 2:
            try:
                net = ipaddress.ip_network(parts[1], strict=False)
                if isinstance(net, ipaddress.IPv4Network):
                    ipv4.add(net)
            except ValueError:
                pass
        # DOMAIN-KEYWORD and IPv6 rules are intentionally ignored:
        # GL.iNet's documented URL filter format supports domains and IPv4/CIDR,
        # not Clash keyword syntax.
    return domains, ipv4

def load_extra() -> set[str]:
    out = set()
    if EXTRA.exists():
        for raw in EXTRA.read_text(encoding="utf-8").splitlines():
            s = raw.strip()
            if not s or s.startswith("#"):
                continue
            d = clean_domain(s)
            if d:
                out.add(d)
    return out

def collapse_domains(domains: set[str]) -> list[str]:
    # GL.iNet says a root domain matches all subdomains.
    # Therefore if qq.com exists, finder.video.qq.com is redundant.
    kept: set[str] = set()
    for d in sorted(domains, key=lambda x: (x.count("."), len(x), x)):
        labels = d.split(".")
        redundant = False
        for i in range(1, len(labels) - 1):
            parent = ".".join(labels[i:])
            if parent in kept:
                redundant = True
                break
        if not redundant:
            kept.add(d)
    return sorted(kept)

def collapse_ipv4(nets: set[ipaddress.IPv4Network]) -> list[str]:
    return [str(n) for n in ipaddress.collapse_addresses(sorted(nets, key=lambda n: (int(n.network_address), n.prefixlen)))]

def write_list(path: Path, ips: list[str], domains: list[str]):
    # No comments: keep every line directly consumable by GL.iNet.
    path.write_text("\n".join(ips + domains) + "\n", encoding="utf-8")

def main():
    chnroute_text = fetch(SOURCES["chnroute"])
    china_text = fetch(SOURCES["china"])
    tencent_text = fetch(SOURCES["tencent"])

    cn_ips = parse_ip_lines(chnroute_text)
    china_domains, china_ips = parse_clash(china_text)
    tencent_domains, tencent_ips = parse_clash(tencent_text)
    extra_domains = load_extra()

    # Safety checks so a temporary upstream failure doesn't publish an empty/broken list.
    if len(cn_ips) < 5000:
        raise RuntimeError(f"chnroute source unexpectedly small: {len(cn_ips)} IPv4 networks")
    if len(china_domains) < 2000:
        raise RuntimeError(f"China domain source unexpectedly small: {len(china_domains)} domains")
    if len(tencent_domains) < 1000:
        raise RuntimeError(f"Tencent source unexpectedly small: {len(tencent_domains)} domains")

    full_ips = collapse_ipv4(cn_ips | china_ips | tencent_ips)
    full_domains = collapse_domains(china_domains | tencent_domains | extra_domains)

    lite_ips = collapse_ipv4(cn_ips | tencent_ips)
    lite_domains = collapse_domains(tencent_domains | extra_domains)

    write_list(OUT_FULL, full_ips, full_domains)
    write_list(OUT_LITE, lite_ips, lite_domains)

    status = {
        "sources": SOURCES,
        "full": {
            "ipv4_networks": len(full_ips),
            "domains": len(full_domains),
            "total_lines": len(full_ips) + len(full_domains),
        },
        "lite": {
            "ipv4_networks": len(lite_ips),
            "domains": len(lite_domains),
            "total_lines": len(lite_ips) + len(lite_domains),
        },
        "notes": [
            "IPv6 is not included because GL.iNet's documented online VPN filter format explicitly lists IPv4/CIDR and domains.",
            "DOMAIN-KEYWORD rules are ignored because GL.iNet does not use Clash keyword syntax.",
            "Subdomains are collapsed when a parent/root domain is already present."
        ]
    }
    STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
