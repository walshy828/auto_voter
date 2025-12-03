#!/usr/bin/env python3
"""
Database migration script to add scheduled_at field to queue_items table.
Run this script to update an existing database with the new column.

Usage:
    python migrate_add_scheduled_at.py
"""

import os
import sys
from sqlalchemy import create_engine, text, inspect

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def migrate():
    """Add scheduled_at field to queue_items table if it doesn't exist."""
    
    # Get database path from environment or use default
    db_path = os.environ.get('AUTO_VOTER_DB', 'sqlite:///./data/auto_voter.db')
    
    print(f"Connecting to database: {db_path}")
    engine = create_engine(db_path, connect_args={"check_same_thread": False})
    
    # Check if column already exists
    inspector = inspect(engine)
    existing_columns = [col['name'] for col in inspector.get_columns('queue_items')]
    
    with engine.connect() as conn:
        if 'scheduled_at' not in existing_columns:
            print("Adding column: scheduled_at")
            conn.execute(text("ALTER TABLE queue_items ADD COLUMN scheduled_at DATETIME"))
            conn.commit()
        else:
            print("Column scheduled_at already exists, skipping")
    
    print("Migration completed successfully!")
    print("\nNew column added:")
    print("  - scheduled_at: When to start this job (for scheduled jobs)")

if __name__ == '__main__':
    try:
        migrate()
    except Exception as e:
        print(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
