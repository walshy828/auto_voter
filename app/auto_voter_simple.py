
import threading
import multiprocessing
import random
import string
import time
import datetime
import re
import html
import json
import requests
from bs4 import BeautifulSoup
from stem import Signal
from stem.control import Controller
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
from expressvpn import connect_alias
import app.config as config
from app.db import SessionLocal
from app.models import QueueItem, QueueStatus

# --- Global Configs (Defaults) --- #
pollToRun = 0
num_threads = 1
start_totalToRun = 0
p2_PerRun = 10
p2_pause = 1
print_debug_msg = False
# We will use this global to track the per-job debug setting
JOB_DEBUG_ENABLED = False 
print_debug_level = 1

RandomTimes = False
RandomMin = 2
RandomMax = 30
tor_delay = 2

cntToPause = 0
longPauseSeconds = 70
shortPauseSeconds = 0

vpn_maxvotes = 0
vpn_enabled = False
vpnmode = 1
CoolDownCount = 0
Cooldown = 95

iPhoneUser = True

def random_hex(length):
    """Generate a random hexadecimal string of specified length."""
    return ''.join(random.choice('0123456789abcdef') for _ in range(length))

INFLUX_URL = config.INFLUX_URL
INFLUX_TOKEN = config.INFLUX_TOKEN
INFLUX_ORG = config.INFLUX_ORG
INFLUX_BUCKET = config.INFLUX_BUCKET
BATCH_SIZE = 10

RunPerScript = 0
cntToRun = 0

print_output = 1
stop_event = threading.Event()

pollid = 0
answerid = 0
use_tor = False

proxies = {'http': 'socks5h://127.0.0.1:9050', 'https': 'socks5h://127.0.0.1:9050'}
# Using threading Lock since we are in a single process (the worker child process)
lock = threading.Lock()
# Using simple integer and lock for counting
count_good = 0 

vpnloc = config.vpnloc
vpnloccnt = len(vpnloc) - 1
vpnlocat = random.randint(0, vpnloccnt)
vpn_votecnt = 0

useragents = config.useragents

# Globals for progress tracking
current_item_id = None
socketio_instance = None


# --- Functions --- #

def interruptible_sleep(seconds):
    """Sleep for roughly 'seconds' time, but wake up immediately if stop_event is set."""
    if stop_event.wait(timeout=seconds):
        return True
    return False

