#!/usr/bin/env python3
"""
Knowledge base CLI.

Usage:
    python kb.py              # list all items (id + source)
    python kb.py <id>         # show full analysis for item
    python kb.py search <q>   # search source + analysis
    python kb.py delete <id>  # delete an item
"""

import sqlite3
import sys

DB_PATH = "research.db"
WIDTH = 80


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def cmd_list():
    with get_conn() as conn:
        rows = conn.execute("SELECT id, url FROM items ORDER BY id DESC").fetchall()
    if not rows:
        print("No items in knowledge base yet.")
        return
    print(f"\n{'ID':>4}  SOURCE")
    print("-" * WIDTH)
    for r in rows:
        source = (r["url"] or "")[:WIDTH - 8]
        print(f"{r['id']:>4}  {source}")
    print(f"\n{len(rows)} item(s). Run `python kb.py <id>` to read one.")


def cmd_show(item_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if not row:
        print(f"No item with id {item_id}.")
        return
    print(f"\n{'─' * WIDTH}")
    print(f"  #{row['id']}  {row['url']}")
    print(f"{'─' * WIDTH}\n")
    print(row["analysis"] or "")
    print()


def cmd_search(query: str):
    pattern = f"%{query}%"
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, url, analysis FROM items WHERE url LIKE ? OR analysis LIKE ? ORDER BY id DESC",
            (pattern, pattern),
        ).fetchall()
    if not rows:
        print(f"No results for '{query}'.")
        return
    print(f"\n{len(rows)} match(es) for '{query}':\n")
    for r in rows:
        print(f"  #{r['id']:>4}  {(r['url'] or '')[:WIDTH - 10]}")
        # Show the first matching snippet from analysis
        analysis = r["analysis"] or ""
        idx = analysis.lower().find(query.lower())
        if idx >= 0:
            start = max(0, idx - 60)
            snippet = analysis[start: idx + 120].replace("\n", " ")
            print(f"          ...{snippet}...")
        print()


def cmd_delete(item_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
    print(f"Deleted item #{item_id}.")


def main():
    args = sys.argv[1:]

    if not args:
        cmd_list()
    elif len(args) == 1 and args[0].isdigit():
        cmd_show(int(args[0]))
    elif len(args) == 2 and args[0] == "search":
        cmd_search(args[1])
    elif len(args) == 2 and args[0] == "delete" and args[1].isdigit():
        cmd_delete(int(args[1]))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
