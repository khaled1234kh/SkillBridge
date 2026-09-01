"""SQLite database setup and connection management.

Stores five record types: students, companies, roles, skills, assessment_attempts.
Uses Python's built-in sqlite3 module against a local file. A test override allows
in-memory databases for unit tests.
"""
import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.environ.get("SKILLBRIDGE_DB", os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skillbridge.db"
))

_override_conn = None
_file_conn = None


def set_db_for_test(conn=None):
    """Point the database layer at a custom connection (e.g. in-memory for tests)."""
    global _override_conn
    _override_conn = conn


def _connect():
    global _file_conn
    if _override_conn is not None:
        return _override_conn
    if _file_conn is None:
        _file_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _file_conn.row_factory = sqlite3.Row
        _file_conn.execute("PRAGMA foreign_keys = ON")
    return _file_conn


def get_connection():
    return _connect()


@contextmanager
def get_cursor():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    # The connection is module-scoped (shared across the app or a test override),
    # so it is never closed here.


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('Student','Company','University Admin')),
    display_name TEXT NOT NULL,
    password_hash TEXT,
    password_salt TEXT,
    auth_provider TEXT NOT NULL DEFAULT 'local',
    google_sub TEXT,
    verified INTEGER NOT NULL DEFAULT 0,
    country TEXT,
    university TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS password_resets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT UNIQUE NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL,
    used INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS google_registrations (
    google_sub TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS universities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country TEXT NOT NULL,
    name TEXT NOT NULL,
    UNIQUE(country, name)
);

CREATE TABLE IF NOT EXISTS email_verifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT UNIQUE NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL,
    used INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    university TEXT NOT NULL,
    target_role_id INTEGER REFERENCES roles(id) ON DELETE SET NULL,
    cv_filename TEXT,
    cohort_confirmed INTEGER NOT NULL DEFAULT 0,
    share_public INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    industry TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    category TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    is_reference INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS role_skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    skill_id INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    required_level TEXT NOT NULL CHECK(required_level IN ('Beginner','Intermediate','Advanced')),
    UNIQUE(role_id, skill_id)
);

CREATE TABLE IF NOT EXISTS self_reported_skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    skill_id INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    level TEXT NOT NULL CHECK(level IN ('Beginner','Intermediate','Advanced')),
    source TEXT NOT NULL DEFAULT 'cv',
    UNIQUE(student_id, skill_id)
);

CREATE TABLE IF NOT EXISTS verified_skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    skill_id INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    level TEXT NOT NULL CHECK(level IN ('Beginner','Intermediate','Advanced')),
    verified_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(student_id, skill_id)
);

CREATE TABLE IF NOT EXISTS learning_path_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    skill_id INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    explanation TEXT,
    practice_exercise TEXT,
    mini_project TEXT,
    resources TEXT,
    roadmap TEXT,
    progress TEXT,
    generated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(student_id, skill_id)
);

CREATE TABLE IF NOT EXISTS tutor_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    skill_id INTEGER REFERENCES skills(id) ON DELETE SET NULL,
    role TEXT NOT NULL CHECK(role IN ('user','assistant')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS assessment_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    skill_id INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    questions TEXT NOT NULL,
    answers TEXT NOT NULL,
    score REAL NOT NULL,
    passed INTEGER NOT NULL DEFAULT 0,
    flags TEXT NOT NULL DEFAULT '[]',
    per_question TEXT,
    level_before TEXT NOT NULL,
    level_after TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def _migrate():
    """Lightweight in-place migration so databases created before an iteration
    keep working: add any columns that the current schema introduced."""
    additions = [
        ("users", "password_hash", "TEXT"),
        ("users", "password_salt", "TEXT"),
        ("users", "auth_provider", "TEXT NOT NULL DEFAULT 'local'"),
        ("users", "google_sub", "TEXT"),
        ("users", "verified", "INTEGER NOT NULL DEFAULT 0"),
        ("users", "country", "TEXT"),
        ("users", "university", "TEXT"),
        ("students", "cohort_confirmed", "INTEGER NOT NULL DEFAULT 0"),
        ("students", "share_public", "INTEGER NOT NULL DEFAULT 0"),
        ("roles", "is_reference", "INTEGER NOT NULL DEFAULT 0"),
        ("learning_path_items", "resources", "TEXT"),
        ("learning_path_items", "roadmap", "TEXT"),
        ("learning_path_items", "progress", "TEXT"),
        ("assessment_attempts", "per_question", "TEXT"),
    ]
    conn = _connect()
    for table, column, ddl in additions:
        cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
    conn.commit()


def init_db():
    with get_cursor() as conn:
        conn.executescript(SCHEMA)
    _migrate()
