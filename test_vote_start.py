#!/usr/bin/env python3
"""Test to isolate if the issue is with vote_start() hanging."""
import os
import sys
import time

# Check if auto_voter_queue can be imported
print("=" * 70)
print("🔍 Testing auto_voter_queue module")
print("=" * 70)

try:
    print("\n1️⃣ Importing app.auto_voter_queue...")
    import app.auto_voter_queue as avq
    print("   ✓ Import successful")
    
    print("\n2️⃣ Checking vote_start function...")
    if hasattr(avq, 'vote_start'):
        print("   ✓ vote_start function exists")
    else:
        print("   ✗ vote_start function NOT found!")
        print("   Available functions:", dir(avq))
        sys.exit(1)
    
    print("\n3️⃣ Checking required module attributes...")
    required_attrs = ['pollid', 'answerid', 'start_totalToRun', 'num_threads', 'p2_PerRun', 'p2_pause']
    for attr in required_attrs:
        if hasattr(avq, attr):
            print(f"   ✓ {attr}")
        else:
            print(f"   ✗ {attr} NOT FOUND")
    
    print("\n4️⃣ Testing vote_start with mock data (2 second timeout test)...")
    avq.pollid = '999999'
    avq.answerid = '888888'
    avq.start_totalToRun = 1  # Very small number
    avq.num_threads = 1
    avq.p2_PerRun = 1
    avq.p2_pause = 0
    
    print("   Calling vote_start(2) with timeout...")
    
    # Use a timeout to detect if vote_start hangs
    import signal
    
    class TimeoutException(Exception):
        pass
    
    def timeout_handler(signum, frame):
        raise TimeoutException("vote_start() took too long (timeout)")
    
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(10)  # 10 second timeout
    
    try:
        start_time = time.time()
        avq.vote_start(2)
        elapsed = time.time() - start_time
        signal.alarm(0)  # Cancel alarm
        print(f"   ✓ vote_start() completed in {elapsed:.1f} seconds")
    except TimeoutException as e:
        print(f"   ✗ TIMEOUT: {e}")
        print("   → vote_start() is hanging or waiting for external resources")
        sys.exit(1)
    except Exception as e:
        signal.alarm(0)
        print(f"   ✗ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("\n" + "=" * 70)
    print("✅ vote_start() test completed successfully!")
    print("   The voting script is working and doesn't hang.")
    print("   Issue is likely in worker.py or Socket.IO streaming.")
    print("=" * 70)
    
except ImportError as e:
    print(f"\n✗ ERROR: Could not import auto_voter_queue: {e}")
    print("   Check that the module exists and all dependencies are installed.")
    sys.exit(1)
except Exception as e:
    print(f"\n✗ Unexpected error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
