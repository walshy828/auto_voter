#!/usr/bin/env python3
"""
Test script to run auto_voter functions directly without the web application.
This simulates the worker functionality for testing purposes.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.db import SessionLocal
from app.models import QueueItem, QueueStatus
import app.auto_voter_queue as avq

def test_queue_item(item_id):
    """
    Test a specific queue item by ID.
    """
    db = SessionLocal()
    try:
        item = db.query(QueueItem).filter(QueueItem.id == item_id).first()
        if not item:
            print(f"❌ Queue item {item_id} not found")
            return False
        
        print(f"📋 Testing Queue Item #{item.id}")
        print(f"   Poll ID: {item.pollid}")
        print(f"   Answer ID: {item.answerid}")
        print(f"   Votes: {item.votes}")
        print(f"   Threads: {item.threads}")
        print(f"   Use VPN: {item.use_vpn}")
        print(f"   Use Tor: {item.use_tor}")
        print()
        
        # Set up auto_voter_queue global variables
        avq.pollid = item.pollid
        avq.answerid = item.answerid
        avq.start_totalToRun = item.votes
        avq.num_threads = item.threads
        avq.p2_PerRun = item.per_run
        avq.p2_pause = item.pause
        avq.use_vpn = bool(item.use_vpn)
        avq.use_tor = bool(item.use_tor)
        
        # Recalculate RunPerScript and cntToRun
        avq.RunPerScript = avq.start_totalToRun // avq.num_threads
        avq.cntToRun = avq.RunPerScript
        
        # Run the voting process
        print("🚀 Starting voting process...")
        print(f"   Configuring: pollid={item.pollid}, answerid={item.answerid}, votes={item.votes}, threads={item.threads}")
        
        try:
            avq.vote_start(2)  # Mode 2 = batch mode
            print("✅ Voting completed successfully")
            return True
        except Exception as e:
            print(f"❌ Voting failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    finally:
        db.close()


def test_direct_vote(pollid, answerid, votes=10, threads=1, per_run=1, pause=70, use_vpn=1, use_tor=0):
    """
    Test voting directly without a queue item.
    """
    print(f"📋 Testing Direct Vote")
    print(f"   Poll ID: {pollid}")
    print(f"   Answer ID: {answerid}")
    print(f"   Votes: {votes}")
    print(f"   Threads: {threads}")
    print(f"   Per Run: {per_run}")
    print(f"   Pause: {pause}s")
    print(f"   Use VPN: {use_vpn}")
    print(f"   Use Tor: {use_tor}")
    print()
    
    # Set up auto_voter_queue global variables
    avq.pollid = pollid
    avq.answerid = answerid
    avq.start_totalToRun = votes
    avq.num_threads = threads
    avq.p2_PerRun = per_run
    avq.p2_pause = pause
    avq.use_vpn = bool(use_vpn)
    avq.use_tor = bool(use_tor)
    
    # Recalculate RunPerScript and cntToRun
    avq.RunPerScript = avq.start_totalToRun // avq.num_threads
    avq.cntToRun = avq.RunPerScript
    
    # Run the voting process
    print("🚀 Starting voting process...")
    
    try:
        avq.vote_start(2)  # Mode 2 = batch mode
        print("✅ Voting completed successfully")
        return True
    except Exception as e:
        print(f"❌ Voting failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def list_queue_items():
    """
    List all queue items in the database.
    """
    db = SessionLocal()
    try:
        items = db.query(QueueItem).order_by(QueueItem.created_at.desc()).all()
        
        if not items:
            print("No queue items found")
            return
        
        print(f"\n📋 Queue Items ({len(items)} total):\n")
        print(f"{'ID':<5} {'Name':<20} {'Poll ID':<10} {'Status':<12} {'Votes':<8} {'Created':<20}")
        print("-" * 85)
        
        for item in items:
            name = (item.queue_name or '-')[:20]
            created = item.created_at.strftime('%Y-%m-%d %H:%M:%S') if item.created_at else '-'
            print(f"{item.id:<5} {name:<20} {item.pollid:<10} {item.status.value:<12} {item.votes:<8} {created:<20}")
        
        print()
    finally:
        db.close()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Test auto_voter functionality')
    parser.add_argument('--list', action='store_true', help='List all queue items')
    parser.add_argument('--item', type=int, help='Test a specific queue item by ID')
    parser.add_argument('--pollid', type=str, help='Poll ID for direct voting')
    parser.add_argument('--answerid', type=str, help='Answer ID for direct voting')
    parser.add_argument('--votes', type=int, default=10, help='Number of votes (default: 10)')
    parser.add_argument('--threads', type=int, default=1, help='Number of threads (default: 1)')
    parser.add_argument('--per-run', type=int, default=1, help='Votes per run before pause (default: 1)')
    parser.add_argument('--pause', type=int, default=5, help='Pause in seconds between runs (default: 5)')
    parser.add_argument('--use-vpn', type=int, default=1, choices=[0, 1], help='Use VPN (0 or 1, default: 1)')
    parser.add_argument('--use-tor', type=int, default=0, choices=[0, 1], help='Use Tor (0 or 1, default: 0)')
    
    args = parser.parse_args()
    
    if args.list:
        list_queue_items()
    elif args.item:
        test_queue_item(args.item)
    elif args.pollid and args.answerid:
        test_direct_vote(
            pollid=args.pollid,
            answerid=args.answerid,
            votes=args.votes,
            threads=args.threads,
            per_run=args.per_run,
            pause=args.pause,
            use_vpn=args.use_vpn,
            use_tor=args.use_tor
        )
    else:
        parser.print_help()
        print("\nExamples:")
        print("  # List all queue items")
        print("  python3 test_auto_voter.py --list")
        print()
        print("  # Test queue item #5")
        print("  python3 test_auto_voter.py --item 5")
        print()
        print("  # Test direct voting")
        print("  python3 test_auto_voter.py --pollid 16315029 --answerid 71679619 --votes 10")
        print()
        print("  # Test with Tor and custom timing")
        print("  python3 test_auto_voter.py --pollid 16315029 --answerid 71679619 --votes 5 --use-tor 1 --per-run 5 --pause 2")
