"""Shared FastAPI dependencies."""

import sqlite3
from collections.abc import Iterator
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends, Request

from minidash.clock import Clock
from minidash.db import connect


def get_conn(request: Request) -> Iterator[sqlite3.Connection]:
    """One SQLite connection per request, closed afterwards."""
    conn = connect(request.app.state.db_path)
    try:
        yield conn
    finally:
        conn.close()


Conn = Annotated[sqlite3.Connection, Depends(get_conn)]


def get_clock(request: Request) -> Clock:
    return request.app.state.clock


ClockDep = Annotated[Clock, Depends(get_clock)]


def get_business_tz(request: Request) -> ZoneInfo:
    return request.app.state.business_tz


BusinessTz = Annotated[ZoneInfo, Depends(get_business_tz)]
