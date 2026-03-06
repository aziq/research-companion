import sqlite3
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent / "research.db"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init():
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id        INTEGER PRIMARY KEY,
                url       TEXT,
                analysis  TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Migrate existing DBs that predate the created_at column
        try:
            conn.execute("ALTER TABLE items ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP")
        except sqlite3.OperationalError:
            pass  # Column already exists


_init()


def save_item(url: str, analysis: str) -> None:
    with _get_conn() as conn:
        conn.execute("INSERT INTO items (url, analysis) VALUES (?, ?)", (url, analysis))


def get_all_items() -> list[sqlite3.Row]:
    with _get_conn() as conn:
        return conn.execute(
            "SELECT id, url, analysis, created_at FROM items ORDER BY id DESC"
        ).fetchall()


def get_item(item_id: int) -> Optional[sqlite3.Row]:
    with _get_conn() as conn:
        return conn.execute(
            "SELECT id, url, analysis, created_at FROM items WHERE id = ?", (item_id,)
        ).fetchone()


def search_items(query: str) -> list[sqlite3.Row]:
    pattern = f"%{query}%"
    with _get_conn() as conn:
        return conn.execute(
            "SELECT id, url, analysis, created_at FROM items "
            "WHERE url LIKE ? OR analysis LIKE ? ORDER BY id DESC",
            (pattern, pattern),
        ).fetchall()


def delete_item(item_id: int) -> None:
    with _get_conn() as conn:
        conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
