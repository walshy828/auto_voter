from app.db import SessionLocal, engine
from app.models import Base, SystemSetting
from sqlalchemy import text

def migrate():
    print("Migrating system_settings table...")
    
    # Create table if not exists
    Base.metadata.create_all(bind=engine)
    
    # Initialize default max_concurrent_workers if not present
    db = SessionLocal()
    try:
        setting = db.query(SystemSetting).filter(SystemSetting.key == 'max_concurrent_workers').first()
        if not setting:
            print("Initializing max_concurrent_workers to 1")
            setting = SystemSetting(key='max_concurrent_workers', value='1')
            db.add(setting)
            db.commit()
        else:
            print(f"max_concurrent_workers already set to {setting.value}")
    except Exception as e:
        print(f"Error initializing settings: {e}")
    finally:
        db.close()
    
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
