# AI Usage Log

## Read this first

This log is unusual, and it says so up front rather than imitating a normal one.

- **Who did the work.** Every file in this repository was written by **Claude (Anthropic, model
  Claude Opus 5.5)** running as an agent in the claude.ai app, with a Linux workspace, a shell, file
  tools and PyPI access.
- **The only human input** was one message on Fri 23 Oct 2026 at 17:07 (New York): the assignment PDF
  and the request *"Complete this project and choose whatever feature track you'd like, I don't want to
  be involved so don't ask me any questions, everything is completely up to you."*
- **So there were no per-slice human prompts.** For each slice, the "prompt" below is the task card in
  `docs/tasks.md` that Claude wrote for itself and then carried out. The "verified" and "changed"
  columns describe checks Claude ran on its own output. In the assignment's terms, the AI was both the
  pair programmer and the reviewer, and nobody independent reviewed either role.
- **How the log was kept.** Claude kept running notes during the session and wrote this file from them
  at the end. Times come from the git commit timestamps.
- **"I" below means Claude.**

Every entry is something that actually happened. Entries 6, 9, 10 and 12 are cases where output was
rejected or substantially rewritten; entries 1, 2, 7 and 8 contain smaller corrections.

---

### Entry 1 — Baseline

| Field | Entry |
|---|---|
| Entry # / date | 1 / Fri 23 Oct 2026, 17:08–17:14 |
| Tool, model, mode | Claude Opus 5.5, claude.ai agent workspace (shell + file tools) |
| Slice | Baseline (Appendix C), commit `47ef1f1` |
| Prompt | The Appendix C prompt from the assignment, verbatim: FastAPI + SQLite, four tables, five endpoints, layered routes/services/repository, 5 seeded restaurants, pytest tests, no dependency beyond fastapi, uvicorn and pytest. |
| What the AI produced | The layered app (`routes/`, `services/`, `repositories/`), seed data with one overnight restaurant (18:00–02:00) chosen on purpose to exercise Track A later, and 11 endpoint tests. |
| What I verified | Looked up fastapi, uvicorn, pytest, httpx, ruff and tzdata on `pypi.org/pypi/<name>/json` before installing. Ran pytest (11 passed), ruff, and a live `uvicorn` smoke test with curl. Read `pip show` to see why `opentelemetry-api` appeared (fastapi requires it). |
| What I changed and why | (a) Appendix C contradicts itself: it allows only three packages but asks for endpoint tests, and FastAPI's `TestClient` needs an HTTP client. I added one as a dev dependency and documented the deviation. (b) Starlette's warning told me to install `httpx2` instead of `httpx`. I did not trust a package name from a warning blindly: confirmed Starlette's own source imports it, the PyPI page links to the pydantic GitHub org with the same author as httpx, it has 22 releases, and checked its two transitive packages too. Then switched. (c) ruff found 7 issues in my code: five `Depends()` defaults (B008), `str, Enum` instead of `StrEnum`, `timezone.utc` instead of `UTC`. Rewrote routes to use an `Annotated` dependency alias rather than silencing the rule. |
| Outcome | Modified, then accepted. |

### Entry 2 — Spec package

| Field | Entry |
|---|---|
| Entry # / date | 2 / 17:14–17:16 |
| Tool, model, mode | Claude Opus 5.5, same session |
| Slice | `docs/requirements.md`, `docs/design.md`, `docs/tasks.md`, then `AGENTS.md` (commits `e9a6945`, `5f3ce4f`) |
| Prompt | Track A bullet list from the assignment and the Appendix A EARS examples. |
| What the AI produced | 15 EARS criteria with error codes, validation order and out-of-scope list; component and sequence diagrams; ADR-001 (release mechanism, 4 options) and ADR-002 (what "closed" means, 3 options); a 10-slice plan; an AGENTS.md with 5 conventions. |
| What I verified | Each criterion maps to a slice and a named test in the traceability table. Checked that the Mermaid blocks use only `flowchart` and `sequenceDiagram` syntax that GitHub renders. |
| What I changed and why | My first `tasks.md` marked all ten slices **Done** before any feature code existed. That would have been a false record in the history, so I changed them to Planned and ticked each one in its own slice commit. |
| Outcome | Modified, then accepted. Note: the design decisions in the ADRs were made by the AI. No human made or reviewed them. |

### Entry 3 — S1, injected clock

