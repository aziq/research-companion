import sqlite3

conn = sqlite3.connect("research.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY,
    url TEXT,
    analysis TEXT
)
""")

conn.commit()

def save_item(url, analysis):
    cur.execute(
        "INSERT INTO items (url, analysis) VALUES (?, ?)",
        (url, analysis)
    )
    conn.commit()

def get_items():
    cur.execute("SELECT url, analysis FROM items")
    return cur.fetchall()