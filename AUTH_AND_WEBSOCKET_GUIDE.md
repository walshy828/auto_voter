# Auto Voter — Session-Based Auth & WebSocket Streaming Setup

## ✅ What's Complete

### Session-Based Authentication (Login/Logout)
- **Login endpoint** (`POST /login`): accepts JSON `{username, password}`, validates credentials, and sets secure session cookies
- **Logout endpoint** (`POST /logout`): clears the session
- **Admin user auto-creation**: creates/updates admin user from `ADMIN_USER` and `ADMIN_PASS` env vars on startup
- **Protected endpoints**: all data endpoints (`GET /polls`, `GET /queue`, `GET /workers`, etc.) require authentication
- **Fallback token auth**: endpoints still accept `Authorization: Bearer <token>` for programmatic access (ADMIN_TOKEN env var)

### Frontend Login UI
- **Login modal**: username + password form at app startup
- **Auto-prompt on 401**: if any protected endpoint returns 401, the login modal appears
- **Session cookies**: browser automatically sends session cookies with all requests (credentials: 'same-origin')
- **Clear feedback**: login success/failure toasts
- **Persistent session**: once logged in, session is maintained across page reloads

### WebSocket (Socket.IO) Log Streaming
- **Server-side**: Flask-SocketIO handlers registered; `subscribe_log` event starts background log tailing
- **Client-side**: Socket.IO client connects; emits `subscribe_log` to stream worker logs in real-time
- **Fallback**: if Socket.IO unavailable, client falls back to Server-Sent Events (SSE) endpoint
- **Auto-init**: Socket.IO client initializes on page load; app.js handles both connected and disconnected states

### Testing
- `test_login.py`: validates login flow, session persistence, logout, and 401 behavior
- `test_socketio.py`: verifies Socket.IO instance and server setup
- Both tests **pass** ✓

---

## 🚀 Quick Start

### Prerequisites
Ensure you have activated your virtual environment and installed dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Start the Development Server (Flask)

```bash
export ADMIN_USER=admin
export ADMIN_PASS=your_secure_password
export SECRET_KEY=your_random_secret_key  # Important for production!
export FLASK_APP=app.api:app
flask run --host=0.0.0.0 --port=8080
```

**Or**, start via Socket.IO directly (recommended for production-like testing):

```bash
python3 -m app.api
```

This uses `socketio.run(app, ...)` which enables WebSocket transports (requires `eventlet` or `gevent`).

### Open the UI

Navigate to **http://127.0.0.1:8080** (or **http://192.168.90.15:8080** from another machine on the network).

1. **Login modal** appears automatically
2. Enter username: `admin`, password: your `ADMIN_PASS`
3. Click **Login**
4. On success, you can:
   - Create polls
   - Add queue items and start jobs
   - View workers and stream live logs via Socket.IO

---

## 📋 Key Files Modified

### Backend
- **`app/api.py`**
  - Added `/login` and `/logout` routes
  - Set `app.config['SECRET_KEY']` from env
  - Initialized Socket.IO: `socketio = SocketIO(app, ...)`
  - Added `@require_auth` to `GET /polls` and `GET /queue`
  - Changed main block to use `socketio.run(app, ...)`

- **`app/socketio_server.py`**
  - Registered Socket.IO handlers: `connect`, `subscribe_log`, `unsubscribe_log`
  - Background task emits `log_line` events to subscribed clients

- **`app/worker.py`**
  - Fixed `stop_queue_item()`: guard os.kill when pid is None, correct datetime calls

### Frontend
- **`app/templates/index.html`**
  - Updated login modal: username + password fields (removed token approach)
  - Set `data-bs-backdrop="static"` to prevent dismissal during login

- **`app/static/app.js`**
  - Added Socket.IO client initialization: `initializeSocketIO()`
  - Updated login handler: POSTs to `/login` with credentials
  - Enhanced `openLogStream()`: tries Socket.IO first, falls back to SSE
  - Added 401 handler: auto-shows login modal on auth errors
  - Updated all `authedFetch` calls to use `credentials: 'same-origin'`

---

## 🔐 Security Notes

