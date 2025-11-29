#!/usr/bin/env python3
"""Simple test script to verify login flow."""
import os
import sys
import json
import requests
from time import sleep

# Set up environment
os.environ['ADMIN_USER'] = 'testadmin'
os.environ['ADMIN_PASS'] = 'testpass123'
os.environ['SECRET_KEY'] = 'test-secret'

# Import and initialize app
from app.api import app

BASE_URL = 'http://127.0.0.1:5000'

def test_auth():
    """Test login and protected endpoints."""
    print("Testing login flow...")
    
    # Start a test client
    client = app.test_client()
    
    # 1. Try to access protected endpoint without auth → should get 401
    print("1. GET /polls without auth:")
    res = client.get('/polls')
    print(f"   Status: {res.status_code} (expected 401)")
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"
    
    # 2. Try to login with wrong credentials → should get 401
    print("2. POST /login with wrong password:")
    res = client.post('/login', json={'username': 'testadmin', 'password': 'wrongpass'})
    print(f"   Status: {res.status_code} (expected 401)")
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"
    
    # 3. Login with correct credentials → should get 200
    print("3. POST /login with correct credentials:")
    res = client.post('/login', json={'username': 'testadmin', 'password': 'testpass123'})
    print(f"   Status: {res.status_code} (expected 200)")
    print(f"   Response: {res.get_json()}")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    
    # 4. Now try to access protected endpoint with session → should work
    print("4. GET /polls with session:")
    res = client.get('/polls')
    print(f"   Status: {res.status_code} (expected 200)")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    print(f"   Data: {res.get_json()}")
    
    # 5. Try GET /queue
    print("5. GET /queue with session:")
    res = client.get('/queue')
    print(f"   Status: {res.status_code} (expected 200)")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    
    # 6. Try GET /workers
    print("6. GET /workers with session:")
    res = client.get('/workers')
    print(f"   Status: {res.status_code} (expected 200)")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    
    # 7. Try to logout
    print("7. POST /logout:")
    res = client.post('/logout')
    print(f"   Status: {res.status_code} (expected 302 or 200)")
    
    # 8. After logout, /polls should return 401
    print("8. GET /polls after logout:")
    res = client.get('/polls')
    print(f"   Status: {res.status_code} (expected 401)")
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"
    
    print("\n✓ All auth tests passed!")

if __name__ == '__main__':
    test_auth()
