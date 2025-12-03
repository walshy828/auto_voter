# Docker Deployment Guide - Vote Trend Indicators

## Overview

The vote trend indicators feature requires new database columns. This guide explains how to deploy the changes to a Docker server.

## Files Included

### 1. Database Migration
- **`migrate_add_trend_fields.py`** - Standalone migration script
- **`alembic/versions/0002_trend_fields.py`** - Alembic migration (alternative)

### 2. Code Changes
- `app/models.py` - Added trend fields to Poll model
- `app/api.py` - Updated API to include trend data
- `app/vote_results_influx_scheduler.py` - Trend calculation logic
- `app/static/app.js` - Frontend display with visual indicators

## Deployment Steps

### Option 1: Automatic Migration (Recommended)

The application will automatically create new columns when it starts using SQLAlchemy's `create_all()`:

```bash
# Pull latest code
git pull

# Restart Docker container
docker-compose restart
```

**Note:** This works for **new columns only**. If the `polls` table already exists, you need Option 2.

### Option 2: Manual Migration Script

For existing databases, run the migration script:

```bash
# Copy migration script to container
docker cp migrate_add_trend_fields.py <container_name>:/app/

# Run migration inside container
docker exec <container_name> python3 migrate_add_trend_fields.py

# Restart application
docker-compose restart
```

### Option 3: Using Alembic

If you prefer Alembic migrations:

```bash
# Inside container or on host
alembic upgrade head
```

## Verification

After deployment, verify the changes:

1. **Check database schema:**
   ```bash
   docker exec <container_name> sqlite3 /app/data/auto_voter.db ".schema polls"
   ```
   
   You should see:
   - `previous_place INTEGER`
   - `place_trend VARCHAR(10)`
   - `votes_ahead_second INTEGER`

2. **Refresh poll results:**
   - Navigate to Polls page
   - Click "Refresh Results" on any poll
   - Verify trend indicators appear (↑/↓/→/★)

3. **Check API response:**
   ```bash
   curl http://localhost:5000/polls
   ```
   
   Response should include new fields:
   ```json
   {
     "previous_place": null,
     "place_trend": "new",
     "votes_ahead_second": 45
   }
   ```

## Rollback

If you need to rollback:

```bash
# Remove columns (SQLite)
docker exec <container_name> sqlite3 /app/data/auto_voter.db \
  "ALTER TABLE polls DROP COLUMN previous_place; \
   ALTER TABLE polls DROP COLUMN place_trend; \
   ALTER TABLE polls DROP COLUMN votes_ahead_second;"
```

**Note:** SQLite doesn't support DROP COLUMN in older versions. You may need to recreate the table.

## Environment Variables

No new environment variables are required. The feature uses existing database configuration:
- `AUTO_VOTER_DB` - Database connection string (default: `sqlite:///./data/auto_voter.db`)

## Troubleshooting

### Issue: Columns already exist error
**Solution:** The migration script checks for existing columns and skips them. Safe to re-run.

### Issue: No trend indicators showing
**Solution:** 
1. Refresh poll results to populate trend data
2. Check browser console for JavaScript errors
3. Verify API returns new fields

### Issue: Database locked
**Solution:** Stop the application before running migrations:
```bash
docker-compose stop
docker exec <container_name> python3 migrate_add_trend_fields.py
docker-compose start
```
