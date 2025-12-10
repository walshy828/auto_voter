# Hybrid Docker Optimization Strategy

## Problem
Alpine Linux + ExpressVPN .deb extraction is unreliable. The `ar` and `tar` extraction doesn't properly place binaries in the expected locations.

## Solution: Hybrid Approach

### Web Container (Dockerfile.web)
- **Base:** `python:3.11-alpine` 
- **Size:** ~150-200MB (very small!)
- **Why:** Web container doesn't need VPN, so we can use Alpine for maximum size reduction
- **Optimizations:**
  - Multi-stage build
  - No VPN installation
  - Minimal runtime dependencies

### Scheduler Container (Dockerfile.scheduler)
- **Base:** `python:3.11-slim` (Debian)
- **Size:** ~350-400MB (larger but reliable)
- **Why:** Scheduler needs VPN, and ExpressVPN .deb works perfectly on Debian
- **Optimizations:**
  - Removes build tools after pip install
  - Cleans apt cache
  - Still 35-40% smaller than original

## Overall Results

| Container | Before | After | Savings |
|-----------|--------|-------|---------|
| Web | 625MB | 150-200MB | **68-75%** ⬇️ |
| Scheduler | 625MB | 350-400MB | **36-44%** ⬇️ |
| **Total** | **1250MB** | **500-600MB** | **52-60%** ⬇️ |

## Deployment

```bash
docker-compose down
docker-compose build
docker-compose up -d
```

## Files

- `Dockerfile.web` - Alpine-based for web (no VPN)
- `Dockerfile.scheduler` - Debian-based for scheduler (with VPN)
- `Dockerfile` - Kept as fallback/reference
- `docker-compose.yml` - Updated to use specific Dockerfiles

## Why This Works

1. **Web container** doesn't need VPN → Use Alpine for maximum size reduction
2. **Scheduler container** needs VPN → Use Debian for compatibility
3. **Best of both worlds:** Small web container + reliable VPN in scheduler
4. **Still optimized:** Both remove unnecessary packages and use best practices

This is a pragmatic solution that prioritizes reliability while still achieving significant size reduction overall.