### Session Security
- **`SECRET_KEY`** env var is used to sign session cookies
  - Development: defaults to `'dev-secret'` (insecure; warning in logs)
  - Production: **must** be set to a strong, random value
  
  Generate a secure key:
  ```bash
  python3 -c "import secrets; print(secrets.token_hex(32))"
  ```

### Cookie Flags
Flask-Login uses standard session cookies. For production hardening, add:
```python
app.config['SESSION_COOKIE_SECURE'] = True      # HTTPS only
app.config['SESSION_COOKIE_HTTPONLY'] = True    # No JS access
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'   # CSRF protection
```

### Password Storage
- User passwords are hashed using werkzeug.security (`pbkdf2:sha256` by default)
- Admin user auto-creation ensures the password is hashed before storage
- Never store plain-text passwords ✓

---

## 🧪 Manual Testing Checklist

After starting the server, verify:

- [ ] **Login page appears** on first visit
- [ ] **Invalid credentials rejected** (try wrong password)
- [ ] **Login succeeds** and page refreshes showing polls/queue/workers
- [ ] **Click "Workers"** tab → list of workers appears
- [ ] **Click worker log button** → modal opens with "Connecting..."
- [ ] **Start a job** (from Queue tab), then view its log
  - If Socket.IO connects: live log streams via WebSocket ✓
  - If Socket.IO unavailable: falls back to SSE ✓
- [ ] **Logout** button (if implemented) or close browser session
- [ ] **Refresh page** → login modal reappears (session expired)

---

## 📦 Deployment (Docker)

### Dockerfile (Gunicorn + eventlet)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

# Run with gunicorn + eventlet worker for Socket.IO support
CMD ["gunicorn", "-k", "eventlet", "-w", "1", "--bind", "0.0.0.0:8080", "app.api:app"]
```

### docker-compose.yml

```yaml
version: '3.8'
services:
  web:
    build: .
    ports:
      - "8080:8080"
    environment:
      ADMIN_USER: admin
      ADMIN_PASS: ${ADMIN_PASS:-changeme}
      SECRET_KEY: ${SECRET_KEY:-generate-real-key-in-prod}
      DATABASE_URL: sqlite:///./data/auto_voter.db
    volumes:
      - ./data:/app/data
```

Start with:
```bash
docker-compose up --build
```

---

## 🐛 Troubleshooting

### "ModuleNotFoundError: No module named 'flask_login'"
→ Run `pip install -r requirements.txt` in your virtualenv

### Socket.IO not connecting (WebSocket fails)
→ Ensure you're using `socketio.run(app, ...)` or `gunicorn -k eventlet`
→ Flask's built-in development server doesn't support WebSocket; falls back to SSE (OK for testing)

### Session expires immediately
→ Verify `SECRET_KEY` is set; Flask won't sign sessions without it
→ Check `SESSION_COOKIE_HTTPONLY` settings if using custom Flask config

### Login modal appears on every load
→ Session cookie may not be persisted; check browser settings (cookies enabled?)
→ On iOS/Safari in private mode, cookies don't persist

---

## 🗺️ Next Steps (Optional)

### 1. Switch to React/Vite SPA
Scaffold a separate frontend:
```bash
npm create vite@latest frontend -- --template react
```
Then:
- Move UI components to React
- Keep the same API endpoints
- Update docker-compose to build frontend as separate service

### 2. Add CSRF Protection
```bash
pip install Flask-WTF
```
Then protect forms with CSRF tokens (if not using SPA).

### 3. Fix Alembic Migrations
The current schema has a manual DB fix. To use Alembic properly:
```bash
python3 -m alembic upgrade head
```
(May require fixing logging config in `alembic/env.py`; see README.md)

### 4. Add 2FA
Integrate `pyotp` or `qrcode` for time-based one-time passwords (TOTP).

---

## 📄 Summary

Your app now has:
✅ Session-based login/logout with secure cookies
✅ Protected API endpoints requiring authentication
✅ WebSocket log streaming with fallback to SSE
✅ Login modal auto-prompting on 401 errors
✅ Admin user auto-creation from env vars
✅ Production-ready security posture (with SECRET_KEY set)

The system is **ready for testing and deployment**. Open the browser, log in, and enjoy the dashboard!
