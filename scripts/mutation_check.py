"""Check that the tests fail when the code is broken.

Applies one small deliberate bug ("mutant") at a time, runs the test suite, and restores the
file. A mutant is "killed" when at least one test fails. Any survivor means a rule is not really
tested. Exits non-zero if a mutant survives or a pattern no longer matches the source.

    python scripts/mutation_check.py
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "minidash"

SCHED = "services/scheduling.py"
ORDERING = "services/ordering.py"
REPO = "repositories/orders.py"

# (description, file, [(original text, replacement), ...])
MUTANTS = [
    ("lead time 45 -> 44 min", SCHED, [("minutes=45)", "minutes=44)")]),
    ("lead time < becomes <=", SCHED, [("if lead < MIN_LEAD", "if lead <= MIN_LEAD")]),
    ("horizon > becomes >=", SCHED, [("if lead > MAX_HORIZON", "if lead >= MAX_HORIZON")]),
    ("horizon 7 -> 8 days", SCHED, [("days=7)", "days=8)")]),
    ("release 30 -> 15 min before", SCHED, [("minutes=30)", "minutes=15)")]),
    (
        "naive datetimes accepted",
        SCHED,
        [("if scheduled_for.tzinfo is None or scheduled_for.utcoffset() is None:", "if False:")],
    ),
    (
        "lead computed without UTC conversion",
        SCHED,
        [
            ("scheduled_utc = scheduled_for.astimezone(UTC)", "scheduled_utc = scheduled_for"),
            ("lead = scheduled_utc - now.astimezone(UTC)", "lead = scheduled_utc - now"),
        ],
    ),
    (
        "hours: ignore interval that opened yesterday",
        SCHED,
        [("for day in (start_day - timedelta(days=1), start_day):", "for day in (start_day,):")],
    ),
    (
        "hours: check delivery time only",
        SCHED,
        [
            (
                "if open_utc <= start_utc and end_utc <= close_utc:",
                "if open_utc <= end_utc <= close_utc:",
            )
        ],
    ),
    (
        "hours: exclusive opening time",
        SCHED,
        [("if open_utc <= start_utc and", "if open_utc < start_utc and")],
    ),
    ("hours: exclusive closing time", SCHED, [("end_utc <= close_utc:", "end_utc < close_utc:")]),
    ("hours: no all-day case", SCHED, [("if opens == closes:", "if False:")]),
    (
        "hours: compare wall-clock times",
        SCHED,
        [
            (
                "start_utc, end_utc = start.astimezone(UTC), end.astimezone(UTC)",
                "start_utc, end_utc = start.astimezone(tz), end.astimezone(tz)",
            ),
            (
                "open_utc = datetime.combine(day, opens, tzinfo=tz).astimezone(UTC)",
                "open_utc = datetime.combine(day, opens, tzinfo=tz)",
            ),
            (
                "close_utc = datetime.combine(close_day, closes, tzinfo=tz).astimezone(UTC)",
                "close_utc = datetime.combine(close_day, closes, tzinfo=tz)",
            ),
        ],
    ),
    (
        "release: no status guard",
        REPO,
        [
            (
                '"WHERE status = ? AND release_at <= ? RETURNING id"',
                '"WHERE ? IS NOT NULL AND release_at <= ? RETURNING id"',
            )
        ],
    ),
    (
        "release: < instead of <=",
        REPO,
        [
            (
                '"WHERE status = ? AND release_at <= ? RETURNING id"',
                '"WHERE status = ? AND release_at < ? RETURNING id"',
            )
        ],
    ),
    (
        "cancel: no status guard",
        REPO,
        [
            (
                '"UPDATE orders SET status = ? WHERE id = ? AND status = ?"',
                '"UPDATE orders SET status = ? WHERE id = ? AND ? IS NOT NULL"',
            )
        ],
    ),
    (
        "PATCH: no status guard",
        REPO,
        [
            (
                '"UPDATE orders SET status = ? WHERE id = ? AND status != ?"',
                '"UPDATE orders SET status = ? WHERE id = ? AND ? IS NOT NULL"',
            )
        ],
    ),
    (
        "placement: skip opening-hours check",
        ORDERING,
        [
            (
                "        if not kitchen_open_for_window(",
                "        if False and kitchen_open_for_window(",
            )
        ],
    ),
    (
        "placement: kitchen window starts at delivery",
        ORDERING,
        [
            (
                "            release_utc,\n            order.scheduled_for,",
                "            order.scheduled_for,\n            order.scheduled_for,",
            )
        ],
    ),
    (
        "placement: scheduled order stored as PLACED",
        ORDERING,
        [("        status = OrderStatus.SCHEDULED", "        status = OrderStatus.PLACED")],
    ),
    (
        "placement: created_at from the wall clock",
        ORDERING,
        [
            (
                "created_at=to_db(now),",
                'created_at=to_db(__import__("datetime").datetime.now(__import__("datetime").UTC)),',
            )
        ],
    ),
    (
        "PATCH: SCHEDULED may be set",
        ORDERING,
        [("    if status == OrderStatus.SCHEDULED:", "    if False:")],
    ),
    (
        "app: interval 0 treated as unset",
        "app.py",
        [
            (
                '    if release_interval is None:  # not `or`: 0 is a valid value meaning "off"\n'
                '        release_interval = float(os.environ.get("MINIDASH_RELEASE_INTERVAL", "15"))',
                "    release_interval = release_interval or float("
                'os.environ.get("MINIDASH_RELEASE_INTERVAL", "15"))',
            )
        ],
    ),
    (
        "app: loop never started",
        "app.py",
        [("    if app.state.release_interval > 0:", "    if False:")],
    ),
    (
        "worker: a failing pass kills the loop",
        "worker.py",
        [
            (
                "        try:\n            await asyncio.to_thread(run_once, db_path, clock)\n"
                "        except Exception:\n"
                '            log.exception("release run failed; retrying in %s s", interval)',
                "        await asyncio.to_thread(run_once, db_path, clock)",
            )
        ],
    ),
    ("storage: drop microseconds", "timeutil.py", [('timespec="microseconds"', 'timespec="auto"')]),
    (
        "storage: keep caller's offset",
        "timeutil.py",
        [("value.astimezone(UTC).isoformat", "value.isoformat")],
    ),
    (
        "migration: never adds columns",
        "db.py",
        [("        if column not in existing:", "        if False:")],
    ),
    (
        "page: repeated time picks the later one",
        "web/logic.js",
        [
            (
                "return valid.length ? Math.min(...valid) : before;",
                "return valid.length ? Math.max(...valid) : before;",
            )
        ],
    ),
    (
        "page: lead-time hint < becomes <=",
        "web/logic.js",
        [
            (
                "if (lead < rules.min_lead_minutes * MINUTE)",
                "if (lead <= rules.min_lead_minutes * MINUTE)",
            )
        ],
    ),
    (
        "page: hours ignore yesterday's interval",
        "web/logic.js",
        [("for (const day of [addDays(startDay, -1), startDay])", "for (const day of [startDay])")],
    ),
    (
        "page: timeline assumes 24-hour days",
        "web/logic.js",
        [("const span = dayEnd - dayStart;", "const span = 24 * HOUR;")],
    ),
    (
        "config: lead time hard-coded",
        "routes/web.py",
        [('"min_lead_minutes": int(MIN_LEAD.total_seconds() // 60),', '"min_lead_minutes": 45,')],
    ),
    (
        "clock: advance in wall-clock time",
        "clock.py",
        [("(self._now.astimezone(UTC) + delta).astimezone(tz)", "self._now + delta")],
    ),
]


def run_tests() -> bool:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def main() -> int:
    if not run_tests():
        print("The unmodified test suite fails; fix that first.")
        return 2

    survivors, stale = [], []
    for description, rel_path, replacements in MUTANTS:
        path = SRC / rel_path
        original = path.read_text()
        mutated = original
        for old, new in replacements:
            if mutated.count(old) != 1:
                stale.append(description)
                break
            mutated = mutated.replace(old, new)
        else:
            try:
                path.write_text(mutated)
                passed = run_tests()
            finally:
                path.write_text(original)
            print(f"{'SURVIVED' if passed else 'killed  '}  {description}")
            if passed:
                survivors.append(description)
            continue
        print(f"STALE     {description} (pattern not found exactly once in {rel_path})")

    killed = len(MUTANTS) - len(survivors) - len(stale)
    print(
        f"\n{killed}/{len(MUTANTS)} mutants killed, {len(survivors)} survived, {len(stale)} stale"
    )
    return 1 if survivors or stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