def start_job(job_config):
    """
    Main entry point for the worker.
    """
    global pollid, answerid, start_totalToRun, num_threads, p2_PerRun, p2_pause
    global use_tor, vpn_enabled, current_item_id, socketio_instance
    global RunPerScript, cntToRun, count_good, stop_event, JOB_DEBUG_ENABLED

    # Reset globals
    stop_event.clear()
    count_good = 0
    vpn_votecnt = 0
    
    # Load Config
    pollid = job_config.get('pollid', 0)
    answerid = job_config.get('answerid', 0)
    start_totalToRun = job_config.get('votes', 100)
    num_threads = job_config.get('threads', 1)
    p2_PerRun = job_config.get('per_run', 10)
    p2_pause = job_config.get('pause', 0)
    vpn_enabled = job_config.get('use_vpn', False)
    use_tor = job_config.get('use_tor', False)
    JOB_DEBUG_ENABLED = job_config.get('debug', False)
    
    current_item_id = job_config.get('item_id')
    socketio_instance = job_config.get('socketio')

    if num_threads < 1: num_threads = 1
    RunPerScript = start_totalToRun // num_threads
    cntToRun = RunPerScript
    
    msg = f"[AutoVoterSimple] Starting Job: Poll={pollid}, Threads={num_threads}, Total={start_totalToRun}, VPN={vpn_enabled}, Debug={JOB_DEBUG_ENABLED}"
    print(msg)
    if JOB_DEBUG_ENABLED:
        log_detailed(f"Job Configuration: {job_config}")

    # Calculate Loops
    if p2_PerRun < 1: p2_PerRun = 1
    LoopTimes = (RunPerScript + p2_PerRun - 1) // p2_PerRun 
    if LoopTimes < 1: LoopTimes = 1
    
    PreviousGood = 0
    
    # Initial VPN Connect if enabled (logic moved inside loop generally, but logging here)
    if vpn_enabled and JOB_DEBUG_ENABLED:
        log_detailed("VPN is enabled. Location switching will occur.")

    for i in range(LoopTimes):
        if stop_event.is_set():
            if JOB_DEBUG_ENABLED:
                log_detailed("Stop event detected. Exiting loop.")
            break
            
        starttime = datetime.datetime.now()
        
        if vpn_enabled:
            # Check stop event before possibly long VPN switch
            if stop_event.is_set(): break
            
            if JOB_DEBUG_ENABLED:
                log_detailed(f"Batch {i+1}: Switching VPN location...")
            new_location()
        
        if JOB_DEBUG_ENABLED:
            log_detailed(f"Batch {i+1}: Starting {num_threads} threads for {p2_PerRun} runs each.")
            
        run_multi_scripts(num_threads, p2_PerRun)

        RunThisLoop = p2_PerRun * num_threads
        GoodThisLoop = count_good - PreviousGood
        GoodThisLoopPercent = (GoodThisLoop / RunThisLoop) * 100 if RunThisLoop > 0 else 0
        WhereAt = (i+1) * RunThisLoop
        PercentGood = (count_good / max(1, WhereAt)) * 100

        now = datetime.datetime.now()
        nowFormat = now.strftime("%H:%M:%S")
        TimeRun = (now - starttime).total_seconds()

        print(f"{nowFormat}: {TimeRun:.0f}s {GoodThisLoop}/{RunThisLoop} ({GoodThisLoopPercent:.1f}%): "
              f"Overall: {count_good}/{WhereAt} ({PercentGood:.1f}%)")
              
        update_queue_progress(current_item_id, WhereAt, count_good, f"Running Batch {i+1}/{LoopTimes}")

        extract_poll_results(pollid)
        
        PreviousGood = count_good

        # Check if job was canceled via web UI after this batch
        if current_item_id:
            try:
                db = SessionLocal()
                item = db.query(QueueItem).filter(QueueItem.id == current_item_id).first()
                if item and item.status == QueueStatus.canceled:
                    print(f"[AutoVoter] Job {current_item_id} was canceled. Stopping after batch {i+1}.")
                    if JOB_DEBUG_ENABLED:
                        log_detailed(f"Batch {i+1}: Job canceled via web UI. Exiting.")
                    stop_event.set()
                    db.close()
                    break
                db.close()
            except Exception as e:
                print(f"[AutoVoter] Error checking cancellation status: {e}")

        # Adaptive Pause Logic
        is_adaptive = False
        pause_duration = p2_pause
        
        if int(GoodThisLoopPercent) < 60 and not use_tor:
            is_adaptive = True
            if p2_pause < 75:
                pause_duration = 70
            elif p2_pause < 120:
                pause_duration = 300
            else:
                pause_duration = 600
        
        if JOB_DEBUG_ENABLED:
            log_detailed(f"Batch {i+1} finished. Success Rate: {GoodThisLoopPercent:.1f}%. Pausing for {pause_duration}s (Adaptive={is_adaptive}).")
            
        # Use interruptible sleep
        if interruptible_sleep(pause_duration):
            if JOB_DEBUG_ENABLED:
                 log_detailed(f"Pause interrupted by stop event.")
            break
        
        if JOB_DEBUG_ENABLED:
             log_detailed(f"Pause complete. Resuming...")


def log_detailed(msg):
    """
    Log a detailed debug message if debug mode is enabled.
    """
    if JOB_DEBUG_ENABLED:
        now = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[DEBUG {now}] {msg}")

def print_debug(msg, levelofdetail=2):
    # Legacy wrapper for old manual script calls, redirected to detailed log if enabled
    if JOB_DEBUG_ENABLED:
        log_detailed(msg)
    elif print_debug_msg and levelofdetail <= print_debug_level:
        now = datetime.datetime.now()
        nowFormat = now.strftime("%H:%M:%S")
        print(f"{nowFormat}: {msg}")

def run_multi_scripts(times, run_count):
    threads = []
    try:
        for i in range(times):
            t = threading.Thread(target=auto_voter, args=(i, run_count))
            t.start()
            threads.append(t)
    except KeyboardInterrupt:
        print("\nCtrl+C detected! Stopping all threads...")
        stop_event.set()

    for t in threads:
        t.join()

def new_location():
    global vpnlocat, vpn_votecnt

    if not vpn_enabled:
        return
        
    if vpnmode == 1:
        start_node = vpnlocat
        while True:
            if vpnloc[vpnlocat]["loc"] == "us":
                break
            vpnlocat = (vpnlocat + 1) % (vpnloccnt + 1)
            if vpnlocat == start_node:
                break
    
    alias = vpnloc[vpnlocat]["alias"]
    if JOB_DEBUG_ENABLED:
        log_detailed(f"VPN Switching to alias: {alias} (loc: {vpnloc[vpnlocat].get('loc')})")

    try:
        connect_alias(alias)
    except Exception as e:
        print(f"VPN Connection Error: {e}")

    vpn_votecnt = 0
    vpnlocat = (vpnlocat + 1) % (vpnloccnt + 1)


