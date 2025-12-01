import multiprocessing
import threading
import time
import datetime
import os
import signal
from app.db import SessionLocal
from app.models import QueueItem, QueueStatus, WorkerProcess
from flask import current_app
import threading


def _run_vote_wrapper(item_id: int, worker_id: int, log_path: str = None):
    """Child process entrypoint: imports the voting module and runs the job.
    Any unhandled exceptions will propagate to the child process and can be inspected via exitcode.
    """
    try:
        # if log_path provided, redirect stdout/stderr to the log file
        if log_path:
            try:
                os.makedirs(os.path.dirname(log_path), exist_ok=True)
                # Open in unbuffered mode for real-time streaming
                lf = open(log_path, 'a+', buffering=1)  # Line buffering
                # dup file descriptor to stdout/stderr
                os.dup2(lf.fileno(), 1)
                os.dup2(lf.fileno(), 2)
                # Make stdout/stderr unbuffered
                import sys
                sys.stdout = os.fdopen(1, 'w', buffering=1)
                sys.stderr = os.fdopen(2, 'w', buffering=1)
            except Exception as e:
                print(f"Failed to open log file {log_path}: {e}")

        print(f"[Worker {worker_id}] Starting vote process for item {item_id}")

        
        import app.auto_voter_queue as avq
        db = SessionLocal()
        it = db.query(QueueItem).filter(QueueItem.id == item_id).first()
        db.close()
        if not it:
            print(f"[Worker {worker_id}] No queue item {item_id} found")
            return

        print(f"[Worker {worker_id}] Configuring: pollid={it.pollid}, answerid={it.answerid}, votes={it.votes}, threads={it.threads}")
        
        avq.pollid = it.pollid
        avq.answerid = it.answerid
        avq.start_totalToRun = it.votes
        avq.num_threads = it.threads
        avq.p2_PerRun = it.per_run
        avq.p2_pause = it.pause
        avq.use_vpn = bool(it.use_vpn)
        avq.use_tor = bool(it.use_tor)
        avq.jobname = it.queue_name or f"poll_{it.pollid}"
        
        # Set progress tracking globals
        avq.current_item_id = item_id
        # Note: socketio_instance will be set by start_queue_item_background

        print(f"[Worker {worker_id}] Calling vote_start(2)...")
        avq.vote_start(2)
        print(f"[Worker {worker_id}] vote_start completed successfully")
    except Exception as e:
        print(f"[Worker {worker_id}] Error: {e}")
        import traceback
        traceback.print_exc()


def tail_log_for_client(socketio, sid, worker_id: int):
    """Background task intended to run under SocketIO to tail a worker log and emit lines to a client sid."""
    db = SessionLocal()
    try:
        wp = db.query(WorkerProcess).filter(WorkerProcess.id == worker_id).first()
        if not wp or not wp.log_path:
            socketio.emit('log_line', {'line': '[no log path found]'}, to=sid)
            return
        log_path = wp.log_path
        # Debug output removed to prevent infinite loop
        try:
            with open(log_path, 'r') as f:
                # Read existing lines
                existing = f.readlines()
                for line in existing:
                    socketio.emit('log_line', {'line': line.rstrip('\n')}, to=sid)
                
                # Tail new lines
                while True:
                    line = f.readline()
                    if line:
                        line_stripped = line.rstrip('\n')
                        socketio.emit('log_line', {'line': line_stripped}, to=sid)
                    else:
                        # Check if process is finished
                        db2 = SessionLocal()
                        try:
                            wp_ref = db2.query(WorkerProcess).filter(WorkerProcess.id == worker_id).first()
                            if wp_ref and wp_ref.end_time:
                                break
                        finally:
                            db2.close()
                        time.sleep(0.5)
        except FileNotFoundError:
            msg = f'[log file not found: {log_path}]'
            socketio.emit('log_line', {'line': msg}, to=sid)
        except Exception as e:
            msg = f'[stream error] {e}'
            socketio.emit('log_line', {'line': msg}, to=sid)
    finally:
        db.close()


