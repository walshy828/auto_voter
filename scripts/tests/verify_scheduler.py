import requests
import os

# Config
BASE_URL = 'http://127.0.0.1:8080'
ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'admin')

def verify_scheduler():
    session = requests.Session()
    
    # 1. Login
    print("Logging in...")
    resp = session.post(f'{BASE_URL}/login', json={'username': ADMIN_USER, 'password': ADMIN_PASS})
    if resp.status_code != 200:
        print(f"❌ Login failed: {resp.text}")
        return False
    print("✅ Login successful")

    # 2. Check Initial Status
    print("Checking initial status...")
    resp = session.get(f'{BASE_URL}/scheduler/status')
    if resp.status_code != 200:
        print(f"❌ Failed to get status: {resp.text}")
        return False
    initial_running = resp.json().get('running')
    print(f"Initial Status: {'Running' if initial_running else 'Paused'}")

    # 3. Pause Scheduler
    print("Pausing scheduler...")
    resp = session.post(f'{BASE_URL}/scheduler/pause')
    if resp.status_code != 200:
        print(f"❌ Failed to pause: {resp.text}")
        return False
    
    resp = session.get(f'{BASE_URL}/scheduler/status')
    if resp.json().get('running'):
        print("❌ Scheduler still running after pause")
        return False
    print("✅ Scheduler paused successfully")

    # 4. Resume Scheduler
    print("Resuming scheduler...")
    resp = session.post(f'{BASE_URL}/scheduler/resume')
    if resp.status_code != 200:
        print(f"❌ Failed to resume: {resp.text}")
        return False
    
    resp = session.get(f'{BASE_URL}/scheduler/status')
    if not resp.json().get('running'):
        print("❌ Scheduler still paused after resume")
        return False
    print("✅ Scheduler resumed successfully")

    return True

if __name__ == "__main__":
    try:
        if verify_scheduler():
            print("\n✅ All scheduler tests passed!")
        else:
            print("\n❌ Verification failed")
            exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("Make sure the server is running on port 8080")
        exit(1)
