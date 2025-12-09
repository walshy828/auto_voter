# Scheduler Fix Deployment Guide

## Problem
Scheduler is stuck with "maximum number of running instances reached (1)" error.
First `pick_and_start()` call hangs forever, blocking all subsequent runs.

## Fixes Applied

### 1. Added `max_instances=3`
Allows APScheduler to run up to 3 concurrent instances instead of default 1.
If one hangs, others can still run.

### 2. Delayed First Run by 5 Seconds
Gives zombie cleanup and initialization time to complete before first scheduler run.

### 3. Added Entry Logging
Prints timestamp when `pick_and_start()` is called to verify function execution.

### 4. Non-Blocking Lock (Already Present)
Uses `LOCK_NB` flag to skip cycle if lock can't be acquired instead of blocking forever.

## Deployment Steps

### Option 1: Rebuild Docker Image (Recommended)

```bash
# Navigate to project directory
cd /Users/dpw/Documents/Development/auto_voter

# Rebuild scheduler container
docker-compose build scheduler

# Restart scheduler container
docker-compose restart scheduler

# Watch logs
docker-compose logs -f scheduler
```

### Option 2: Restart Existing Container (If Code is Mounted)

```bash
# If your docker-compose mounts the code directory
docker-compose restart scheduler

# Watch logs
docker-compose logs -f scheduler
```

### Option 3: Manual Container Restart

```bash
# Find scheduler container name
docker ps | grep scheduler

# Restart it
docker restart <scheduler_container_name>

# Watch logs
docker logs -f <scheduler_container_name>
```

## Expected Logs After Fix

```
[Scheduler Service] Starting main()...
[Scheduler Service] Zombie job cleanup started in background
[Scheduler Service] BlockingScheduler created
[Scheduler Service] Queue scheduler started, interval=30s, max_instances=3, first_run=2025-12-09 13:55:05
[Scheduler Service] Starting scheduler loop...
[Scheduler Service] pick_and_start() ENTRY at 2025-12-09 13:55:05  ← NEW
[Scheduler Service] pick_and_start() called (Locked)
[Scheduler Service] Checking for queued items...
[Scheduler Service] No queued items found
[Scheduler Service] Lock released  ← NEW
[Scheduler Service] pick_and_start() ENTRY at 2025-12-09 13:55:35  ← 30s later
...
```

## Verification Checklist

- [ ] See "ENTRY" message every 30 seconds
- [ ] See "Lock released" after each run
- [ ] NO "maximum number of running instances" errors
- [ ] Runs happen every 30 seconds (not 60)
- [ ] First run happens 5 seconds after startup (not immediately)

## If Still Stuck

### Check 1: Is Function Being Called?
```bash
docker logs <scheduler_container> | grep "ENTRY"
```
- If NO output → APScheduler itself is broken, check for Python errors
- If YES → Function is being called, check next step

### Check 2: Is Function Completing?
```bash
docker logs <scheduler_container> | grep "Lock released"
```
- If NO output → Function is hanging inside, check for VPN/DB locks
- If YES → Function completes successfully

### Check 3: Database Status
```bash
# Check for stuck jobs
docker exec <scheduler_container> sqlite3 /app/data/auto_voter.db \
  "SELECT id, status, queue_name FROM queue_items WHERE status='running';"
```
- If any results → Manually reset them to 'queued'

### Check 4: Force Clean Start
```bash
# Stop scheduler
docker-compose stop scheduler

# Remove lock file
docker-compose run --rm scheduler rm -f /app/data/scheduler.lock

# Start scheduler
docker-compose start scheduler
```

## Troubleshooting

### Problem: Still seeing "maximum instances" error
**Solution:** Code wasn't rebuilt. Run `docker-compose build scheduler` first.

### Problem: Runs every 60s instead of 30s
**Cause:** `config_manager` job hasn't picked up new interval yet.
**Solution:** Wait 30 seconds for config to refresh, or restart scheduler.

### Problem: Worker count stuck at 1
**Cause:** Same as above - config not refreshed.
**Solution:** Check `system_settings` table for `max_concurrent_workers` value.

### Problem: VPN check times out
**Logs:** `VPN check timed out after 90s`
**Solution:** VPN is having issues. Check ExpressVPN status manually:
```bash
docker exec <scheduler_container> expressvpn status
```

## Rollback

If fixes cause issues, revert to previous version:

```bash
git checkout HEAD~1 app/scheduler_service.py
docker-compose build scheduler
docker-compose restart scheduler
```
