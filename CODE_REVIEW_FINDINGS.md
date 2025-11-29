# Code Review Findings & Recommendations

## Executive Summary
Found multiple areas for optimization:
- **20+ test/debug scripts** that can be moved to a `/scripts` directory
- **Hardcoded credentials** in `config.py` that should use environment variables
- **Duplicate configuration** between files
- **Opportunities** to consolidate settings into the UI

## Critical Issues

### 1. Hardcoded Credentials in `config.py`
**Risk: HIGH** - Security vulnerability

**Current State:**
```python
INFLUX_URL = "http://192.168.90.130:8086"
INFLUX_TOKEN = "J47-RkivTj-rstcved53KzVukr4to1e99pU6af9QtBuZ5At80QbW9HOfrfUl1-NsLlhRgtF3rRFgTaBpZv8w6A=="
INFLUX_ORG = "walshy"
INFLUX_BUCKET = "voter"
```

**Recommendation:**
- Move to environment variables
- Add to SystemSettings table for UI management
- Keep `.env` file in `.gitignore`

### 2. Stale Hardcoded Poll Data
**Risk: MEDIUM** - Unused code

**Current State:**
```python
polls = [
    ["KevinMorinSutton", "16237736","71375890",""],
    ["JoaoDaSilvaMarlborough", "16237736","71375881",""],
    ["AlexDeschaineAlgonquin", "16237736","71375882",""],
]
```

**Recommendation:**
- **REMOVE** - Polls are now managed via database
- This appears to be legacy code from before the UI was built

### 3. Test/Debug Scripts Clutter
**Risk: LOW** - Organization issue

**Files to relocate:**
```
debug_worker.py
inspect_stuck.py  
reproduce_error.py
reproduce_vpn_error.py
reset_stuck_items.py
test_*.py (7 files)
verify_*.py (2 files)
```

**Recommendation:**
- Create `/scripts` directory
- Move all test/debug scripts there
- Update `.dockerignore` to exclude `/scripts`

### 4. Migration Scripts
**Risk: LOW** - Can be archived

**Files:**
```
migrate_poll_results.py
migrate_poll_scheduler_config.py
migrate_poll_snapshots.py
migrate_progress_tracking.py
migrate_settings.py
migrate_use_tor.py
```

**Recommendation:**
- Move to `/scripts/migrations/`
- These are one-time scripts, keep for reference but exclude from Docker

## Configuration Consolidation

### Settings to Move to UI

#### InfluxDB Settings
- URL
- Token  
- Organization
- Bucket

#### VPN/Proxy Settings
- VPN mode (US only vs expanded)
- Max votes per VPN
- Cooldown settings
- VPN location list (could be JSON in settings)

#### Voting Behavior
- `cntToPause` - votes before long pause
- `longPauseSeconds` - duration of long pause
- `CoolDownCount` - cooldown iterations
- `Cooldown` - cooldown duration

#### User Agents
- Store as JSON array in settings
- Allow UI editing

## Code Efficiency Issues

### Database Session Management
**Location:** Multiple files

**Issue:** Some functions create sessions without proper cleanup

**Example from `vote_results_influx_scheduler.py`:**
```python
db = SessionLocal()
# ... code ...
db.close()  # Should be in finally block
```

**Recommendation:**
Use context managers:
```python
with SessionLocal() as db:
    # ... code ...
```

### Duplicate VPN Location Lists
**Issue:** VPN locations defined in `config.py` but may also be in other files

**Recommendation:**
- Single source of truth in SystemSettings
- Load once at startup, cache in memory

## Proposed Changes

### Phase 1: Safety & Security (High Priority)
1. Move credentials to environment variables
2. Remove hardcoded poll data
3. Add `.env.example` file for documentation

### Phase 2: Organization (Medium Priority)
1. Create `/scripts` directory structure
2. Move test/debug files
3. Update documentation

### Phase 3: Settings UI (Medium Priority)
1. Create Settings page in UI
2. Add InfluxDB configuration
3. Add voting behavior settings
4. Add VPN/proxy settings

### Phase 4: Code Cleanup (Low Priority)
1. Refactor database session management
2. Remove unused imports
3. Add type hints where missing
4. Consolidate duplicate code

## Files Requiring Changes

### Immediate Changes
- `app/config.py` - Remove credentials, move to env vars
- `.env.example` - Create with template
- `.gitignore` - Ensure `.env` is excluded

### UI Changes
- `app/api.py` - Add settings endpoints
- `app/templates/index.html` - Add settings modal
- `app/static/app.js` - Add settings UI logic

### Database
- `app/models.py` - Potentially expand SystemSetting model
- Migration script - Add default settings

## Risk Assessment

| Change | Risk | Impact | Effort |
|--------|------|--------|--------|
| Remove hardcoded polls | Low | Low | 5 min |
| Move credentials to env | Low | High | 15 min |
| Reorganize scripts | Low | Low | 10 min |
| Add settings UI | Medium | High | 2-3 hours |
| Refactor DB sessions | Medium | Medium | 1-2 hours |

## Next Steps

1. Review and approve this plan
2. Implement Phase 1 changes (security)
3. Test thoroughly
4. Proceed with subsequent phases
