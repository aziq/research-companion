#!/usr/bin/env python3
"""
Knowledge base CLI.

Usage:
    python kb.py                    # list all items
    python kb.py <id>               # show full item (analysis + original content)
    python kb.py search <q>         # search across source, content, analysis
    python kb.py delete <id>        # delete an item
"""

import sys

from bot.db import get_all_items, get_item, search_items, delete_item

WIDTH = 80

_TYPE_ICONS = {
    "url": "🔗", "note": "📝", "voice_memo": "🎙", "audio": "🎵",
    "video": "🎬", "photo": "📷", "document": "📄", "unknown": "❓",
}


def cmd_list():
    rows = get_all_items()
    if not rows:
        print("No items in knowledge base yet.")
        return
    print(f"\n{'ID':>4}  {'TYPE':<12}  {'DATE':<16}  {'NOTE':<20}  SOURCE")
    print("-" * WIDTH)
    for r in rows:
        icon = _TYPE_ICONS.get(r["source_type"], "")
        stype = f"{icon} {r['source_type']}"
        date = (r["created_at"] or "")[:16]
        note = (r["user_note"] or " - NA - ")[:20]
        source = (r["source"] or "")[:WIDTH - 56] or "-"
        print(f"{r['id']:>4}  {stype:<12} {date:<16}  {note:<20}  {source}")
    print(f"\n{len(rows)} item(s). Run `python kb.py <id>` to read one.")


def cmd_show(item_id: int):
    row = get_item(item_id)
    if not row:
        print(f"No item with id {item_id}.")
        return
    icon = _TYPE_ICONS.get(row["source_type"], "")
    print(f"\n{'─' * WIDTH}")
    print(f"  #{row['id']}  {icon} {row['source_type']}  {row['source'] or ''}")
    print(f"  {row['created_at']}")
    if row["user_note"]:
        print(f"  Context: {row['user_note']}")
    print(f"{'─' * WIDTH}")

    if row["content"]:
        print(f"\n--- Original Content ({len(row['content'])} chars) ---")
        preview = row["content"][:500]
        print(preview)
        if len(row["content"]) > 500:
            print(f"  ... ({len(row['content']) - 500} more chars)")

    print(f"\n--- Analysis ---")
    print(row["analysis"] or "(no analysis)")
    print()


def cmd_search(query: str):
    rows = search_items(query)
    if not rows:
        print(f"No results for '{query}'.")
        return
    print(f"\n{len(rows)} match(es) for '{query}':\n")
    for r in rows:
        icon = _TYPE_ICONS.get(r["source_type"], "")
        date = (r["created_at"] or "")[:16]
        print(f"  #{r['id']:>4}  {icon} {r['source_type']:<10}  {date}  {(r['source'] or '')[:WIDTH - 40]}")
        # Show snippet from whichever field matched
        for field in ("source", "content", "analysis", "user_note"):
            text = r[field] or ""
            idx = text.lower().find(query.lower())
            if idx >= 0:
                start = max(0, idx - 60)
                snippet = text[start: idx + 120].replace("\n", " ")
                print(f"          ...{snippet}...")
                break
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
