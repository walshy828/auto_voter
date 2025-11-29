#!/usr/bin/env python3
"""Test script to manually refresh poll results"""
import sys
sys.path.insert(0, '/Users/dpw/Documents/Development/auto_voter')

from app.vote_results_influx_scheduler import extract_poll_results

# Test refresh for poll 16315029
pollid = '16315029'
url = f"https://poll.fm/{pollid}/results"

print(f"Testing refresh for poll {pollid}...")
extract_poll_results(url, pollid)
print("Refresh complete!")

# Check results
from app.db import SessionLocal
from app.models import Poll

db = SessionLocal()
polls = db.query(Poll).filter(Poll.pollid == pollid).all()
for p in polls:
    print(f"\nPoll: {p.entryname}")
    print(f"  Answer ID: {p.answerid}")
    print(f"  Total Votes (answer): {p.total_votes}")
    print(f"  Total Poll Votes: {p.total_poll_votes}")
    print(f"  Place: {p.current_place}")
    print(f"  Gap: {p.votes_behind_first}")
    print(f"  Status: {p.status}")
db.close()
