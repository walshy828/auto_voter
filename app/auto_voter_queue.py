import subprocess
import threading
import multiprocessing
import random
import string
import time
import datetime
import re
import html
import json
import os
import requests
from bs4 import BeautifulSoup
from stem import Signal
from stem.control import Controller
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
from expressvpn import connect_alias
import app.config as config

# --- Global Configs --- #
QUEUE_FILE = 'queue.json'
# polls configuration is now passed via queue item parameters
pollToRun = 0
jobname = "default_poll"  # Will be set by worker.py
num_threads = 100            #Optimied: 110
start_totalToRun =1000
start_process = 2 #BATCHES
p2_PerRun = 10                  #Optimied: 24
p2_pause = 70                  #Optimied: 65
print_debug_msg=False
print_debug_level=1
DEBUG_MODE = os.environ.get('DEBUG_MODE', 'false').lower() == 'true'

RandomTimes = False
RandomMin = 2
RandomMax = 30
tor_delay=1

cntToPause = 0
longPauseSeconds = 70
shortPauseSeconds = 0

vpn_maxvotes = 0
vpnmode = 1
CoolDownCount = 0
Cooldown = 95


iPhoneUser = True

INFLUX_URL = config.INFLUX_URL
INFLUX_TOKEN = config.INFLUX_TOKEN
INFLUX_ORG = config.INFLUX_ORG
INFLUX_BUCKET = config.INFLUX_BUCKET
BATCH_SIZE = 10

RunPerScript = start_totalToRun // num_threads
cntToRun = RunPerScript

print_output = 1
stop_event = threading.Event()

pollid, answerid = 0,0
#use_tor = protocol.lower() == "tor"
use_tor = False
use_vpn = True

# Tor Config
TOR_SOCKS_PORT = int(os.environ.get('TOR_SOCKS_PORT', 9050))
TOR_CONTROL_PORT = int(os.environ.get('TOR_CONTROL_PORT', 9051))
TOR_PASSWORD = os.environ.get('TOR_PASSWORD', "welcomeTomyPa55word")

proxies = {
    'http': f'socks5h://127.0.0.1:{TOR_SOCKS_PORT}',
    'https': f'socks5h://127.0.0.1:{TOR_SOCKS_PORT}'
}
# Use threading instead of multiprocessing for gevent compatibility
# The worker runs in a single process, so threading is sufficient
lock = threading.Lock()
count_good_value = 0  # Simple integer instead of multiprocessing.Value

# Progress tracking globals
current_item_id = None
socketio_instance = None

vpnloc = config.vpnloc  # you can load this from config if big
vpnloccnt = len(vpnloc) - 1
vpnlocat = random.randint(0,vpnloccnt)
vpn_votecnt = 0

useragents = config.useragents  # better load it externally if large

# --- Functions --- #
def start():
    global pollid, answerid,start_totalToRun,num_threads, p2_PerRun,p2_pause,RunPerScript,cntToRun
    #vote_start(start_process)
    add_to_queue(0,"",0,0,6000, 100, 10, 70)
    add_to_queue(1, "", 0, 0, 6000, 100, 10, 70)
    add_to_queue(2, "", 0, 0, 6000, 100, 10, 70)
    #add_to_queue(3,"",0,0,12000, 100, 10, 70)
    #add_to_queue(4, "", 0, 0, 15000, 100, 10, 70)
    #add_to_queue(0,"OwenGrangerDavidProuty",16084911,70796551,2000, 100, 10, 70)


    next_item=process_next_item()

    while next_item is not None:

        print(f"WORKING ON : {next_item}")
        pollid = next_item['pollid']
        answerid = next_item['answerid']
        start_totalToRun = next_item['votes']  # The votes key holds the total run count
        num_threads = next_item['threads']
        p2_PerRun = next_item['perRun']
        p2_pause = next_item['pause']

        RunPerScript = start_totalToRun // num_threads
        cntToRun = RunPerScript

        vote_start(2)

        # Get the next item for the next iteration of the loop
        next_item = process_next_item()




def load_queue():
    """Loads the queue from the JSON file."""
    if not os.path.exists(QUEUE_FILE):
        return []
    with open(QUEUE_FILE, 'r') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            # Handle empty or malformed file
            return []


def save_queue(queue):
    """Saves the current queue to the JSON file."""
    with open(QUEUE_FILE, 'w') as f:
        json.dump(queue, f, indent=4)


# ---

