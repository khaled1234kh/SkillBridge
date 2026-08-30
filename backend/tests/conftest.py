import sqlite3

import pytest

from app import database, seed

# Use a shared in-memory SQLite connection for all tests so each test starts
# from freshly seeded data and nothing persists across tests.


@pytest.fixture()
def db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    database.set_db_for_test(conn)
    seed.seed()
    yield conn
    database.set_db_for_test()
    conn.close()


@pytest.fixture()
def client(db):
    from fastapi.testclient import TestClient
    from app import main
    with TestClient(main.app) as c:
        yield c


@pytest.fixture()
def login(client):
    def do(email, password="demo1234"):
        r = client.post("/api/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, r.text
        return r.json()
    return do


@pytest.fixture()
def auth_headers(login):
    def h(email, password="demo1234"):
        payload = login(email, password)
        return {"Authorization": f"Bearer {payload['token']}"}
    return h


@pytest.fixture()
def student_payload(login):
    return login("aisha@student.edu")


@pytest.fixture()
def student_id(student_payload):
    return student_payload["student"]["id"]