def _monitor_process(proc: multiprocessing.Process, item_id: int, worker_id: int, socketio=None):
    """Monitor thread that waits for the child process to exit and updates the DB record."""
    proc.join()
    exitcode = proc.exitcode

    db = SessionLocal()
    try:
        it = db.query(QueueItem).filter(QueueItem.id == item_id).first()
        wp = db.query(WorkerProcess).filter(WorkerProcess.id == worker_id).first()
        if wp:
            wp.end_time = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
            wp.exit_code = exitcode
            wp.result_msg = f"exitcode={exitcode}"
        if it:
            it.exit_code = exitcode
            it.pid = None
            it.completed_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
            it.status = QueueStatus.completed if exitcode == 0 else QueueStatus.canceled
            it.result_msg = f"exitcode={exitcode}"
            it.worker_id = worker_id
        db.commit()
        
        if socketio:
            try:
                socketio.emit('queue_update', {'type': 'complete', 'item_id': item_id, 'status': 'completed' if exitcode == 0 else 'canceled'})
            except Exception as e:
                print(f"[_monitor_process] Failed to emit socketio event: {e}")
    finally:
        db.close()


def start_queue_item_background(item_id: int, socketio=None):
    """
    Start a queue item in a background process.
    Returns the PID of the started process.
    """
    from app.db import SessionLocal
    from app.models import QueueItem, QueueStatus, WorkerProcess
    import datetime
    import os
    import app.auto_voter_queue as avq
    
    # Set socketio instance for progress updates
    if socketio:
        avq.socketio_instance = socketio
    
    db = SessionLocal()
    it = db.query(QueueItem).filter(QueueItem.id == item_id).first()
    if not it:
        db.close()
        raise ValueError('item not found')
    if it.status != QueueStatus.queued:
        db.close()
        raise ValueError('item not queued')

    it.status = QueueStatus.running
    it.started_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    
    # Emit 'running' status update immediately
    if socketio:
        try:
            socketio.emit('queue_update', {'type': 'status', 'item_id': item_id, 'status': 'running'})
        except Exception as e:
            print(f"[start_queue_item_background] Failed to emit running status: {e}")

    # prepare log file
    logs_dir = os.environ.get('AUTO_VOTER_LOG_DIR', './data/logs')
    os.makedirs(logs_dir, exist_ok=True)
    timestamp = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).strftime('%Y%m%d%H%M%S')
    log_path = os.path.join(logs_dir, f'job_{item_id}_{timestamp}.log')

    # create worker process metadata
    wp = WorkerProcess(pid=None, item_id=item_id, log_path=log_path, start_time=datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None))
    db.add(wp)
    db.commit()
    db.refresh(wp)

    db.add(it)
    it.worker_id = wp.id
    db.commit()

    # Use 'spawn' context to ensure a clean process without gevent monkey-patching artifacts
    ctx = multiprocessing.get_context('spawn')
    proc = ctx.Process(target=_run_vote_wrapper, args=(item_id, wp.id, log_path))
    proc.start()

    # persist PID
    wp.pid = proc.pid
    it.pid = proc.pid
    db.add(wp); db.add(it)
    db.commit()
    
    worker_id = wp.id
    db.close()

    # Start a monitor thread in this process to update the DB when child exits
    monitor = threading.Thread(target=_monitor_process, args=(proc, item_id, worker_id, socketio), daemon=True)
    monitor.start()

    return proc.pid


def stop_queue_item(item_id: int, sig=signal.SIGTERM):
    """Attempt to stop a running queue item by PID and mark it canceled."""
    db = SessionLocal()
    it = db.query(QueueItem).filter(QueueItem.id == item_id).first()
    if not it:
        db.close()
        raise ValueError('item not found')
    if not it.pid and not it.worker_id:
        db.close()
        raise ValueError('item not running')
    pid = it.pid
    # try to lookup worker record
    wp = None
    if it.worker_id:
        try:
            wp = db.query(WorkerProcess).filter(WorkerProcess.id == it.worker_id).first()
            if wp and not pid:
                pid = wp.pid
        except Exception:
            wp = None
    try:
        if pid:
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                # process already gone
                pass
    except Exception:
        # ignore kill errors
        pass

    it.status = QueueStatus.canceled
    it.completed_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    it.result_msg = f'killed pid {pid}'
    it.pid = None
    if wp:
        wp.end_time = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        wp.exit_code = -1
        wp.result_msg = it.result_msg
        wp.pid = None
        db.add(wp)
    db.commit()
    db.close()

    return True
