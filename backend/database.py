import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "timebalance.db"

DEFAULT_ACTIVITIES = [
    ("Trading", 180),  # limite quotidienne en minutes
    ("Études", None),
    ("Sport", None),
    ("Personnel", None),
    ("Repos", None),
]


def get_db():
    """Dépendance FastAPI : une connexion SQLite par requête."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            daily_limit_minutes INTEGER
        );
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL REFERENCES activities(id),
            day TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS time_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL REFERENCES activities(id),
            start_at TEXT NOT NULL,
            end_at TEXT
        );
        """
    )
    if conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0] == 0:
        conn.executemany(
            "INSERT INTO activities (name, daily_limit_minutes) VALUES (?, ?)",
            DEFAULT_ACTIVITIES,
        )
    conn.commit()
    conn.close()