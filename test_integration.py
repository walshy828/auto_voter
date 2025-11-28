#!/usr/bin/env python3
"""Integration test: full auth + API flow."""
import os
os.environ['ADMIN_USER'] = 'testadmin'
os.environ['ADMIN_PASS'] = 'testpass123'
os.environ['SECRET_KEY'] = 'test-secret'

from app.api import app
from app.db import SessionLocal
from app.models import Poll, QueueItem

def test_full_flow():
    """Test: login → create poll → add queue → view workers → list endpoint."""
    print("🧪 Full Integration Test: Auth + API Flow")
    print("=" * 60)
    
    client = app.test_client()
    
    # 1. Try to create poll without auth → should fail
    print("\n1️⃣ CREATE POLL (no auth):")
    res = client.post('/polls', json={'entryname': 'Test Poll', 'pollid': '12345', 'answerid': '99'})
    print(f"   Status: {res.status_code} (expected 401)")
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"
    print("   ✓ Correctly rejected")
    
    # 2. Login
    print("\n2️⃣ LOGIN:")
    res = client.post('/login', json={'username': 'testadmin', 'password': 'testpass123'})
    print(f"   Status: {res.status_code}")
    assert res.status_code == 200
    print(f"   Response: {res.get_json()}")
    print("   ✓ Logged in successfully")
    
    # 3. Create a poll (now with auth)
    print("\n3️⃣ CREATE POLL (with auth):")
    res = client.post('/polls', json={'entryname': 'Test Entry', 'pollid': '12345', 'answerid': '99'})
    print(f"   Status: {res.status_code}")
    assert res.status_code == 200
    poll_data = res.get_json()
    poll_id = poll_data['id']
    print(f"   Created poll: {poll_data}")
    print(f"   ✓ Poll created with ID: {poll_id}")
    
    # 4. List polls
    print("\n4️⃣ LIST POLLS:")
    res = client.get('/polls')
    print(f"   Status: {res.status_code}")
    assert res.status_code == 200
    polls = res.get_json()
    print(f"   Found {len(polls)} poll(s)")
    print(f"   ✓ Polls retrieved: {[p['entryname'] for p in polls]}")
    
    # 5. Add queue item
    print("\n5️⃣ ADD QUEUE ITEM:")
    res = client.post('/queue', json={
        'poll_db_id': poll_id,
        'votes': 1000,
        'threads': 10,
        'per_run': 10,
        'pause': 70
    })
    print(f"   Status: {res.status_code}")
    assert res.status_code == 200
    queue_data = res.get_json()
    queue_id = queue_data['id']
    print(f"   Created queue item: {queue_data}")
    print(f"   ✓ Queue item created with ID: {queue_id}")
    
    # 6. List queue
    print("\n6️⃣ LIST QUEUE:")
    res = client.get('/queue')
    print(f"   Status: {res.status_code}")
    assert res.status_code == 200
    queue = res.get_json()
    print(f"   Found {len(queue)} item(s) in queue")
    print(f"   ✓ Queue items: {[(q['id'], q['status']) for q in queue]}")
    
    # 7. List workers (should be empty initially)
    print("\n7️⃣ LIST WORKERS:")
    res = client.get('/workers')
    print(f"   Status: {res.status_code}")
    assert res.status_code == 200
    workers = res.get_json()
    print(f"   Found {len(workers)} worker(s)")
    print(f"   ✓ Workers endpoint accessible")
    
    # 8. Logout
    print("\n8️⃣ LOGOUT:")
    res = client.post('/logout')
    print(f"   Status: {res.status_code}")
    assert res.status_code == 200
    print("   ✓ Logged out")
    
    # 9. Try to access protected endpoint after logout → should fail
    print("\n9️⃣ GET POLLS (after logout):")
    res = client.get('/polls')
    print(f"   Status: {res.status_code} (expected 401)")
    assert res.status_code == 401
    print("   ✓ Correctly rejected")
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)

if __name__ == '__main__':
    test_full_flow()
