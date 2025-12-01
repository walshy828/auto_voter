"""Standalone scheduler service to run the queue runner and poll results scheduler.
Run this in a separate process (supervisord/systemd or a separate container) to avoid duplicate scheduler runs.
"""
import os
import time
from apscheduler.schedulers.blocking import BlockingScheduler
from app.db import SessionLocal, init_db
from app.models import QueueItem, QueueStatus, PollSchedulerConfig
from app.worker import start_queue_item_background

# Initialize database tables if they don't exist
print("[Scheduler Service] Initializing database...")
init_db()
print("[Scheduler Service] Database initialized")


def pick_and_start():
    """Pick and start queued voting items."""
    print("[Scheduler Service] pick_and_start() called")
    db = SessionLocal()
    try:
        # Check if workers are paused
        from app.models import SystemSetting
        paused_setting = db.query(SystemSetting).filter(SystemSetting.key == 'workers_paused').first()
        if paused_setting and paused_setting.value == 'true':
            # Workers are paused, skip processing
            print("[Scheduler Service] Workers are paused, skipping queue processing")
            return
        
        print("[Scheduler Service] Checking for queued items...")
        it = db.query(QueueItem).filter(QueueItem.status == QueueStatus.queued).order_by(QueueItem.created_at.asc()).first()
        if it:
            print(f"[Scheduler Service] Found queued item {it.id}, attempting to start...")
            try:
                start_queue_item_background(it.id)
                print(f"[Scheduler Service] Successfully started item {it.id}")
            except Exception as e:
                print(f"[Scheduler Service] Failed to start queued item {it.id}: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("[Scheduler Service] No queued items found")
    except Exception as e:
        print(f"[Scheduler Service] Error in pick_and_start: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


def run_poll_results_scheduler():
    """Run poll results capture for all polls if enabled and interval has elapsed."""
    from app.vote_results_influx_scheduler import run_all_polls
    from datetime import datetime, timedelta, timezone
    
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
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if config.last_run:
            next_run = config.last_run + timedelta(minutes=config.interval_minutes)
            if now < next_run:
                # Not time yet
                return
        
        print(f"[Poll Scheduler] Running poll results capture...")
        run_all_polls(db_session=db)
        
        # Update last run time
        config.last_run = now
        db.commit()
        print(f"[Poll Scheduler] Completed at {now.strftime('%Y-%m-%d %H:%M:%S')}")
        
    except Exception as e:
        print(f"[Poll Scheduler] Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


# Global variable to track current interval
current_queue_interval = 30


def manage_scheduler_config(scheduler):
    """Check DB for scheduler interval changes and update job if needed."""
    global current_queue_interval
    from app.models import SystemSetting
    
    db = SessionLocal()
    try:
        setting = db.query(SystemSetting).filter(SystemSetting.key == 'scheduler_interval').first()
        if setting and setting.value:
            new_interval = int(setting.value)
            if new_interval != current_queue_interval:
                print(f"[Scheduler Manager] Interval changed from {current_queue_interval}s to {new_interval}s. Rescheduling.")
                scheduler.reschedule_job('queue_runner', trigger='interval', seconds=new_interval)
                current_queue_interval = new_interval
    except Exception as e:
        print(f"[Scheduler Manager] Error: {e}")
    finally:
        db.close()


def check_auto_switch_to_lazy(scheduler):
    """Check if system is idle and switch to Lazy Mode if enabled."""
    from app.models import SystemSetting, PollSchedulerConfig, Poll, QueueItem, QueueStatus
    
    db = SessionLocal()
    try:
        # 1. Check if auto-switch is enabled
        setting = db.query(SystemSetting).filter(SystemSetting.key == 'auto_switch_to_lazy').first()
        if not setting or setting.value != 'true':
            return

        # 2. Check for active queue items
        active_items = db.query(QueueItem).filter(
            QueueItem.status.in_([QueueStatus.queued, QueueStatus.running])
        ).count()
        
        if active_items > 0:
            return # Not idle

        # 3. Check for active polls
        active_polls = db.query(Poll).filter(Poll.status == 'active').count()
        if active_polls > 0:
            return # Not idle
            
        # 4. Switch to Lazy Mode
        # Lazy Mode: Scheduler 3600s, Poll Results 60m
        
        # Update Scheduler Interval
        setting_sched = db.query(SystemSetting).filter(SystemSetting.key == 'scheduler_interval').first()
        if not setting_sched:
            setting_sched = SystemSetting(key='scheduler_interval')
            db.add(setting_sched)
            
        current_sched_val = int(setting_sched.value) if setting_sched.value else 0
        
        # Only switch if not already in Lazy mode (approx > 50 mins)
        if current_sched_val < 3000:
            print("[Auto-Switch] System is idle (no active polls/queue). Switching to Lazy Mode 🦥")
            setting_sched.value = '3600'
            
            # Update Poll Results Interval
            poll_config = db.query(PollSchedulerConfig).first()
            if not poll_config:
                poll_config = PollSchedulerConfig()
                db.add(poll_config)
            poll_config.interval_minutes = 60
            
            db.commit()
            
            # Force immediate config update
            manage_scheduler_config(scheduler)
            
    except Exception as e:
        print(f"[Auto-Switch] Error: {e}")
    finally:
        db.close()


def check_and_disconnect_idle_vpn():
    """Disconnect VPN if system has been idle (no running/queued jobs) to save CPU."""
    from app.models import QueueItem, QueueStatus
    
    db = SessionLocal()
    try:
        # Check if there are any running or queued items
        active_count = db.query(QueueItem).filter(
            QueueItem.status.in_([QueueStatus.queued, QueueStatus.running])
        ).count()
        
        if active_count == 0:
            # No active jobs, disconnect VPN to save CPU
            print("[VPN Idle Check] No active jobs, disconnecting VPN to save CPU...")
            try:
                import subprocess
                # Check if expressvpn command exists
                try:
                    subprocess.run(['which', 'expressvpn'], capture_output=True, timeout=2, check=True)
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                    print("[VPN Idle Check] ExpressVPN not found, skipping")
                    return
                
                # Check if connected first
                result = subprocess.run(['expressvpn', 'status'], 
                                      capture_output=True, text=True, timeout=3)
                if 'Connected' in result.stdout:
                    # Extract location for logging
                    location = "Unknown"
                    for line in result.stdout.split('\n'):
                        if 'Connected to' in line:
                            location = line.split('Connected to')[-1].strip()
                            break
                    print(f"[VPN Idle Check] Disconnecting from {location}...")
                    subprocess.run(['expressvpn', 'disconnect'], 
                                 capture_output=True, timeout=5)
                    print("[VPN Idle Check] ✓ VPN disconnected successfully")
                else:
                    print("[VPN Idle Check] VPN already disconnected")
            except subprocess.TimeoutExpired:
                print("[VPN Idle Check] VPN command timed out")
            except Exception as e:
                print(f"[VPN Idle Check] Error disconnecting VPN: {e}")
        else:
            print(f"[VPN Idle Check] {active_count} active job(s), keeping VPN connected")
    except Exception as e:
        print(f"[VPN Idle Check] Error checking jobs: {e}")
    finally:
        db.close()


def main():
    global current_queue_interval
    print("[Scheduler Service] Starting main()...")
    
    try:
        current_queue_interval = int(os.environ.get('AUTO_VOTER_SCHEDULE_INTERVAL', '30'))
        print(f"[Scheduler Service] Interval set to {current_queue_interval}s")
        
        sched = BlockingScheduler()
        print("[Scheduler Service] BlockingScheduler created")
        
        # Add queue item scheduler
        sched.add_job(pick_and_start, 'interval', seconds=current_queue_interval, id='queue_runner')
        print(f"[Scheduler Service] Queue scheduler started, interval={current_queue_interval}s")
        
        # Add poll results scheduler (checks config for interval)
        # Run every minute and let the function check if it should actually run
        sched.add_job(run_poll_results_scheduler, 'interval', minutes=1, id='poll_results_runner')
        print(f"[Scheduler Service] Poll results scheduler started, checks every 1 minute")
        
        # Add config manager (checks every 30s)
        sched.add_job(manage_scheduler_config, 'interval', seconds=30, args=[sched], id='config_manager')
        print("[Scheduler Service] Config manager added")
        
        # Add auto-switch checker (checks every 5 minutes)
        sched.add_job(check_auto_switch_to_lazy, 'interval', minutes=5, args=[sched], id='auto_switch_checker')
        print("[Scheduler Service] Auto-switch checker added")
        
        # Add VPN idle checker (checks every 5 minutes to disconnect when idle)
        sched.add_job(check_and_disconnect_idle_vpn, 'interval', minutes=5, id='vpn_idle_checker')
        print("[Scheduler Service] VPN idle checker added (5 min interval)")
        
        print("[Scheduler Service] Starting scheduler loop...")
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        print("[Scheduler Service] Received shutdown signal")
        pass
    except Exception as e:
        print(f"[Scheduler Service] FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == '__main__':
    print("[Scheduler Service] __main__ block executing...")
    main()

