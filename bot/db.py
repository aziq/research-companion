import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "research.db"

_CREATE_SQL = """\
CREATE TABLE IF NOT EXISTS items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL DEFAULT 'unknown',
    source      TEXT NOT NULL DEFAULT '',
    content     TEXT NOT NULL DEFAULT '',
    analysis    TEXT NOT NULL DEFAULT '',
    user_note   TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
)"""


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init():
    with _get_conn() as conn:
        info = conn.execute("PRAGMA table_info(items)").fetchall()
        cols = {row["name"] for row in info}

        if not cols:
            conn.execute(_CREATE_SQL)
            return

        if "source_type" in cols:
            return  # already on new schema

        # Migrate from old schema (id, url, analysis, maybe created_at)
        has_created_at = "created_at" in cols
        conn.execute("ALTER TABLE items RENAME TO _items_old")
        conn.execute(_CREATE_SQL)
        ts_col = (
            "COALESCE(created_at, strftime('%Y-%m-%dT%H:%M:%S', 'now'))"
            if has_created_at
            else "strftime('%Y-%m-%dT%H:%M:%S', 'now')"
        )
        conn.execute(
            f"INSERT INTO items (id, source, analysis, created_at) "
            f"SELECT id, COALESCE(url, ''), COALESCE(analysis, ''), {ts_col} "
            f"FROM _items_old"
        )
        conn.execute("DROP TABLE _items_old")


_init()


def save_item(
    source_type: str,
    source: str,
    content: str,
    analysis: str,
    user_note: str = "",
) -> None:
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO items (source_type, source, content, analysis, user_note) "
            "VALUES (?, ?, ?, ?, ?)",
            (source_type, source, content, analysis, user_note),
        )


def get_all_items() -> list[sqlite3.Row]:
    with _get_conn() as conn:
        return conn.execute(
            "SELECT id, source_type, source, content, analysis, user_note, created_at "
            "FROM items ORDER BY id DESC"
        ).fetchall()


def get_item(item_id: int) -> sqlite3.Row | None:
    with _get_conn() as conn:
        return conn.execute(
            "SELECT id, source_type, source, content, analysis, user_note, created_at "
            "FROM items WHERE id = ?",
            (item_id,),
        ).fetchone()


def search_items(query: str) -> list[sqlite3.Row]:
    pattern = f"%{query}%"
    with _get_conn() as conn:
        return conn.execute(
            "SELECT id, source_type, source, content, analysis, user_note, created_at "
            "FROM items "
            "WHERE source LIKE ? OR content LIKE ? OR analysis LIKE ? OR user_note LIKE ? "
            "ORDER BY id DESC",
            (pattern, pattern, pattern, pattern),
        ).fetchall()


def delete_item(item_id: int) -> None:
    with _get_conn() as conn:
        conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
