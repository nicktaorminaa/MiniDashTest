"""ASGI entry point: `uvicorn minidash.main:app`."""

from minidash.app import create_app

app = create_app()