def add_to_queue(poll_index_to_run,my_jobname,my_pollid,my_answerid, votes, threads, per_run, pause):
    """Adds a dictionary item with the specified fields to the end of the queue."""
    print(f"Adding task for '{poll_index_to_run}' to the queue...")

    # Create the task dictionary


    if(my_pollid>=100):
        pollid=my_pollid
        answerid=my_answerid
        jobname=my_jobname
    else:
        # Fallback: use parameters if polls array doesn't exist
        pollid = my_pollid if my_pollid else 0
        answerid = my_answerid if my_answerid else 0
        jobname = my_jobname if my_jobname else "unknown_poll"

    task_item = {
        "jobname": jobname,
        "pollid": pollid,
        "answerid": answerid,
        "votes": votes,
        "threads": threads,
        "perRun": per_run,
        "pause": pause,
        "timestamp": time.time()  # Optional: add a timestamp for when the task was created
    }

    queue = load_queue()
    queue.append(task_item)
    save_queue(queue)
    print("Task added.")


def process_next_item():
    """
    Reads the first item (dictionary) from the queue, removes it, and returns it.
    Returns None if the queue is empty.
    """
    queue = load_queue()
    if not queue:
        print("Queue is empty. Nothing to process.")
        return None

    # Get the first item (FIFO - First-In, First-Out)
    item_to_process = queue.pop(0)
    save_queue(queue)
    print(f"Processing task for '{item_to_process}'...")
    return item_to_process

def update_queue_progress(item_id, votes_cast, votes_success, status):
    """
    Update queue item progress and emit Socket.IO event.
    """
    if not item_id:
        return
    
    try:
        from app.db import SessionLocal
        from app.models import QueueItem
        import datetime
        
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
                
                # Emit Socket.IO event if socketio instance is available
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
                        if DEBUG_MODE:
                            print(f"[DEBUG] Failed to emit Socket.IO event: {e}")
        finally:
            db.close()
    except Exception as e:
        if DEBUG_MODE:
            print(f"[DEBUG] Failed to update progress: {e}")

def connect_vpn():
    """Connect to ExpressVPN using random location from vpnloc list."""
    global vpnlocat
    """Connect to ExpressVPN with a random location from the list."""
    global vpnlocat
    start_time = time.time()
    try:
        import subprocess
        # Check if expressvpn command exists first (quick check)
        try:
            subprocess.run(['which', 'expressvpn'], capture_output=True, timeout=2, check=True)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            print("[VPN] ExpressVPN not found or not available")
            return False

        # Check if already connected (short timeout)
        status_start = time.time()
        try:
            result = subprocess.run(['expressvpn', 'status'], capture_output=True, text=True, timeout=3)
            status_elapsed = time.time() - status_start
            if DEBUG_MODE:
                print(f"[VPN DEBUG] Status output: {result.stdout}")
            print(f"[VPN PERF] Status check took {status_elapsed:.2f}s")
            
            if 'Connected' in result.stdout:
                # Extract location from status output
                location = "Unknown"
                for line in result.stdout.split('\n'):
                    if 'Connected to' in line:
                        location = line.split('Connected to')[-1].strip()
                        break
                total_elapsed = time.time() - start_time
                print(f"[VPN] Already connected to: {location} (total: {total_elapsed:.2f}s)")
                return True
        except subprocess.TimeoutExpired:
            status_elapsed = time.time() - status_start
            print(f"[VPN] Status check timed out after {status_elapsed:.2f}s")
            # Don't return False here, try to connect anyway
        
        # Get random location from list
        try:
            # If vpnmode is 1, ensure we pick a US location
            if vpnmode == 1:
                # Try to find a US location starting from current vpnlocat
                start_index = vpnlocat
                found_us = False
                while True:
                    if vpnloc[vpnlocat]["loc"] == "us":
                        found_us = True
                        break
                    vpnlocat = (vpnlocat + 1) % (vpnloccnt + 1)
                    if vpnlocat == start_index:
                        break
                
                if not found_us:
                     print("[VPN] Warning: No US locations found, using current index")

            location_alias = vpnloc[vpnlocat]["alias"]
            print(f"[VPN] Connecting to location: {location_alias} (loc={vpnloc[vpnlocat].get('loc', 'unknown')})...")
        except (IndexError, KeyError) as e:
            print(f"[VPN] Error getting location from list: {e}, falling back to 'smart'")
            location_alias = "smart"
        
        # Enforce Network Lock OFF before connecting
        netlock_start = time.time()
        try:
            subprocess.run(['expressvpn', 'preferences', 'set', 'network_lock', 'off'], 
                         capture_output=True, timeout=5, check=False)
            netlock_elapsed = time.time() - netlock_start
            print(f"[VPN] Enforced Network Lock: OFF ({netlock_elapsed:.2f}s)")
        except Exception as e:
            netlock_elapsed = time.time() - netlock_start
            print(f"[VPN] Warning: Failed to set network_lock off after {netlock_elapsed:.2f}s: {e}")

        connect_start = time.time()
        try:
            result = subprocess.run(['expressvpn', 'connect', location_alias], 
                                  capture_output=True, text=True, timeout=15)
            connect_elapsed = time.time() - connect_start
            
            if result.returncode == 0:
                # Get the connected location
                location = "Unknown"
                for line in result.stdout.split('\n'):
                    if 'Connected to' in line:
                        location = line.split('Connected to')[-1].strip()
                        break
                total_elapsed = time.time() - start_time
                print(f"[VPN] ✓ Connected successfully to: {location} (connect: {connect_elapsed:.2f}s, total: {total_elapsed:.2f}s)")
                return True
            else:
                # Check for "already connected" message
                if "Please disconnect first" in result.stdout or "Please disconnect first" in result.stderr:
                     total_elapsed = time.time() - start_time
                     print(f"[VPN] VPN was already connected (detected via connect error, total: {total_elapsed:.2f}s).")
                     return True
                     
                print(f"[VPN] Connection failed after {connect_elapsed:.2f}s: {result.stderr} {result.stdout}")
                return False
        except subprocess.TimeoutExpired:
            connect_elapsed = time.time() - connect_start
            print(f"[VPN] Connection timed out after {connect_elapsed:.2f}s")
            return False
    except Exception as e:
        total_elapsed = time.time() - start_time
        print(f"[VPN] Error connecting after {total_elapsed:.2f}s: {e}")
        return False