def auto_voter(thread_id, RunCount):
    global vpn_votecnt, count_good
    cntpause = 0
    NoVoteRun = 0
    BATCH_GOOD = BATCH_BAD = BATCH_TOTAL = 0
    VOTE_BATCH=[]

    # Thread startup delay
    start_delay = random.randint(1,8)
    if JOB_DEBUG_ENABLED:
        log_detailed(f"[Thread {thread_id}] Starting up. Sleeping {start_delay}s.")
    
    if interruptible_sleep(start_delay):
        return

    for i in range(RunCount):
        if stop_event.is_set():
            break

        if RandomTimes:
            timeoutseconds = random.randint(RandomMin, RandomMax)
        else:
            timeoutseconds = shortPauseSeconds
        
        if JOB_DEBUG_ENABLED:
            log_detailed(f"[Thread {thread_id}] Vote attempt {i+1}/{RunCount}. Timeout set to {timeoutseconds}s.")

        try:
            # Create completely fresh session with no shared state
            session = requests.Session()
            # Explicitly clear any cookies (should be empty, but being defensive)
            session.cookies.clear()
            # Force a fresh TCP connection every time
            adapter = requests.adapters.HTTPAdapter(max_retries=1)
            session.mount('http://', adapter)
            session.mount('https://', adapter)

            # set the connection header to close
            session.headers.update({'Connection': 'close'})
            
            if use_tor:
                try:
                    if JOB_DEBUG_ENABLED:
                        log_detailed(f"[Thread {thread_id}] TOR: Signal NEWNYM...")
                    with Controller.from_port(port=9051) as controller:
                        controller.authenticate(password="welcomeTomyPa55word")
                        controller.signal(Signal.NEWNYM)
                        # Interruptible TOR delay
                        if interruptible_sleep(tor_delay): return
                    session.proxies.update(proxies)
                    if JOB_DEBUG_ENABLED:
                        log_detailed(f"[Thread {thread_id}] TOR: Proxy updated.")
                except Exception as tor_e:
                     if JOB_DEBUG_ENABLED:
                        log_detailed(f"[Thread {thread_id}] TOR Error: {tor_e}")

            # Initial Page Load
            if JOB_DEBUG_ENABLED:
                log_detailed(f"[Thread {thread_id}] GET https://poll.fm/{pollid}")
            
            # Use threading Lock for stop check if needed? No, Event is thread safe.
            if stop_event.is_set(): return

            # Random jitter before initial GET to spread out cookie requests and appear more human
            if stop_event.wait(random.uniform(0.8, 1.8)): return

            resp = session.get(f"https://poll.fm/{pollid}", timeout=10)
            resp.raise_for_status()

            PD_REQ_AUTH = resp.cookies.get("PD_REQ_AUTH")
            
            # Debug: Log cookie to verify uniqueness across threads
            if JOB_DEBUG_ENABLED:
                log_detailed(f"[Thread {thread_id}] Received PD_REQ_AUTH: {PD_REQ_AUTH[:8] if PD_REQ_AUTH else 'None'}...")
            
            # Try to get PDjs_poll cookie from server, fallback to client-side timestamp generation if missing
            pd_poll_val = resp.cookies.get(f"PDjs_poll_{pollid}")
            if not pd_poll_val:
                pd_poll_val = int(time.time())

            soup = BeautifulSoup(resp.text, 'html.parser')

            pz = next((i['value'] for i in soup.find_all('input', type='hidden') if i.get('name') == 'pz'), None)
            vote_button = soup.find('a', attrs={'data-vote': True})

            if vote_button:
                #t = int(time.time() * 1000) % 50000
                data_vote = json.loads(html.unescape(vote_button['data-vote']))
                payload = {
                    "va": data_vote.get('at'),
                    "pt": "0",
                    "r": "1",
                    "p": data_vote.get('id'),
                    "a": f"{answerid}",
                    "o": "",
                    #"t": t,
                    "t": data_vote.get('t'),
                    "token": data_vote.get('n'),
                    #"token": random_hex(32),
                    "pz": pz
                }

                headers = {
                    "User-Agent": random.choice(useragents),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Cookie": f"PD_REQ_AUTH={PD_REQ_AUTH}; PDjs_poll_{pollid}={pd_poll_val}",
                    "Referer": f"https://poll.fm/{pollid}",
                    "Priority": "u=0,i",
                    "accept-language": "en-US,en;q=0.9",
                    "Upgrade-Insecure-Requests": "1"
                }
                
                # --- DETAILED DEBUG OF PAYLOAD AND HEADERS ---
                if JOB_DEBUG_ENABLED:
                    # Log the cookie being used to verify uniqueness
                    cookie_preview = headers["Cookie"][:50] + "..." if len(headers["Cookie"]) > 50 else headers["Cookie"]
                    log_detailed(f"[Thread {thread_id}] Using Cookie: {cookie_preview}")
                    
                    debug_info = {
                        "payload": payload,
                        "headers": headers
                    }
                    log_detailed(f"[Thread {thread_id}] Submitting Vote. Data:\n{json.dumps(debug_info, indent=2)}")
                else:
                    print_debug(payload, 2)
                
                if stop_event.is_set(): return
                
                # Random jitter to prevent exact simultaneous submissions
                if stop_event.wait(random.uniform(0.8, 1.8)): return
                
                vote_resp = session.get(f"https://poll.fm/vote?", params=payload, headers=headers)
                
                # --- DETAILED DEBUG OF RESPONSE ---
                if JOB_DEBUG_ENABLED:
                    log_detailed(f"[Thread {thread_id}] Response Code: {vote_resp.status_code}")
                    log_detailed(f"[Thread {thread_id}] Response URL: {vote_resp.url}")
                    # log_detailed(f"[Thread {thread_id}] Response Headers: {vote_resp.headers}") # Verbose, maybe skip?
                
                soup_vote = BeautifulSoup(vote_resp.text, 'html.parser')

                VOTE_GOOD = 0
                if vote_resp.url.endswith("g=voted") and "revoted" not in vote_resp.url:
                    VOTE_GOOD = 1
                    NoVoteRun = 0
                    vpn_votecnt += 1
                    with lock:
                        count_good += 1
                else:
                    NoVoteRun += 1

                if VOTE_GOOD == 1:
                    if JOB_DEBUG_ENABLED:
                        log_detailed(f"[Thread {thread_id}] SUCCESS: Vote counted!")
                    else:
                        print_debug(f"Good: {vote_resp.url}", 1)
                else:
                    if JOB_DEBUG_ENABLED:
                        log_detailed(f"[Thread {thread_id}] FAIL: Vote not counted. URL: {vote_resp.url}")
                    else:
                        print_debug(f"Failed: {vote_resp.url}", 1)

                if (vpn_enabled and vpn_maxvotes > 0 and vpn_votecnt >= vpn_maxvotes) or (vpn_enabled and not use_tor and NoVoteRun > 3):
                     # Note: VPN switching is handled by start_job between batches, not by individual threads
                     if JOB_DEBUG_ENABLED:
                        log_detailed(f"[Thread {thread_id}] VPN Switch Condition Met (Failed/MaxVotes). Will switch after batch completes.")

                # Influx Record Building
                title = (soup_vote.title.string.strip() if soup_vote.title and soup_vote.title.string else "Unknown_Poll")
                VOTE_BATCH.append(build_influx_record(VOTE_GOOD, title))

                BATCH_TOTAL += 1
                if BATCH_TOTAL >= BATCH_SIZE:
                    influx_write_records(VOTE_BATCH)
                    VOTE_BATCH.clear()
            else:
                 if JOB_DEBUG_ENABLED:
                    log_detailed(f"[Thread {thread_id}] FAIL: Vote button not found on page.")

            # CoolDown Logic
            if CoolDownCount > 0 and NoVoteRun >= CoolDownCount:
                if JOB_DEBUG_ENABLED:
                     log_detailed(f"[Thread {thread_id}] Cooldown triggered! Failed {NoVoteRun} times. Sleeping {Cooldown}s.")
                influx_write_records(VOTE_BATCH)
                VOTE_BATCH.clear()
                if interruptible_sleep(Cooldown): return

            cntpause += 1
            if cntToPause == 0:
                if interruptible_sleep(timeoutseconds): return
            elif (cntpause == cntToPause):
                if JOB_DEBUG_ENABLED:
                     log_detailed(f"[Thread {thread_id}] Long pause triggered ({longPauseSeconds}s).")
                influx_write_records(VOTE_BATCH)
                VOTE_BATCH.clear()
                if interruptible_sleep(longPauseSeconds): return
                cntpause = 0

        except Exception as e:
            if JOB_DEBUG_ENABLED:
                 log_detailed(f"[Thread {thread_id}] EXCEPTION: {e}")
            else:
                print(f"Voting error: {e}")
            if interruptible_sleep(2): return

    influx_write_records(VOTE_BATCH)
    VOTE_BATCH.clear()


