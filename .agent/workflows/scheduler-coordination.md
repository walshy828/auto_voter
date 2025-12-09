---
description: How scheduler coordination works between web and scheduler containers
---

# Scheduler Service Coordination

## Overview
The auto-voter system uses a **multi-container architecture** where the web service and scheduler service run in separate Docker containers. They coordinate through the **shared database** using specific `SystemSetting` keys.

## Architecture

### Containers
1. **Web Container** (`app/api.py`)
   - Serves the web UI
   - Handles user requests
   - Communicates with scheduler via database flags

2. **Scheduler Container** (`app/scheduler_service.py`)
   - Runs the BlockingScheduler
   - Processes queue items
   - Updates status in database

### Database Coordination Keys

The following `SystemSetting` keys are used for coordination:

| Key | Type | Updated By | Read By | Purpose |
|-----|------|------------|---------|---------|
| `scheduler_last_run` | ISO timestamp | Scheduler | Web | Tracks when scheduler last ran |
| `scheduler_next_run` | ISO timestamp | Scheduler | Web | Indicates next scheduled run |
| `scheduler_trigger_requested` | boolean ('true'/'false') | Web | Scheduler | Manual trigger flag |

## How It Works

### Status Display
1. Web UI calls `/scheduler/run-info` endpoint
2. API reads `scheduler_last_run` and `scheduler_next_run` from database
3. UI displays:
   - **Status**: Running (if last_run < 5 min ago), Stale (if > 5 min), Unknown
   - **Last Run**: Timestamp of last execution
   - **Next Run**: Calculated next execution time

### Manual Trigger
1. User clicks "Trigger Now" button in web UI
2. Web UI calls `/scheduler/trigger` endpoint (POST)
3. API sets `scheduler_trigger_requested = 'true'` in database
4. Scheduler service checks this flag on each run
5. If flag is set, scheduler processes immediately and clears the flag

### Scheduler Execution Flow

Each time `pick_and_start()` runs:
1. **Update last_run**: Set `scheduler_last_run` to current time
2. **Check trigger flag**: If `scheduler_trigger_requested = true`, clear it
3. **Process queue**: Pick and start queued items as normal
4. **Update next_run**: Calculate and set `scheduler_next_run` based on interval

## Benefits

✅ **No Freezing**: Web doesn't call scheduler directly, avoiding blocking
✅ **Container Independence**: Services can restart independently
✅ **Real-time Status**: Web always shows current scheduler state
✅ **Manual Control**: Users can trigger scheduler without direct access

## Troubleshooting

### Status shows "STALE"
- Scheduler container might be stopped
- Check scheduler container logs: `docker logs <scheduler_container>`
- Verify scheduler service is running

### "Trigger Now" doesn't work
- Check web container can write to database
- Check scheduler container is polling database
- Verify `scheduler_trigger_requested` flag is being set and cleared

### Times not updating
- Ensure both containers share the same database
- Check database connectivity from both containers
- Verify `SystemSetting` table exists and is accessible
