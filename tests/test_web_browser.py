"""S12: the customer page in a real browser (FE-1, FE-3 to FE-6).

Starts the app on a free port with a ManualClock and drives headless Chromium with Playwright.
Optional: skipped unless Playwright and its Chromium are installed
(`pip install playwright==1.63.0 && playwright install chromium`).
"""

import json
import re
import socket
import threading
import time
import urllib.request
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
import uvicorn

from minidash.app import create_app
from minidash.clock import ManualClock

from .conftest import START  # Fri 23 Oct 2026, 14:00 New York

sync_api = pytest.importorskip("playwright.sync_api")
expect = sync_api.expect

RELEASE_AT = datetime(2026, 10, 23, 19, 30, tzinfo=UTC)  # 15:30 New York, for a 16:00 delivery


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            chromium = p.chromium.launch()
        except sync_api.Error as exc:
            pytest.skip(f"Playwright's Chromium is not installed: {exc}")
        yield chromium
        chromium.close()


@pytest.fixture
def live(db_path):
    clock = ManualClock(START)
    app = create_app(db_path, clock=clock, business_tz="America/New_York", release_interval=0.1)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        assert time.monotonic() < deadline, "server did not start"
        time.sleep(0.02)
    yield SimpleNamespace(url=f"http://127.0.0.1:{port}", clock=clock)
    server.should_exit = True
    thread.join(timeout=5)


def get_json(url):
    with urllib.request.urlopen(url) as response:
        return json.load(response)


def open_page(browser, live, timezone_id="America/New_York", init_script=None):
    context = browser.new_context(timezone_id=timezone_id)
    if init_script:
        context.add_init_script(init_script)
    page = context.new_page()
    page.errors = []
    page.on("pageerror", lambda exc: page.errors.append(str(exc)))
    page.goto(live.url)
    expect(page.locator("body[data-ready='true']")).to_be_attached()
    return page


def build_order(page, restaurant="Pasta Palace", item="Spaghetti Carbonara", quantity=2):
    page.get_by_role("button", name=re.compile(restaurant)).click()
    for _ in range(quantity):
        page.get_by_role("button", name=f"Add one {item}").click()
    page.get_by_label("Delivery address").fill("1 Main St")


def schedule_for(page, date, hhmm):
    page.get_by_label("Schedule for later").check()
    page.get_by_label("Date").fill(date)
    page.get_by_label("Time").fill(hhmm)


def test_schedule_then_cancel_in_a_real_browser(browser, live):
    page = open_page(browser, live)
    expect(page.get_by_role("button", name=re.compile("Pasta Palace"))).to_contain_text("Open now")
    expect(page.get_by_role("button", name=re.compile("Late Night Noodles"))).to_contain_text(
        "Closed now"
    )

    expect(page.locator("#cart-total")).to_be_hidden()  # nothing in the cart yet
    build_order(page)
    expect(page.locator("#cart-total")).to_contain_text("$29.00")
    schedule_for(page, "2026-10-23", "16:00")
    expect(page.locator("#hint")).to_have_text("Pasta Palace starts your order at 3:30 PM.")
    expect(page.locator("#timeline .tl-kitchen")).to_be_visible()
    expect(page.locator("#place")).to_have_text("Schedule for 4:00 PM")
    page.locator("#place").click()

    order = page.locator("li.order").first
    expect(order).to_contain_text("Scheduled")
    expect(order).to_contain_text("Delivery Fri, Oct 23, 4:00 PM")
    expect(order).to_contain_text("Goes to the kitchen at 3:30 PM")
    expect(order).to_contain_text("2 × Spaghetti Carbonara. $29.00")
    assert get_json(f"{live.url}/orders/1")["status"] == "SCHEDULED"

    order.get_by_role("button", name="Cancel order").click()
    expect(order).to_contain_text("Cancelled before it went to the kitchen")
    expect(order.get_by_role("button", name="Cancel order")).to_have_count(0)
    assert get_json(f"{live.url}/orders/1")["status"] == "CANCELLED"
    assert page.errors == []


def test_status_updates_when_the_order_is_released(browser, live):
    page = open_page(browser, live)
    build_order(page, quantity=1)
    schedule_for(page, "2026-10-23", "16:00")
    page.locator("#place").click()
    order = page.locator("li.order").first
    expect(order).to_contain_text("Scheduled")

    live.clock.set(RELEASE_AT)  # the server's release loop runs every 0.1 s; the page polls
    expect(order).to_contain_text("Sent to the kitchen", timeout=10_000)
    expect(order).to_contain_text("Went to the kitchen at 3:30 PM")
    expect(order.get_by_role("button", name="Cancel order")).to_have_count(0)
    assert page.errors == []


def test_server_rejection_is_explained(browser, live):
    page = open_page(browser, live)
    build_order(page, "Late Night Noodles", "Dan Dan Noodles", 1)

    schedule_for(page, "2026-10-23", "14:30")
    expect(page.locator("#hint")).to_have_text("Pick a time at least 45 minutes from now.")

    schedule_for(page, "2026-10-23", "18:15")  # opens 18:00, so the kitchen window starts too early
    expect(page.locator("#hint")).to_have_class(re.compile("warn"))
    page.locator("#place").click()  # the page warns but lets the server decide
    expect(page.locator("#form-error")).to_contain_text(
        "The kitchen starts your order 30 minutes before delivery"
    )
    expect(page.locator("#tracker-empty")).to_be_visible()

    schedule_for(page, "2026-10-23", "18:30")
    expect(page.locator("#hint")).to_have_text("Late Night Noodles starts your order at 6:00 PM.")
    assert page.errors == []


def test_page_works_when_storage_is_blocked(browser, live):
    blocked = (
        "Object.defineProperty(window, 'localStorage', "
        "{ get() { throw new DOMException('blocked', 'SecurityError'); } });"
    )
    page = open_page(browser, live, init_script=blocked)
    build_order(page, quantity=1)
    page.locator("#place").click()  # as soon as possible
    expect(page.locator("li.order").first).to_contain_text("Sent to the kitchen")
    assert page.errors == []


def test_browser_time_zone_does_not_change_the_order(browser, live):
    page = open_page(browser, live, timezone_id="Asia/Tokyo")
    build_order(page, quantity=1)
    schedule_for(page, "2026-10-23", "16:00")  # 16:00 New York, typed on a Tokyo laptop
    page.locator("#place").click()
    expect(page.locator("li.order").first).to_contain_text("Delivery Fri, Oct 23, 4:00 PM")
    assert get_json(f"{live.url}/orders/1")["scheduled_for"] == "2026-10-23T20:00:00.000000+00:00"
    assert page.errors == []


def test_orders_are_remembered_after_a_reload(browser, live):
    page = open_page(browser, live)
    build_order(page, quantity=1)
    schedule_for(page, "2026-10-23", "17:00")
    page.locator("#place").click()
    expect(page.locator("li.order")).to_have_count(1)
    page.reload()
    expect(page.locator("body[data-ready='true']")).to_be_attached()
    expect(page.locator("li.order").first).to_contain_text("Goes to the kitchen at 4:30 PM")
    assert page.errors == []
