"""Standalone scheduler service to run the queue runner and poll results scheduler.
Run this in a separate process (supervisord/systemd or a separate container) to avoid duplicate scheduler runs.
"""
import os
import time
from apscheduler.schedulers.blocking import BlockingScheduler
from app.db import SessionLocal
from app.models import QueueItem, QueueStatus, PollSchedulerConfig
from app.worker import start_queue_item_background


def pick_and_start():
    """Pick and start queued voting items."""
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


def run_poll_results_scheduler():
    """Run poll results capture for all polls if enabled and interval has elapsed."""
    from app.vote_results_influx_scheduler import run_all_polls
    from datetime import datetime, timedelta
    
    db = SessionLocal()
    try:
        config = db.query(PollSchedulerConfig).first()
        if not config:
            # Create default config if it doesn't exist
            config = PollSchedulerConfig(enabled=0, interval_minutes=15)
            db.add(config)
            db.commit()
            print(f"[Poll Scheduler] Created default config (disabled)")
            return
        
        if not config.enabled:
            return
        
        # Check if enough time has elapsed since last run
        now = datetime.utcnow()
        if config.last_run_at:
            next_run = config.last_run_at + timedelta(minutes=config.interval_minutes)
            if now < next_run:
                # Not time yet
                return
        
        print(f"[Poll Scheduler] Running poll results capture...")
        run_all_polls(db_session=db)
        
        # Update last run time
        config.last_run_at = now
        db.commit()
        print(f"[Poll Scheduler] Completed at {now.strftime('%Y-%m-%d %H:%M:%S')}")
        
    except Exception as e:
        print(f"[Poll Scheduler] Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


def main():
    queue_interval = int(os.environ.get('AUTO_VOTER_SCHEDULE_INTERVAL', '30'))
    
    sched = BlockingScheduler()
    
    # Add queue item scheduler
    sched.add_job(pick_and_start, 'interval', seconds=queue_interval)
    print(f"Queue scheduler started, interval={queue_interval}s")
    
    # Add poll results scheduler (checks config for interval)
    # Run every minute and let the function check if it should actually run
    sched.add_job(run_poll_results_scheduler, 'interval', minutes=1)
    print(f"Poll results scheduler started, checks every 1 minute")
    
    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == '__main__':
    main()
