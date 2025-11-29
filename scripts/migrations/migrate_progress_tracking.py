import sqlite3
import os

DB_FILE = 'data/auto_voter.db'

def migrate():
    if not os.path.exists(DB_FILE):
        print(f"Database file {DB_FILE} does not exist. Please run the app first to create it.")
        return
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Check if columns already exist
    cursor.execute("PRAGMA table_info(queue_items)")
    columns = [col[1] for col in cursor.fetchall()]
    
    changes_made = False
    
    # Add votes_cast column
    if 'votes_cast' not in columns:
        cursor.execute("ALTER TABLE queue_items ADD COLUMN votes_cast INTEGER DEFAULT 0")
        print("Added 'votes_cast' column")
        changes_made = True
    
    # Add votes_success column
    if 'votes_success' not in columns:
        cursor.execute("ALTER TABLE queue_items ADD COLUMN votes_success INTEGER DEFAULT 0")
        print("Added 'votes_success' column")
        changes_made = True
    
    # Add success_rate column
    if 'success_rate' not in columns:
        cursor.execute("ALTER TABLE queue_items ADD COLUMN success_rate REAL DEFAULT 0.0")
        print("Added 'success_rate' column")
        changes_made = True
    
    # Add current_status column
    if 'current_status' not in columns:
        cursor.execute("ALTER TABLE queue_items ADD COLUMN current_status VARCHAR(100)")
        print("Added 'current_status' column")
        changes_made = True
    
    # Add last_update column
    if 'last_update' not in columns:
        cursor.execute("ALTER TABLE queue_items ADD COLUMN last_update DATETIME")
        print("Added 'last_update' column")
        changes_made = True
    
    if changes_made:
        conn.commit()
        print("\nMigration complete: Added progress tracking fields to queue_items table.")
    else:
        print("All progress tracking columns already exist. No migration needed.")
    
    conn.close()

if __name__ == '__main__':
    migrate()
