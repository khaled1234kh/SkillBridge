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
def auth_headers(client):
    def login(email, password="demo1234"):
        r = client.post("/api/login", json={"email": email, "password": password})
        return r.json()
    return login


@pytest.fixture()
def student_id(auth_headers):
    s = auth_headers("aisha@student.edu")
    return s["entity_id"]
