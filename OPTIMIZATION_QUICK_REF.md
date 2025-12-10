# Docker & Code Optimization Quick Reference

## 🚀 Quick Deploy

```bash
# Automated deployment (recommended)
./deploy_optimizations.sh

# Manual deployment
docker build -f Dockerfile.optimized -t auto_voter:optimized .
docker tag auto_voter:optimized auto_voter:latest
docker-compose -f docker-compose.optimized.yml up -d
```

## 📊 Expected Improvements

| Metric | Improvement |
|--------|-------------|
| Image Size | 625MB → 275-325MB (**50-60%** ⬇️) |
| Memory Usage | **25-35%** ⬇️ |
| CPU (Idle) | **50%** ⬇️ |
| API Response | **20-30%** ⬆️ |
| DB Queries | **80%** ⬇️ |
| Startup Time | **30%** ⬆️ |

## 📁 Files Created

- `Dockerfile.optimized` - Multi-stage Alpine build
- `docker-compose.optimized.yml` - Resource-limited config
- `app/utils/db_helpers.py` - Database utilities with caching
- `.env.production` - Production environment template
- `deploy_optimizations.sh` - Automated deployment script

## 📝 Files Modified

- `requirements.txt` - Removed 3 unused deps, pinned versions
- `.dockerignore` - Added more exclusions
- `app/scheduler_service.py` - Uses cached settings

## ✅ Verification Commands

```bash
# Check image size
docker images auto_voter:optimized

# Monitor resources
docker stats --no-stream

# Test functionality
curl http://localhost:8282/api/polls

# View logs
docker-compose logs -f scheduler
```

## 🔄 Rollback

```bash
# Quick rollback
docker-compose -f docker-compose.optimized.yml down
docker-compose up -d

# Full rollback with data restore
sudo cp -r /docker/auto_voter/data_backup /docker/auto_voter/data
docker-compose up -d
```

## 🐛 Common Issues

**Alpine build fails:**
```bash
# Check package names (apk vs apt-get)
# See Dockerfile.optimized for mappings
```

**VPN not working:**
```bash
# Check logs
docker-compose logs scheduler | grep -i vpn

# Fallback to original Dockerfile for scheduler
```

**Memory limits too low:**
```yaml
# Edit docker-compose.optimized.yml
limits:
  memory: 1024M  # Increase as needed
```

## 📚 Documentation

- **Implementation Plan:** `implementation_plan.md`
- **Walkthrough:** `walkthrough.md`
- **Scheduler Optimization:** `SCHEDULER_OPTIMIZATION.md`

## 🎯 Key Optimizations

1. **Multi-stage Docker build** - Discards build tools
2. **Alpine Linux base** - 5MB vs 150MB
3. **Cached settings** - 5min TTL, 80% fewer queries
4. **Lazy imports** - Faster startup
5. **Resource limits** - Prevents bloat
6. **Version pinning** - Reproducible builds

## 💡 Tips

- Monitor for 24-48 hours before production
- Use `deploy_optimizations.sh` for safe deployment
- Keep backups before deploying
- Check logs for any errors after deployment
- Adjust resource limits based on your workload

---

**Need help?** See `walkthrough.md` for detailed troubleshooting.
