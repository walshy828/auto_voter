from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# Database file path (mounted volume or local file)
DB_PATH = os.environ.get('AUTO_VOTER_DB', 'sqlite:///./data/auto_voter.db')

# Optimize SQLite for reduced disk I/O
# - WAL mode: Write-Ahead Logging for better concurrency and fewer disk syncs
# - synchronous=NORMAL: Reduce fsync calls while maintaining crash safety
# - cache_size: Larger cache to reduce disk reads
# - pool_pre_ping: Check connections before use to avoid stale connections
engine = create_engine(
    DB_PATH, 
    connect_args={
        "check_same_thread": False,
        "timeout": 30  # Increase timeout for busy database
    },
    pool_pre_ping=True,
    pool_recycle=3600,  # Recycle connections after 1 hour
    echo=False  # Disable SQL logging to reduce overhead
)

# Enable SQLite optimizations on connect
from sqlalchemy import event

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    # Enable WAL mode for better concurrency
    cursor.execute("PRAGMA journal_mode=WAL")
    # Reduce sync frequency (NORMAL is safe for most cases)
    cursor.execute("PRAGMA synchronous=NORMAL")
    # Increase cache size (negative = KB, so -64000 = 64MB)
    cursor.execute("PRAGMA cache_size=-64000")
    # Set temp store to memory
    cursor.execute("PRAGMA temp_store=MEMORY")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def init_db():
    # create folders if needed
    try:
        os.makedirs(os.path.dirname(DB_PATH.replace('sqlite:///', '')), exist_ok=True)
    except Exception:
        pass
    Base.metadata.create_all(bind=engine)
    ensure_admin_user()

# Create default admin user if none exists
def ensure_admin_user():
    from app.models import User
    import os
    
    db = SessionLocal()
    try:
        # Check if any users exist
        user_count = db.query(User).count()
        if user_count == 0:
            # Create default admin user from env or use defaults
            default_username = os.environ.get('ADMIN_USER', 'admin')
            default_password = os.environ.get('ADMIN_PASS', 'test')
            
            admin = User(username=default_username)
            admin.set_password(default_password)
            db.add(admin)
            db.commit()
            print(f"Created default admin user: {default_username}")
    finally:
        db.close()
