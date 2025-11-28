from gevent import monkey
monkey.patch_all()

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

import datetime
from datetime import timezone, timedelta
import signal
from flask import Flask, request, jsonify, abort, render_template, redirect, url_for
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from app.db import SessionLocal, init_db
from app.models import Poll, QueueItem, QueueStatus, User
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import os
from app.worker import start_queue_item_background, stop_queue_item
from app.models import WorkerProcess
from app.socketio_server import register_socketio_handlers
from flask import Response, make_response
import time

from flask_socketio import SocketIO


# EST timezone (UTC-5)
EST = timezone(timedelta(hours=-5))

def to_est_string(dt):
    """Convert a UTC datetime to EST and return ISO format string"""
    if dt is None:
        return None
    # Assume dt is in UTC, convert to EST
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(EST).isoformat()


# --- Simple token auth ---
ADMIN_TOKEN = os.environ.get('ADMIN_TOKEN')


def check_token_from_request(req):
    # Accept Authorization: Bearer <token> or ?token= in querystring
    auth = req.headers.get('Authorization')
    if auth and auth.startswith('Bearer '):
        return auth.split(None, 1)[1]
    token = req.args.get('token')
    if token:
        return token
    return None


def require_auth(f):
    def wrapper(*args, **kwargs):
        # allow session-authenticated users or token-based admin
        try:
            if current_user and getattr(current_user, 'is_authenticated', False):
                return f(*args, **kwargs)
        except Exception:
            pass
        if not ADMIN_TOKEN:
            return abort(401, 'Unauthorized')
        token = check_token_from_request(request)
        if not token or token != ADMIN_TOKEN:
            return abort(401, 'Unauthorized')
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper


app = Flask(__name__)

# Secret key for sessions
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret')

# Initialize DB at import time so the database/tables exist before serving
init_db()

# SocketIO attached to the app
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

# Register socket handlers after app and socketio are available
register_socketio_handlers(socketio, app)


# --- Login manager ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.id == int(user_id)).first()
        return u
    finally:
        db.close()


def ensure_admin_user():
    """Create or update admin user from env vars ADMIN_USER and ADMIN_PASS (if provided)."""
    admin_user = os.environ.get('ADMIN_USER')
    admin_pass = os.environ.get('ADMIN_PASS')
    if not admin_user or not admin_pass:
        return
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.username == admin_user).first()
        if not u:
            u = User(username=admin_user)
            u.set_password(admin_pass)
            db.add(u)
            db.commit()
        else:
            # update password if different
            if not u.check_password(admin_pass):
                u.set_password(admin_pass)
                db.add(u)
                db.commit()
    finally:
        db.close()


ensure_admin_user()

# Scheduler: pick queued items every 30s and start them (simple FIFO)
scheduler = BackgroundScheduler()


def _get_max_concurrent_workers():
    """Get max concurrent workers setting (default 1)."""
    from app.models import SystemSetting
    db = SessionLocal()
    try:
        setting = db.query(SystemSetting).filter(SystemSetting.key == 'max_concurrent_workers').first()
        if setting and setting.value:
            return int(setting.value)
        return 1
    except:
        return 1
    finally:
        db.close()


def _get_scheduler_interval():
    """
    Get scheduler interval in seconds.
    Priority:
    1. Database setting (system_settings.scheduler_interval)
    2. Environment variable (SCHEDULER_INTERVAL)
    3. Default (60 seconds)
    """
    # 1. Check DB
    from app.models import SystemSetting
    db = SessionLocal()
    try:
        setting = db.query(SystemSetting).filter(SystemSetting.key == 'scheduler_interval').first()
        if setting and setting.value:
            return int(setting.value)
    except:
        pass
    finally:
        db.close()

    # 2. Check Env
    env_val = os.environ.get('SCHEDULER_INTERVAL')
    if env_val:
        try:
            return int(env_val)
        except ValueError:
            pass

    # 3. Default
    return 60


