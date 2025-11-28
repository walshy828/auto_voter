# 🔍 Troubleshooting: Worker Not Completing & Logs Not Streaming

## Issue #1: "Connecting..." Never Completes (No Log Output)

### Root Causes
1. **Worker process never started** → log file doesn't exist
2. **Worker process is hanging** → vote_start() never returns
3. **Log file exists but background task not tailing** → tail_log_for_client() has an issue
4. **Socket.IO not connected** → subscribe_log handler not called

### Diagnosis Steps

#### Step 1: Check if worker started (run the debug script)
```bash
cd /Users/dpw/Documents/Development/auto_voter
python3 debug_worker.py
```

This will:
- Create a poll
- Add a queue item
- Start a job
- Check log file exists
- Show worker process details

Look for:
- `Queue Item Status: running` (should be "running", not "queued")
- `PID: <number>` (should be a process ID, not None)
- `Log exists: True` (should be True)
- `Log file contents: [Worker] Starting...` (should show debug output)

#### Step 2: Check browser console
Open DevTools (F12) and look for:
```
Socket.IO connected
subscribe_log received: worker_id=1
Found worker: id=1, pid=12345, log_path=./data/logs/job_1_...log
Starting background tail task for worker 1
```

If you don't see these messages, Socket.IO connection failed.

#### Step 3: Check if vote_start() is hanging
Run this to see if the worker process hangs:
```bash
ps aux | grep auto_voter_queue
ps aux | grep vote_start
```

If process is alive and stuck, the voting script is likely hanging (waiting for network, Tor, etc.).

---

## Issue #2: Worker Never Completes

### Root Causes
1. **vote_start() takes a very long time** (normal for real voting)
2. **vote_start() is hanging/infinite loop** (bug in voting script)
3. **Monitor thread not running** (daemon thread exited early)

### Diagnosis Steps

#### Step 1: Check if monitor thread is tracking the worker
Look at logs when starting a job. You should see:
```
[Worker 1] Starting vote process for item 1
[Worker 1] Configuring: pollid=999999, answerid=88888, votes=10, threads=1
[Worker 1] Calling vote_start(2)...
```

If you see these, the worker started. Now wait to see:
```
[Worker 1] vote_start completed successfully
```

If you never see this, vote_start is hanging.

#### Step 2: Check auto_voter_queue.py
Open `app/auto_voter_queue.py` and look for:
- Long `for` loops
- Network requests (Tor, vpn connections)
- `time.sleep()` calls
- Infinite loops

For testing, you can mock vote_start() to return immediately:

```python
# In app/auto_voter_queue.py, comment out real vote_start
def vote_start(mode):
    print(f"MOCK vote_start called with mode={mode}")
    print("Sleeping for 3 seconds...")
    import time
    time.sleep(3)
    print("MOCK vote_start completed!")
    # Don't call the real voting code for now
```

#### Step 3: Check if the database is updating
Run this while a job is running:
```bash
sqlite3 ./data/auto_voter.db "SELECT id, status, exit_code, completed_at FROM queue_items ORDER BY id DESC LIMIT 3;"
```

You should see:
- `id=X, status=running, exit_code=NULL, completed_at=NULL` (currently running)
- Once done: `id=X, status=completed, exit_code=0, completed_at=2025-11-26 ...`

If status stays "running" forever, the monitor thread isn't updating the DB.

---

## Issue #3: Log File Exists But Not Streaming

### Root Causes
1. **Socket.IO handler exception** (check server logs)
2. **Log file not being written** (stdout/stderr redirection failing)
3. **tail_log_for_client() exiting early** (database session issue)

### Diagnosis Steps

#### Step 1: Check server logs
Look at the Flask/Socket.IO server terminal for errors like:
```
[Socket.IO] ERROR: Worker 1 not found in DB
[Socket.IO] subscribe_log received: worker_id=1, sid=...
[stream error] [errno 2] No such file or directory: './data/logs/...'
```

#### Step 2: Manually check log file
While job is running:
```bash
tail -f ./data/logs/job_*.log
```

You should see:
```
[Worker 1] Starting vote process for item 1
[Worker 1] Configuring: pollid=999999...
[Worker 1] Calling vote_start(2)...
```

If file is empty or doesn't exist, stdout redirection failed.

#### Step 3: Test Socket.IO connection manually
In browser console:
```javascript
// Check if Socket.IO connected
console.log('Socket connected:', socket && socketConnected);

// Manually emit subscribe_log
socket.emit('subscribe_log', {worker_id: 1});

// Check for log_line events
socket.on('log_line', (data) => console.log('LOG:', data));
```

---

## Quick Fixes

### Fix #1: Mock vote_start() for testing
Edit `app/auto_voter_queue.py`:
```python
def vote_start(mode):
    """Temporary mock for testing."""
    print("Starting mock vote_start...")
    import time
    for i in range(5):
        print(f"Progress: {i+1}/5")
        time.sleep(1)
    print("Mock vote_start completed!")
```

Then retry. Logs should appear immediately.

### Fix #2: Check SECRET_KEY is set
```bash
echo "SECRET_KEY=$SECRET_KEY"
```

If empty, Socket.IO won't connect. Set it:
```bash
export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
```

### Fix #3: Increase worker timeout
Some voting scripts take a long time. Try with smaller vote count:
```
Votes: 5
Threads: 1
Per run: 1
Pause: 1
```

### Fix #4: Check log directory permissions
```bash
ls -la ./data/logs/
chmod 755 ./data/logs
```

---

## Debug Output Checklist

After running `debug_worker.py`, check for:

- [ ] "Poll created" ✓
- [ ] "Queue item created" ✓
- [ ] "Job started" ✓ (HTTP 200)
- [ ] "Status: running" (not queued)
- [ ] "PID: <number>" (not None)
- [ ] "Log exists: True"
- [ ] "Log file contents: [Worker] Starting..." (not empty)
- [ ] "Process ... is RUNNING" (or "NOT running" if completed)

If any of these are missing/wrong, note which one and refer to diagnosis steps above.

---

## Test Without Vote Script

To isolate the issue, try this minimal test:
```bash
python3 -c "
import os, time, multiprocessing, sys
os.environ['ADMIN_USER'] = 'admin'
os.environ['ADMIN_PASS'] = 'pass'

from app.api import app

# Create log dir
os.makedirs('./data/logs', exist_ok=True)

# Minimal worker test
def test_worker():
    log_path = './data/logs/test_minimal.log'
    with open(log_path, 'w') as f:
        f.write('[TEST] Worker started\n')
        f.flush()
        for i in range(5):
            f.write(f'[TEST] Step {i+1}/5\n')
            f.flush()
            time.sleep(1)
        f.write('[TEST] Worker completed\n')
    print('Test worker finished')

# Run test
proc = multiprocessing.Process(target=test_worker)
proc.start()
print('Process started, PID:', proc.pid)
proc.join()
print('Process exited with code:', proc.exitcode)

# Check log
with open('./data/logs/test_minimal.log', 'r') as f:
    print('Log contents:')
    print(f.read())
"
```

This creates a minimal worker that writes to a log file. If this works, the issue is in auto_voter_queue.py.

---

## Next Steps

1. Run `debug_worker.py` and share output
2. Check browser console for Socket.IO messages
3. Check server logs for errors
4. Try with mocked vote_start() if voting script hangs
5. Check log directory permissions and contents

---

**Need help? Share the output from `debug_worker.py` and browser console!**