def disconnect_vpn():
    """Disconnect from ExpressVPN."""
    start_time = time.time()
    try:
        import subprocess
        # Check if expressvpn command exists first
        try:
            subprocess.run(['which', 'expressvpn'], capture_output=True, timeout=2, check=True)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            print("[VPN] ExpressVPN not found, skipping disconnect")
            return True
        
        # Check if connected (short timeout)
        try:
            result = subprocess.run(['expressvpn', 'status'], capture_output=True, text=True, timeout=3)
            if 'Not connected' in result.stdout:
                print("[VPN] Already disconnected")
                return True
        except subprocess.TimeoutExpired:
            print("[VPN] Status check timed out")
            return False
        
        # Disconnect
        print("[VPN] Disconnecting from ExpressVPN...")
        try:
            result = subprocess.run(['expressvpn', 'disconnect'], capture_output=True, text=True, timeout=5)
            disconnect_elapsed = time.time() - start_time
            
            if result.returncode == 0 or 'Not connected' in result.stdout:
                print(f"[VPN] ✓ Disconnected successfully ({disconnect_elapsed:.2f}s)")
                return True
            else:
                print(f"[VPN] Disconnection failed after {disconnect_elapsed:.2f}s: {result.stderr}")
                
                # Check for daemon error
                if "Cannot connect to expressvpnd daemon" in result.stderr or "expressvpnd daemon is not running" in result.stderr:
                    print("[VPN] Daemon appears to be down during disconnect. Attempting to restart...")
                    try:
                        subprocess.run(['service', 'expressvpn', 'restart'], timeout=10)
                        print("[VPN] Daemon restart command issued. Waiting 5s...")
                        time.sleep(5)
                        # Try disconnect one more time
                        subprocess.run(['expressvpn', 'disconnect'], capture_output=True, timeout=5)
                        return True # Assume success or at least we tried
                    except Exception as de:
                        print(f"[VPN] Failed to restart daemon: {de}")
                
                return False
        except subprocess.TimeoutExpired:
            disconnect_elapsed = time.time() - start_time
            print(f"[VPN] Disconnect timed out after {disconnect_elapsed:.2f}s")
            return False
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[VPN] Error disconnecting after {elapsed:.2f}s: {e}")
        return False

