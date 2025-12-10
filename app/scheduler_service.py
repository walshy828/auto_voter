"""Standalone scheduler service to run the queue runner and poll results scheduler.
Run this in a separate process (supervisord/systemd or a separate container) to avoid duplicate scheduler runs.
"""
import os
import time
import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from app.db import SessionLocal, init_db
from app.models import QueueItem, QueueStatus, PollSchedulerConfig
from app.utils.db_helpers import get_cached_bool_setting, get_cached_int_setting, invalidate_setting_cache
# Note: start_queue_item_background import deferred to pick_and_start() to speed up startup

# Initialize database tables if they don't exist
print("[Scheduler Service] Initializing database...")
init_db()
print("[Scheduler Service] Database initialized")

# Global lock to prevent concurrent pick_and_start executions
_pick_and_start_running = False



def ensure_vpn_connected():
    """Ensure VPN is connected. If not, attempt to connect up to 3 times."""
    import subprocess
    
    try:
        # Check if expressvpn command exists
        try:
            subprocess.run(['which', 'expressvpn'], capture_output=True, timeout=2, check=True)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            print("[VPN Check] ExpressVPN command not found. Cannot ensure VPN.")
            return False
        
        # Check if already connected
        result = subprocess.run(['expressvpn', 'status'], capture_output=True, text=True, timeout=3)
        if 'Connected' in result.stdout:
            return True
        
        # Kill any hung expressvpn processes before attempting to connect
        print("[VPN Check] Cleaning up any hung ExpressVPN processes...")
        try:
            # Find and kill any stuck 'expressvpn connect' processes
            ps_result = subprocess.run(['pgrep', '-f', 'expressvpn connect'], 
                                      capture_output=True, text=True, timeout=2)
            if ps_result.stdout.strip():
                pids = ps_result.stdout.strip().split('\n')
                for pid in pids:
                    if pid:
                        try:
                            print(f"[VPN Check] Killing hung process {pid}")
                            subprocess.run(['kill', '-9', pid], timeout=2)
                        except:
                            pass
                time.sleep(1)  # Give processes time to die
        except Exception as e:
            print(f"[VPN Check] Error cleaning up processes: {e}")
        
        print("[VPN Check] VPN not connected. Attempting to connect...")
        
        # Try to connect up to 3 times
        for attempt in range(3):
            try:
                print(f"[VPN Check] Connection attempt {attempt+1}/3...")
                result = subprocess.run(['expressvpn', 'connect'], 
                                      capture_output=True, text=True, timeout=30)
                
                # Check for "already connected" message in stderr/stdout
                if "Please disconnect first" in result.stderr or "Please disconnect first" in result.stdout:
                    print("[VPN Check] VPN was already connected (detected via error message).")
                    return True
                
                # Verify connection with retries
                # Sometimes status takes a moment to update after connect returns
                for status_try in range(3):
                    time.sleep(2)
                    verify = subprocess.run(['expressvpn', 'status'], 
                                          capture_output=True, text=True, timeout=3)
                    if 'Connected' in verify.stdout:
                        print(f"[VPN Check] Successfully connected (status check {status_try+1}).")
                        return True
                
                # If we get here, verification failed despite connect returning
                print(f"[VPN Check] Verification failed after connection attempt.")
                print(f"[VPN Check] Command output: {result.stdout}")
                print(f"[VPN Check] Command error: {result.stderr}")
                
                # Try explicit smart connect on last attempt
                if attempt == 2:
                    print("[VPN Check] Trying 'smart' location as fallback...")
                    subprocess.run(['expressvpn', 'connect', 'smart'], 
                                 capture_output=True, timeout=30)
            except subprocess.TimeoutExpired as e:
                print(f"[VPN Check] Attempt {attempt+1} failed with error: {e}")
                # Kill the timed-out process
                try:
                    subprocess.run(['pkill', '-9', '-f', 'expressvpn connect'], timeout=2)
                except:
                    pass
            except Exception as e: # Catch other exceptions during connection attempt
                print(f"[VPN Check] Attempt {attempt+1} failed with error: {e}")
                time.sleep(2)
        
        print(f"[VPN Check] Failed to connect after 3 attempts.")
        return False
    except Exception as e:
        print(f"[VPN Check] Error: {e}")
        return False


