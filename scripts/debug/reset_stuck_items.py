import datetime
from app.db import SessionLocal
from app.models import QueueItem, QueueStatus, WorkerProcess

db = SessionLocal()
items = db.query(QueueItem).filter(QueueItem.id.in_([1, 4])).all()
for it in items:
    print(f"Resetting item {it.id}...")
    it.status = QueueStatus.canceled
    it.completed_at = datetime.datetime.utcnow()
    it.result_msg = "Manually reset"
    
    if it.worker_id:
        wp = db.query(WorkerProcess).filter(WorkerProcess.id == it.worker_id).first()
        if wp:
            wp.end_time = datetime.datetime.utcnow()
            wp.exit_code = -1
            wp.result_msg = "Manually reset"

db.commit()
db.close()
print("Done.")
