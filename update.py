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

# V4 Balanced：
# 目标不是“把所有中国网站都塞进去”，而是优先覆盖：
# 中国大陆 IPv4 + 国内主流 App / 视频 / 社交 / 电商 / 云 / 游戏厂商。
#
# 这样比 ChinaMax 10 万级列表轻很多，同时比最初 1 万条版本覆盖更广。

CRITICAL_SOURCES = {
    "chnroute": "https://raw.githubusercontent.com/mayaxcn/china-ip-list/master/chnroute.txt",
    "china": "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/China/China.list",
    "tencent": "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Tencent/Tencent.list",
}

OPTIONAL_SOURCES = {
    # 视频 / 直播 / 短视频
    "douyin": "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/DouYin/DouYin.list",
    "bytedance": "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/Ruleset/ByteDance.list",
    "kuaishou": "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/KuaiShou/KuaiShou.list",
    "bilibili": "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/BiliBili/BiliBili.list",
    "iqiyi": "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/iQIYI/iQIYI.list",
    "youku": "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Youku/Youku.list",
    "huya": "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/HuYa/HuYa.list",

    # 国内厂商 / App / 游戏基础设施
    "netease": "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/NetEase/NetEase.list",
    "baidu": "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Baidu/Baidu.list",
    "jingdong": "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/JingDong/JingDong.list",
    "pinduoduo": "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Pinduoduo/Pinduoduo.list",
    "weibo": "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Weibo/Weibo.list",
    "zhihu": "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Zhihu/Zhihu.list",
}

DOMAIN_RE = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$",
    re.I,
)

# 国内主流服务兜底根域名。
# GL.iNet 对根域名可覆盖其子域，因此这里尽量使用“根域”而不是堆大量子域名。
FORCE_DOMAINS = {
    # 腾讯 / 微信 / QQ / 视频号 / 腾讯视频 / 游戏
    "qq.com", "weixin.com", "wechat.com", "servicewechat.com",
    "qpic.cn", "qlogo.cn", "gtimg.com", "tencent.com",
    "qcloud.com", "myqcloud.com", "tencent-cloud.net",
    "weixinbridge.com", "v.qq.com", "wegame.com.cn",

    # 抖音 / 今日头条 / 西瓜 / 字节国内
    "douyin.com", "douyincdn.com", "douyinpic.com", "douyinstatic.com",
    "douyinvod.com", "idouyinvod.com", "iesdouyin.com", "iesdouyin.net",
    "amemv.com", "snssdk.com", "ixigua.com", "ixiguavideo.com",
    "toutiao.com", "pstatp.com", "byteimg.com", "bytedance.com",
    "bytedance.net", "zijieapi.com", "zijiecdn.com", "zijiecdn.net",

    # 快手 / A站
    "kuaishou.com", "gifshow.com", "yximgs.com",
    "acfun.cn", "acfun.com",

    # B站
    "bilibili.com", "bilivideo.com", "hdslb.com",
    "biliapi.com", "biliapi.net",

    # 主流长视频 / 直播
    "iqiyi.com", "qiyi.com", "iqiyipic.com", "iqiyiedge.com",
    "youku.com", "ykimg.com",
    "mgtv.com", "hunantv.com",
    "miguvideo.com", "migu.cn",
    "huya.com", "douyu.com", "douyucdn.cn",
    "pptv.com", "pplive.cn", "cctv.com", "cntv.cn",

    # 网易 / 网易游戏
    "netease.com", "neteasegame.com", "neteasegames.com",
    "163.com", "126.com", "126.net", "163yun.com",
    "easebar.com", "ntes53.com", "ntescdn.com",

    # 米哈游 / HoYoverse 中国区（不加入 hoyoverse.com）
    "mihoyo.com", "mihoyocg.com", "mihoyo.com.cn",
    "miyoushe.com", "yuanshen.com", "bh3.com",

    # 国内游戏厂商 / 平台
    "wegame.com.cn", "taptap.cn", "taptap.com",
    "4399.com", "4399.cn",
    "37.com", "37wan.com",
    "wanmei.com", "wmsj.cn", "perfectworld.com.cn",
    "shandagames.com", "盛趣.com",
    "seasun.com", "kingsoft.com",

    # 社交 / 内容
    "xiaohongshu.com", "xhscdn.com",
    "weibo.com", "weibo.cn",
    "zhihu.com", "zhimg.com",
    "douban.com", "doubanio.com",
    "tieba.com",

    # 百度
    "baidu.com", "bdimg.com", "bdstatic.com",
    "baidubce.com", "baidupcs.com", "baidustatic.com",

    # 阿里系国内常用服务（不导入完整 Alibaba 海外域）
    "taobao.com", "tmall.com", "1688.com",
    "alicdn.com", "aliimg.com",
    "alipay.com", "alipayobjects.com",
    "aliyun.com", "aliyuncs.com", "alicloudccp.com",
    "youku.com", "ykimg.com",

    # 京东 / 拼多多 / 美团
    "jd.com", "jd.cn", "360buyimg.com", "jcloudcs.com",
    "pinduoduo.com", "yangkeduo.com",
    "meituan.com", "meituan.net", "dianping.com",

    # 出行 / 地图 / 本地生活
    "didichuxing.com",
    "amap.com", "autonavi.com",
    "ctrip.com", "tripcdn.com", "qunar.com",
    "12306.cn",

    # 手机厂商 / 应用商店 / 云
    "huawei.com", "huaweicloud.com", "huaweicloudapis.com",
    "vmall.com",
    "mi.com", "xiaomi.com", "miui.com", "xiaomiyoupin.com",
    "oppo.com", "oppomobile.com",
    "vivo.com.cn",

    # 常见国内 CDN / 云
    "aliyuncs.com", "alicdn.com",
    "qcloud.com", "myqcloud.com",
    "ksyun.com", "ksyuncdn.com",
    "ucloud.cn", "ucloud.com.cn",
    "volcengine.com", "volccdn.com",
}