def _scheduled_pick_and_start():
    print("[SCHEDULER] Checking for queued items...")
    db = SessionLocal()
    try:
        # Check current running workers
        running_count = db.query(QueueItem).filter(QueueItem.status == QueueStatus.running).count()
        max_workers = _get_max_concurrent_workers()
        
        if running_count >= max_workers:
            print(f"[SCHEDULER] Max concurrent workers reached ({running_count}/{max_workers}). Waiting...")
            return

        # pick the next queued item
        it = db.query(QueueItem).filter(QueueItem.status == QueueStatus.queued).order_by(QueueItem.created_at.asc()).first()
        if it:
            print(f"[SCHEDULER] Found queued item {it.id}, attempting to start...")
            try:
                start_queue_item_background(it.id, socketio=socketio)
                print(f"[SCHEDULER] Successfully started item {it.id}")
                socketio.emit('queue_update', {'type': 'start', 'item_id': it.id})
            except Exception as e:
                print(f"[SCHEDULER] Failed to start queued item {it.id}: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("[SCHEDULER] No queued items found")
    finally:
        db.close()


# Only start scheduler in the main process to avoid duplicate runs under some servers
_SCHEDULER_STARTED = False

def start_scheduler_if_needed():
    global _SCHEDULER_STARTED
    # avoid multiple scheduler instances in the same process
    if _SCHEDULER_STARTED:
        return
        
    # If running under Werkzeug reloader, we want to run in the child process (WERKZEUG_RUN_MAIN='true')
    # If we are in the parent process of the reloader, we might want to skip starting the scheduler to avoid duplicates,
    # but it's hard to detect reliably if we are the parent of a reloader vs a standalone process.
    # However, the critical fix is to ensure it DOES start in the child.
    # The previous environment variable check prevented the child from starting it because the parent set the flag.
    # By using a global variable, the child (which is a fresh process) will start with False and thus start the scheduler.
    
    interval = _get_scheduler_interval()
    print(f"[SCHEDULER] Starting scheduler with {interval}s interval (PID: {os.getpid()})...")
    scheduler.add_job(_scheduled_pick_and_start, 'interval', seconds=interval, id='poll_queue_runner', replace_existing=True)
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown(wait=False))
    _SCHEDULER_STARTED = True
    print("[SCHEDULER] Scheduler started successfully")


# Start scheduler automatically (in development this may run twice if using the reloader - env flag prevents duplicates)
start_scheduler_if_needed()


# ====== Poll Results Scheduler ======

def _get_poll_scheduler_config():
    """Get or create poll scheduler config."""
    from app.models import PollSchedulerConfig
    db = SessionLocal()
    try:
        config = db.query(PollSchedulerConfig).first()
        if not config:
            config = PollSchedulerConfig(enabled=0, interval_minutes=15)
            db.add(config)
            db.commit()
            db.refresh(config)
        return config
    finally:
        db.close()


