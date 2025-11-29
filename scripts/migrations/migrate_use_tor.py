import sqlite3
import os

DB_FILE = 'data/auto_voter.db'

def migrate_db():
    if not os.path.exists(DB_FILE):
        print(f"Database file {DB_FILE} not found.")
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        # Check if use_tor exists in polls
        cursor.execute("PRAGMA table_info(polls)")
        columns = [info[1] for info in cursor.fetchall()]
        if 'use_tor' not in columns:
            print("Adding use_tor to polls...")
            cursor.execute("ALTER TABLE polls ADD COLUMN use_tor INTEGER DEFAULT 0")
        else:
            print("use_tor already exists in polls.")

        # Check if use_tor exists in queue_items
        cursor.execute("PRAGMA table_info(queue_items)")
        columns = [info[1] for info in cursor.fetchall()]
        if 'use_tor' not in columns:
            print("Adding use_tor to queue_items...")
            cursor.execute("ALTER TABLE queue_items ADD COLUMN use_tor INTEGER DEFAULT 0")
        else:
            print("use_tor already exists in queue_items.")

        conn.commit()
        print("Migration complete.")
    except Exception as e:
        print(f"Migration failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_db()