| Field | Entry |
|---|---|
| Entry # / date | 3 / 17:16–17:17 |
| Tool, model, mode | Claude Opus 5.5, same session |
| Slice | S1: `Clock`, `SystemClock`, `ManualClock`; `created_at` from the clock (commit `23785e4`) |
| Prompt | Task card S1 in `docs/tasks.md` + AGENTS.md rule 2 (never call `datetime.now()` in app code). |
| What the AI produced | `clock.py`, a `ClockDep` dependency, `create_app(clock=...)`, the route passes `now` into the service, 4 tests. |
| What I verified | `grep` for `datetime.now` in `src/` (only `SystemClock` remains). Mutation: putting `datetime.now` back in `place_order` fails `test_created_at_comes_from_injected_clock`. |
| What I changed and why | First run failed at collection: the test imported `START` from `conftest` with a relative import but `tests/` was not a package. Added `tests/__init__.py`. |
| Outcome | Accepted after a small fix. (A real bug in this slice's `ManualClock.advance` was found later; see entry 12.) |

### Entry 4 — S2, schema and timestamps

| Field | Entry |
|---|---|
| Entry # / date | 4 / 17:17–17:18 |
| Tool, model, mode | Claude Opus 5.5, same session |
| Slice | S2: `migrate()`, three nullable columns, index, `timeutil.to_db` (commit `f3396ce`) |
| Prompt | Task card S2. |
| What the AI produced | Migration via `PRAGMA table_info` + `ALTER TABLE`, fixed-width UTC formatter, response fields, 6 tests including migrating a hand-built baseline-shaped database. |
| What I verified | Three mutants: no UTC conversion (2 tests fail), skip `ALTER` (15 fail), drop microseconds (1 fails). The last one taught me something: only the fixed-width test catches it. The sort-order test alone would miss it, because `+` happens to sort before `.`. |
| What I changed and why | My own design said new databases get the columns from `CREATE TABLE` and old ones from a migration. While coding I changed this to one migration path for both (less code, and the migration runs in every test), and updated `design.md` in the same commit so the doc matches the code. |
| Outcome | Accepted. |

### Entry 5 — S3, lead-time and horizon rule

| Field | Entry |
|---|---|
| Entry # / date | 5 / 17:18–17:19 |
| Tool, model, mode | Claude Opus 5.5, same session |
| Slice | S3: `validate_schedule` (commit `3c4ff9c`) |
| Prompt | Task card S3 with boundaries 44:59 / 45:00 − 1 µs / 45:00 / 46:00 and 7 d / 7 d + 1 µs. |
| What the AI produced | A pure function returning `release_at` in UTC, and 11 tests including the 1 Nov 2026 fall-back night. |
| What I verified | Five mutants, all caught: 45→44, `<`→`<=`, `>`→`>=`, no UTC conversion, 30→15. The no-UTC mutant is caught only by the DST test. |
| What I changed and why | Nothing after writing. I converted both operands to UTC from the start because Python subtracts two datetimes that share a `tzinfo` by wall clock. This was anticipated, not found by testing, so it does not count as a defect found. |
| Outcome | Accepted as written. |

### Entry 6 — S4, opening hours (test rewritten)

| Field | Entry |
|---|---|
| Entry # / date | 6 / 17:19–17:20 |
| Tool, model, mode | Claude Opus 5.5, same session |
| Slice | S4: `kitchen_open_for_window` (commit `5081bca`) |
| Prompt | Task card S4 + ADR-002 (whole kitchen window inside one opening interval, overnight hours, inclusive ends, compare in UTC). |
| What the AI produced | The rule and 16 tests. One failed: the DST fall-back case. |
| What I verified | Read the failure. The rule was correct; **my test helper was wrong**. It built the window end as `start + timedelta(minutes=30)` on a `ZoneInfo` datetime. That is wall-clock arithmetic and it resets `fold`, so on the DST night the "window" ended an hour *before* it started. It is the same trap I had just guarded against in the app code. |
| What I changed and why | **Rewrote the helper** to add the 30 minutes in UTC. Then 5 mutants, all caught (skip previous-day interval, delivery-only check, exclusive start, wall-clock comparison, no all-day case). |
| Outcome | Test helper rejected and rewritten; rule accepted. |

### Entry 7 — S5, scheduled placement over HTTP

| Field | Entry |
|---|---|
| Entry # / date | 7 / 17:20–17:21 |
| Tool, model, mode | Claude Opus 5.5, same session |
| Slice | S5: `scheduled_for` on `POST /orders` (commit `b86d45c`) |
| Prompt | Task card S5 + the validation order in `requirements.md`. |
| What the AI produced | Schema and service changes, a `BusinessTz` dependency, 18 API tests. All passed on the first run. |
| What I verified | Read the whole diff instead of trusting the green run. Mutants: skip hours check, delivery-only window, store PLACED, schedule check before items. All caught. |
| What I changed and why | The diff review found two problems the tests did not. (1) The `RESTAURANT_CLOSED` message hard-coded "30 minutes" outside the scheduling module and read badly, so it now shows the actual local window ("closed during the kitchen window 21:45-22:15"), with a test. (2) Adding `SCHEDULED` to the status enum silently made it a legal value for `PATCH /status`. A restaurant tool could push any order into `SCHEDULED` with no `release_at`, and the release job would never pick it up. I recorded it as a known gap in the commit message and fixed it in S9. |
| Outcome | Modified, then accepted with a documented gap. |

### Entry 8 — S6, release exactly once

| Field | Entry |
|---|---|
| Entry # / date | 8 / 17:21–17:24 |
| Tool, model, mode | Claude Opus 5.5, same session |
| Slice | S6: `release_due_orders` (commit `eb375b6`) |
| Prompt | Task card S6 + ADR-001 (one `UPDATE ... WHERE status='SCHEDULED' AND release_at <= now RETURNING id`). |
| What the AI produced | Repository and service functions, and 8 tests including 8 threads × 3 passes over 40 orders. |
| What I verified | Checked that the parallel test has teeth: replaced the guarded `UPDATE` with select-then-update. It failed every time, and every one of the 8 workers claimed all 40 orders. Spotted in review that `RETURNING` needs SQLite 3.35+, which some Linux system Pythons lack, so `init_db` now fails fast with a clear message (tested). |
| What I changed and why | **My verification script was wrong.** A 30-run stress loop reported 30/30 failures. The tests were fine; my loop grepped for a summary line that `-q` on top of the config's `-q` suppresses. Switched to checking the exit code: 0/30 failures. |
| Outcome | Accepted; the stress script was rewritten. |

### Entry 9 — S7, background loop (weak test rewritten)

| Field | Entry |
|---|---|
| Entry # / date | 9 / 17:24–17:26 |
| Tool, model, mode | Claude Opus 5.5, same session |
| Slice | S7: `worker.release_loop` in the app lifespan, `python -m minidash.worker --once` (commit `e09d583`) |
| Prompt | Task card S7. |
| What the AI produced | The loop with exception logging, `MINIDASH_RELEASE_INTERVAL` (0 = off), the CLI, and 4 tests. |
| What I verified | Three mutants. "No exception guard" and "loop never started" were caught. **"Interval 0 treated as unset" survived.** That is the exact bug I had written a code comment about (`release_interval or default` turns 0 into 15). |
| What I changed and why | Worked out why the test missed it: the loop's first pass runs at start-up, before the test had created its order, and the next pass would be 15 s later, so "still SCHEDULED after 0.15 s" passed either way. **Rewrote the test** so a due order already exists when the app starts. The mutant is now caught. 15/15 repeated runs pass. |
| Outcome | Test rejected and rewritten. |

### Entry 10 — S8, cancel (race test rejected)

| Field | Entry |
|---|---|
| Entry # / date | 10 / 17:26–17:28 |
| Tool, model, mode | Claude Opus 5.5, same session |
| Slice | S8: `POST /orders/{id}/cancel` (commit `bee85a6`) |
| Prompt | Task card S8. |
| What the AI produced | A guarded `UPDATE ... AND status='SCHEDULED'`, the endpoint, and 7 tests including a cancel-vs-release race. All passed. |
| What I verified | I wondered whether the race test actually raced, so I printed the outcome counts. Five runs: released 40, cancelled 0 every time. The releaser finished before the first HTTP cancel landed, so the "race" only ever checked one outcome. |
| What I changed and why | **Rejected that test and rewrote it.** Orders now come due one minute apart while the releaser walks time forward, and the canceller works from the last order backwards, so they meet in the middle (about 20/20 each run). The test now asserts that both outcomes happened. Also added AC-11a: an order that is due but not yet reached by the release job is still cancellable, because "released" means the status change, not the clock. Removing the guard fails 4 tests; 20/20 repeated runs pass. |
| Outcome | Test rejected and rewritten; code accepted. |

### Entry 11 — S9, status guard

| Field | Entry |
|---|---|
| Entry # / date | 11 / 17:29–17:30 |
| Tool, model, mode | Claude Opus 5.5, same session |
| Slice | S9: PATCH cannot touch `SCHEDULED` orders or set `SCHEDULED` (commit `b2ef33d`) |
| Prompt | Task card S9 + the gap found in entry 7. |
| What the AI produced | Tests first, then `update_status_unless_scheduled` with the guard in SQL, two new error codes, and removal of the now-unused unguarded repository function. |
| What I verified | Ran the new tests against the pre-fix code: 5 of 7 failed, which confirmed the hole was real. After the fix, 3 mutants were all caught. Added a test for PATCH to the same status, because the guard depends on SQLite counting a no-op update in `rowcount`. |
| What I changed and why | Nothing beyond the plan. |
| Outcome | Accepted. |

### Entry 12 — ManualClock DST bug (own S1 code rewritten)

| Field | Entry |
|---|---|
| Entry # / date | 12 / 17:30–17:31 |
| Tool, model, mode | Claude Opus 5.5, same session |
| Slice | Follow-up to S1 (commit `8d48a43`) |
| Prompt | None; found while writing the demo script, which runs its clock in `America/New_York`. |
| What the AI produced | Originally (in S1): `self._now = self._now + delta`. |
| What I verified | Realised that with a `ZoneInfo` clock this is wall-clock arithmetic, the third time this pitfall came up. Wrote a test first: advancing 1 h from 01:30 EDT on 1 Nov 2026 gave 07:30 UTC instead of 06:30. It failed. |
| What I changed and why | `advance` now adds in UTC and converts back to the caller's zone. All tests pass. |
| Outcome | Original code rejected and rewritten. |

### Entry 13 — S10, demo, mutation script, docs

| Field | Entry |
|---|---|
| Entry # / date | 13 / 17:31–17:34 |
| Tool, model, mode | Claude Opus 5.5, same session |
| Slice | S10 (commit `ae6ff1b`) |
| Prompt | Task card S10. |
| What the AI produced | `scripts/demo_scheduled_orders.py`, `scripts/mutation_check.py` (29 mutants), `docs/dependencies.md`, README. |
| What I verified | Ran the demo end to end. Ran the mutation script: 29/29 killed in 58 s, and `git status` showed every source file restored. Ran the README's live-server steps exactly as written against `uvicorn`: create, read, cancel, cancel again (409), PATCH to `SCHEDULED` (422), and the background loop released an overdue order within about a second and logged it. |
| What I changed and why | Caught an omission: ADR-002 promised `tzdata` for Windows in `requirements.txt`, but no slice had added it. Added it with a `sys_platform == "win32"` marker (already checked on PyPI in entry 1). Exempted only the mutation script from the line-length rule, because its patterns must match source lines exactly. |
| Outcome | Accepted. |

### Entry 14 — This log and the reflection

| Field | Entry |
|---|---|
| Entry # / date | 14 / 17:34 onward |
| Tool, model, mode | Claude Opus 5.5, same session |
| Slice | `AI_LOG.md`, `Reflection.pdf` |
| Prompt | Sections 5 and 7 of the assignment. |
| What the AI produced | This file and the reflection. |
| What I verified | Every entry above was checked against the git history (`git log`, commit messages) and the notes taken during the session. |
| What I changed and why | I chose to write both in Claude's own voice rather than as if a student had done the work. The assignment says the spec, the design decision and the reflection must be the student's own thinking, and that code a student cannot explain is not theirs. A first-person student narrative written by the AI would be false. |
| Outcome | Accepted by the AI. Not reviewed by a human. |

---

## Summary

| | |
|---|---|
| Human prompts | 1 (the initial request) |
| Commits | 15 (baseline, spec, rules file, 10 slices, 1 follow-up fix, this log) |
| Tests | 95, all passing; 29/29 mutants killed |
| Output rejected or substantially rewritten | 4 (entries 6, 9, 10, 12) |
| Defects found by review, not by tests | 2 (PATCH hole in entry 7; missing `tzdata` in entry 13) |
| Mistakes in the AI's own verification | 2 (test helper in entry 6; stress loop in entry 8) |