def _scheduled_poll_results_capture():
    """Run poll results capture if enabled."""
    from app.models import PollSchedulerConfig
    from app.vote_results_influx_scheduler import run_all_polls
    import datetime
    
    db = SessionLocal()
    try:
        config = db.query(PollSchedulerConfig).first()
        if not config or not config.enabled:
            return
        
        print("[Poll Results Scheduler] Running poll results capture...")
        run_all_polls(db_session=db)
        
        # Update last_run timestamp
        config.last_run = datetime.datetime.utcnow()
        db.commit()
        print("[Poll Results Scheduler] Completed")
    except Exception as e:
        print(f"[Poll Results Scheduler] Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


def _update_poll_scheduler_job():
    """Update or create the poll results scheduler job based on config."""
    from app.models import PollSchedulerConfig
    
    config = _get_poll_scheduler_config()
    job_id = 'poll_results_capture'
    
    if config.enabled:
        interval_seconds = config.interval_minutes * 60
        print(f"[Poll Results Scheduler] Updating job: interval={config.interval_minutes} minutes")
        scheduler.add_job(
            _scheduled_poll_results_capture,
            'interval',
            seconds=interval_seconds,
            id=job_id,
            replace_existing=True
        )
    else:
        # Remove job if disabled
        try:
            scheduler.remove_job(job_id)
            print("[Poll Results Scheduler] Job removed (disabled)")
        except:
            pass  # Job doesn't exist


# Initialize poll scheduler on startup
_update_poll_scheduler_job()


@app.route('/scheduler/status', methods=['GET'])
@require_auth
def scheduler_status():
    job = scheduler.get_job('poll_queue_runner')
    # If job exists and next_run_time is not None, it's running (not paused)
    running = (job is not None and job.next_run_time is not None)
    return jsonify({'running': running})


@app.route('/scheduler/pause', methods=['POST'])
@require_auth
def scheduler_pause():
    job = scheduler.get_job('poll_queue_runner')
    if job:
        job.pause()
    return jsonify({'paused': True})


@app.route('/scheduler/resume', methods=['POST'])
@require_auth
def scheduler_resume():
    job = scheduler.get_job('poll_queue_runner')
    if job:
        job.resume()
    return jsonify({'resumed': True})


@app.route('/poll-scheduler/config', methods=['GET'])
@require_auth
def get_poll_scheduler_config():
    from app.models import PollSchedulerConfig
    db = SessionLocal()
    try:
        config = db.query(PollSchedulerConfig).first()
        if not config:
            config = PollSchedulerConfig(enabled=0, interval_minutes=15)
            db.add(config)
            db.commit()
            db.refresh(config)
        return jsonify({
            'enabled': bool(config.enabled),
            'interval_minutes': config.interval_minutes,
            'last_run': to_est_string(config.last_run)
        })
    finally:
        db.close()


@app.route('/poll-scheduler/config', methods=['POST'])
@require_auth
def update_poll_scheduler_config():
    from app.models import PollSchedulerConfig
    data = request.json or {}
    
    db = SessionLocal()
    try:
        config = db.query(PollSchedulerConfig).first()
        if not config:
            config = PollSchedulerConfig()
            db.add(config)
        
        if 'enabled' in data:
            config.enabled = 1 if data['enabled'] else 0
        if 'interval_minutes' in data:
            interval = int(data['interval_minutes'])
            if interval < 1:
                return abort(400, 'interval_minutes must be at least 1')
            config.interval_minutes = interval
        
        db.commit()
        db.refresh(config)
        
        # Update the scheduler job
        _update_poll_scheduler_job()
        
        return jsonify({
            'enabled': bool(config.enabled),
            'interval_minutes': config.interval_minutes,
            'last_run': to_est_string(config.last_run)
        })
    finally:
        db.close()


@app.route('/poll-scheduler/run-now', methods=['POST'])
@require_auth
def run_poll_scheduler_now():
    """Manually trigger poll results capture."""
    try:
        _scheduled_poll_results_capture()
        return jsonify({'success': True, 'message': 'Poll results capture triggered'})
    except Exception as e:
        return abort(500, str(e))


@app.route('/settings/concurrency', methods=['GET'])
@require_auth
def get_concurrency_setting():
    from app.models import SystemSetting
    db = SessionLocal()
    try:
        # Max Workers
        setting_workers = db.query(SystemSetting).filter(SystemSetting.key == 'max_concurrent_workers').first()
        val_workers = int(setting_workers.value) if (setting_workers and setting_workers.value) else 1
        
        # Scheduler Interval
        # Note: We use the helper to get the effective interval (including env/default), 
        # but for the UI input we might want to show the DB override if it exists, or the effective one.
        # For simplicity, just return the effective interval.
        val_interval = _get_scheduler_interval()
        
        return jsonify({
            'max_concurrent_workers': val_workers,
            'scheduler_interval': val_interval
        })
    finally:
        db.close()


@app.route('/settings/concurrency', methods=['POST'])
@require_auth
def update_concurrency_setting():
    from app.models import SystemSetting
    data = request.json or {}
    
    db = SessionLocal()
    try:
        # Update Max Workers
        if 'max_concurrent_workers' in data:
            val_workers = int(data['max_concurrent_workers'])
            if val_workers < 1:
                return abort(400, 'Max workers must be at least 1')
            
            setting_workers = db.query(SystemSetting).filter(SystemSetting.key == 'max_concurrent_workers').first()
            if not setting_workers:
                setting_workers = SystemSetting(key='max_concurrent_workers')
                db.add(setting_workers)
            setting_workers.value = str(val_workers)
            
        # Update Scheduler Interval
        reschedule = False
        if 'scheduler_interval' in data:
            val_interval = int(data['scheduler_interval'])
            if val_interval < 1:
                return abort(400, 'Interval must be at least 1 second')
                
            setting_interval = db.query(SystemSetting).filter(SystemSetting.key == 'scheduler_interval').first()
            if not setting_interval:
                setting_interval = SystemSetting(key='scheduler_interval')
                db.add(setting_interval)
            
            # Check if changed to reschedule
            if not setting_interval.value or int(setting_interval.value) != val_interval:
                reschedule = True
                
            setting_interval.value = str(val_interval)

        db.commit()
        
        # Reschedule if needed
        if reschedule:
            new_interval = _get_scheduler_interval() # Should fetch the new DB value
            print(f"[SCHEDULER] Rescheduling job with new interval: {new_interval}s")
            scheduler.add_job(_scheduled_pick_and_start, 'interval', seconds=new_interval, id='poll_queue_runner', replace_existing=True)

        return jsonify({
            'max_concurrent_workers': int(data.get('max_concurrent_workers', 1)),
            'scheduler_interval': int(data.get('scheduler_interval', 60))
        })
    finally:
        db.close()


@app.route('/login', methods=['POST'])
def login():
    data = request.json or {}
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return abort(400, 'username and password required')
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.username == username).first()
        if not u or not u.check_password(password):
            return abort(401, 'invalid credentials')
        login_user(u)
        return jsonify({'ok': True})
    finally:
        db.close()


