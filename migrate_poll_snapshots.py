from app.db import SessionLocal, engine
from app.models import Base
from sqlalchemy import text, inspect

def migrate():
    print("Migrating poll snapshot enhancements...")
    
    # Create new tables (poll_snapshots)
    Base.metadata.create_all(bind=engine)
    
    # Check if Poll table needs column updates
    inspector = inspect(engine)
    columns = [c['name'] for c in inspector.get_columns('polls')]
    
    with engine.connect() as conn:
        if 'status' not in columns:
            print("Adding status to polls table")
            conn.execute(text("ALTER TABLE polls ADD COLUMN status VARCHAR(20) DEFAULT 'active'"))
        
        if 'poll_title' not in columns:
            print("Adding poll_title to polls table")
            conn.execute(text("ALTER TABLE polls ADD COLUMN poll_title VARCHAR(512)"))
            
        if 'total_poll_votes' not in columns:
            print("Adding total_poll_votes to polls table")
            conn.execute(text("ALTER TABLE polls ADD COLUMN total_poll_votes INTEGER DEFAULT 0"))
            
        conn.commit()
            
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
