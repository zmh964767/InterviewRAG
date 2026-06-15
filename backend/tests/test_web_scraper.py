"""web_scraper SSRF 防护测试

覆盖 validate_url():
- 协议白名单：file:// / ftp:// 拒绝
- IP 字面量：127.0.0.1 / 10.x / 192.168 / 172.16-31 / 169.254 拒绝
- 域名 → 内网名（localhost）拒绝
- 域名 → DNS 解析到 127.0.0.1（用 127.0.0.1.nip.io 模拟）拒绝
- 域名 → DNS 解析失败（NXDOMAIN）默认拒绝（fail-closed）
- 合法公网域名放行
"""

import pytest

from app.parsers.web_scraper import validate_url


class TestValidateUrlProtocol:
    """协议白名单"""

    def test_file_protocol_rejected(self):
        with pytest.raises(ValueError, match="不支持的协议"):
            validate_url("file:///etc/passwd")

    def test_ftp_protocol_rejected(self):
        with pytest.raises(ValueError, match="不支持的协议"):
            validate_url("ftp://example.com/file.txt")

    def test_https_allowed(self):
        # 公网域名的 HTTPS 应当放行（不做 DNS 校验因为 https://www.example.com 是真实可解析的）
        validate_url("https://www.example.com/")


class TestValidateUrlIPLiteral:
    """IP 字面量直接校验"""

    def test_ipv4_loopback_rejected(self):
        with pytest.raises(ValueError):
            validate_url("http://127.0.0.1/")

    def test_ipv4_loopback_with_port_rejected(self):
        with pytest.raises(ValueError):
            validate_url("http://127.0.0.1:8080/admin")

    def test_ipv4_private_10_rejected(self):
        with pytest.raises(ValueError):
            validate_url("http://10.0.0.1/")

    def test_ipv4_private_192_rejected(self):
        with pytest.raises(ValueError):
            validate_url("http://192.168.1.1/")

    def test_ipv4_private_172_rejected(self):
        with pytest.raises(ValueError):
            validate_url("http://172.16.0.1/")

    def test_ipv4_link_local_rejected(self):
        # 169.254.x.x（云元数据地址，经典 SSRF 目标）
        with pytest.raises(ValueError):
            validate_url("http://169.254.169.254/latest/meta-data/")

    def test_ipv6_loopback_rejected(self):
        with pytest.raises(ValueError):
            validate_url("http://[::1]/")


class TestValidateUrlPrivateDomains:
    """常见内网域名精确集合"""

    def test_localhost_rejected(self):
        with pytest.raises(ValueError):
            validate_url("http://localhost/admin")

    def test_nip_io_to_loopback_rejected(self):
        # 127.0.0.1.nip.io 是公网 DNS 服务，会把前缀解析成对应 IP
        # 这里前缀就是 127.0.0.1，所以会解析到 loopback
        with pytest.raises(ValueError, match="不允许访问内网域名"):
            validate_url("http://127.0.0.1.nip.io/")

    def test_nip_io_to_public_rejected_by_dns(self):
        # 1.1.1.1.nip.io 也会被精确集合先拦下（防止直接命中公共 IP 走 DNS）
        with pytest.raises(ValueError):
            validate_url("http://1.1.1.1.nip.io/")


class TestValidateUrlDNSResolution:
    """DNS 解析 + 失败 fail-closed"""

    def test_dns_resolution_to_loopback_rejected(self, monkeypatch):
        """模拟 DNS 把 attacker.com 解析到 127.0.0.1，必须拦下"""
        import socket

        def fake_getaddrinfo(host, port, *args, **kwargs):
            return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", port))]

        monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

        with pytest.raises(ValueError):
            validate_url("https://attacker.com/payload")

    def test_dns_resolution_failure_rejected_by_default(self, monkeypatch):
        """DNS 失败默认拒绝（SSRF 反模式：不能让攻击者通过让 DNS SERVFAIL 来放行）"""
        import socket

        def fake_getaddrinfo_fails(host, port, *args, **kwargs):
            raise socket.gaierror("Name or service not known")

        monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo_fails)

        with pytest.raises(ValueError):
            validate_url("https://nonexistent-domain-xyz.invalid/")


class TestValidateUrlPublicDomain:
    """合法公网域名放行（不依赖真实 DNS）"""

    def test_juejin_allowed(self, monkeypatch):
        """模拟 DNS 解析到公网 IP"""
        import socket

        def fake_getaddrinfo(host, port, *args, **kwargs):
            return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.179.124.45", port))]

        monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
        validate_url("https://juejin.cn/")

    def test_google_allowed(self, monkeypatch):
        import socket

        def fake_getaddrinfo(host, port, *args, **kwargs):
            return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("142.250.190.46", port))]

        monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
        validate_url("https://www.google.com/")

    def test_url_without_host_rejected(self):
        with pytest.raises(ValueError):
            validate_url("http:///path")
