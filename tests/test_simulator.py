import json
import re
from datetime import datetime

from dailyanchor import simulator


def _config(html):
    return json.loads(re.search(r"const CONFIG = (.*);", html).group(1))


def test_page_embeds_endpoints_and_server_time():
    html = simulator.render_simulator("/mcp", "/dashboard", now=datetime(2026, 10, 21, 9, 5))

    config = _config(html)
    assert config["mcpPath"] == "/mcp"
    assert config["dashboardPath"] == "/dashboard"
    assert config["serverNow"] == "2026-10-21T09:05:00"
    assert "__CONFIG__" not in html


def test_page_says_it_is_a_simulation():
    html = simulator.render_simulator("/mcp", "/dashboard")

    assert "This is a simulation." in html


def test_closing_script_tag_in_config_is_escaped():
    html = simulator.render_simulator("/mcp</script>", "/dashboard")

    assert "/mcp</script>" not in html
    assert _config(html)["mcpPath"] == "/mcp</script>"


def test_live_chat_is_off_without_a_model():
    assert _config(simulator.render_simulator("/mcp", "/dashboard"))["chatModel"] is None
    html = simulator.render_simulator("/mcp", "/dashboard", chat_model="gpt-test")
    assert _config(html)["chatModel"] == "gpt-test"
