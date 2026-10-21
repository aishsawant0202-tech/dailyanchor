from dailyanchor.server import build_transport_security


def test_no_public_hosts_keeps_sdk_default():
    assert build_transport_security([]) is None


def test_public_host_is_allowed_alongside_localhost():
    settings = build_transport_security(["dailyanchor.example.com"])

    assert settings.enable_dns_rebinding_protection
    assert "dailyanchor.example.com" in settings.allowed_hosts
    assert "dailyanchor.example.com:*" in settings.allowed_hosts
    assert "127.0.0.1:*" in settings.allowed_hosts
    assert "https://dailyanchor.example.com" in settings.allowed_origins


def _request(url):
    from urllib.parse import urlsplit
    from starlette.requests import Request

    parts = urlsplit(url)
    return Request({"type": "http", "scheme": parts.scheme, "server": (parts.hostname, parts.port or 443),
                    "path": parts.path, "query_string": b"", "headers": [(b"host", parts.netloc.encode())],
                    "root_path": ""})


def test_live_chat_hands_openai_the_public_mcp_url(monkeypatch):
    from dailyanchor import server

    monkeypatch.setattr(server, "ALLOWED_HOSTS", ["demo.sslip.io"])

    assert server._public_mcp_url(_request("https://demo.sslip.io/simulator/chat")) == "https://demo.sslip.io/mcp"
    assert server._public_mcp_url(_request("http://demo.sslip.io/simulator/chat")) is None
    assert server._public_mcp_url(_request("https://other.example/simulator/chat")) is None
    assert server._public_mcp_url(_request("http://127.0.0.1:8000/simulator/chat")) is None
