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

## Environment Variables

Create a `.env` file in the root directory to configure the application. See `.env.example` for a template.

| Variable | Default | Description |
|----------|---------|-------------|
| **General** | | |
| `FLASK_ENV` | `production` | Flask environment (development/production) |
| `FLASK_SECRET_KEY` | `dev-secret...` | Secret key for Flask sessions |
| `DEBUG_MODE` | `false` | Enable verbose debug logging |
| **Authentication** | | |
| `ADMIN_USER` | `admin` | Username for admin access |
| `ADMIN_PASS` | `test` | Password for admin access |
| `ADMIN_TOKEN` | - | Optional token for API authentication |
| **Database & Storage** | | |
| `AUTO_VOTER_DB` | `sqlite:///./data/auto_voter.db` | Database connection string |
| `AUTO_VOTER_LOG_DIR` | `./data/logs` | Directory for worker logs |
| **InfluxDB (Optional)** | | |
| `INFLUX_URL` | - | InfluxDB URL |
| `INFLUX_TOKEN` | - | InfluxDB Token |
| `INFLUX_ORG` | - | InfluxDB Organization |
| `INFLUX_BUCKET` | - | InfluxDB Bucket |
| **Tor Configuration** | | |
| `TOR_SOCKS_PORT` | `9050` | Tor SOCKS proxy port |
| `TOR_CONTROL_PORT` | `9051` | Tor control port |
| `TOR_PASSWORD` | `welcomeTomyPa55word` | Tor control password |
| **Scheduler** | | |
| `AUTO_VOTER_SCHEDULE_INTERVAL` | `30` | Interval (seconds) for the standalone scheduler service |
| `SCHEDULER_INTERVAL` | `30` | Interval (seconds) for the internal app scheduler |
| **VPN** | | |
| `EXPRESSVPN_ACTIVATION_CODE` | - | Activation code for ExpressVPN |

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


## Docker Deployment

### Quick Start with Docker Compose

The application can be deployed using Docker with two services:
- **web**: Flask application with SocketIO
- **scheduler**: Background scheduler for queue and poll processing

#### Prerequisites

1. Docker and Docker Compose installed
2. ExpressVPN activation code (optional, for VPN features)

#### Configuration

Create a `.env` file in your project directory with the required environment variables:

```bash
# Required
ADMIN_USER=admin
ADMIN_PASS=your_secure_password
FLASK_SECRET_KEY=your_random_secret_key

# Optional - ExpressVPN
EXPRESSVPN_ACTIVATION_CODE=your_activation_code

# Optional - InfluxDB
INFLUX_URL=http://your-influx-server:8086
INFLUX_TOKEN=your_influx_token
INFLUX_ORG=your_org
INFLUX_BUCKET=your_bucket

# Optional - Tor
TOR_SOCKS_PORT=9050
TOR_CONTROL_PORT=9051
TOR_PASSWORD=welcomeTomyPa55word
```

#### Deploy with Docker Compose

```bash
# Using docker-compose
docker-compose up -d

# Or using Portainer stack with the provided docker-compose.yml
```

The web interface will be available at `http://localhost:8282`

#### Volume Mounts

Data is persisted in `/docker/auto_voter/data` which contains:
- SQLite database (`auto_voter.db`)
- Worker logs (`logs/`)

#### Troubleshooting

**ExpressVPN Issues:**
- The container requires `NET_ADMIN` capability and `/dev/net/tun` device access
- If ExpressVPN fails to start, the application will continue without VPN features
- Check logs: `docker-compose logs web` or `docker-compose logs scheduler`

**Database Issues:**
- Ensure the data directory has proper permissions
- The database will be created automatically on first run

### Manual Docker Build

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

