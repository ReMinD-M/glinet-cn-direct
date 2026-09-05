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

# V3 MAX:
# - ChinaMax 作为国内域名/App/媒体/游戏/云服务的主源
# - mayax chnroute 作为中国大陆 IPv4 的补充
#
# ChinaMax 自身已经汇总大量国内子规则，包括：
# BiliBili / ByteDance / DouYin / Douyu / HuYa / Kuaishou / iQIYI /
# Youku / TencentVideo / WeChat / Tencent / NetEase / TapTap / 4399 /
# WanMeiShiJie / Xiaomi / Huawei / Baidu / Alibaba / JD / Meituan /
# Pinduoduo / Weibo / Zhihu / Migu / CCTV / IPTVMainland 等。
#
# 它明确排除了 TikTok / YouTube / Steam / Netflix 等海外类别，
# 所以比“把所有游戏/媒体规则无脑合并”更适合国内直连用途。

SOURCES = {
    "chinamax": "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/ChinaMax/ChinaMax.list",
    "chnroute": "https://raw.githubusercontent.com/mayaxcn/china-ip-list/master/chnroute.txt",
}

DOMAIN_RE = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$",
    re.I,
)

# 这些是“国内主流服务”的兜底根域名。
# 大多数已在 ChinaMax 中，重复会自动去重。
# 这里只补最关键的 App / 视频 / 社交 / 游戏 / CDN 根域，
# 避免上游某次重构时突然漏掉核心业务。
FORCE_DOMAINS = {
    # 微信 / 腾讯 / QQ / 视频号 / 腾讯视频 / WeGame
    "qq.com", "weixin.com", "wechat.com", "servicewechat.com",
    "qpic.cn", "qlogo.cn", "gtimg.com", "tencent.com",
    "qcloud.com", "myqcloud.com", "tencent-cloud.net",
    "v.qq.com", "wegame.com.cn",

    # 抖音 / 字节
    "douyin.com", "douyincdn.com", "douyinpic.com", "douyinstatic.com",
    "douyinvod.com", "idouyinvod.com", "iesdouyin.com", "iesdouyin.net",
    "amemv.com", "snssdk.com", "byteimg.com", "bytecdn.cn",
    "bytedance.com", "bytedance.net", "zijieapi.com", "zijiecdn.com",
    "zijiecdn.net", "pstatp.com", "pstatp.com",

    # 快手
    "kuaishou.com", "gifshow.com", "yximgs.com",

    # B站
    "bilibili.com", "bilibili.tv", "bilivideo.com", "hdslb.com",
    "biliapi.com", "biliapi.net",

    # 爱奇艺 / 优酷 / 芒果 / 咪咕 / 直播平台
    "iqiyi.com", "qiyi.com", "iqiyipic.com", "iqiyiedge.com",
    "youku.com", "ykimg.com", "mgtv.com", "hunantv.com",
    "miguvideo.com", "huya.com", "douyu.com",

    # 网易 / 国内游戏
    "netease.com", "163.com", "126.net", "163yun.com",
    "mihoyo.com", "mihoyocg.com", "miyoushe.com", "yuanshen.com",
    "wanmei.com", "wmsj.cn", "perfectworld.com.cn",
    "taptap.cn", "taptap.com", "4399.com", "37.com",

    # 国内常用 App / 电商 / 出行 / 社交
    "xiaohongshu.com", "xhscdn.com", "weibo.com", "weibo.cn",
    "baidu.com", "bdimg.com", "bdstatic.com",
    "taobao.com", "tmall.com", "alicdn.com", "alipay.com",
    "jd.com", "360buyimg.com", "pinduoduo.com", "meituan.com",
    "dianping.com", "didichuxing.com", "amap.com", "autonavi.com",
    "zhihu.com", "zhimg.com",

    # 国内厂商 / 应用商店 / 云
    "huawei.com", "huaweicloud.com", "mi.com", "xiaomi.com",
    "oppo.com", "vivo.com.cn", "aliyun.com", "cloud.tencent.com",
}

