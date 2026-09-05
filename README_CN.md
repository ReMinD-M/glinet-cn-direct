# GL.iNet 国内直连订阅（适合 VPN Dashboard / 排除指定域名/IP列表）

这个模板会每天自动合并并生成 GL.iNet 可直接订阅的纯文本列表：

- 中国大陆 IPv4：`mayaxcn/china-ip-list` 的 `chnroute.txt`
- 常用中国域名：Blackmatrix7 的 `China.list`
- 腾讯/微信相关域名和 IPv4：Blackmatrix7 的 `Tencent.list`
- 你自己的补充域名：`extra_domains.txt`

生成两个文件：

- `glinet-cn-direct.txt`：完整版（推荐）
- `glinet-cn-direct-lite.txt`：轻量版，只保留中国 IPv4 + 腾讯/微信规则

## 第一次使用

1. 在 GitHub 新建一个 **Public** 仓库，例如：`glinet-cn-direct`
2. 把本模板里的所有文件上传到仓库根目录，必须保留 `.github/workflows/update.yml`
3. 进入仓库的 **Actions**
4. 点击 `Update GL.iNet CN Direct List`
5. 点击 **Run workflow**
6. 等运行完成后，仓库里的 `glinet-cn-direct.txt` 会被自动生成

## 路由器里填的 URL

假设你的 GitHub 用户名是 `YOURNAME`，仓库叫 `glinet-cn-direct`：

完整版：
https://raw.githubusercontent.com/YOURNAME/glinet-cn-direct/main/glinet-cn-direct.txt

轻量版：
https://raw.githubusercontent.com/YOURNAME/glinet-cn-direct/main/glinet-cn-direct-lite.txt

GL.iNet VPN Dashboard 建议：

- 至：**排除指定的域名/IP列表**
- 模式：**订阅 URL**
- URL：填上面的完整版 raw URL
- 经由：你的国外 VPN 隧道

这样，命中列表的目标会被排除出 VPN，走本地 WAN；其余流量继续走国外 VPN。

## 为什么不直接塞 10 万+ 中国域名

路由器最终仍要把订阅内容加载成规则。这个模板选用中等规模的“中国常用域名 + 腾讯/微信 + 中国 IPv4”，并自动：
- 删除重复项
- 如果已有父域名，删除多余子域名
- 合并可合并的 IPv4 CIDR
- 忽略 Clash 的 `DOMAIN-KEYWORD`
- 默认不加入 IPv6

如果视频号直播仍出现国外出口，最可靠的兜底方案仍是：把直播设备整机设置为“不使用 VPN”。