def influx_clean_str(stringtoclean):
    clean_string = re.sub(r'[^A-Za-z0-9 ]+', '', stringtoclean)
    clean_string = clean_string.replace(" ", "_")
    return clean_string

def build_influx_record(VOTE_GOOD, title):
    VOTE_BAD = 1 if VOTE_GOOD == 0 else 0
    unique_id = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    unix_time = int(time.time() * 1e9)
    title_clean = influx_clean_str(title)
    
    answer_script_name = f"Poll_{pollid}"

    influx_str = (
        f"vote,"
        f"pollid={pollid},"
        f"polltitle={title_clean},"
        f"answerid={answerid},"
        f"answer_script_name={answer_script_name},"
        f"unique_id={unique_id} "
        f"votes={VOTE_GOOD}i,"
        f"fail={VOTE_BAD}i "
        f"{unix_time}"
    )
    return influx_str

def influx_write_records(records):
    if not records:
        return
    try:
        client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        write_api = client.write_api(write_options=SYNCHRONOUS)
        write_api.write(bucket=INFLUX_BUCKET, record=records)
    except Exception as e:
        if JOB_DEBUG_ENABLED:
             log_detailed(f"InfluxDB Error: {e}")
        else:
            print(f"InfluxDB error: {e}")

def extract_poll_results(pollid):
    url = f"https://poll.fm/{pollid}/results"
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        page_title_tag = soup.title
        page_title = (page_title_tag.string.strip() if page_title_tag and page_title_tag.string else "Unknown_Poll")
        poll_title = influx_clean_str(re.sub(r'[^A-Za-z0-9 ]+', '', page_title))

        poll_closed = "Poll_Closed" in poll_title
        if poll_closed:
            print(f"Poll Closed - {pollid}; {page_title}")
            return
            
        influx_batch = []
        for li in soup.find_all('li', class_='pds-feedback-group'):
            answer_text = li.find('span', class_='pds-answer-text').text.strip()
            votes_text = li.find('span', class_='pds-feedback-votes').text.strip()

            votematch = re.search(r'\\d[\\d,]*', votes_text)
            if votematch:
                votes = int(votematch.group().replace(',', ''))
            else:
                votes = 0

            try:
                vote_name, vote_school = answer_text.split(", ", 1)
            except ValueError:
                vote_name = answer_text
                vote_school = "Unknown"

            vote_name = influx_clean_str(vote_name)
            vote_school = influx_clean_str(vote_school)

            unix_time = int(time.time() * 1e9)
            influx_record = (
                f"pollresults,"
                f"pollid={pollid},"
                f"polltitle={poll_title},"
                f"name={vote_name},"
                f"school={vote_school} "
                f"votes={votes}i "
                f"{unix_time}"
            )
            influx_batch.append(influx_record)

        influx_write_records(influx_batch)

    except Exception as e:
        if JOB_DEBUG_ENABLED:
             log_detailed(f"Poll Results Error: {e}")
        else:
             print(f"Results Error: {e}")

def update_queue_progress(item_id, votes_cast, votes_success, status):
    """
    Update queue item progress and emit Socket.IO event.
    Adapted from the old auto_voter_queue.py.
    """
    if not item_id:
        return
    
    try:
        db = SessionLocal()
        try:
            item = db.query(QueueItem).filter(QueueItem.id == item_id).first()
            if item:
                item.votes_cast = votes_cast
                item.votes_success = votes_success
                item.success_rate = (votes_success / votes_cast * 100) if votes_cast > 0 else 0
                item.current_status = status
                item.last_update = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
                db.commit()
                
                # Emit Socket.IO event
                if socketio_instance:
                    try:
                        socketio_instance.emit('queue_progress', {
                            'item_id': item_id,
                            'votes_cast': votes_cast,
                            'votes_success': votes_success,
                            'success_rate': item.success_rate,
                            'status': status,
                            'last_update': item.last_update.isoformat() if item.last_update else None
                        })
                    except Exception as e:
                        pass
        finally:
            db.close()
    except Exception as e:
        print(f"Failed to update progress: {e}")