@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({'ok': True})


@app.route('/polls', methods=['POST'])
@require_auth
def create_poll():
    data = request.json or {}
    entryname = data.get('entryname')
    pollid = str(data.get('pollid'))
    answerid = str(data.get('answerid'))
    use_tor = int(data.get('use_tor', 0))
    if not entryname or not pollid or not answerid:
        return abort(400, 'entryname, pollid, answerid required')

    db = SessionLocal()
    p = Poll(entryname=entryname, pollid=pollid, answerid=answerid, use_tor=use_tor)
    db.add(p)
    db.commit()
    db.refresh(p)
    db.close()
    return jsonify({'id': p.id, 'entryname': p.entryname, 'pollid': p.pollid, 'answerid': p.answerid})


@app.route('/polls', methods=['GET'])
@require_auth
def list_polls():
    db = SessionLocal()
    polls = db.query(Poll).order_by(Poll.created_at.desc()).all()
    out = [{
        'id': p.id, 
        'entryname': p.entryname, 
        'pollid': p.pollid, 
        'answerid': p.answerid, 
        'use_tor': p.use_tor, 
        'created_at': to_est_string(p.created_at),
        'status': p.status,
        'poll_title': p.poll_title,
        'total_poll_votes': p.total_poll_votes,
        'total_votes': p.total_votes,
        'current_place': p.current_place,
        'votes_behind_first': p.votes_behind_first,
        'last_snapshot_at': to_est_string(p.last_snapshot_at)
    } for p in polls]
    db.close()
    return jsonify(out)


@app.route('/polls/<int:poll_id>', methods=['DELETE'])
@require_auth
def delete_poll(poll_id):
    db = SessionLocal()
    try:
        p = db.query(Poll).filter(Poll.id == poll_id).first()
        if not p:
            return abort(404, 'poll not found')
        db.delete(p)
        db.commit()
        return jsonify({'deleted': True})
    finally:
        db.close()


@app.route('/polls/<int:poll_id>', methods=['PUT'])
@require_auth
def update_poll(poll_id):
    db = SessionLocal()
    try:
        p = db.query(Poll).filter(Poll.id == poll_id).first()
        if not p:
            return abort(404, 'poll not found')
        
        data = request.get_json()
        
        # Update allowed fields
        if 'entryname' in data:
            p.entryname = data['entryname']
        if 'pollid' in data:
            p.pollid = data['pollid']
        if 'answerid' in data:
            p.answerid = data['answerid']
        if 'use_tor' in data:
            p.use_tor = int(data['use_tor'])
        if 'status' in data:
            p.status = data['status']
        
        db.commit()
        return jsonify({'success': True, 'id': p.id})
    except Exception as e:
        db.rollback()
        return abort(500, str(e))
    finally:
        db.close()


@app.route('/polls/<int:poll_id>/refresh', methods=['POST'])
@require_auth
def refresh_poll_results(poll_id):
    from app.vote_results_influx_scheduler import extract_poll_results
    db = SessionLocal()
    try:
        p = db.query(Poll).filter(Poll.id == poll_id).first()
        if not p:
            return abort(404, 'poll not found')
        
        url = f"https://poll.fm/{p.pollid}/results"
        extract_poll_results(url, p.pollid)
        
        # Refresh from DB to get updated stats
        db.refresh(p)
        
        return jsonify({
            'success': True,
            'total_votes': p.total_votes,
            'current_place': p.current_place,
            'votes_behind_first': p.votes_behind_first,
            'last_snapshot_at': to_est_string(p.last_snapshot_at)
        })
    except Exception as e:
        return abort(500, str(e))
    finally:
        db.close()


