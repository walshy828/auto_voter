#!/usr/bin/env python3
"""Debug script to check worker process and log file setup."""
import os
import sys
import time

# Set env vars
os.environ['ADMIN_USER'] = 'testadmin'
os.environ['ADMIN_PASS'] = 'testpass'
os.environ['SECRET_KEY'] = 'test-secret'

from app.api import app
from app.db import SessionLocal
from app.models import QueueItem, WorkerProcess, Poll
import subprocess

def debug_worker_and_logs():
    """Debug: start a job and check log file creation."""
    print("=" * 70)
    print("🔍 DEBUG: Worker Process & Log File Setup")
    print("=" * 70)
    
    client = app.test_client()
    
    # 1. Login
    print("\n1️⃣ Logging in...")
    res = client.post('/login', json={'username': 'testadmin', 'password': 'testpass'})
    assert res.status_code == 200
    print("   ✓ Logged in")
    
    # 2. Create a poll
    print("\n2️⃣ Creating a poll...")
    res = client.post('/polls', json={
        'entryname': 'Debug Poll',
        'pollid': '999999',
        'answerid': '88888'
    })
    assert res.status_code == 200
    poll = res.get_json()
    print(f"   ✓ Poll created: {poll}")
    
    # 3. Add a queue item
    print("\n3️⃣ Adding queue item...")
    res = client.post('/queue', json={
        'poll_db_id': poll['id'],
        'votes': 10,  # Small number for quick test
        'threads': 1,
        'per_run': 1,
        'pause': 1
    })
    assert res.status_code == 200
    queue_item = res.get_json()
    queue_id = queue_item['id']
    print(f"   ✓ Queue item created: {queue_item}")
    
    # 4. Check queue item status before starting
    print("\n4️⃣ Checking queue item status (before start)...")
    db = SessionLocal()
    try:
        it = db.query(QueueItem).filter(QueueItem.id == queue_id).first()
        print(f"   Status: {it.status.value}")
        print(f"   PID: {it.pid}")
        print(f"   Worker ID: {it.worker_id}")
    finally:
        db.close()
    
    # 5. Start the job via API
    print("\n5️⃣ Starting the job...")
    res = client.post(f'/queue/{queue_id}/start', json={})
    assert res.status_code == 200, f"Failed to start: {res.get_json()}"
    result = res.get_json()
    print(f"   ✓ Job started: {result}")
    
    # 6. Wait a moment for process to start
    print("\n6️⃣ Waiting for process to start...")
    time.sleep(1)
    
    # 7. Check job status and worker record
    print("\n7️⃣ Checking queue item and worker records...")
    db = SessionLocal()
    try:
        it = db.query(QueueItem).filter(QueueItem.id == queue_id).first()
        print(f"   Queue Item #{it.id}:")
        print(f"     Status: {it.status.value}")
        print(f"     PID: {it.pid}")
        print(f"     Worker ID: {it.worker_id}")
        print(f"     Started at: {it.started_at}")
        
        if it.worker_id:
            wp = db.query(WorkerProcess).filter(WorkerProcess.id == it.worker_id).first()
            if wp:
                print(f"   Worker Process #{wp.id}:")
                print(f"     PID: {wp.pid}")
                print(f"     Log path: {wp.log_path}")
                print(f"     Log exists: {os.path.exists(wp.log_path) if wp.log_path else 'N/A'}")
                print(f"     Start time: {wp.start_time}")
                print(f"     End time: {wp.end_time}")
                
                # Try to read log file
                if wp.log_path and os.path.exists(wp.log_path):
                    print(f"\n   📄 Log file contents (first 500 chars):")
                    with open(wp.log_path, 'r') as f:
                        content = f.read()
                    print(f"   {content[:500]}")
                    if len(content) > 500:
                        print(f"   ... ({len(content)} total chars)")
    finally:
        db.close()
    
    # 8. Check if process is still running
    print("\n8️⃣ Checking if process is still running...")
    db = SessionLocal()
    try:
        it = db.query(QueueItem).filter(QueueItem.id == queue_id).first()
        if it.pid:
            try:
                result = subprocess.run(['ps', '-p', str(it.pid)], capture_output=True, text=True)
                if result.returncode == 0:
                    print(f"   ✓ Process {it.pid} is RUNNING")
                    print(f"   {result.stdout}")
                else:
                    print(f"   ✗ Process {it.pid} is NOT running (already exited)")
            except Exception as e:
                print(f"   Error checking process: {e}")
    finally:
        db.close()
    
    # 9. List all workers
    print("\n9️⃣ Getting worker list via API...")
    res = client.get('/workers')
    assert res.status_code == 200
    workers = res.get_json()
    print(f"   Found {len(workers)} worker(s)")
    for w in workers:
        print(f"     Worker #{w['id']}: PID={w['pid']}, Item={w['item_id']}, Status={w['exit_code']}")
    
    print("\n" + "=" * 70)
    print("✅ Debug complete. Check logs above to identify issues.")
    print("=" * 70)

if __name__ == '__main__':
    debug_worker_and_logs()
