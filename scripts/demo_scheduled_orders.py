"""Five-minute demo of Track A (scheduled orders), with a clock we can move by hand.

Runs the real app in-process against a throwaway SQLite file. Release passes call the same
worker.run_once the background loop uses, so each step is visible.

    python scripts/demo_scheduled_orders.py
"""

import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from minidash.app import create_app  # noqa: E402
from minidash.clock import ManualClock  # noqa: E402
from minidash.worker import run_once  # noqa: E402

NY = ZoneInfo("America/New_York")
PASTA = {"restaurant_id": 1, "items": [{"menu_item_id": 1, "quantity": 2}], "address": "1 Main St"}
NOODLES = {"restaurant_id": 5, "items": [{"menu_item_id": 13, "quantity": 1}], "address": "1 Main"}


def local(ts: str | None) -> str:
    return datetime.fromisoformat(ts).astimezone(NY).strftime("%a %H:%M") if ts else "-"


def step(title: str) -> None:
    print(f"\n== {title}")


def show(label: str, response) -> dict:
    body = response.json()
    if "error" in body:
        print(f"   {label}: HTTP {response.status_code} {body['error']['code']}")
        print(f"      {body['error']['message']}")
    else:
        print(
            f"   {label}: HTTP {response.status_code} order #{body['id']} {body['status']:<9}"
            f" deliver {local(body['scheduled_for'])}  release {local(body['release_at'])}"
            f"  released {local(body['released_at'])}"
        )
    return body


def main() -> None:
    clock = ManualClock(datetime(2026, 10, 23, 14, 0, tzinfo=NY))
    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "demo.db")
        app = create_app(db, clock=clock, business_tz="America/New_York", release_interval=0)
        with TestClient(app) as api:

            def at(hh: int, mm: int, day: int = 23) -> str:
                return datetime(2026, 10, day, hh, mm, tzinfo=NY).isoformat()

            def release() -> None:
                ids = run_once(db, clock)
                print(f"   release pass at {clock.now():%H:%M:%S.%f}: released {ids}")

            print(f"Clock: {clock.now():%A %d %b %Y %H:%M} New York")

            step("1. Times that are rejected")
            show(
                "44 min ahead     ",
                api.post("/orders", json={**PASTA, "scheduled_for": at(14, 44)}),
            )
            show(
                "8 days ahead     ",
                api.post("/orders", json={**PASTA, "scheduled_for": at(14, 0, 31)}),
            )
            show(
                "no UTC offset    ",
                api.post("/orders", json={**PASTA, "scheduled_for": "2026-10-23T16:00:00"}),
            )
            show(
                "noodles at 18:15 ",
                api.post("/orders", json={**NOODLES, "scheduled_for": at(18, 15)}),
            )

            step("2. Two valid scheduled orders")
            a = show(
                "A for 16:00      ", api.post("/orders", json={**PASTA, "scheduled_for": at(16, 0)})
            )
            b = show(
                "B for 17:00      ", api.post("/orders", json={**PASTA, "scheduled_for": at(17, 0)})
            )

            step("3. Restaurant tools cannot jump the queue")
            show(
                "PATCH A PREPARING",
                api.patch(f"/orders/{a['id']}/status", json={"status": "PREPARING"}),
            )

            step("4. Customer cancels B before it is released")
            show("cancel B         ", api.post(f"/orders/{b['id']}/cancel"))

            step("5. Release happens at release_at, not a microsecond before")
            clock.set(datetime(2026, 10, 23, 15, 30, tzinfo=NY) - timedelta(microseconds=1))
            release()
            clock.advance(timedelta(microseconds=1))
            release()
            show("A                ", api.get(f"/orders/{a['id']}"))

            step("6. Exactly once: running again releases nothing")
            release()

            step("7. A released order can no longer be cancelled; B is never released")
            show("cancel A         ", api.post(f"/orders/{a['id']}/cancel"))
            clock.set(datetime(2026, 10, 23, 18, 0, tzinfo=NY))
            release()
            show("B                ", api.get(f"/orders/{b['id']}"))

            step("8. Kitchen moves A along as normal")
            show(
                "PATCH A PREPARING",
                api.patch(f"/orders/{a['id']}/status", json={"status": "PREPARING"}),
            )

    print("\nDone. All times are New York local; the API stores and returns UTC.")


if __name__ == "__main__":
    main()
