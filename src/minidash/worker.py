"""Release scheduled orders in the background.

The API starts `release_loop` from its lifespan. The same pass can be run from a shell or cron:

    python -m minidash.worker --once   # one pass, then exit
    python -m minidash.worker          # loop forever; then run the API with
                                       # MINIDASH_RELEASE_INTERVAL=0
"""

import argparse
import asyncio
import logging
import os

from minidash.clock import Clock, SystemClock
from minidash.db import connect, init_db
from minidash.services.scheduling import release_due_orders

log = logging.getLogger("minidash.worker")


def run_once(db_path: str, clock: Clock) -> list[int]:
    conn = connect(db_path)
    try:
        released = release_due_orders(conn, clock.now())
    finally:
        conn.close()
    if released:
        log.info("released scheduled orders %s", released)
    return released


async def release_loop(db_path: str, clock: Clock, interval: float) -> None:
    """Run a release pass every `interval` seconds until cancelled.

    A failing pass is logged and retried on the next tick, so one bad run cannot stop all
    future releases.
    """
    while True:
        try:
            await asyncio.to_thread(run_once, db_path, clock)
        except Exception:
            log.exception("release run failed; retrying in %s s", interval)
        await asyncio.sleep(interval)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Release scheduled MiniDash orders that are due.")
    parser.add_argument("--db", default=os.environ.get("MINIDASH_DB", "minidash.db"))
    parser.add_argument("--once", action="store_true", help="run one pass and exit")
    parser.add_argument("--interval", type=float, default=15.0, help="seconds between passes")
    args = parser.parse_args(argv)

    init_db(args.db)
    clock = SystemClock()
    if args.once:
        released = run_once(args.db, clock)
        print(f"released {len(released)} order(s): {released}")
        return 0
    logging.basicConfig(level=logging.INFO)
    asyncio.run(release_loop(args.db, clock, args.interval))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
