"""S11: the web page is served, and GET /config gives it the server's rules and time."""

import re
from datetime import UTC, datetime
from pathlib import Path

from minidash.routes.web import WEB_DIR

APP_JS = (WEB_DIR / "app.js").read_text() if (WEB_DIR / "app.js").exists() else ""


def test_index_is_served_at_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "<title>MiniDash</title>" in r.text


def test_static_files_are_served_with_the_right_types(client):
    js = client.get("/static/logic.js")
    assert js.status_code == 200
    assert "javascript" in js.headers["content-type"]
    assert client.get("/static/nope.js").status_code == 404


def test_config_reports_rules_zone_and_injected_clock(client, clock):
    body = client.get("/config").json()
    assert body == {
        "now": "2026-10-23T18:00:00.000000+00:00",
        "business_timezone": "America/New_York",
        "min_lead_minutes": 45,
        "max_horizon_days": 7,
        "release_before_minutes": 30,
    }
    clock.set(datetime(2026, 10, 24, 1, 2, 3, tzinfo=UTC))
    assert client.get("/config").json()["now"] == "2026-10-24T01:02:03.000000+00:00"


def test_config_numbers_come_from_the_scheduling_module(client, monkeypatch):
    from datetime import timedelta

    from minidash.routes import web

    monkeypatch.setattr(web, "MIN_LEAD", timedelta(minutes=60))
    assert client.get("/config").json()["min_lead_minutes"] == 60


def test_web_routes_stay_out_of_the_api_docs(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/" not in paths


def test_every_api_path_the_page_calls_exists(client):
    """Contract check: the paths in app.js must match real routes, so a renamed endpoint
    breaks a test instead of silently breaking the page."""
    if not APP_JS:
        return  # app.js arrives in S12
    called = set(re.findall(r'api\(\s*[`"](/[^`"]*)[`"]', APP_JS))
    assert called, "expected app.js to call the API through api(...)"
    routes = [r.path for r in client.app.routes]
    patterns = [re.compile("^" + re.sub(r"\{[^}]+\}", "[^/]+", p) + "$") for p in routes]
    for path in called:
        concrete = re.sub(r"\$\{[^}]+\}", "1", path)
        assert any(p.match(concrete) for p in patterns), f"app.js calls unknown path {path}"


def test_page_files_exist_in_the_package():
    assert {"index.html", "logic.js"} <= {p.name for p in Path(WEB_DIR).iterdir()}
