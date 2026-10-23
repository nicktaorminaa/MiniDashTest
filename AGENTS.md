# AGENTS.md — rules for AI assistants working in this repository

## Stack
- Python 3.11+ with FastAPI and SQLite (stdlib `sqlite3`, no ORM).
- Tests: pytest, run with `pytest` from the repo root. Lint: `ruff check .` and `ruff format --check .`.

## Conventions
1. **Layers.** Routes parse HTTP and call services. Services hold business rules and transactions.
   Repositories hold all SQL. Do not put SQL in routes or rules in repositories.
2. **Time.** Never call `datetime.now()` or `time.time()` in application code. Take `now` from the
   injected `Clock`. All stored times are UTC strings made by `minidash.timeutil.to_db`.
3. **Errors.** Business-rule failures raise `DomainError(code, message, status)` with an
   UPPER_SNAKE_CASE code that is listed in `docs/requirements.md`.
4. **State changes are guarded in SQL.** A status change puts the expected current status in the
   `WHERE` clause and checks the row count. No read-then-write.
5. **Tests come with the slice.** Each change ships with tests that fail when the change is reverted,
   including boundary values (e.g. 44:59 / 45:00 / 46:00).

## Boundaries
- Only touch files the current slice needs. No unrequested helper modules.
- No new dependency without checking it on https://pypi.org first and recording it in
  `docs/dependencies.md`.
- Never put secrets, API keys or personal data in code, tests, prompts or commits.