@app.route('/polls/<int:poll_id>/snapshot', methods=['GET'])
@require_auth
def get_poll_snapshot(poll_id):
    from app.models import PollSnapshot
    db = SessionLocal()
    try:
        p = db.query(Poll).filter(Poll.id == poll_id).first()
        if not p:
            return abort(404, 'poll not found')
        
        # Get latest snapshots for this poll
        snapshots = db.query(PollSnapshot).filter(
            PollSnapshot.poll_id == poll_id
        ).order_by(PollSnapshot.place.asc()).all()
        
        # Calculate time since last snapshot
        time_since = None
        if p.last_snapshot_at:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            last_snap = p.last_snapshot_at.replace(tzinfo=timezone.utc) if p.last_snapshot_at.tzinfo is None else p.last_snapshot_at
            delta = now - last_snap
            hours = int(delta.total_seconds() // 3600)
            minutes = int((delta.total_seconds() % 3600) // 60)
            if hours > 0:
                time_since = f"{hours}h {minutes}m ago"
            else:
                time_since = f"{minutes}m ago"
        
        return jsonify({
            'poll': {
                'id': p.id,
                'entryname': p.entryname,
                'pollid': p.pollid,
                'answerid': p.answerid,
                'poll_title': p.poll_title,
                'status': p.status,
                'total_poll_votes': p.total_poll_votes,
                'last_snapshot_at': to_est_string(p.last_snapshot_at),
                'time_since': time_since
            },
            'snapshots': [{
                'place': s.place,
                'answer_text': s.answer_text,
                'answerid': s.answerid or '-',
                'votes': s.votes,
                'percent': s.percent,
                'gap': (snapshots[0].votes - s.votes) if s.place > 1 else 0
            } for s in snapshots]
        })
    finally:
        db.close()


@app.route('/queue', methods=['POST'])
@require_auth
def add_queue_item():
    data = request.json or {}
    # Either poll database id or direct pollid/answerid
    poll_db_id = data.get('poll_db_id')
    queue_name = data.get('queue_name', '')
    pollid = data.get('pollid')
    answerid = data.get('answerid')
    votes = int(data.get('votes', 0))
    threads = int(data.get('threads', 1))
    per_run = int(data.get('per_run', 1))
    pause = int(data.get('pause', 0))
    use_vpn = int(data.get('use_vpn', 1))
    use_tor = int(data.get('use_tor', 0))

    db = SessionLocal()
    poll_ref = None
    if poll_db_id:
        poll_ref = db.query(Poll).filter(Poll.id == int(poll_db_id)).first()
        if not poll_ref:
            db.close()
            return abort(404, 'poll not found')
        pollid = pollid or poll_ref.pollid
        answerid = answerid or poll_ref.answerid
        # If queue_name not provided and poll_db_id exists, use poll name
        if not queue_name and poll_ref:
            queue_name = poll_ref.entryname

    if not pollid or not answerid:
        db.close()
        return abort(400, 'pollid and answerid required')

    item = QueueItem(poll_id=(poll_ref.id if poll_ref else None), pollid=str(pollid), answerid=str(answerid), votes=votes, threads=threads, per_run=per_run, pause=pause, use_vpn=use_vpn, use_tor=use_tor)
    db.add(item)
    db.commit()
    db.refresh(item)
    db.close()
    socketio.emit('queue_update', {'type': 'add', 'item_id': item.id})
    return jsonify({'id': item.id, 'status': item.status.value})


@app.route('/queue', methods=['GET'])
@require_auth
def list_queue():
    db = SessionLocal()
    items = db.query(QueueItem).order_by(QueueItem.created_at.asc()).all()
    out = []
    for it in items:
        out.append({
            'id': it.id,
            'queue_name': it.queue_name,
            'pollid': it.pollid,
            'answerid': it.answerid,
            'votes': it.votes,
            'threads': it.threads,
            'per_run': it.per_run,
            'pause': it.pause,
            'use_vpn': it.use_vpn,
            'use_tor': it.use_tor,
            'status': it.status.value,
            'worker_id': it.worker_id,
            'created_at': to_est_string(it.created_at),
            'started_at': to_est_string(it.started_at),
            'completed_at': to_est_string(it.completed_at),
            # Progress tracking fields
            'votes_cast': it.votes_cast or 0,
            'votes_success': it.votes_success or 0,
            'success_rate': it.success_rate or 0.0,
            'current_status': it.current_status,
            'last_update': to_est_string(it.last_update),
        })
    db.close()
    return jsonify(out)


@app.route('/queue/<int:item_id>/start', methods=['POST'])
@require_auth
def start_queue_item(item_id):
    # Start a queue item in the background
    from app.worker import start_queue_item_background
    try:
        pid = start_queue_item_background(item_id, socketio=socketio)
        socketio.emit('queue_update', {'type': 'start', 'item_id': item_id})
        return jsonify({'started': True, 'pid': pid})
    except Exception as e:
        return abort(500, str(e))


@app.route('/queue/<int:item_id>/cancel', methods=['POST'])
@require_auth
def cancel_queue_item(item_id):
    db = SessionLocal()
    it = db.query(QueueItem).filter(QueueItem.id == item_id).first()
    if not it:
        db.close()
        return abort(404)
    try:
        if it.status == QueueStatus.running:
            # attempt to stop
            stop_queue_item(item_id)
        else:
            it.status = QueueStatus.canceled
            it.completed_at = datetime.datetime.utcnow()
            db.commit()
        socketio.emit('queue_update', {'type': 'cancel', 'item_id': item_id})
        return jsonify({'canceled': True})
    finally:
        db.close()


@app.route('/queue/<int:item_id>/retry', methods=['POST'])
@require_auth
def retry_queue_item(item_id):
    db = SessionLocal()
    try:
        old_item = db.query(QueueItem).filter(QueueItem.id == item_id).first()
        if not old_item:
            return abort(404, 'item not found')
        
        # Create a copy
        new_item = QueueItem(
            poll_id=old_item.poll_id,
            queue_name=old_item.queue_name,
            pollid=old_item.pollid,
            answerid=old_item.answerid,
            votes=old_item.votes,
            threads=old_item.threads,
            per_run=old_item.per_run,
            pause=old_item.pause,
            use_vpn=old_item.use_vpn,
            use_tor=old_item.use_tor,
            status=QueueStatus.queued
        )
        db.add(new_item)
        db.commit()
        db.refresh(new_item)
        socketio.emit('queue_update', {'type': 'add', 'item_id': new_item.id})
        return jsonify({'id': new_item.id, 'status': new_item.status.value})
    finally:
        db.close()


@app.route('/workers', methods=['GET'])
@require_auth
def list_workers():
    db = SessionLocal()
    workers = db.query(WorkerProcess).order_by(WorkerProcess.start_time.desc()).all()
    out = []
    for w in workers:
        out.append({
            'id': w.id,
            'pid': w.pid,
            'item_id': w.item_id,
            'log_path': w.log_path,
            'start_time': to_est_string(w.start_time),
            'end_time': to_est_string(w.end_time),
            'exit_code': w.exit_code,
            'result_msg': w.result_msg,
        })
    db.close()
    return jsonify(out)


@app.route('/workers/<int:worker_id>/log', methods=['GET'])
@require_auth
def worker_log(worker_id):
    db = SessionLocal()
    w = db.query(WorkerProcess).filter(WorkerProcess.id == worker_id).first()
    db.close()
    if not w:
        return abort(404)
    if not w.log_path or not os.path.exists(w.log_path):
        return jsonify({'log': ''})
    # return last 10k chars of log for performance
    with open(w.log_path, 'r', encoding='utf-8', errors='ignore') as f:
        data = f.read()
    return jsonify({'log': data})


@app.route('/workers/<int:worker_id>/stream', methods=['GET'])
@require_auth
def worker_stream(worker_id):
    # Server-Sent Events streaming of the worker log file
    db = SessionLocal()
    w = db.query(WorkerProcess).filter(WorkerProcess.id == worker_id).first()
    db.close()
    if not w or not w.log_path:
        return abort(404)

    # SSE kept for backward compatibility, but prefer WebSocket
    def generate():
        try:
            with open(w.log_path, 'r', encoding='utf-8', errors='ignore') as f:
                f.seek(0, 2)
                while True:
                    line = f.readline()
                    if line:
                        yield f"data: {line.strip()}\n\n"
                    else:
                        time.sleep(0.5)
        except GeneratorExit:
            return
        except Exception as e:
            yield f"data: [stream error] {e}\n\n"

    return Response(generate(), mimetype='text/event-stream')


@app.route('/')
def index():
    # serve the single-page web UI
    return render_template('index.html')


if __name__ == '__main__':
    # use socketio.run so WebSocket transports work (eventlet/gevent)
    socketio.run(app, host='0.0.0.0', port=8080, debug=True)
