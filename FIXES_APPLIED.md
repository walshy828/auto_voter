# 🔧 Fixes Applied for Worker & Log Streaming Issues

## Issues Identified & Fixed

### ✅ Issue #1: Socket.IO Background Task Database Error
**Problem**: `tail_log_for_client()` was querying the database after closing it (temporal dead zone).

**Fix Applied**: 
- Moved `db.close()` to the `finally` block
- Each database query in the loop now opens a fresh session
- Added proper error handling for missing log files

**File**: `app/worker.py` (line ~45)

### ✅ Issue #2: Worker Process Not Logging Debug Info
**Problem**: No way to diagnose why vote_start() hangs or never completes.

**Fix Applied**:
- Added detailed debug logging to `_run_vote_wrapper()`:
  - `[Worker {id}] Starting vote process...`
  - `[Worker {id}] Configuring: pollid=..., votes=..., threads=...`
  - `[Worker {id}] Calling vote_start(2)...`
  - `[Worker {id}] vote_start completed successfully`
  - Traceback on any errors

**File**: `app/worker.py` (line ~8)

### ✅ Issue #3: Socket.IO Handler Not Providing Feedback
**Problem**: No way to know if Socket.IO connection failed or if worker wasn't found.

**Fix Applied**:
- Added debug logging to Socket.IO handlers in `app/socketio_server.py`:
  - `[Socket.IO] Client connected: {sid}`
  - `[Socket.IO] subscribe_log received: worker_id=..., sid=...`
  - `[Socket.IO] Found worker: id=..., pid=..., log_path=...`
  - `[Socket.IO] ERROR: Worker X not found in DB`
  - `[Socket.IO] Starting background tail task...`
- Added verification that worker exists before tailing log
- Emits initial connection message to client

**File**: `app/socketio_server.py` (line ~12)

---

## New Debug Tools Created

### 1. **debug_worker.py** — Full End-to-End Test
Simulates a complete workflow and checks all components:
```bash
python3 debug_worker.py
```

Checks:
- ✓ Login works
- ✓ Poll creation
- ✓ Queue item creation
- ✓ Job startup
- ✓ Log file created and has content
- ✓ Worker process still running
- ✓ Worker metadata in database
- ✓ Workers API endpoint working

### 2. **test_vote_start.py** — Isolate Voting Script Issues
Tests if vote_start() hangs or completes:
```bash
python3 test_vote_start.py
```

Checks:
- ✓ auto_voter_queue module can be imported
- ✓ All required attributes exist
- ✓ vote_start() completes within 10 seconds (with timeout detection)

### 3. **TROUBLESHOOTING_WORKERS_AND_LOGS.md** — Comprehensive Guide
Step-by-step diagnosis for:
- Log streaming "Connecting..." never completes
- Worker process never finishes
- Log file exists but not streaming

---

## Recommended Next Steps

### 1️⃣ Run the Debug Script
```bash
cd /Users/dpw/Documents/Development/auto_voter
python3 debug_worker.py
```

This will tell you:
- Is the worker process starting? (look for `Status: running`)
- Is the log file being created? (look for `Log exists: True`)
- Does the log have content? (check log file contents section)

### 2️⃣ If Log File Empty or Missing
Run:
```bash
python3 test_vote_start.py
```

This will tell you:
- Does vote_start() complete, or does it hang?
- Are there errors in the voting script?

### 3️⃣ If Socket.IO Not Connecting
Check browser console (F12 → Console) for:
```
Socket.IO connected ✓
```

If not there, check server logs for:
```
[Socket.IO] Client connected: ...
```

### 4️⃣ If All Tests Pass But Logs Still Not Streaming
Check the log file manually while a job is running:
```bash
tail -f ./data/logs/job_*.log
```

You should see:
```
[Worker 1] Starting vote process...
[Worker 1] Configuring: pollid=999999, answerid=888888, votes=10...
[Worker 1] Calling vote_start(2)...
```

If nothing appears, stdout redirection is failing (check log directory permissions).

---

## Key Improvements Made

| Component | Before | After |
|-----------|--------|-------|
| **Worker logging** | Minimal | Detailed debug messages at each step |
| **Database handling** | Closed too early | Proper session management in loops |
| **Socket.IO feedback** | Silent failures | Clear error messages |
| **Debugging tools** | None | 3 new test scripts + troubleshooting guide |
| **Error handling** | Basic | Detailed error reporting with tracebacks |

---

## Files Modified

1. **app/worker.py**
   - ✅ Enhanced `_run_vote_wrapper()` with debug logging
   - ✅ Fixed `tail_log_for_client()` database session management

2. **app/socketio_server.py**
   - ✅ Added debug logging to all handlers
   - ✅ Added worker verification before tailing
   - ✅ Added initial connection confirmation message

3. **New files created**
   - ✅ `debug_worker.py` — Full workflow test
   - ✅ `test_vote_start.py` — Voting script isolation test
   - ✅ `TROUBLESHOOTING_WORKERS_AND_LOGS.md` — Comprehensive guide

---

## Expected Behavior After Fixes

### Scenario: Start a Job and View Logs

1. **Queue**: Job appears with status `queued`
2. **Click "Start"**: Status changes to `running`, PID appears
3. **Click "Workers" tab**: Worker appears with job reference
4. **Click "Log" button**: Modal opens, shows "Connecting..."
5. **Server logs show**:
   ```
   [Socket.IO] Client connected: socket_...
   [Socket.IO] subscribe_log received: worker_id=1, sid=...
   [Socket.IO] Found worker: id=1, pid=12345, log_path=./data/logs/job_1_...log
   [Socket.IO] Starting background tail task for worker 1
   [Worker 1] Starting vote process for item 1
   [Worker 1] Calling vote_start(2)...
   ```
6. **Log modal shows**:
   ```
   [Connected to worker 1]
   [Worker 1] Starting vote process for item 1
   [Worker 1] Configuring: pollid=999999, answerid=888888, votes=10, threads=1
   [Worker 1] Calling vote_start(2)...
   ```
7. **After vote_start() completes**:
   - Log shows: `[Worker 1] vote_start completed successfully`
   - Queue item status changes to `completed`
   - Modal closes (or shows final log)

---

## Quick Checklist

Before running a job, verify:
- [ ] Flask app is running: `python3 -m app.api`
- [ ] Browser is logged in (admin / password)
- [ ] SECRET_KEY is set: `echo $SECRET_KEY` (should not be empty)
- [ ] `./data/logs` directory exists: `ls -la ./data/logs`

Then run a job and check:
- [ ] Queue item starts (status → running)
- [ ] Log file created: `ls -la ./data/logs/job_*.log`
- [ ] Worker process visible: `ps aux | grep auto_voter_queue`
- [ ] Log modal shows content (not "Connecting..." forever)

---

## Summary

You now have:
✅ Enhanced logging to diagnose issues
✅ Fixed database session handling
✅ 3 debug scripts to isolate problems
✅ Comprehensive troubleshooting guide

**Run `python3 debug_worker.py` to start diagnosing!**
