from app.db import SessionLocal
from app.models import QueueItem, WorkerProcess

db = SessionLocal()
items = db.query(QueueItem).filter(QueueItem.id.in_([1, 4])).all()
for it in items:
    print(f"Item {it.id}: status={it.status}, pid={it.pid}, worker_id={it.worker_id}")
    if it.worker_id:
        wp = db.query(WorkerProcess).filter(WorkerProcess.id == it.worker_id).first()
        if wp:
            print(f"  Worker {wp.id}: pid={wp.pid}, exit_code={wp.exit_code}, end_time={wp.end_time}")
db.close()
