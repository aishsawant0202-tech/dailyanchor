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
