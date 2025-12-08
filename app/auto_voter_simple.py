
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
from app.models import QueueItem

# --- Global Configs (Defaults) --- #
pollToRun = 0
num_threads = 1
start_totalToRun = 0
p2_PerRun = 10
p2_pause = 1
print_debug_msg = False
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
# Using simple integer and lock for counting, or Value if we strictly followed manual but threading is fine here
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

def start_job(job_config):
    """
    Main entry point for the worker.
    job_config: dict with keys:
      pollid, answerid, votes, threads, per_run, pause, use_vpn, use_tor, item_id, socketio
    """
    global pollid, answerid, start_totalToRun, num_threads, p2_PerRun, p2_pause
    global use_tor, vpn_enabled, current_item_id, socketio_instance
    global RunPerScript, cntToRun, count_good, stop_event

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
    
    current_item_id = job_config.get('item_id')
    socketio_instance = job_config.get('socketio')

    if num_threads < 1: num_threads = 1
    RunPerScript = start_totalToRun // num_threads
    cntToRun = RunPerScript
    
    print(f"[AutoVoterSimple] Starting Job: Poll={pollid}, Threads={num_threads}, Total={start_totalToRun}, VPN={vpn_enabled}")

    # Mode 2 (Batch) logic from manual script
    # LoopTimes = max(1, RunPerScript // p2_PerRun) 
    # Logic in manual script:
    #   LoopTimes = max(1, RunPerScript // p2_PerRun)
    #   for i in range(LoopTimes): ...
    
    # We need to handle the case where RunPerScript < p2_PerRun (run at least once)
    if p2_PerRun < 1: p2_PerRun = 1
    LoopTimes = (RunPerScript + p2_PerRun - 1) // p2_PerRun # Ceiling division usually better, but sticking to manual script logic
    if LoopTimes < 1: LoopTimes = 1
    
    PreviousGood = 0
    
    # Initial VPN Connect if enabled
    if vpn_enabled:
         # new_location() called in loop, but maybe good to ensure connected first?
         # Manual script calls new_location() at start of loop.
         pass

    for i in range(LoopTimes):
        if stop_event.is_set():
            break
            
        starttime = datetime.datetime.now()
        
        if vpn_enabled:
            # Manual switch logic
            new_location()
            
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
              
        # INTEGRATION: Update Queue Progress in DB/UI
        update_queue_progress(current_item_id, WhereAt, count_good, f"Running Batch {i+1}/{LoopTimes}")

        # Write results to influx (Manual script does this)
        extract_poll_results(pollid)
        
        PreviousGood = count_good

        # Adaptive Pause Logic from manual script
        if int(GoodThisLoopPercent) < 60 and not use_tor:
            if p2_pause < 75:
                print("Sleep 70 (Adaptive)")
                time.sleep(70)
            elif p2_pause < 120:
                print("Sleep 300 (Adaptive)")
                time.sleep(300)
            else:
                print("Sleep 600 (Adaptive)")
                time.sleep(600)
        else:
            time.sleep(p2_pause)


def print_debug(msg, levelofdetail=2):
    if print_debug_msg and levelofdetail <= print_debug_level:
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
        
    # Manual script logic: if vpnmode 1, find 'us' location
    if vpnmode == 1:
        # Simple loop to find next US location
        # Note: Be careful of infinite loop if no US locations exist
        start_node = vpnlocat
        while True:
            # Check current
            if vpnloc[vpnlocat]["loc"] == "us":
                break
            # Advance
            vpnlocat = (vpnlocat + 1) % (vpnloccnt + 1)
            # Safety break
            if vpnlocat == start_node:
                break

    try:
        # connect_alias from expressvpn module
        connect_alias(vpnloc[vpnlocat]["alias"])
    except Exception as e:
        print(f"VPN Connection Error: {e}")

    vpn_votecnt = 0
    vpnlocat = (vpnlocat + 1) % (vpnloccnt + 1)


