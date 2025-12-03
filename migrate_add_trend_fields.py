#!/usr/bin/env python3
"""
Database migration script to add trend tracking fields to polls table.
Run this script to update an existing database with the new columns.

Usage:
    python migrate_add_trend_fields.py
"""

import os
import sys
from sqlalchemy import create_engine, text, inspect

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def migrate():
    """Add trend tracking fields to polls table if they don't exist."""
    
    # Get database path from environment or use default
    db_path = os.environ.get('AUTO_VOTER_DB', 'sqlite:///./data/auto_voter.db')
    
    print(f"Connecting to database: {db_path}")
    engine = create_engine(db_path, connect_args={"check_same_thread": False})
    
    # Check if columns already exist
    inspector = inspect(engine)
    existing_columns = [col['name'] for col in inspector.get_columns('polls')]
    
    columns_to_add = {
        'previous_place': 'INTEGER',
        'place_trend': 'VARCHAR(10)',
        'votes_ahead_second': 'INTEGER'
    }
    
    with engine.connect() as conn:
        for column_name, column_type in columns_to_add.items():
            if column_name not in existing_columns:
                print(f"Adding column: {column_name}")
                conn.execute(text(f"ALTER TABLE polls ADD COLUMN {column_name} {column_type}"))
                conn.commit()
            else:
                print(f"Column {column_name} already exists, skipping")
    
    print("Migration completed successfully!")
    print("\nNew columns added:")
    print("  - previous_place: Stores last known placement for trend comparison")
    print("  - place_trend: Caches trend direction (up/down/same/new)")
    print("  - votes_ahead_second: For 1st place, shows lead over 2nd place")

if __name__ == '__main__':
    try:
        migrate()
    except Exception as e:
        print(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
