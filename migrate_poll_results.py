from app.db import SessionLocal, engine
from app.models import Base, Poll
from sqlalchemy import text, inspect

def migrate():
    print("Migrating poll results tables...")
    
    # Create new tables
    Base.metadata.create_all(bind=engine)
    
    # Check if Poll table needs column updates
    inspector = inspect(engine)
    columns = [c['name'] for c in inspector.get_columns('polls')]
    
    with engine.connect() as conn:
        if 'total_votes' not in columns:
            print("Adding total_votes to polls table")
            conn.execute(text("ALTER TABLE polls ADD COLUMN total_votes INTEGER DEFAULT 0"))
        
        if 'current_place' not in columns:
            print("Adding current_place to polls table")
            conn.execute(text("ALTER TABLE polls ADD COLUMN current_place INTEGER"))
            
        if 'votes_behind_first' not in columns:
            print("Adding votes_behind_first to polls table")
            conn.execute(text("ALTER TABLE polls ADD COLUMN votes_behind_first INTEGER"))
            
        if 'last_snapshot_at' not in columns:
            print("Adding last_snapshot_at to polls table")
            conn.execute(text("ALTER TABLE polls ADD COLUMN last_snapshot_at DATETIME"))
            
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
