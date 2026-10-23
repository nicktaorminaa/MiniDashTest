# Tasks — Track A: Scheduled Orders

Each slice is one commit. A slice is done when its tests pass, `ruff check` and `ruff format --check`
pass, the full suite still passes, and the whole diff has been read for anything outside the slice.

| # | Slice | Criteria | Verified by | Status |
|---|---|---|---|---|
| S1 | **Inject a clock.** `Clock` protocol, `SystemClock`, `ManualClock`; `create_app(clock=...)`; `created_at` comes from the clock. | AC-14 | `tests/test_clock.py`: `ManualClock` set/advance; `created_at` equals the injected time; naive datetimes rejected by `ManualClock`. | Done |
| S2 | **Schema and timestamps.** Three nullable columns, index, idempotent migration of a baseline database, fixed-width UTC formatter; `GET /orders/{id}` returns the new fields. | AC-15 | `tests/test_schema.py`: migrating a baseline-shaped DB keeps rows and adds columns; running twice is a no-op; formatted strings sort in time order across offsets. | Done |
| S3 | **Lead-time and horizon rule.** Pure `validate_schedule(scheduled_for, now)`. | AC-3, AC-4, AC-5 | `tests/test_schedule_rules.py`: 44:59 / 45:00 / 46:00 minutes; 7 days exactly / +1 µs; naive datetime; non-UTC offset normalised; `release_at` is 30 min earlier. | Done |
| S4 | **Opening-hours rule.** Pure `kitchen_open_for_window(...)` with overnight hours, 24-hour restaurants, inclusive ends, DST. | AC-6 | `tests/test_opening_hours.py`: same-day hours, window crossing opening/closing, overnight before/after midnight, all-day, fall-back DST night. | Done |
| S5 | **Scheduled placement through the API.** `scheduled_for` on `POST /orders`, status `SCHEDULED`, error codes, validation order. | AC-1, AC-2, AC-3–AC-6, AC-15 | `tests/test_api_scheduled.py`: happy path, immediate path unchanged, each error code over HTTP, precedence when two rules fail. | Done |
| S6 | **Release service.** `release_due_orders(conn, now)` with a single state-guarded `UPDATE ... RETURNING`. | AC-7–AC-10 | `tests/test_release.py`: 1 µs before vs at `release_at`; second run releases nothing; 8 threads × 40 orders release each id exactly once; catch-up after downtime; immediate and cancelled orders untouched. | Done |
| S7 | **Release worker.** Lifespan background loop with error logging, and `python -m minidash.worker --once`. | AC-7, AC-10, AC-14 | `tests/test_worker.py`: loop releases an order after `ManualClock.advance`; a failing run is logged and the loop continues; CLI releases overdue orders. | Done |
| S8 | **Cancel before release.** `POST /orders/{id}/cancel` with a guarded `UPDATE`. | AC-11, AC-12 | `tests/test_cancel.py`: cancel then release → never placed; release then cancel → 409, unchanged; cancel twice → 409; immediate order → 409; unknown id → 404. | Planned |
| S9 | **Guard the status endpoint.** PATCH cannot change a `SCHEDULED` order or set `SCHEDULED`. | AC-13 | `tests/test_status_guard.py`: PATCH on scheduled → 409 and still scheduled (release still happens later); PATCH to `SCHEDULED` → 422; released orders can be PATCHed normally. | Planned |
| S10 | **Demo and docs.** In-process demo script with a manual clock, README run/test/demo instructions, dependency audit. | — | `scripts/demo_scheduled_orders.py` runs to completion; README commands run from a fresh clone. | Planned |

## Mutation checks

`scripts/mutation_check.py` applies small deliberate bugs to the source (one at a time) and confirms
the test suite fails for each. Results are recorded in `AI_LOG.md`.
