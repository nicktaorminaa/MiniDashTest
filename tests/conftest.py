import pytest
from fastapi.testclient import TestClient

from minidash.app import create_app


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def client(db_path):
    with TestClient(create_app(db_path)) as c:
        yield c