# 明确不应进入“国内直连”的常见国际域名。
# 如果某个上游列表未来误混入，做最后一道过滤。
DENY_SUFFIXES = {
    "tiktok.com",
    "tiktokcdn.com",
    "tiktokv.com",
    "byteoversea.com",
    "youtube.com",
    "googlevideo.com",
    "netflix.com",
    "steamcommunity.com",
    "steampowered.com",
    "epicgames.com",
    "hoyoverse.com",
}

def fetch(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "glinet-cn-direct-builder/4.0"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")

def is_denied_domain(domain: str) -> bool:
    domain = domain.lower().rstrip(".")
    return any(
        domain == suffix or domain.endswith("." + suffix)
        for suffix in DENY_SUFFIXES
    )

def clean_domain(s: str) -> str | None:
    s = s.strip().lower().rstrip(".").lstrip(".")
    if not s or " " in s or "/" in s:
        return None

    # 已在用户的 GL.iNet 上实测：
    # VPN Dashboard 会把数字开头域名计为 invalid。
    if not s[0].isalpha():
        return None

    if is_denied_domain(s):
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

def parse_rules(text: str):
    domains: set[str] = set()
    ipv4: set[ipaddress.IPv4Network] = set()
    stats = {
        "domain": 0,
        "ipv4": 0,
        "ignored": 0,
        "invalid": 0,
    }

    # 兼容少数 raw 源意外被压成一行的情况：
    # 先用正则把规则 token 重新切开。
    normalized = text.replace("\r", "\n")
    rule_tokens = re.split(
        r"(?=(?:DOMAIN(?:-SUFFIX)?|IP-CIDR|IP-CIDR6|DOMAIN-KEYWORD|PROCESS-NAME),)",
        normalized,
    )

    # 正常多行文本优先逐行；如果行数极少则使用 token fallback。
    lines = normalized.splitlines()
    chunks = lines if len(lines) > 3 else rule_tokens

    for raw in chunks:
        s = raw.strip()
        if not s or s.startswith("#"):
            continue

        # 一行里若同时带了前导说明文字，截到第一个可识别规则起点。
        m = re.search(
            r"(DOMAIN(?:-SUFFIX)?|IP-CIDR6?|DOMAIN-KEYWORD|PROCESS-NAME),",
            s,
        )
        if m and m.start() > 0:
            s = s[m.start():]

        parts = [p.strip() for p in s.split(",")]
        if not parts:
            continue

        kind = parts[0].upper()

        if kind in ("DOMAIN", "DOMAIN-SUFFIX") and len(parts) >= 2:
            d = clean_domain(parts[1])
            if d:
                domains.add(d)
                stats["domain"] += 1
            else:
                stats["invalid"] += 1

        elif kind == "IP-CIDR" and len(parts) >= 2:
            try:
                net = ipaddress.ip_network(parts[1], strict=False)
            except ValueError:
                stats["invalid"] += 1
                continue

            if isinstance(net, ipaddress.IPv4Network):
                ipv4.add(net)
                stats["ipv4"] += 1

        elif kind in ("IP-CIDR6", "DOMAIN-KEYWORD", "PROCESS-NAME"):
            stats["ignored"] += 1

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
    # GL.iNet 根域名可覆盖全部子域，自动删掉冗余子域。
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
    path.write_text(
        "\n".join(ips + domains) + "\n",
        encoding="utf-8",
    )

def main():
    source_status = {}

    # --- Critical sources ---
    chnroute_text = fetch(CRITICAL_SOURCES["chnroute"])
    china_text = fetch(CRITICAL_SOURCES["china"])
    tencent_text = fetch(CRITICAL_SOURCES["tencent"])

    cn_ips = parse_ip_lines(chnroute_text)
    china_domains, china_ips, china_stats = parse_rules(china_text)
    tencent_domains, tencent_ips, tencent_stats = parse_rules(tencent_text)

    if len(cn_ips) < 5000:
        raise RuntimeError(
            f"chnroute source unexpectedly small: {len(cn_ips)} IPv4 networks"
        )
    if len(china_domains) < 2000:
        raise RuntimeError(
            f"China source unexpectedly small: {len(china_domains)} domains"
        )
    if len(tencent_domains) < 1000:
        raise RuntimeError(
            f"Tencent source unexpectedly small: {len(tencent_domains)} domains"
        )

    source_status["china"] = china_stats
    source_status["tencent"] = tencent_stats

    all_domains = set(china_domains) | set(tencent_domains)
    all_ips = set(cn_ips) | set(china_ips) | set(tencent_ips)

    # --- Optional dedicated service sources ---
    optional_failures = {}

    for name, url in OPTIONAL_SOURCES.items():
        try:
            text = fetch(url)
            domains, ips, stats = parse_rules(text)
            all_domains |= domains
            all_ips |= ips
            source_status[name] = {
                **stats,
                "unique_domains_loaded": len(domains),
                "unique_ipv4_loaded": len(ips),
            }
        except Exception as e:
            # 一个小平台源挂掉不能导致整份订阅停止更新。
            optional_failures[name] = str(e)

    extra_domains = load_extra()

    force_domains = {
        d for d in (clean_domain(x) for x in FORCE_DOMAINS)
        if d
    }

    full_ips = collapse_ipv4(all_ips)
    full_domains = collapse_domains(
        all_domains | force_domains | extra_domains
    )

    total = len(full_ips) + len(full_domains)

    # 防止某个上游突然膨胀成 10 万级，重新把路由器拖慢。
    if total > 30000:
        raise RuntimeError(
            f"Balanced list grew too large ({total} lines); refusing to publish. "
            "Review upstream sources before increasing the 30,000-line safety cap."
        )

    # 太小也不发布，避免空/残缺订阅覆盖路由器。
    if total < 10000:
        raise RuntimeError(
            f"Balanced list unexpectedly small ({total} lines); refusing to publish."
        )

    write_list(OUT_FULL, full_ips, full_domains)

    # Lite：大陆 IPv4 + Tencent/微信 + 核心根域名
    lite_ips = collapse_ipv4(cn_ips | tencent_ips)
    lite_domains = collapse_domains(
        tencent_domains | force_domains | extra_domains
    )
    write_list(OUT_LITE, lite_ips, lite_domains)

    status = {
        "profile": "V4 Balanced",
        "goal": "Mainland China IP + mainstream Chinese apps/video/social/ecommerce/cloud/games without ChinaMax-scale bloat",
        "critical_sources": CRITICAL_SOURCES,
        "optional_sources": OPTIONAL_SOURCES,
        "optional_failures": optional_failures,
        "source_stats": source_status,
        "full": {
            "ipv4_networks": len(full_ips),
            "domains": len(full_domains),
            "total_lines": total,
            "safety_cap": 30000,
        },
        "lite": {
            "ipv4_networks": len(lite_ips),
            "domains": len(lite_domains),
            "total_lines": len(lite_ips) + len(lite_domains),
        },
        "compatibility": {
            "numeric_prefix_domains": "excluded for GL.iNet compatibility",
            "domain_keyword": "ignored",
            "ipv6": "ignored in this GL.iNet URL list",
            "process_name": "ignored",
            "overseas_suffixes": sorted(DENY_SUFFIXES),
        },
        "notes": [
            "This profile intentionally avoids ChinaMax's 100k+ domain scale.",
            "Optional service feeds are fault-tolerant: one unavailable source will not stop the daily build.",
            "Root domains are collapsed so subdomain-heavy feeds use fewer GL.iNet rules.",
            "No static list can guarantee every app/game flow if it uses hard-coded IPs, private DoH, or new CDN nodes.",
        ],
    }

    STATUS.write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(status, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