def auto_voter(thread_id, RunCount):
    global vpn_votecnt, count_good
    cntpause = 0
    switchvpn = False
    NoVoteRun = 0
    BATCH_GOOD = BATCH_BAD = BATCH_TOTAL = 0
    VOTE_BATCH=[]

    time.sleep(random.randint(1,8))

    for _ in range(RunCount):
        if stop_event.is_set():
            break

        if RandomTimes:
            timeoutseconds = random.randint(RandomMin, RandomMax)
        else:
            timeoutseconds = shortPauseSeconds

        try:
            session = requests.Session()
            if use_tor:
                with Controller.from_port(port=9051) as controller:
                    controller.authenticate(password="welcomeTomyPa55word")
                    controller.signal(Signal.NEWNYM)
                    time.sleep(tor_delay)
                session.proxies.update(proxies)

            resp = session.get(f"https://poll.fm/{pollid}", timeout=10)
            resp.raise_for_status()

            PD_REQ_AUTH = resp.cookies.get("PD_REQ_AUTH")
            soup = BeautifulSoup(resp.text, 'html.parser')

            pz = next((i['value'] for i in soup.find_all('input', type='hidden') if i.get('name') == 'pz'), None)
            vote_button = soup.find('a', attrs={'data-vote': True})

            if vote_button:
                data_vote = json.loads(html.unescape(vote_button['data-vote']))
                payload = {
                    "va": data_vote.get('at'),
                    "pt": "0",
                    "r": "1",
                    "p": data_vote.get('id'),
                    "a": f"{answerid}",
                    "o": "",
                    "t": data_vote.get('t'),
                    "token": data_vote.get('n'),
                    "pz": pz
                }

                headers = {
                    "User-Agent": random.choice(useragents),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Cookie": f"PD_REQ_AUTH={PD_REQ_AUTH}; PDjs_poll_{pollid}={int(time.time())}",
                    "Referer": f"https://poll.fm/{pollid}",
                    "Priority": "u=0,i",
                    "accept-language": "en-US,en;q=0.9",
                    "Upgrade-Insecure-Requests": "1"
                }
                
                print_debug(payload, 2)
                vote_resp = session.get(f"https://poll.fm/vote?", params=payload, headers=headers)
                soup_vote = BeautifulSoup(vote_resp.text, 'html.parser')

                VOTE_GOOD = 0
                if vote_resp.url.endswith("g=voted"):
                    VOTE_GOOD = 1
                    NoVoteRun = 0
                    vpn_votecnt += 1
                    with lock:
                        count_good += 1
                else:
                    NoVoteRun += 1

                if VOTE_GOOD == 1:
                    print_debug(f"Good: {vote_resp.url}", 1)
                else:
                    print_debug(f"Failed: {vote_resp.url}", 1)

                # Manual Logic: Switch VPN triggers?
                # The manual script had logic:
                # if start_process==1 and ((vpn_maxvotes and vpn_votecnt >= vpn_maxvotes) or (not use_tor and NoVoteRun > 3)):
                #    switchvpn = True
                # In this ported version, we use the Batch Mode (start_process=2) logic mainly.
                # But if we strictly want to support the inline switching:
                if (vpn_enabled and vpn_maxvotes > 0 and vpn_votecnt >= vpn_maxvotes) or (vpn_enabled and not use_tor and NoVoteRun > 3):
                     switchvpn = True

                # Influx Record Building
                title = (soup_vote.title.string.strip() if soup_vote.title and soup_vote.title.string else "Unknown_Poll")
                VOTE_BATCH.append(build_influx_record(VOTE_GOOD, title))

                BATCH_TOTAL += 1
                if BATCH_TOTAL >= BATCH_SIZE:
                    influx_write_records(VOTE_BATCH)
                    VOTE_BATCH.clear()

            if switchvpn:
                new_location()
                switchvpn = False

            # CoolDown Logic
            if CoolDownCount > 0 and NoVoteRun >= CoolDownCount:
                influx_write_records(VOTE_BATCH)
                VOTE_BATCH.clear()
                time.sleep(Cooldown)

            cntpause += 1
            if cntToPause == 0:
                time.sleep(timeoutseconds)
            elif (cntpause == cntToPause):
                influx_write_records(VOTE_BATCH)
                VOTE_BATCH.clear()
                time.sleep(longPauseSeconds)
                cntpause = 0

        except Exception as e:
            print(f"Voting error: {e}")
            time.sleep(2)

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
    
    # Needs a fallback if poll pollToRun index access fails, manual script assumed pollToRun global index
    # We will just use the pollid as the name if we can't find a better one
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
            # percent = li.find('span', class_='pds-feedback-per').text.strip()

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

