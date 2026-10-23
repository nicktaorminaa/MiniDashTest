# Requirements — Track A: Scheduled Orders

A customer can place an order now for delivery later. The order is held and released to the
restaurant 30 minutes before the requested delivery time.

## Glossary

| Term | Meaning |
|---|---|
| `scheduled_for` | Requested delivery time. ISO 8601 with a UTC offset, e.g. `2026-10-24T19:00:00-04:00`. |
| `release_at` | `scheduled_for − 30 min`. When the order is handed to the kitchen. |
| Kitchen window | The interval `[release_at, scheduled_for]`. The kitchen must be open for all of it. |
| Business time zone | The single time zone in which restaurant opening hours are written (`MINIDASH_TZ`, default `America/New_York`). |
| Now | The value of the injected clock, never the machine's wall clock directly. |

## User stories

- **US-1** As a customer, I want to choose a delivery time up to a week ahead, so that food arrives when I need it.
- **US-2** As a customer, I want a clear error when the time I pick is not possible, so that I can choose another.
- **US-3** As a restaurant, I want scheduled orders to reach my queue once, at a predictable time before delivery, so that I can prepare them without duplicates.
- **US-4** As a customer, I want to cancel a scheduled order before the kitchen sees it.
- **US-5** As a developer, I want every time rule to read from an injected clock, so that tests are deterministic.

## Acceptance criteria (EARS)

Error responses use the body `{"error": {"code": "<CODE>", "message": "..."}}`.

| ID | Story | Criterion |
|---|---|---|
| **AC-1** | US-1 | WHEN a customer places an order with a valid `scheduled_for`, THE SYSTEM SHALL create it with status `SCHEDULED`, store `scheduled_for` and `release_at = scheduled_for − 30 min` in UTC, and return 201. |
| **AC-2** | US-1 | WHEN a customer places an order without `scheduled_for`, THE SYSTEM SHALL create it with status `PLACED` and null schedule fields, exactly as the baseline did. |
| **AC-3** | US-2 | IF `scheduled_for` has no UTC offset, THEN THE SYSTEM SHALL reject the order with 422 `SCHEDULE_TIMEZONE_REQUIRED`. |
| **AC-4** | US-2 | IF `scheduled_for` is less than 45 minutes after now, THEN THE SYSTEM SHALL reject the order with 422 `SCHEDULE_TOO_SOON`. Exactly 45 minutes is accepted. |
| **AC-5** | US-2 | IF `scheduled_for` is more than 7 days after now, THEN THE SYSTEM SHALL reject the order with 422 `SCHEDULE_TOO_FAR`. Exactly 7 days is accepted. |
| **AC-6** | US-2 | IF the restaurant is not open for the whole kitchen window (in the business time zone, including hours that cross midnight), THEN THE SYSTEM SHALL reject the order with 422 `RESTAURANT_CLOSED`. |
| **AC-7** | US-3 | WHEN now reaches `release_at` of a `SCHEDULED` order, THE SYSTEM SHALL change its status to `PLACED` and record `released_at` on the next release run. |
| **AC-8** | US-3 | WHILE now is before `release_at`, THE SYSTEM SHALL keep the order `SCHEDULED`. |
| **AC-9** | US-3 | WHEN the release job runs repeatedly or in parallel, THE SYSTEM SHALL move each scheduled order from `SCHEDULED` to `PLACED` exactly once. |
| **AC-10** | US-3 | WHEN the service starts after one or more `release_at` times have passed, THE SYSTEM SHALL release those orders on its first run. |
| **AC-11** | US-4 | WHEN a customer cancels a `SCHEDULED` order, THE SYSTEM SHALL mark it `CANCELLED` and never release it. |
| **AC-11a** | US-4 | WHILE an order is still `SCHEDULED` after its `release_at` because the release job has not run yet, THE SYSTEM SHALL still allow it to be cancelled. (Released means the status change, not the clock.) |
| **AC-12** | US-4 | IF a customer cancels an order that is not `SCHEDULED`, THEN THE SYSTEM SHALL return 409 `ORDER_NOT_CANCELLABLE` and change nothing. |
| **AC-13** | US-3 | IF `PATCH /orders/{id}/status` targets a `SCHEDULED` order, THEN THE SYSTEM SHALL return 409 `ORDER_IS_SCHEDULED` and change nothing. IF it asks for status `SCHEDULED`, THEN THE SYSTEM SHALL return 422 `STATUS_NOT_SETTABLE`. |
| **AC-14** | US-5 | THE SYSTEM SHALL take now from an injected `Clock` for validation, release, `created_at` and `released_at`. |
| **AC-15** | US-1 | WHEN a client reads an order, THE SYSTEM SHALL include `scheduled_for`, `release_at` and `released_at` (null when not applicable). |

### Validation order

When several rules fail at once, the first failing check wins, in this order: restaurant exists (404) →
items on menu → timezone → too soon → too far → restaurant closed. This keeps error codes predictable
for clients and tests.

### Why the whole kitchen window must be open (AC-6)

The assignment says to reject a scheduled time when the restaurant is closed. Checking only the delivery
time would accept a 11:10 delivery at a restaurant that opens at 11:00, which releases the order at
10:40 to a closed kitchen. Requiring the full window `[release_at, scheduled_for]` closes that gap.
See ADR-002 in `design.md`.

## Out of scope

- Authentication and authorization. Anyone with an order id can cancel it, as anyone can already PATCH
  its status in the baseline.
- Changing the scheduled time after placement (cancel and re-order instead).
- Per-restaurant time zones, day-of-week hours, holidays and temporary closures.
- Cancelling orders that are not `SCHEDULED`, refunds and payments.
- Customer or restaurant notifications.
- Guaranteeing delivery by `scheduled_for` (prep and travel time are not modelled).
- Running release workers on several hosts against one database (SQLite is single-host).
- Status transition rules beyond AC-13 (that is Track C).

## Traceability

| Criterion | Slice (`tasks.md`) | Tests |
|---|---|---|
| AC-1 | S5 | `test_api_scheduled.py::test_scheduled_order_is_created_scheduled` |
| AC-2 | S5 | `test_api_scheduled.py::test_order_without_schedule_is_placed_immediately` |
| AC-3 | S3, S5 | `test_schedule_rules.py::test_naive_datetime_rejected`, `test_api_scheduled.py::test_api_error_codes` |
| AC-4 | S3, S5 | `test_schedule_rules.py::test_lead_time_boundaries` |
| AC-5 | S3, S5 | `test_schedule_rules.py::test_horizon_boundaries` |
| AC-6 | S4, S5 | `test_opening_hours.py` (all), `test_api_scheduled.py::test_api_rejects_closed_restaurant` |
| AC-7, AC-8 | S6 | `test_release.py::test_release_boundary` |
| AC-9 | S6 | `test_release.py::test_second_run_releases_nothing`, `test_release.py::test_parallel_release_is_exactly_once` |
| AC-10 | S6, S7 | `test_release.py::test_catch_up_after_downtime`, `test_worker.py::test_cli_once_releases_overdue_orders` |
| AC-11, AC-11a, AC-12 | S8 | `test_cancel.py` (all) |
| AC-13 | S9 | `test_status_guard.py` (all) |
| AC-14 | S1, S7 | `test_clock.py`, `test_worker.py::test_background_loop_releases_with_injected_clock` |
| AC-15 | S2, S5 | `test_schema.py`, `test_api_scheduled.py::test_scheduled_order_is_created_scheduled` |
