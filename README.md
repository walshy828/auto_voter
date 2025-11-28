# Auto Voter — Web UI

This repository contains a small Flask web UI and worker to manage polls and a queue of voting jobs.

Quick start (local, development):

1. Create and activate a virtualenv

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies

```bash
pip install -r requirements.txt
```

3. Run the Flask app

```bash
export FLASK_APP=app.api:app
flask run --host=0.0.0.0 --port=8080
```

Open http://localhost:8080/ to use the admin UI.

Scheduler behavior

- The app includes a BackgroundScheduler (APScheduler) that periodically (every 30s) picks the next queued item and starts it.
- The scheduler will start automatically when the app imports `app.api`. An environment flag prevents duplicate starts in simple setups. If you run multiple Gunicorn workers you may want to run the scheduler in a single dedicated process instead.

Standalone scheduler service

- A dedicated scheduler implementation is provided at `app/scheduler_service.py`. Run that separately under a process manager (supervisord/systemd/container) to avoid scheduler duplication across web workers.

Example supervisord program stanza:

```
[program:auto_voter_scheduler]
; run from repository root
command=/path/to/venv/bin/python /app/app/scheduler_service.py
directory=/app
autostart=true
autorestart=true
stderr_logfile=/var/log/auto_voter_scheduler.err.log
stdout_logfile=/var/log/auto_voter_scheduler.out.log
```

Worker control and cancellation

- When a queue item is started the worker PID is persisted in the DB (`queue_items.pid`).
- A monitor thread updates the DB record when the worker process exits, setting `status` and `exit_code`.
- You can cancel a running queue item; this will send SIGTERM to the worker PID and mark the item canceled.

Docker

Build and run the container (example):

```bash
docker build -t auto_voter_webapp .
docker run -p 8080:8080 -v "$(pwd)/data:/app/data" auto_voter_webapp
```

Notes

- The database is SQLite by default and stored at `./data/auto_voter.db`. You can change the DB via `AUTO_VOTER_DB` env var.
- If you previously ran the app and the DB schema lacks the new columns (`pid`, `exit_code`) you may need to recreate the DB or run an ALTER TABLE migration.

Alembic migrations

Alembic is wired to the project. Configure the DB url via the `AUTO_VOTER_DB` env var or set `sqlalchemy.url` in `alembic.ini`. To run migrations:

```bash
pip install -r requirements.txt
alembic upgrade head
```

This repository includes an initial migration at `alembic/versions/0001_initial.py`.

Logs per job

- Worker logs are written to `./data/logs` by default. Each job gets a `job_<item>_<timestamp>.log` file. You can view logs via the API endpoint `/workers/<id>/log` or from the filesystem.

Testing
-------

To run the integration and unit tests:

```bash
make test
```

Or run them individually:

```bash
python3 test_login.py
python3 test_integration.py
python3 test_socketio.py
```

Note: `test_vote_start.py` requires a VPN connection and external resources, so it is not included in the default test suite.

