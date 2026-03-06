#!/usr/bin/env python3
"""
Knowledge base CLI.

Usage:
    python kb.py              # list all items (id + source + date)
    python kb.py <id>         # show full analysis for item
    python kb.py search <q>   # search source + analysis
    python kb.py delete <id>  # delete an item
"""

import sys

from bot.db import get_all_items, get_item, search_items, delete_item

WIDTH = 80


def cmd_list():
    rows = get_all_items()
    if not rows:
        print("No items in knowledge base yet.")
        return
    print(f"\n{'ID':>4}  {'DATE':<20}  SOURCE")
    print("-" * WIDTH)
    for r in rows:
        date = (r["created_at"] or "")[:16]
        source = (r["url"] or "")[:WIDTH - 30]
        print(f"{r['id']:>4}  {date:<20}  {source}")
    print(f"\n{len(rows)} item(s). Run `python kb.py <id>` to read one.")


def cmd_show(item_id: int):
    row = get_item(item_id)
    if not row:
        print(f"No item with id {item_id}.")
        return
    print(f"\n{'─' * WIDTH}")
    print(f"  #{row['id']}  {row['url']}")
    print(f"  {row['created_at']}")
    print(f"{'─' * WIDTH}\n")
    print(row["analysis"] or "")
    print()


def cmd_search(query: str):
    rows = search_items(query)
    if not rows:
        print(f"No results for '{query}'.")
        return
    print(f"\n{len(rows)} match(es) for '{query}':\n")
    for r in rows:
        date = (r["created_at"] or "")[:16]
        print(f"  #{r['id']:>4}  {date}  {(r['url'] or '')[:WIDTH - 30]}")
        analysis = r["analysis"] or ""
        idx = analysis.lower().find(query.lower())
        if idx >= 0:
            start = max(0, idx - 60)
            snippet = analysis[start: idx + 120].replace("\n", " ")
            print(f"          ...{snippet}...")
        print()


def cmd_delete(item_id: int):
    delete_item(item_id)
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
