import os
import sys
import json

# Set env vars BEFORE importing app
os.environ['ADMIN_USER'] = 'testadmin'
os.environ['ADMIN_PASS'] = 'testpass'
os.environ['SECRET_KEY'] = 'test-secret'

from app.api import app, ensure_admin_user
from app.db import SessionLocal
from app.models import Poll, QueueItem, QueueStatus, User

def test_use_tor():
    print("Testing Use Tor feature...")
    
    # Ensure admin user exists
    ensure_admin_user()
    
    db = SessionLocal()
    user_count = db.query(User).count()
    print(f"User count: {user_count}")
    admin = db.query(User).filter(User.username == 'testadmin').first()
    if admin:
        print(f"Admin user found: {admin.username}")
    else:
        print("Admin user NOT found")
    db.close()
    
    client = app.test_client()
    
    # Login
    print("Logging in...")
    res = client.post('/login', json={'username': 'testadmin', 'password': 'testpass'})
    if res.status_code != 200:
        print(f"Login failed: {res.status_code}")
        print(res.get_json())
        return
    print("Logged in.")
    
    # 1. Create Poll with Use Tor
    print("Creating poll with Use Tor...")
    res = client.post('/polls', json={
        'entryname': 'Tor Poll',
        'pollid': '999',
        'answerid': '888',
        'use_tor': 1
    })
    if res.status_code != 200:
        print(f"Failed to create poll: {res.status_code}")
        print(res.get_json())
        return
    poll_data = res.get_json()
    poll_id = poll_data['id']
    
    # Verify DB
    db = SessionLocal()
    p = db.query(Poll).filter(Poll.id == poll_id).first()
    if p and p.use_tor == 1:
        print("SUCCESS: Poll created with use_tor=1")
    else:
        print(f"FAILED: Poll use_tor is {p.use_tor if p else 'None'}")
    db.close()
    
    # 2. Add Queue Item with Use Tor
    print("Adding queue item with Use Tor...")
    res = client.post('/queue', json={
        'poll_db_id': poll_id,
        'votes': 5,
        'use_tor': 1
    })
    if res.status_code != 200:
        print(f"Failed to add queue item: {res.status_code}")
        print(res.get_json())
        return
    item_data = res.get_json()
    item_id = item_data['id']
    
    # Verify DB
    db = SessionLocal()
    it = db.query(QueueItem).filter(QueueItem.id == item_id).first()
    if it and it.use_tor == 1:
        print("SUCCESS: Queue item created with use_tor=1")
    else:
        print(f"FAILED: Queue item use_tor is {it.use_tor if it else 'None'}")
    db.close()

if __name__ == "__main__":
    test_use_tor()
