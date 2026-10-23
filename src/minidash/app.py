"""Application factory."""

import os

from fastapi import FastAPI

from minidash.db import init_db
from minidash.errors import DomainError, domain_error_handler
from minidash.routes import orders, restaurants


def create_app(db_path: str | None = None) -> FastAPI:
    db_path = db_path or os.environ.get("MINIDASH_DB", "minidash.db")
    init_db(db_path)

    app = FastAPI(title="MiniDash", version="0.1.0")
    app.state.db_path = db_path
    app.add_exception_handler(DomainError, domain_error_handler)
    app.include_router(restaurants.router)
    app.include_router(orders.router)
    return app