def fetch(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "glinet-cn-direct-builder/3.0"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")

def clean_domain(s: str) -> str | None:
    s = s.strip().lower().rstrip(".").lstrip(".")
    if not s or " " in s or "/" in s:
        return None

    # 已实测：GL.iNet VPN Dashboard 的 URL 检测器会把数字开头的域名判为 invalid。
    if not s[0].isalpha():
        return None

    return s if DOMAIN_RE.fullmatch(s) else None

def parse_ip_lines(text: str) -> set[ipaddress.IPv4Network]:
    out: set[ipaddress.IPv4Network] = set()

    for raw in text.splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue

        try:
            net = ipaddress.ip_network(s, strict=False)
        except ValueError:
            continue

        if isinstance(net, ipaddress.IPv4Network):
            out.add(net)

    return out

def parse_chinamax(text: str):
    domains: set[str] = set()
    ipv4: set[ipaddress.IPv4Network] = set()

    stats = {
        "domain": 0,
        "domain_suffix": 0,
        "domain_keyword_ignored": 0,
        "ipv4": 0,
        "ipv6_ignored": 0,
        "ip_asn_ignored": 0,
        "process_ignored": 0,
        "invalid_or_unsupported": 0,
    }

    for raw in text.splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue

        parts = [p.strip() for p in s.split(",")]
        kind = parts[0].upper()

        if kind in ("DOMAIN", "DOMAIN-SUFFIX") and len(parts) >= 2:
            d = clean_domain(parts[1])
            if d:
                domains.add(d)
                if kind == "DOMAIN":
                    stats["domain"] += 1
                else:
                    stats["domain_suffix"] += 1
            else:
                stats["invalid_or_unsupported"] += 1

        elif kind == "IP-CIDR" and len(parts) >= 2:
            try:
                net = ipaddress.ip_network(parts[1], strict=False)
            except ValueError:
                stats["invalid_or_unsupported"] += 1
                continue

            if isinstance(net, ipaddress.IPv4Network):
                ipv4.add(net)
                stats["ipv4"] += 1

        elif kind == "IP-CIDR6":
            stats["ipv6_ignored"] += 1

        elif kind == "DOMAIN-KEYWORD":
            # GL.iNet 目标域名列表不支持 Clash 的 DOMAIN-KEYWORD 语义。
            stats["domain_keyword_ignored"] += 1

        elif kind == "IP-ASN":
            stats["ip_asn_ignored"] += 1

        elif kind == "PROCESS-NAME":
            stats["process_ignored"] += 1

        else:
            stats["invalid_or_unsupported"] += 1

    return domains, ipv4, stats

def load_extra() -> set[str]:
    out: set[str] = set()

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
    """
    GL.iNet 的根域名规则会覆盖子域名。
    如果 qq.com 已存在，则 finder.video.qq.com 没必要再保留。
    """
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
    ordered = sorted(
        nets,
        key=lambda n: (int(n.network_address), n.prefixlen),
    )
    return [str(n) for n in ipaddress.collapse_addresses(ordered)]

def write_list(path: Path, ips: list[str], domains: list[str]):
    # 不写任何注释，避免 GL.iNet 把注释也送进在线检测器。
    path.write_text(
        "\n".join(ips + domains) + "\n",
        encoding="utf-8",
    )

def main():
    chinamax_text = fetch(SOURCES["chinamax"])
    chnroute_text = fetch(SOURCES["chnroute"])

    max_domains, max_ips, source_stats = parse_chinamax(chinamax_text)
    cn_ips = parse_ip_lines(chnroute_text)
    extra_domains = load_extra()

    # 上游异常保护：ChinaMax 正常应有 10 万级域名、数千 IPv4。
    if len(max_domains) < 80000:
        raise RuntimeError(
            f"ChinaMax domain source unexpectedly small: {len(max_domains)} domains"
        )

    if len(max_ips) < 5000:
        raise RuntimeError(
            f"ChinaMax IPv4 source unexpectedly small: {len(max_ips)} networks"
        )

    if len(cn_ips) < 5000:
        raise RuntimeError(
            f"chnroute source unexpectedly small: {len(cn_ips)} IPv4 networks"
        )

    force_domains = {
        d for d in (clean_domain(x) for x in FORCE_DOMAINS)
        if d
    }

    # MAX 完整版：
    # ChinaMax + 最新大陆 IPv4 + 本地补充 + 核心 App 兜底域名
    full_ips = collapse_ipv4(max_ips | cn_ips)
    full_domains = collapse_domains(
        max_domains | force_domains | extra_domains
    )

    write_list(OUT_FULL, full_ips, full_domains)

    # lite 仅作为故障回退。
    # 为了保持旧文件名可用，这里输出“IP + 核心 App 根域名”，
    # 不建议用户追求全覆盖时使用 lite。
    lite_ips = collapse_ipv4(cn_ips)
    lite_domains = collapse_domains(force_domains | extra_domains)
    write_list(OUT_LITE, lite_ips, lite_domains)

    status = {
        "profile": "V3 ChinaMax / GL.iNet MAX",
        "sources": SOURCES,
        "source_stats": source_stats,
        "full": {
            "ipv4_networks": len(full_ips),
            "domains": len(full_domains),
            "total_lines": len(full_ips) + len(full_domains),
            "purpose": "MAX coverage: mainland IP + mainstream Chinese apps/video/games/cloud/CDN",
        },
        "lite": {
            "ipv4_networks": len(lite_ips),
            "domains": len(lite_domains),
            "total_lines": len(lite_ips) + len(lite_domains),
            "purpose": "fallback only",
        },
        "compatibility": {
            "numeric_prefix_domains": "excluded because GL.iNet reports them invalid",
            "domain_keyword": "ignored; GL.iNet URL list has no Clash keyword semantics",
            "ipv6": "ignored in this file",
            "ip_asn": "ignored",
            "process_name": "ignored",
        },
        "important": [
            "ChinaMax is intentionally used as the main source instead of stacking many duplicate domestic rule sets.",
            "ChinaMax excludes major overseas categories such as TikTok, YouTube and Steam from its domestic aggregate.",
            "No domain/IP list can guarantee every proprietary game or app flow when an app uses hard-coded IPs, private DoH, or new CDN nodes.",
        ],
    }

    STATUS.write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(status, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
