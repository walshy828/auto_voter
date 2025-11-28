"""Standalone scheduler service to run the queue runner outside the web workers.
Run this in a separate process (supervisord/systemd or a separate container) to avoid duplicate scheduler runs.
"""
import os
import time
from apscheduler.schedulers.blocking import BlockingScheduler
from app.db import SessionLocal
from app.models import QueueItem, QueueStatus
from app.worker import start_queue_item_background


def pick_and_start():
    db = SessionLocal()
    try:
        it = db.query(QueueItem).filter(QueueItem.status == QueueStatus.queued).order_by(QueueItem.created_at.asc()).first()
        if it:
            try:
                start_queue_item_background(it.id)
            except Exception as e:
                print(f"Failed to start queued item {it.id}: {e}")
    finally:
        db.close()


def main():
    interval = int(os.environ.get('AUTO_VOTER_SCHEDULE_INTERVAL', '30'))
    sched = BlockingScheduler()
    sched.add_job(pick_and_start, 'interval', seconds=interval)
    print(f"Scheduler service started, interval={interval}s")
    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == '__main__':
    main()