def vote_start(start_mode):
    """
    Start the voting process.
    
    Args:
        start_mode: 1 = simple mode, 2 = batch mode with pauses
    
    Batch mode (2) logic:
    - Runs in loops until total votes per thread (RunPerScript) is reached
    - Each loop: switches VPN (if use_vpn=True and use_tor=False), runs threads, pauses
    - Adaptive pausing: if success rate < 60% and not using Tor, extends pause time
    """
    try:
        job_start_time = time.time()
        print(f"[vote_start] Starting with mode={start_mode}")
        global RunPerScript, cntToRun
        
        # Connect to VPN if needed
        vpn_connected = False
        if use_vpn:
            vpn_start = time.time()
            print(f"[vote_start] VPN enabled for this job, connecting...")
            vpn_connected = connect_vpn()
            vpn_elapsed = time.time() - vpn_start
            if not vpn_connected:
                print(f"[vote_start] WARNING: VPN connection failed after {vpn_elapsed:.2f}s")
            else:
                print(f"[vote_start] VPN connection completed in {vpn_elapsed:.2f}s")
        
        # Recalculate RunPerScript based on current globals
        # This is critical because worker.py sets start_totalToRun/num_threads but might not update RunPerScript
        if num_threads > 0:
            RunPerScript = start_totalToRun // num_threads
        else:
            RunPerScript = 0
        cntToRun = RunPerScript
        
        print(f"[vote_start] Calculated RunPerScript={RunPerScript}, cntToRun={cntToRun}")

        if start_mode == 1:
            print(f"[vote_start] Running simple mode")
            run_multi_scripts(num_threads, cntToRun)
        elif start_mode == 2:
            print(f"[vote_start] Running batch mode")
            # Reset the counter at the start of the entire voting session
            global count_good_value
            if DEBUG_MODE:
                print(f"[DEBUG] Resetting count_good. Previous value: {count_good_value}")
        count_good_value = 0
        
        # Calculate total votes per thread we need to run
        # Note: RunPerScript = start_totalToRun // num_threads
        # We will run until we hit this target per thread
        
        # Resume from where we left off if this is a resumed job
        total_ran_per_thread = 0
        if current_item_id:
            from app.db import SessionLocal
            from app.models import QueueItem
            db = SessionLocal()
            try:
                item = db.query(QueueItem).filter(QueueItem.id == current_item_id).first()
                if item and item.votes_cast:
                    # Calculate how many votes per thread have already been cast
                    # votes_cast is the total across all threads
                    # total_ran_per_thread is per thread
                    if num_threads > 0:
                        total_ran_per_thread = item.votes_cast // num_threads
                        print(f"[vote_start] Resuming from batch: {total_ran_per_thread} votes already cast per thread (total: {item.votes_cast})")
                    else:
                        total_ran_per_thread = 0
            finally:
                db.close()
        
        batch_index = 0
        
        # print(f"[vote_start] Entering batch loop. RunPerScript={RunPerScript}")
        
        while total_ran_per_thread < RunPerScript:
            batch_index += 1
            
            # Check for pause status before each batch
            if current_item_id:
                from app.db import SessionLocal
                from app.models import QueueItem, QueueStatus
                db = SessionLocal()
                try:
                    item = db.query(QueueItem).filter(QueueItem.id == current_item_id).first()
                    if item and item.status == QueueStatus.paused:
                        pause_start = time.time()
                        last_log_time = time.time()
                        print(f"[vote_start] Item {current_item_id} is paused, waiting...")
                        # Wait in a loop checking every 5 seconds for resume
                        while True:
                            time.sleep(5)
                            db.refresh(item)
                            if item.status != QueueStatus.paused:
                                pause_duration = time.time() - pause_start
                                print(f"[vote_start] Item {current_item_id} resumed after {pause_duration:.1f}s")
                                break
                            # Only log every 60 seconds to avoid log spam
                            if time.time() - last_log_time >= 60:
                                pause_duration = time.time() - pause_start
                                print(f"[vote_start] Still paused ({pause_duration:.0f}s elapsed)...")
                                last_log_time = time.time()
                finally:
                    db.close()
            
            # Determine how many to run in this batch
            # Don't exceed the remaining votes needed per thread
            # And don't exceed the batch size (p2_PerRun)
            remaining_per_thread = RunPerScript - total_ran_per_thread
            to_run_this_batch = min(p2_PerRun, remaining_per_thread)
            
            # print(f"[vote_start] Batch {batch_index}: to_run_this_batch={to_run_this_batch}, remaining={remaining_per_thread}")
            
            if to_run_this_batch <= 0:
                break

            # Start timing for this batch
            batch_start = time.time()
            starttime = datetime.datetime.now()

            # Switch VPN location only if using VPN and NOT using Tor
            # print(f"[vote_start] use_vpn={use_vpn}, use_tor={use_tor}")
            if use_vpn and not use_tor:
                # Skip switch on first batch if we just connected in the preamble
                if batch_index == 1 and vpn_connected:
                    print(f"[vote_start] First batch with fresh VPN connection, skipping immediate switch.")
                else:
                    vpn_switch_start = time.time()
                    # print(f"[vote_start] Calling new_location()...")
                    try:
                        success = new_location()
                        vpn_switch_elapsed = time.time() - vpn_switch_start
                        if success:
                            print(f"[vote_start PERF] VPN location switch took {vpn_switch_elapsed:.2f}s")
                        else:
                            # All VPN retry attempts failed
                            error_msg = f"FATAL: VPN connection failed after {vpn_switch_elapsed:.2f}s - all retry attempts exhausted"
                            print(f"[vote_start] {error_msg}")
                            
                            # Update queue item status to failed
                            if current_item_id:
                                from app.db import SessionLocal
                                from app.models import QueueItem, QueueStatus
                                db = SessionLocal()
                                try:
                                    item = db.query(QueueItem).filter(QueueItem.id == current_item_id).first()
                                    if item:
                                        item.status = QueueStatus.canceled
                                        item.current_status = error_msg
                                        item.completed_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
                                        db.commit()
                                        print(f"[vote_start] Updated queue item {current_item_id} status to canceled")
                                finally:
                                    db.close()
                            
                            # Exit the job
                            raise Exception(error_msg)
                    except Exception as e:
                        if "FATAL: VPN connection failed" in str(e):
                            # Re-raise VPN fatal errors
                            raise
                        else:
                            # Other errors - log but continue
                            vpn_switch_elapsed = time.time() - vpn_switch_start
                            print(f"[vote_start] ERROR: VPN location switch failed after {vpn_switch_elapsed:.2f}s: {e}")
                            import traceback
                            traceback.print_exc()
                            # Continue anyway - might still work with current location
                    # print(f"[vote_start] new_location() completed")
            
            # Run the voting threads
            if DEBUG_MODE:
                print(f"[DEBUG] Batch {batch_index}: Running {num_threads} threads x {to_run_this_batch} votes")
            
            voting_start = time.time()
            print(f"[vote_start] Calling run_multi_scripts({num_threads}, {to_run_this_batch})...")
            try:
                run_multi_scripts(num_threads, to_run_this_batch)
                voting_elapsed = time.time() - voting_start
                print(f"[vote_start PERF] Voting batch {batch_index} took {voting_elapsed:.2f}s")
            except Exception as e:
                voting_elapsed = time.time() - voting_start
                print(f"[vote_start] ERROR: Voting batch {batch_index} failed after {voting_elapsed:.2f}s: {e}")
                import traceback
                traceback.print_exc()
                # Continue to next batch - some votes may have succeeded
            
            # Update counters
            total_ran_per_thread += to_run_this_batch
            
            # Calculate statistics
            # Total votes cast so far = threads * votes_per_thread_so_far
            WhereAt = total_ran_per_thread * num_threads
            
            # Calculate success for this specific batch (approximate, since count_good is cumulative)
            # We can't easily track per-batch success without another counter, but we can track delta
            # However, for the UI, we care about overall progress
            
            PercentGood = (count_good_value / max(1, WhereAt)) * 100

            # Print progress
            now = datetime.datetime.now()
            nowFormat = now.strftime("%H:%M:%S")
            TimeRun = (now - starttime).total_seconds()

            print(f"{nowFormat}: Batch {batch_index} done. {to_run_this_batch} per thread. "
                  f"Overall: {count_good_value}/{WhereAt} ({PercentGood:.1f}%)")
            
            # Update progress in database and emit Socket.IO event
            if current_item_id:
                update_queue_progress(
                    current_item_id,
                    WhereAt,
                    count_good_value,
                    f"Batch {batch_index} complete"
                )
            
            # Extract poll results after each batch
            extract_poll_results(pollid)

            # Check if we are done
            if total_ran_per_thread >= RunPerScript:
                break

            # Adaptive pausing logic
            # Calculate success rate for the last batch would require tracking previous count_good
            # For simplicity, let's use the overall success rate for adaptive pausing
            
            pause_start = time.time()
            if int(PercentGood) < 60 and not use_tor:
                pause_time = 70 if p2_pause < 75 else (300 if p2_pause < 120 else 600)
                if current_item_id:
                    update_queue_progress(
                        current_item_id,
                        WhereAt,
                        count_good_value,
                        f"Pausing ({pause_time}s) - Low success rate"
                    )
                
                if p2_pause < 75:
                    if DEBUG_MODE:
                        print("[DEBUG] Low success rate, sleeping 70s")
                    time.sleep(70)
                elif p2_pause < 120:
                    if DEBUG_MODE:
                        print("[DEBUG] Low success rate, sleeping 300s")
                    # Disconnect during long sleep to save CPU
                    if use_vpn and not use_tor:
                        disconnect_vpn()
                    time.sleep(300)
                else:
                    if DEBUG_MODE:
                        print("[DEBUG] Low success rate, sleeping 600s")
                    # Disconnect during long sleep to save CPU
                    if use_vpn and not use_tor:
                        disconnect_vpn()
                    time.sleep(600)
            else:
                if current_item_id and p2_pause > 0:
                    update_queue_progress(
                        current_item_id,
                        WhereAt,
                        count_good_value,
                        f"Pausing ({p2_pause}s)"
                    )
                
                if DEBUG_MODE:
                    print(f"[DEBUG] Sleeping {p2_pause}s")
                
                # Disconnect during pause if > 10s to save CPU
                if p2_pause > 10 and use_vpn and not use_tor:
                    disconnect_vpn()
                
                time.sleep(p2_pause)
            
            pause_elapsed = time.time() - pause_start
            batch_elapsed = time.time() - batch_start
            print(f"[vote_start PERF] Batch {batch_index} total (including pause): {batch_elapsed:.2f}s (pause: {pause_elapsed:.2f}s)")
    except Exception as e:
        print(f"[vote_start] FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        # Disconnect VPN if we connected it (but keep connected if using Tor)
        if use_vpn and not use_tor and vpn_connected:
            print("[vote_start] Job complete, disconnecting VPN...")
            disconnect_vpn()
        elif use_vpn and use_tor:
            print("[vote_start] Job complete, keeping VPN connected (Tor mode)")

def print_debug(msg, levelofdetail=2):

    if print_debug_msg and levelofdetail<=print_debug_level:
        now = datetime.datetime.now()
        nowFormat = now.strftime("%H:%M:%S")
        print(f"{nowFormat}: {msg}")

def run_multi_scripts(times, run_count):
    # print(f"[run_multi_scripts] Starting {times} threads, {run_count} runs each")
    threads = []
    try:
        for i in range(times):
            # print(f"[run_multi_scripts] Creating thread {i}")
            t = threading.Thread(target=auto_voter, args=(i, run_count))
            t.start()
            threads.append(t)
            # print(f"[run_multi_scripts] Thread {i} started")
    except KeyboardInterrupt:
        print("\nCtrl+C detected! Stopping all threads...")
        stop_event.set()
    except Exception as e:
        print(f"[run_multi_scripts] Error creating threads: {e}")
        import traceback
        traceback.print_exc()

    # print(f"[run_multi_scripts] Waiting for {len(threads)} threads to complete...")
    for i, t in enumerate(threads):
        # print(f"[run_multi_scripts] Joining thread {i}...")
        t.join()
        # print(f"[run_multi_scripts] Thread {i} completed")
    # print(f"[run_multi_scripts] All threads completed")

def new_location():
    """
    Switch to a new VPN location with retry logic.
    Tries up to 3 different locations before giving up.
    Returns True if successful, False if all attempts failed.
    """
    global vpnlocat
    max_retries = 3
    
    for attempt in range(max_retries):
        start_time = time.time()
        
        # Disconnect first
        disconnect_start = time.time()
        try:
            if not disconnect_vpn():
                disconnect_elapsed = time.time() - disconnect_start
                print(f"[VPN] Failed to disconnect after {disconnect_elapsed:.2f}s on attempt {attempt + 1}/{max_retries}")
                
                # Check if we should restart daemon
                # Note: disconnect_vpn handles its own logging, but if it returned False, something went wrong.
                # We'll rely on the retry loop to handle it.
                
                if attempt < max_retries - 1:
                    print(f"[VPN] Retrying with next location...")
                    vpnlocat = (vpnlocat + 1) % (vpnloccnt + 1)
                    continue
                else:
                    return False
            disconnect_elapsed = time.time() - disconnect_start
        except Exception as e:
            disconnect_elapsed = time.time() - disconnect_start
            print(f"[VPN] Error during disconnect after {disconnect_elapsed:.2f}s: {e}")
            # Try to continue anyway
        
        # Increment location counter
        vpnlocat = (vpnlocat + 1) % (vpnloccnt + 1)
        
        if vpnmode == 1:
            # Find next US location
            start_index = vpnlocat
            while True:
                vpnlocat = (vpnlocat + 1) % (vpnloccnt + 1)
                if vpnloc[vpnlocat]["loc"] == "us":
                    break
                if vpnlocat == start_index:
                    print("[VPN] Warning: No US locations found in config!")
                    break

        connect_start = time.time()
        try:
            location_alias = vpnloc[vpnlocat]["alias"]
            print(f"[VPN] Attempt {attempt + 1}/{max_retries}: Switching to location: {location_alias}...")
            
            result = subprocess.run(['expressvpn', 'connect', location_alias], 
                                  capture_output=True, text=True, timeout=30)
            connect_elapsed = time.time() - connect_start
            total_elapsed = time.time() - start_time
            
            if result.returncode == 0:
                # Extract location from output
                location = "Unknown"
                for line in result.stdout.split('\n'):
                    if 'Connected to' in line:
                        location = line.split('Connected to')[-1].strip()
                        break
                print(f"[VPN] ✓ Switched to: {location} (disconnect: {disconnect_elapsed:.2f}s, connect: {connect_elapsed:.2f}s, total: {total_elapsed:.2f}s)")
                return True
            else:
                print(f"[VPN] Failed to switch to {location_alias} after {total_elapsed:.2f}s: {result.stderr}")
                
                # Check for daemon error
                if "Cannot connect to expressvpnd daemon" in result.stderr or "expressvpnd daemon is not running" in result.stderr:
                    print("[VPN] Daemon appears to be down. Attempting to restart...")
                    try:
                        subprocess.run(['service', 'expressvpn', 'restart'], timeout=10)
                        print("[VPN] Daemon restart command issued. Waiting 5s...")
                        time.sleep(5)
                    except Exception as de:
                        print(f"[VPN] Failed to restart daemon: {de}")

                if attempt < max_retries - 1:
                    print(f"[VPN] Retrying with next location...")
                    continue
                else:
                    return False
                    
        except subprocess.TimeoutExpired:
            connect_elapsed = time.time() - connect_start
            total_elapsed = time.time() - start_time
            print(f"[VPN] ERROR: Connection to {location_alias} timed out after {connect_elapsed:.2f}s (total: {total_elapsed:.2f}s)")
            
            # Kill ONLY the hanging connect process, not the daemon
            print("[VPN] Attempting to kill hanging VPN connection process...")
            try:
                # Use pkill -f to match the full command line "expressvpn connect"
                # This avoids killing the daemon "expressvpnd"
                subprocess.run(['pkill', '-9', '-f', 'expressvpn connect'], timeout=5)
            except:
                pass
            
            if attempt < max_retries - 1:
                print(f"[VPN] Retrying with next location...")
                continue
            else:
                return False
                
        except Exception as e:
            total_elapsed = time.time() - start_time
            print(f"[VPN] Error switching to {location_alias} after {total_elapsed:.2f}s: {e}")
            import traceback
            traceback.print_exc()
            
            if attempt < max_retries - 1:
                print(f"[VPN] Retrying with next location...")
                continue
            else:
                return False
    
    return False

def auto_voter(thread_id, RunCount):
    try:
        print(f"[auto_voter] Thread {thread_id} starting, RunCount={RunCount}")
        global vpn_votecnt
        cntpause = 0
        switchvpn = False
        NoVoteRun = 0
        BATCH_GOOD = BATCH_BAD = BATCH_TOTAL = 0
        VOTE_BATCH=[]
        # Note: count_good is a shared counter across all threads, don't reset it here

        if DEBUG_MODE:
            print(f"[DEBUG] Thread {thread_id} started, will run {RunCount} votes")

        # print(f"[auto_voter] Thread {thread_id} sleeping initial delay...")
        time.sleep(random.randint(1,8))
        # print(f"[auto_voter] Thread {thread_id} entering loop...")

        for _ in range(RunCount):
            if stop_event.is_set():
                # print(f"[auto_voter] Thread {thread_id} stop_event set, breaking...")
                break

            if RandomTimes:
                timeoutseconds = random.randint(RandomMin, RandomMax)
            else:
                timeoutseconds = shortPauseSeconds

            try:
                # print(f"[auto_voter] Thread {thread_id} creating session...")
                session = requests.Session()
                if use_tor:
                    try:
                        with Controller.from_port(port=TOR_CONTROL_PORT) as controller:
                            controller.authenticate(password=TOR_PASSWORD)
                            controller.signal(Signal.NEWNYM)
                            time.sleep(tor_delay)
                    except Exception as e:
                        print(f"Tor Control Error (Port {TOR_CONTROL_PORT}): {e}")
                        # Continue anyway, maybe just SOCKS is working or we don't need new identity yet
                    
                    session.proxies.update(proxies)
                
                # print(f"[auto_voter] Thread {thread_id} requesting poll {pollid}...")
                # print(f"[auto_voter] Thread {thread_id} requesting poll {pollid}...")
                resp = session.get(f"https://poll.fm/{pollid}", timeout=30)
                # print(f"[auto_voter] Thread {thread_id} got response: {resp.status_code}")
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
                        "a": f"{answerid}", #%2C
                        "o": "",
                        #"t": str(int(time.time())),
                        "t": data_vote.get('t'),
                        "token": data_vote.get('n'),
                        "pz": pz
                    }

                    headers = {
                        "User-Agent": random.choice(useragents),
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                        "Cookie": f"PD_REQ_AUTH={PD_REQ_AUTH}; PDjs_poll_{pollid}={int(time.time())}",
                        "Referer": f"https://poll.fm/{pollid}",
                        "Priority": "u=0,i",
                        "accept-language": "en-US,en;q=0.9",
                        "accept-encoding": "gzip, deflate, br, zstd",
                        "Upgrade-Insecure-Requests": "1"

                    }
                    print_debug(payload, 2)
                    vote_resp = session.get(f"https://poll.fm/vote?", params=payload, headers=headers)
                    soup_vote = BeautifulSoup(vote_resp.text, 'html.parser')

                    VOTE_GOOD = 0
                    if vote_resp.url.endswith("g=voted"):
                        VOTE_GOOD=1
                        NoVoteRun = 0
                        #vote_success(thread_id)
                        vpn_votecnt += 1
                        global count_good_value
                        with lock:
                            count_good_value += 1

                    else:
                        NoVoteRun += 1

                    if VOTE_GOOD==1:
                        print_debug(f"Good: {vote_resp.url}",1)
                    else:
                        print_debug(f"Failed: {vote_resp.url}",1)

                    if start_process==1 and ((vpn_maxvotes and vpn_votecnt >= vpn_maxvotes) or (not use_tor and NoVoteRun > 3)):
                        switchvpn = True

                    # Influx Record Building
                    title_str = soup_vote.title.string if soup_vote.title else "Unknown"
                    VOTE_BATCH.append(build_influx_record(VOTE_GOOD, title_str))

                    BATCH_TOTAL += 1
                    if BATCH_TOTAL >= BATCH_SIZE:
                        influx_write_records(VOTE_BATCH)
                        VOTE_BATCH.clear()

                if switchvpn:
                    new_location()
                    switchvpn = False

                if CoolDownCount > 0 and NoVoteRun >= CoolDownCount:
                    #print("G:" + str() + ";B:" + "; Cool until " + str(
                    #    datetime.datetime.now() + datetime.timedelta(seconds=CoolDown)), 2, thread_id)
                    influx_write_records(VOTE_BATCH)
                    VOTE_BATCH.clear()
                    time.sleep(CoolDown)

                cntpause = cntpause + 1
                if cntToPause == 0:
                    if DEBUG_MODE:
                        print(f"[DEBUG] Thread {thread_id} pausing {timeoutseconds}s")
                    time.sleep(timeoutseconds)
                elif (cntpause == cntToPause):
                    if DEBUG_MODE:
                        print(f"[DEBUG] Thread {thread_id} long pause {longPauseSeconds}s")
                    influx_write_records(VOTE_BATCH)
                    VOTE_BATCH.clear()
                    time.sleep(longPauseSeconds)
                    cntpause = 0

            except Exception as e:
                print(f"Voting error: {type(e).__name__}: {e}")
                if print_debug_msg:
                    import traceback
                    traceback.print_exc()
                time.sleep(2)

        influx_write_records(VOTE_BATCH)
        VOTE_BATCH.clear()
        print(f"[auto_voter] Thread {thread_id} completed successfully")
    except Exception as e:
        print(f"[auto_voter] Thread {thread_id} FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()

def vote_success(thread_id):
    print(f"[Thread {thread_id}] Vote success!")

def influx_clean_str(stringtoclean):

    clean_string = re.sub(r'[^A-Za-z0-9 ]+', '', stringtoclean)  # Remove non-alphanumeric characters
    clean_string = clean_string.replace(" ", "_")  # Replace spaces with underscores
    return clean_string

def build_influx_record(VOTE_GOOD, title):
    if VOTE_GOOD==0:
        VOTE_BAD=1
        status_str = 'fail'
    else:
        VOTE_BAD=0
        status_str = 'success'
        
    unique_id = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    unix_time = int(time.time() * 1e9)
    title_clean = influx_clean_str(title)
    answer_script_name = influx_clean_str(jobname)
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
    
    # SQLite: Save PollVote
    try:
        from app.db import SessionLocal
        from app.models import Poll, PollVote
        db = SessionLocal()
        
        # Try to link to a poll record if possible
        poll_record = db.query(Poll).filter(Poll.pollid == str(pollid)).first()
        
        pv = PollVote(
            poll_id=poll_record.id if poll_record else None,
            pollid=str(pollid),
            timestamp=datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
            answerid=str(answerid),
            status=status_str,
            worker_id=None # We don't easily have worker_id here in this function scope without passing it down
        )
        db.add(pv)
        db.commit()
        db.close()
    except Exception as e:
        if DEBUG_MODE:
            print(f"[DEBUG] Failed to save PollVote to SQLite: {e}")

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
        page_title = soup.title.string if soup.title else "Unknown_Poll"
        poll_title = influx_clean_str(re.sub(r'[^A-Za-z0-9 ]+', '', page_title))

        poll_closed = "Poll_Closed" in poll_title
        if poll_closed:
            print(f"Poll Closed - {pollid}; {page_title}")
            return
        influx_batch = []
        for li in soup.find_all('li', class_='pds-feedback-group'):
            answer_text = li.find('span', class_='pds-answer-text').text.strip()
            votes_text = li.find('span', class_='pds-feedback-votes').text.strip()
            percent = li.find('span', class_='pds-feedback-per').text.strip()

            votematch = re.search(r'\d[\d,]*', votes_text)
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

    except requests.exceptions.RequestException as e:
        print(f"Request Error: {e}")
    except AttributeError as e:
        print(f"Parsing Error: {e}")



# --- Start --- #
if __name__ == "__main__":
    start()
