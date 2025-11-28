# Quick Reference: Session Auth + WebSocket Setup

## Start the App (3 simple steps)

```bash
# 1. Set environment variables
export ADMIN_USER=admin
export ADMIN_PASS=your_password
export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# 2. Start the server (with WebSocket support)
python3 -m app.api

# 3. Open browser
# http://127.0.0.1:8080
# Login: admin / your_password
```

---

## What's New ✨

| Feature | Details |
|---------|---------|
| **Login Modal** | Auto-appears on page load; username + password |
| **Protected APIs** | All endpoints require authentication (401 if not logged in) |
| **Session Cookies** | Secure, signed with SECRET_KEY |
| **WebSocket Logs** | Real-time log streaming via Socket.IO |
| **SSE Fallback** | Works in browsers without WebSocket support |
| **Auto-Redirect** | 401 errors auto-show login modal |

---

## Key Endpoints

### Authentication
- `POST /login` - Login with username/password
- `POST /logout` - Clear session

### Protected Data (require login)
- `POST /polls` - Create poll
- `GET /polls` - List polls
- `POST /queue` - Add queue item
- `GET /queue` - List queue
- `GET /workers` - List workers
- `GET /workers/<id>/log` - Get worker log
- `GET /workers/<id>/stream` - Stream log (SSE fallback)

### WebSocket (Socket.IO)
- `emit('subscribe_log', {worker_id: N})` - Subscribe to live logs
- `on('log_line', callback)` - Receive log lines
- `emit('unsubscribe_log')` - Stop streaming

---

## Test the Implementation

```bash
# Test 1: Login flow
python3 test_login.py

# Test 2: Socket.IO setup
python3 test_socketio.py

# Test 3: Full workflow (login → create → queue → logout)
python3 test_integration.py
```

All should print: `✅ ... tests passed!`

---

## Security Checklist ✅

- [x] Passwords hashed (werkzeug.security)
- [x] Session cookies signed with SECRET_KEY
- [x] Protected endpoints with @require_auth
- [x] Auto-login modal on 401
- [x] Token fallback for programmatic use
- [ ] HTTPS enabled (production)
- [ ] SESSION_COOKIE_SECURE set (production)
- [ ] CSRF tokens added (optional)

---

## Browser Testing Checklist

- [ ] Login modal appears on first visit
- [ ] Login with correct credentials works
- [ ] Invalid password rejected (toast shown)
- [ ] After login, dashboard loads (polls, queue, workers visible)
- [ ] Create a poll: appears in table
- [ ] Add queue item: appears in queue table
- [ ] Click worker log: modal opens, log streams
  - First attempt: via WebSocket (fastest)
  - If no WebSocket: falls back to SSE
- [ ] Refresh page: still logged in (session persists)
- [ ] Click logout: returns to login modal
- [ ] Refresh after logout: login required again

---

## Troubleshooting 1-Liners

```bash
# Check if Flask-SocketIO works
python3 -c "import flask_socketio; print('✓ Flask-SocketIO OK')"

# Check if eventlet (WebSocket worker) is installed
python3 -c "import eventlet; print('✓ eventlet OK')"

# Verify SECRET_KEY is set
echo $SECRET_KEY  # Should not be empty

# Test login directly
curl -X POST http://127.0.0.1:8080/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your_password"}' \
  -c cookies.txt && echo "✓ Login OK"

# Test protected endpoint with cookies
curl -b cookies.txt http://127.0.0.1:8080/polls && echo "✓ Auth OK"
```

---

## Files to Know

| File | Purpose |
|------|---------|
| `app/api.py` | Flask app, login routes, Socket.IO init |
| `app/socketio_server.py` | WebSocket handlers |
| `app/templates/index.html` | UI with login modal |
| `app/static/app.js` | Frontend: auth, Socket.IO client |
| `test_login.py` | Validate auth flow |
| `test_integration.py` | Full workflow test |
| `AUTH_AND_WEBSOCKET_GUIDE.md` | Detailed docs |

---

## FAQ

**Q: Do I need Socket.IO?**  
A: No, SSE fallback works fine. But WebSocket is faster and more reliable.

**Q: Where's the logout button?**  
A: Add to navbar: `<button onclick="fetch('/logout',{method:'POST'}).then(()=>location.reload())">Logout</button>`

**Q: Can I use a different password hashing?**  
A: Yes, modify `app/models.py` User class (currently uses werkzeug.security PBKDF2).

**Q: How long do sessions last?**  
A: Until browser closes or 24 hours (default Flask-Login). Customize with `PERMANENT_SESSION_LIFETIME`.

**Q: Can I use this with my own DB?**  
A: Yes, `app/db.py` uses SQLAlchemy. Change `DATABASE_URL` env var to your DB URI.

---

**🎉 You're all set! Open http://127.0.0.1:8080 and enjoy your secure, real-time dashboard.**
