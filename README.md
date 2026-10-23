# MiniDash — Scheduled Orders (Track A)

MiniDash is a small food-delivery REST API (FastAPI + SQLite). This repository adds **scheduled
orders**: a customer can order now for delivery between 45 minutes and 7 days ahead, the order is held
as `SCHEDULED`, and it is released to the restaurant (`PLACED`) exactly once, 30 minutes before the
delivery time. A scheduled order can be cancelled until it is released.

> **How this repository was made.** Everything here (baseline, spec, code, tests, log, reflection) was
> produced by Claude, an AI model, from a single human request with no further human input.
> `AI_LOG.md` records what happened, including the mistakes. See it before treating this as anyone's
> own work.

## Requirements

- Python 3.11 or newer, with SQLite 3.35 or newer (bundled with the python.org installers for 3.11+;
  the app checks at start-up and says so if not).
- No other system packages. On Windows, `tzdata` is installed automatically from `requirements.txt`.

## Set up

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

## Run the tests and linter

```bash
pytest                             # 95 tests, about 3 seconds
ruff check . && ruff format --check .
python scripts/mutation_check.py   # optional, about 1 minute: 29 deliberate bugs, each must fail a test
```

## Run the demo (5 minutes, no waiting)

```bash
python scripts/demo_scheduled_orders.py
```

The demo runs the real app with a clock it moves by hand, and walks through: rejected times (too soon,
too far, no time zone, restaurant closed), two scheduled orders, a blocked status change, a
cancellation, release at exactly `release_at` (not a microsecond earlier), a second release pass that
does nothing, and a cancel after release that is refused.

## Run the API

```bash
PYTHONPATH=src uvicorn minidash.main:app --reload
# Windows PowerShell: $env:PYTHONPATH="src"; uvicorn minidash.main:app --reload
```

Open http://127.0.0.1:8000/docs for interactive docs. Configuration (all optional):

| Variable | Default | Meaning |
|---|---|---|
| `MINIDASH_DB` | `minidash.db` | SQLite file. Created and seeded on first start; older baseline files are migrated in place. |
| `MINIDASH_TZ` | `America/New_York` | Time zone that restaurant opening hours are written in. |
| `MINIDASH_RELEASE_INTERVAL` | `15` | Seconds between release passes. `0` turns the background loop off. |

To release without the in-app loop (for example from cron): `PYTHONPATH=src python -m minidash.worker --once`.

### Try it with curl

```bash
# a delivery time 2 hours from now, with its UTC offset
WHEN=$(python -c "from datetime import datetime,timedelta;print((datetime.now().astimezone()+timedelta(hours=2)).isoformat(timespec='seconds'))")

curl -s -X POST localhost:8000/orders -H 'content-type: application/json' \
  -d "{\"restaurant_id\":3,\"items\":[{\"menu_item_id\":7,\"quantity\":2}],\"address\":\"1 Main St\",\"scheduled_for\":\"$WHEN\"}"
curl -s localhost:8000/orders/1                    # status SCHEDULED, release_at = WHEN - 30 min
curl -s -X POST localhost:8000/orders/1/cancel     # CANCELLED (409 once it has been released)
```

Seed restaurants open 10:00–23:00 (Taco Town, id 3) and later; Late Night Noodles (id 5) is open
18:00–02:00. Times are in `MINIDASH_TZ`, so pick a delivery time inside those hours there.

## API

| Method and path | Purpose |
|---|---|
| `GET /restaurants` | List restaurants (baseline) |
| `GET /restaurants/{id}/menu` | Menu for one restaurant (baseline) |
| `POST /orders` | Place an order. Optional `scheduled_for` (ISO 8601 with offset) makes it a scheduled order. |
| `GET /orders/{id}` | One order, now including `scheduled_for`, `release_at`, `released_at` |
| `PATCH /orders/{id}/status` | Restaurant/driver tools. Refuses `SCHEDULED` orders (409) and the value `SCHEDULED` (422). |
| `POST /orders/{id}/cancel` | **New.** Cancel a `SCHEDULED` order; 409 once released. |

Errors use `{"error": {"code": "...", "message": "..."}}`. Codes: `SCHEDULE_TIMEZONE_REQUIRED`,
`SCHEDULE_TOO_SOON`, `SCHEDULE_TOO_FAR`, `RESTAURANT_CLOSED`, `ORDER_NOT_CANCELLABLE`,
`ORDER_IS_SCHEDULED`, `STATUS_NOT_SETTABLE`, plus the baseline's `RESTAURANT_NOT_FOUND`,
`ITEM_NOT_ON_MENU`, `ORDER_NOT_FOUND`.

## Layout

```
docs/          requirements.md (EARS criteria), design.md (diagrams, ADR-001, ADR-002),
               tasks.md (slices), dependencies.md (registry checks)
src/minidash/  app.py, clock.py, db.py, timeutil.py, worker.py, errors.py, schemas.py,
               routes/, services/ (ordering, scheduling, menu), repositories/
tests/         one file per slice, plus the baseline tests
scripts/       demo_scheduled_orders.py, mutation_check.py
AI_LOG.md      AI usage log        AGENTS.md   rules for AI assistants in this repo
```