def pick_and_start():
    """Pick and start queued voting items with locking and max worker check."""
    # Use a simple in-process lock to prevent concurrent executions
    # This is more efficient than file locking for same-process calls
    global _pick_and_start_running
    
    if _pick_and_start_running:
        print("[Scheduler Service] pick_and_start already running, skipping this cycle")
        return
    
    _pick_and_start_running = True
    
    try:
        print(f"[Scheduler Service] pick_and_start() called at {datetime.datetime.now()}")
        db = SessionLocal()
        try:
            from app.models import SystemSetting
            
            # Update last run timestamp (less frequently to reduce writes)
            now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
            
            # Only update timestamp every 30 minutes to reduce DB writes
            last_run_setting = db.query(SystemSetting).filter(SystemSetting.key == 'scheduler_last_run').first()
            should_update_timestamp = False
            
            if not last_run_setting:
                last_run_setting = SystemSetting(key='scheduler_last_run', value=now.isoformat())
                db.add(last_run_setting)
                should_update_timestamp = True
            else:
                # Only update if more than 30 minutes have passed
                try:
                    last_run = datetime.datetime.fromisoformat(last_run_setting.value)
                    if (now - last_run).total_seconds() > 1800:  # 30 minutes
                        should_update_timestamp = True
                except:
                    should_update_timestamp = True
            
            if should_update_timestamp:
                last_run_setting.value = now.isoformat()
                db.commit()
            
            # Clear manual trigger flag if it was set
            trigger_setting = db.query(SystemSetting).filter(SystemSetting.key == 'scheduler_trigger_requested').first()
            if trigger_setting and trigger_setting.value == 'true':
                print("[Scheduler Service] Manual trigger detected, processing...")
                trigger_setting.value = 'false'
                db.commit()
            
            # Check if workers are paused (using cached setting)
            if get_cached_bool_setting('workers_paused', default=False):
                print("[Scheduler Service] Workers are paused, skipping queue processing")
                return
            
            # 1. Check for scheduled jobs whose time has arrived
            scheduled_items = db.query(QueueItem).filter(
                QueueItem.status == QueueStatus.scheduled,
                QueueItem.scheduled_at <= now
            ).all()
            
            for item in scheduled_items:
                print(f"[Scheduler Service] Transitioning scheduled item {item.id} to queued")
                item.status = QueueStatus.queued
                db.commit()

            # 2. Check max concurrent workers (using cached setting)
            max_workers = get_cached_int_setting('max_concurrent_workers', default=1)
            
            running_count = db.query(QueueItem).filter(QueueItem.status == QueueStatus.running).count()
            
            if running_count >= max_workers:
                print(f"[Scheduler Service] Max concurrent workers reached ({running_count}/{max_workers}). Waiting...")
                return

            # 3. Pick and start
            print("[Scheduler Service] Checking for queued items...")
            it = db.query(QueueItem).filter(QueueItem.status == QueueStatus.queued).order_by(QueueItem.created_at.asc()).first()
            if it:
                print(f"[Scheduler Service] Found queued item {it.id}, attempting to start...")
                
                # Check VPN if required (with timeout protection)
                if it.use_vpn:
                    print(f"[Scheduler Service] Item {it.id} requires VPN. Checking connection...")
                    try:
                        # Run VPN check with timeout using threading
                        import threading
                        vpn_result = [False]
                        def vpn_check():
                            vpn_result[0] = ensure_vpn_connected()
                        
                        vpn_thread = threading.Thread(target=vpn_check, daemon=True)
                        vpn_thread.start()
                        vpn_thread.join(timeout=90)  # 90 second timeout for VPN
                        
                        if vpn_thread.is_alive():
                            print(f"[Scheduler Service] VPN check timed out after 90s. Skipping item {it.id}...")
                            return
                        
                        if not vpn_result[0]:
                            print(f"[Scheduler Service] Could not establish VPN connection. Skipping start of item {it.id}...")
                            return
                    except Exception as vpn_e:
                        print(f"[Scheduler Service] VPN check error: {vpn_e}")
                        return

                try:
                    # Deferred import to speed up scheduler startup
                    from app.worker import start_queue_item_background
                    start_queue_item_background(it.id)
                    print(f"[Scheduler Service] Successfully started item {it.id}")
                except Exception as e:
                    print(f"[Scheduler Service] Failed to start queued item {it.id}: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print("[Scheduler Service] No queued items found")
        finally:
            db.close()
        
        # Removed update_next_run_time() to reduce unnecessary DB writes
        
    except Exception as e:
        print(f"[Scheduler Service] Error in pick_and_start: {e}")
        import traceback
        traceback.print_exc()
    finally:
        _pick_and_start_running = False



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
        
        # Ensure VPN is connected for results scraping to avoid IP blocks/leaks
        ensure_vpn_connected()
        
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


def update_next_run_time():
    """Update the scheduler_next_run setting in the database."""
    global current_queue_interval
    from app.models import SystemSetting
    
    db = SessionLocal()
    try:
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        next_run = now + datetime.timedelta(seconds=current_queue_interval)
        
        next_run_setting = db.query(SystemSetting).filter(SystemSetting.key == 'scheduler_next_run').first()
        if not next_run_setting:
            next_run_setting = SystemSetting(key='scheduler_next_run', value=next_run.isoformat())
            db.add(next_run_setting)
        else:
            next_run_setting.value = next_run.isoformat()
        db.commit()
    except Exception as e:
        print(f"[Scheduler Service] Error updating next_run: {e}")
    finally:
        db.close()


def manage_scheduler_config(scheduler):
    """Check DB for scheduler interval changes and update job if needed."""
    global current_queue_interval
    
    try:
        # Use cached setting with force refresh to check for changes
        new_interval = get_cached_int_setting('scheduler_interval', default=current_queue_interval, use_cache=False)
        if new_interval != current_queue_interval:
            print(f"[Scheduler Manager] Interval changed from {current_queue_interval}s to {new_interval}s. Rescheduling.")
            scheduler.reschedule_job('queue_runner', trigger='interval', seconds=new_interval)
            current_queue_interval = new_interval
    except Exception as e:
        print(f"[Scheduler Manager] Error: {e}")


def check_auto_switch_to_lazy(scheduler):
    """Check if system is idle and switch to Lazy Mode if enabled."""
    from app.models import SystemSetting, PollSchedulerConfig, Poll, QueueItem, QueueStatus
    
    db = SessionLocal()
    try:
        # 1. Check if auto-switch is enabled (using cached setting)
        if not get_cached_bool_setting('auto_switch_to_lazy', default=False):
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


def purge_old_data():
    """
    Purge old data based on the days_to_purge setting.
    Deletes:
    - Log files older than X days
    - Polls older than X days
    - Workers older than X days
    - Queue items (completed/canceled/failed) older than X days
    """
    print("[Data Purge] Starting purge job...")
    db = SessionLocal()
    try:
        from app.models import SystemSetting, Poll, WorkerProcess
        from datetime import datetime, timedelta, timezone
        
        # Get retention setting (default 30 days)
        setting = db.query(SystemSetting).filter(SystemSetting.key == 'days_to_purge').first()
        if not setting:
            # Create default setting if it doesn't exist
            setting = SystemSetting(key='days_to_purge', value='30')
            db.add(setting)
            db.commit()
            print("[Data Purge] Created default days_to_purge setting (30 days)")
        
        days = int(setting.value)
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
        print(f"[Data Purge] Retention period: {days} days (cutoff: {cutoff.strftime('%Y-%m-%d %H:%M:%S')})")
        
        # 1. Purge old log files
        log_dir = os.environ.get('AUTO_VOTER_LOG_DIR', './data/logs')
        deleted_logs = 0
        if os.path.exists(log_dir):
            for filename in os.listdir(log_dir):
                filepath = os.path.join(log_dir, filename)
                if os.path.isfile(filepath):
                    try:
                        mtime = datetime.fromtimestamp(os.path.getmtime(filepath), tz=timezone.utc).replace(tzinfo=None)
                        if mtime < cutoff:
                            os.remove(filepath)
                            deleted_logs += 1
                    except Exception as e:
                        print(f"[Data Purge] Error deleting log file {filename}: {e}")
        
        # 2. Purge old polls
        old_polls = db.query(Poll).filter(Poll.created_at < cutoff).delete(synchronize_session=False)
        
        # 3. Purge old workers (only those that have ended)
        old_workers = db.query(WorkerProcess).filter(
            WorkerProcess.end_time.isnot(None),
            WorkerProcess.end_time < cutoff
        ).delete(synchronize_session=False)
        
        # 4. Purge old queue items (completed, canceled, or failed)
        old_queue = db.query(QueueItem).filter(
            QueueItem.completed_at.isnot(None),
            QueueItem.completed_at < cutoff,
            QueueItem.status.in_([QueueStatus.completed, QueueStatus.canceled])
        ).delete(synchronize_session=False)
        
        db.commit()
        print(f"[Data Purge] ✓ Deleted: {deleted_logs} log files, {old_polls} polls, {old_workers} workers, {old_queue} queue items")
    except Exception as e:
        print(f"[Data Purge] Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


def reset_zombie_jobs():
    """
    Reset any jobs that are stuck in 'running' or 'paused' state on startup.
    Since the scheduler is just starting, any such jobs are zombies from a previous run
    that was interrupted (e.g. container restart).
    """
    print("[Scheduler Service] Checking for zombie jobs...")
    db = SessionLocal()
    try:
        zombies = db.query(QueueItem).filter(
            QueueItem.status.in_([QueueStatus.running, QueueStatus.paused])
        ).all()
        
        if zombies:
            print(f"[Scheduler Service] Found {len(zombies)} zombie jobs. Resetting to queued...")
            for item in zombies:
                print(f"[Scheduler Service] Resetting job {item.id} (was {item.status})")
                item.status = QueueStatus.queued
                item.current_status = "Recovered from restart - queued to run"
                # Note: We don't reset votes_cast, so it will continue adding to the total.
                # If the user wants to start fresh, they can cancel and add a new item.
            db.commit()
            print("[Scheduler Service] Zombie jobs reset successfully")
        else:
            print("[Scheduler Service] No zombie jobs found")
    except Exception as e:
        print(f"[Scheduler Service] Error resetting zombie jobs: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


def main():
    global current_queue_interval
    print("[Scheduler Service] Starting main()...")
    
    # Reset zombie jobs in background to avoid blocking startup
    import threading
    zombie_thread = threading.Thread(target=reset_zombie_jobs, daemon=True)
    zombie_thread.start()
    print("[Scheduler Service] Zombie job cleanup started in background")
    
    try:
        current_queue_interval = int(os.environ.get('AUTO_VOTER_SCHEDULE_INTERVAL', '30'))
        print(f"[Scheduler Service] Interval set to {current_queue_interval}s")
        
        sched = BlockingScheduler()
        print("[Scheduler Service] BlockingScheduler created")
        
        # Add queue item scheduler with max_instances to prevent blocking
        # Delay first run by 5 seconds to ensure initialization completes
        first_run = datetime.datetime.now() + datetime.timedelta(seconds=5)
        sched.add_job(
            pick_and_start, 
            'interval', 
            seconds=current_queue_interval, 
            id='queue_runner',
            max_instances=3,  # Allow up to 3 concurrent instances to prevent total blocking
            replace_existing=True,
            next_run_time=first_run
        )
        print(f"[Scheduler Service] Queue scheduler started, interval={current_queue_interval}s, max_instances=3, first_run={first_run}")
        
        # Add poll results scheduler (checks config for interval)
        # Run every 5 minutes to reduce DB polling overhead
        sched.add_job(run_poll_results_scheduler, 'interval', minutes=5, id='poll_results_runner')
        print(f"[Scheduler Service] Poll results scheduler started, checks every 5 minutes")
        
        # Add config manager (checks every 5 minutes to reduce DB polling)
        sched.add_job(manage_scheduler_config, 'interval', minutes=5, args=[sched], id='config_manager')
        print("[Scheduler Service] Config manager added (5 min interval)")
        
        # Add auto-switch checker (checks every 5 minutes)
        sched.add_job(check_auto_switch_to_lazy, 'interval', minutes=5, args=[sched], id='auto_switch_checker')
        print("[Scheduler Service] Auto-switch checker added")
        
        # Add VPN idle checker (checks every 2 minutes to disconnect when idle)
        sched.add_job(check_and_disconnect_idle_vpn, 'interval', minutes=2, id='vpn_idle_checker')
        print("[Scheduler Service] VPN idle checker added (2 min interval)")
        
        # Add data purge job (runs daily at 3 AM)
        sched.add_job(purge_old_data, 'cron', hour=3, minute=0, id='data_purge')
        print("[Scheduler Service] Data purge job added (runs daily at 3:00 AM)")
        
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

