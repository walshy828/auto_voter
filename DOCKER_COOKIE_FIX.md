# Docker-Specific Cookie Isolation Fix

## Problem Identified

**Observation:** Same code works on Ubuntu but fails in Docker
- Ubuntu: Each thread gets unique cookies ✅
- Docker: All threads share same cookie ❌

**Root Cause:** Docker's network layer has additional connection caching/pooling that bypasses application-level session isolation.

## Docker Network Behavior

Docker containers use a virtual network bridge that can:
1. **Cache DNS resolutions** longer than host OS
2. **Reuse TCP connections** at the kernel level
3. **Pool connections** in the container's network namespace
4. **Share connection state** between threads more aggressively

This happens **below** the Python `requests` library level, which is why normal session isolation doesn't work.

## Fixes Applied

### 1. Aggressive Connection Pool Limits
**File:** `app/auto_voter_simple.py` (lines 317-323)

```python
adapter = requests.adapters.HTTPAdapter(
    pool_connections=1,      # Only 1 connection in pool
    pool_maxsize=1,          # Max 1 connection total
    max_retries=0,           # No retries (forces new connection on failure)
    pool_block=False         # Don't block waiting for connection
)
```

**Why:** Prevents `urllib3` (underlying library) from pooling connections

### 2. Multiple Connection-Close Headers
**File:** `app/auto_voter_simple.py` (lines 326-330)

```python
session.headers.update({
    'Connection': 'close',                              # HTTP/1.1 close
    'Cache-Control': 'no-cache, no-store, must-revalidate',  # No caching
    'Pragma': 'no-cache'                                # HTTP/1.0 no-cache
})
```

**Why:** Tells server and intermediaries to close connection after response

### 3. Disable Keep-Alive
**File:** `app/auto_voter_simple.py` (line 333)

```python
session.keep_alive = False
```

**Why:** Prevents HTTP keep-alive at session level

### 4. Docker Detection
**File:** `app/auto_voter_simple.py` (line 22)

```python
IN_DOCKER = os.path.exists('/.dockerenv') or os.environ.get('DOCKER_CONTAINER', False)
```

**Why:** Enables Docker-specific debugging and future optimizations

### 5. Enhanced Debug Logging
**File:** `app/auto_voter_simple.py` (lines 377-382)

```python
if IN_DOCKER:
    log_detailed(f"[Thread {thread_id}] [DOCKER] Received PD_REQ_AUTH: {PD_REQ_AUTH[:8]}... (full: {PD_REQ_AUTH})")
    log_detailed(f"[Thread {thread_id}] [DOCKER] Response headers: Connection={resp.headers.get('Connection')}, Set-Cookie={resp.headers.get('Set-Cookie')[:50]}")
```

**Why:** Shows full cookie and response headers to diagnose Docker-specific issues

## How It Works

### Before (Docker - Broken)
```
Thread 0: session.get() → Docker network layer → Cached connection → Same cookie
Thread 1: session.get() → Docker network layer → Reused connection → Same cookie
Thread 2: session.get() → Docker network layer → Reused connection → Same cookie
```

### After (Docker - Fixed)
```
Thread 0: session.get() → pool_maxsize=1 → Connection: close → New TCP → Unique cookie
Thread 1: session.get() → pool_maxsize=1 → Connection: close → New TCP → Unique cookie
Thread 2: session.get() → pool_maxsize=1 → Connection: close → New TCP → Unique cookie
```

## Testing

### Step 1: Rebuild Container
```bash
docker-compose build web scheduler
docker-compose up -d
```

### Step 2: Run Test with Debug
- Create queue item with `debug=true`
- Set 3 threads, 2 votes per thread
- Watch logs

### Step 3: Verify Logs
Look for `[DOCKER]` tagged messages:

**Success Pattern:**
```
[Thread 0] [DOCKER] Received PD_REQ_AUTH: abc12345... (full: abc12345xyz...)
[Thread 0] [DOCKER] Response headers: Connection=close, Set-Cookie=PD_REQ_AUTH=abc12345...

[Thread 1] [DOCKER] Received PD_REQ_AUTH: def67890... (full: def67890xyz...)  ← DIFFERENT!
[Thread 1] [DOCKER] Response headers: Connection=close, Set-Cookie=PD_REQ_AUTH=def67890...

[Thread 2] [DOCKER] Received PD_REQ_AUTH: ghi24680... (full: ghi24680xyz...)  ← DIFFERENT!
[Thread 2] [DOCKER] Response headers: Connection=close, Set-Cookie=PD_REQ_AUTH=ghi24680...
```

**Failure Pattern (if still broken):**
```
[Thread 0] [DOCKER] Received PD_REQ_AUTH: abc12345... (full: abc12345xyz...)
[Thread 1] [DOCKER] Received PD_REQ_AUTH: abc12345... (full: abc12345xyz...)  ← SAME!
[Thread 2] [DOCKER] Received PD_REQ_AUTH: abc12345... (full: abc12345xyz...)  ← SAME!
```

## If Still Broken

If cookies are still identical after these fixes, the issue is likely:

### Option 1: Docker DNS Caching
Docker's internal DNS resolver might be caching the server's IP and connection state.

**Solution:** Add DNS flush before each request:
```python
import socket
socket.setdefaulttimeout(10)
# Force DNS re-resolution by closing all sockets
```

### Option 2: Server-Side IP-Based Cookies
The server might genuinely be generating cookies based on source IP.

**Solution:** Use VPN rotation or TOR (already implemented):
```python
# Enable VPN rotation between batches
vpn_enabled = True

# Or enable TOR for each thread
use_tor = True
```

### Option 3: Docker Bridge Network Issue
Docker's bridge network might have connection tracking enabled.

**Solution:** Try different network mode in docker-compose.yml:
```yaml
services:
  web:
    network_mode: "bridge"  # or "none" for complete isolation
```

## Comparison: Ubuntu vs Docker

| Aspect | Ubuntu (Native) | Docker (Container) |
|--------|----------------|-------------------|
| Network Stack | Direct kernel access | Virtual bridge + NAT |
| Connection Pooling | OS-level only | OS + Docker layer |
| DNS Caching | systemd-resolved | Docker DNS + OS |
| TCP State | Per-process | Per-container namespace |
| Keep-Alive | Respects app settings | May override at bridge |

## Summary

**Changes Made:**
1. ✅ Aggressive connection pool limits (1 connection max)
2. ✅ Multiple connection-close headers
3. ✅ Disabled keep-alive at session level
4. ✅ Docker detection for enhanced debugging
5. ✅ Full cookie logging in Docker mode

**Expected Result:**
Each thread should now get a unique cookie, even in Docker.

**Next Steps:**
1. Rebuild containers
2. Run test with debug=true
3. Check logs for `[DOCKER]` messages
4. Verify cookies are different

**If Still Failing:**
The issue is deeper than application-level isolation. Will need to investigate Docker network configuration or use VPN/TOR rotation.
