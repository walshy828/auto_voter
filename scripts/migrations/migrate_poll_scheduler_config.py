import sqlite3
import os

DB_FILE = 'data/auto_voter.db'

def migrate():
    if not os.path.exists(DB_FILE):
        print(f"Database file {DB_FILE} does not exist. Please run the app first to create it.")
        return
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Check if table already exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='poll_scheduler_config'")
    if cursor.fetchone():
        print("Table 'poll_scheduler_config' already exists. Skipping migration.")
        conn.close()
        return
    
    # Create the table
    cursor.execute("""
        CREATE TABLE poll_scheduler_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            enabled INTEGER DEFAULT 0,
            interval_minutes INTEGER DEFAULT 15,
            last_run DATETIME
        )
    """)
    
    # Insert default config
    cursor.execute("""
        INSERT INTO poll_scheduler_config (enabled, interval_minutes)
        VALUES (0, 15)
    """)
    
    conn.commit()
    conn.close()
    print("Migration complete: Created 'poll_scheduler_config' table with default config.")

if __name__ == '__main__':
    migrate()
