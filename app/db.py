from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# Database file path (mounted volume or local file)
DB_PATH = os.environ.get('AUTO_VOTER_DB', 'sqlite:///./data/auto_voter.db')

engine = create_engine(DB_PATH, connect_args={"check_same_thread": False})
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
