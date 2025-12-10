import os
import re
import csv
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from influxdb_client import InfluxDBClient, DeleteApi
from influxdb_client.client.write_api import SYNCHRONOUS
try:
    from fake_useragent import UserAgent
except ImportError:
    UserAgent = None

# ====== Configuration ======
INFLUX_URL = os.environ.get('INFLUX_URL', '')
INFLUX_TOKEN = os.environ.get('INFLUX_TOKEN', '')
INFLUX_ORG = os.environ.get('INFLUX_ORG', '')
INFLUX_BUCKET = os.environ.get('INFLUX_BUCKET', '')

pollsdone = []

# ====== Functions ======

def start():
    while True:
        if ProcessToRun == 1:
            run_all_polls()
        elif ProcessToRun == 2:
            run_single_poll()
        elif ProcessToRun == 99:
            test()
        else:
            print(f"Unknown ProcessToRun mode: {ProcessToRun}")
            break

def run_all_polls(db_session=None):
    """
    Run poll results capture for all polls in the database.
    If db_session is provided, use it. Otherwise, create a new session.
    """
    from app.db import SessionLocal
    from app.models import Poll
    
    # Use provided session or create new one
    db = db_session or SessionLocal()
    close_db = (db_session is None)  # Only close if we created it
    
    try:
        polls = db.query(Poll).filter(Poll.status == 'active').all()
        print(f"[Poll Results] Running for {len(polls)} active polls...")
        
        for poll in polls:
            url = f"https://poll.fm/{poll.pollid}/results"
            extract_poll_results(url, poll.pollid)
        
        pollsdone.clear()
        print(f"[Poll Results] Completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    finally:
        if close_db:
            db.close()

def run_single_poll():
    pollid_single = polls[SinglePollIndex][1]
    url = f"https://poll.fm/{pollid_single}/results"
    extract_poll_results(url, pollid_single)
    pollsdone.clear()
    print_next_run()

def print_next_run():
    now = datetime.now()
    next_time = now + timedelta(seconds=RunPollEveryXsec)
    print(f"Done at {now.strftime('%Y-%m-%d %H:%M:%S')}; Next in {RunPollEveryXsec} seconds at {next_time.strftime('%Y-%m-%d %H:%M:%S')}")
    time.sleep(RunPollEveryXsec)

def write_to_influx(batch):
    try:
        with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG, timeout=30_000) as client:
            write_api = client.write_api(write_options=SYNCHRONOUS)
            write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=batch)
    except Exception as e:
        print(f"InfluxDB Write Error: {e}")

def clean_influx_string(text):
    if text is None:
        return ""
    text = str(text)
    text = re.sub(r'[^A-Za-z0-9 ]+', '', text)  # Remove non-alphanumeric characters
    text = text.replace('’', "'").replace('\\', '\\\\').replace('"', '\\"').replace(" ", "_")
    return text

def test():
    try:
        with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
            delete_api = client.delete_api()
            #start = "1970-01-01T00:00:00Z"
            #stop = datetime.utcnow().isoformat() + "Z"
            start = "1970-01-01T00:00:00Z"
            stop = datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z"
            delete_api.delete(start, stop, '_measurement="states"', bucket=INFLUX_BUCKET, org=INFLUX_ORG)
            print("Test delete complete.")
    except Exception as e:
        print(f"Test delete failed: {e}")

