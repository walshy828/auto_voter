# Cookie Isolation: Why Host Network Mode Doesn't Help

## The Misconception

**Assumption:** Using `network_mode: "host"` will give each thread a unique IP/network identity, resulting in unique cookies.

**Reality:** This doesn't work because:

1. **All threads still share the same source IP** - Even in host mode, all outbound connections from the container use the host's IP address
2. **Cookies are application-level** - Cookie generation happens at the HTTP layer, not the network layer
3. **Port conflicts** - Host mode causes both containers to fight over port 8080

## The Real Issue

Cookies might be shared because:

### 1. Server-Side Behavior
poll.fm might be:
- Generating cookies based on IP address
- Reusing cookies for same IP within a time window  
- Rate-limiting cookie generation per IP

### 2. Connection Pooling (Already Fixed)
Your recent changes to `auto_voter_simple.py` addressed this:
```python
# Force a fresh TCP connection every time
adapter = requests.adapters.HTTPAdapter(max_retries=1)
session.mount('http://', adapter)
session.mount('https://', adapter)

# Set the connection header to close
session.headers.update({'Connection': 'close'})
```

This is the **correct approach** - forces new TCP connections, prevents pooling.

## Actual Solutions for Cookie Isolation

### ✅ Already Implemented
1. **Fresh session per vote** - `session = requests.Session()` in loop
2. **Clear cookies** - `session.cookies.clear()`
3. **No connection pooling** - HTTPAdapter with max_retries=1
4. **Connection: close header** - Forces TCP close after each request
5. **Random timing** - Spreads requests across time

### ✅ Additional Options

#### Option 1: Use VPN Location Rotation
Since you have VPN, rotate locations between batches:
- Each batch uses different VPN server
- Different exit IP = different cookies
- Already implemented in `new_location()`

#### Option 2: Use TOR for Each Thread
Enable TOR with NEWNYM for each vote:
- Each thread gets new TOR circuit
- Different exit IP per vote
- Already supported via `use_tor` flag

#### Option 3: Verify Cookie Uniqueness
Enable debug mode to see if cookies are actually different:
```python
if JOB_DEBUG_ENABLED:
    log_detailed(f"[Thread {thread_id}] Received PD_REQ_AUTH: {PD_REQ_AUTH[:8]}...")
```

## Testing Cookie Isolation

### Step 1: Enable Debug Mode
Set `debug=true` when creating a queue item

### Step 2: Run Small Test
- 3 threads
- 2 votes per thread
- Check logs

### Step 3: Analyze Logs
Look for patterns like:
```
[Thread 0] Received PD_REQ_AUTH: abc12345...
[Thread 1] Received PD_REQ_AUTH: xyz67890...  ← Different = Good
[Thread 2] Received PD_REQ_AUTH: def24680...  ← Different = Good
```

If all cookies are **identical**, the issue is:
- Server generates cookies based on IP
- All threads share same IP (expected)
- Solution: Use VPN rotation or TOR

If cookies are **different**, isolation is working correctly!

## Why Cookies Might Legitimately Be the Same

**Important:** If poll.fm generates cookies based on IP address, then:
- All threads from same IP will get same cookie
- This is **server behavior**, not a bug in your code
- Solution: Rotate IP addresses (VPN/TOR)

## Current Status

### ✅ Fixed
- Removed `network_mode: "host"` (was causing port conflicts)
- Session isolation is correct
- Connection pooling disabled
- Fresh TCP connections per request

### ⏳ To Verify
1. Rebuild containers: `docker-compose build`
2. Restart: `docker-compose up -d`
3. Run test with debug=true
4. Check if cookies are unique

### 🎯 Next Steps If Cookies Still Shared

If debug logs show identical cookies across threads:

**Option A: Accept It**
- If server generates cookies by IP, this is expected
- Your vote counting should still work
- Cookies might just be for tracking, not validation

**Option B: Rotate IPs**
- Enable VPN rotation between batches (already implemented)
- Or enable TOR for each thread (already supported)

**Option C: Increase Timing Spread**
- Increase random delay before requests
- Server might generate new cookie if enough time passes

## Deployment

```bash
# Remove host network mode (already done)
# Rebuild containers
docker-compose build

# Restart services
docker-compose up -d

# Watch logs
docker-compose logs -f web
docker-compose logs -f scheduler
```

## Summary

- ❌ Host network mode doesn't help with cookies
- ✅ Application-level isolation is correct
- ✅ Connection pooling is disabled
- ⏳ Need to verify if cookies are actually shared
- 🎯 If shared, use VPN/TOR rotation (already available)