def extract_poll_results(url, pollid, force=False):
    if not force and pollid in pollsdone:
        return
    if not force:
        pollsdone.append(pollid)

    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        page_title = soup.title.string or "Unknown_Poll"
        
        # Detect poll status
        poll_closed = any(keyword in page_title for keyword in ['Poll Closed', 'Poll_Closed', 'poll closed', 'poll_closed'])
        poll_status = 'closed' if poll_closed else 'active'
        
        if poll_closed:
            print(f"Poll Closed - {pollid}; {page_title}")
        
        # Prepare for SQLite update
        from app.db import SessionLocal
        from app.models import Poll, PollResult, PollSnapshot
        db = SessionLocal()
        
        # Find ALL polls in DB with this pollid (there may be multiple, one per answer being tracked)
        poll_records = db.query(Poll).filter(Poll.pollid == str(pollid)).all()
        
        influx_batch = []
        all_answers = []  # List of dicts: {answerid, answer_text, votes, percent}
        total_poll_votes = 0
        
        # Parse all answers from the results page
        for li in soup.find_all('li', class_='pds-feedback-group'):
            answer_text = li.find('span', class_='pds-answer-text').text.strip()
            votes_text = li.find('span', class_='pds-feedback-votes').text.strip()
            percent = li.find('span', class_='pds-feedback-per').text.strip()

            votematch = re.search(r'\d[\d,]*', votes_text)
            if votematch:
                votes = int(votematch.group().replace(',', ''))
            else:
                votes = 0
            
            total_poll_votes += votes
            
            # We don't have answerid from the results page, so we'll use a placeholder or try to extract
            # The results page typically doesn't show answer IDs, only text
            # For now, we'll store answer_text and leave answerid blank for non-target answers
            all_answers.append({
                'answer_text': answer_text,
                'votes': votes,
                'percent': percent
            })

            # InfluxDB logic (unchanged)
            try:
                vote_name, vote_school = answer_text.split(", ", 1)
            except ValueError:
                vote_name = answer_text
                vote_school = "Unknown"

            vote_name = clean_influx_string(vote_name)
            vote_school = clean_influx_string(vote_school)
            poll_title_clean = clean_influx_string(re.sub(r'[^A-Za-z0-9 ]+', '', page_title))

            unix_time = int(time.time() * 1e9)
            influx_record = (
                f"pollresults,"
                f"pollid={pollid},"
                f"polltitle={poll_title_clean},"
                f"name={vote_name},"
                f"school={vote_school} "
                f"votes={votes}i "
                f"{unix_time}"
            )
            influx_batch.append(influx_record)

        # Write to Influx
        write_to_influx(influx_batch)
        
        # Sort answers by votes descending to determine places
        all_answers.sort(key=lambda x: x['votes'], reverse=True)
        
        # Assign place rankings
        for i, answer in enumerate(all_answers):
            answer['place'] = i + 1
        
        # SQLite: Update ALL poll records for this pollid
        for poll_record in poll_records:
            # Delete old snapshots for this specific poll record
            db.query(PollSnapshot).filter(PollSnapshot.poll_id == poll_record.id).delete()
            
            # Insert new snapshots for all answers (same for all poll records)
            for answer in all_answers:
                snapshot = PollSnapshot(
                    poll_id=poll_record.id,
                    pollid=str(pollid),
                    answerid='',  # We don't have this from results page
                    answer_text=answer['answer_text'],
                    votes=answer['votes'],
                    place=answer['place'],
                    percent=answer['percent'],
                    updated_at=datetime.now(timezone.utc).replace(tzinfo=None)
                )
                db.add(snapshot)
            
            # Update Poll record with comprehensive stats
            poll_record.status = poll_status
            poll_record.poll_title = page_title
            poll_record.total_poll_votes = total_poll_votes
            poll_record.last_snapshot_at = datetime.now(timezone.utc).replace(tzinfo=None)
            
            # Find stats for THIS poll's target answer (match by entryname)
            # Normalize text for better matching (remove spaces, commas, lowercase)
            def normalize_text(text):
                return text.lower().replace(' ', '').replace(',', '').replace('-', '')
            
            target_answer_normalized = normalize_text(poll_record.entryname)
            target_stats = None
            
            for answer in all_answers:
                answer_normalized = normalize_text(answer['answer_text'])
                # Try exact normalized match first, then contains
                if target_answer_normalized == answer_normalized or target_answer_normalized in answer_normalized:
                    target_stats = answer
                    break
            
            if target_stats:
                # Store previous placement before updating
                old_place = poll_record.current_place
                
                # Update current stats
                poll_record.total_votes = target_stats['votes']
                poll_record.current_place = target_stats['place']
                
                # Calculate votes_behind_first or votes_ahead_second
                if target_stats['place'] > 1:
                    poll_record.votes_behind_first = all_answers[0]['votes'] - target_stats['votes']
                    poll_record.votes_ahead_second = None
                else:
                    # In 1st place
                    poll_record.votes_behind_first = 0
                    # Calculate lead over 2nd place
                    if len(all_answers) > 1:
                        poll_record.votes_ahead_second = target_stats['votes'] - all_answers[1]['votes']
                    else:
                        poll_record.votes_ahead_second = 0
                
                # Calculate trend
                if old_place is None:
                    poll_record.place_trend = 'new'
                elif old_place > target_stats['place']:
                    poll_record.place_trend = 'up'  # Moving up (e.g., 3rd -> 2nd)
                elif old_place < target_stats['place']:
                    poll_record.place_trend = 'down'  # Moving down (e.g., 2nd -> 3rd)
                else:
                    poll_record.place_trend = 'same'
                
                # Update previous_place for next comparison
                poll_record.previous_place = old_place
            else:
                # If no match found, log it for debugging
                print(f"[WARNING] Could not find match for '{poll_record.entryname}' in poll {pollid}")
            
            # Also save to PollResult for historical tracking
            for answer in all_answers:
                pr = PollResult(
                    poll_id=poll_record.id,
                    timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
                    answer_text=answer['answer_text'],
                    votes=answer['votes'],
                    percent=answer['percent']
                )
                db.add(pr)
            
        db.commit()
        db.close()

    except requests.exceptions.RequestException as e:
        print(f"Request Error: {e}")
    except AttributeError as e:
        print(f"Parsing Error: {e}")
    except Exception as e:
        print(f"Error in extract_poll_results: {e}")
        import traceback
        traceback.print_exc()

# ====== Main ======

if __name__ == "__main__":
    start()
