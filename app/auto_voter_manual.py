
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
import requests
from bs4 import BeautifulSoup
from stem import Signal
from stem.control import Controller
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
from expressvpn import connect_alias
import config

# --- Global Configs --- #
polls = config.polls
pollToRun = 0
num_threads = 1           #Optimied: 110
start_totalToRun =3000
start_process = 2 #BATCHES
p2_PerRun = 10                 #Optimied: 24
p2_pause = 1                  #Optimied: 65
print_debug_msg=False
print_debug_level=1

RandomTimes = False
RandomMin = 2
RandomMax = 30
tor_delay=2

cntToPause = 0
longPauseSeconds = 70
shortPauseSeconds = 0

vpn_maxvotes = 0
vpn_enabled=False
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

pollid, answerid, protocol = polls[pollToRun][1:4]
use_tor = protocol.lower() == "tor"

proxies = {'http': 'socks5h://127.0.0.1:9050', 'https': 'socks5h://127.0.0.1:9050'}
lock = multiprocessing.Lock()
count_good = multiprocessing.Value('i', 0)

vpnloc = config.vpnloc  # you can load this from config if big
vpnloccnt = len(vpnloc) - 1
vpnlocat = random.randint(0,vpnloccnt)
vpn_votecnt = 0

useragents = config.useragents  # better load it externally if large

# --- Functions --- #

def start(start_mode):
    if start_mode == 1:
        run_multi_scripts(num_threads, cntToRun)
    elif start_mode == 2:
        LoopTimes = max(1, RunPerScript // p2_PerRun)
        PreviousGood = 0
        for i in range(LoopTimes):
            starttime = datetime.datetime.now()
            new_location()
            run_multi_scripts(num_threads, p2_PerRun)

            RunThisLoop = p2_PerRun * num_threads
            GoodThisLoop = count_good.value - PreviousGood
            GoodThisLoopPercent = (GoodThisLoop / RunThisLoop) * 100
            WhereAt = (i+1) * RunThisLoop
            PercentGood = (count_good.value / max(1, WhereAt)) * 100

            now = datetime.datetime.now()
            nowFormat = now.strftime("%H:%M:%S")
            TimeRun = (now - starttime).total_seconds()

            print(f"{nowFormat}: {TimeRun:.0f}s {GoodThisLoop}/{RunThisLoop} ({GoodThisLoopPercent:.1f}%): "
                  f"Overall: {count_good.value}/{WhereAt} ({PercentGood:.1f}%)")
            #write results to influx
            extract_poll_results(pollid)
            PreviousGood = count_good.value

            if int(GoodThisLoopPercent)<60 and not use_tor:
                if p2_pause<75:
                    print("Sleep 70")
                    time.sleep(70)
                elif p2_pause<120:
                    print("Sleep 300")
                    time.sleep(300)
                else:
                    print("Sleep 600")
                    time.sleep(600)
            else:
                time.sleep(p2_pause)

def print_debug(msg, levelofdetail=2):

    if print_debug_msg and levelofdetail<=print_debug_level:
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

    if vpn_enabled==False:
        return
    if vpnmode == 1:
        while vpnloc[vpnlocat]["loc"] != "us":
            vpnlocat = (vpnlocat + 1) % (vpnloccnt + 1)

    try:
        connect_alias(vpnloc[vpnlocat]["alias"])
    except Exception as e:
        print(f"VPN Connection Error: {e}")

    vpn_votecnt = 0
    vpnlocat = (vpnlocat + 1) % (vpnloccnt + 1)


def auto_voter(thread_id, RunCount):
    global vpn_votecnt
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
                    controller.authenticate(password="welcomeTomyPa55word")  #
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
                    with lock:
                        count_good.value += 1

                else:
                    NoVoteRun += 1

                if VOTE_GOOD==1:
                    print_debug(f"Good: {vote_resp.url}",1)
                else:
                    print_debug(f"Failed: {vote_resp.url}",1)

                if start_process==1 and ((vpn_maxvotes and vpn_votecnt >= vpn_maxvotes) or (not use_tor and NoVoteRun > 3)):
                    switchvpn = True

                # Influx Record Building

                title = (soup_vote.title.string.strip()
                    if soup_vote.title and soup_vote.title.string
                    else "Unknown_Poll")
                VOTE_BATCH.append(build_influx_record(VOTE_GOOD, title))

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
                time.sleep(timeoutseconds)
            elif (cntpause == cntToPause):
                #print("G:" + str(vote_good) + ";B:" + str(vote_bad) + "; LongPause until " + str(
                #    datetime.datetime.now() + datetime.timedelta(seconds=longPauseSeconds)), 2, thread_id)
                influx_write_records(VOTE_BATCH)
                VOTE_BATCH.clear()
                time.sleep(longPauseSeconds)
                cntpause = 0



        except Exception as e:
            print(f"Voting error: {e}")
            time.sleep(2)

    influx_write_records(VOTE_BATCH)
    VOTE_BATCH.clear()

def vote_success(thread_id):
    print(f"[Thread {thread_id}] Vote success!")

def influx_clean_str(stringtoclean):

    clean_string = re.sub(r'[^A-Za-z0-9 ]+', '', stringtoclean)  # Remove non-alphanumeric characters
    clean_string = clean_string.replace(" ", "_")  # Replace spaces with underscores
    return clean_string

def build_influx_record(VOTE_GOOD, title):
    if VOTE_GOOD==0:
        VOTE_BAD=1
    else:
        VOTE_BAD=0
    unique_id = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    unix_time = int(time.time() * 1e9)
    title_clean = influx_clean_str(title)
    answer_script_name = influx_clean_str(polls[pollToRun][0])
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
        page_title = (page_title_tag.string.strip()
                    if page_title_tag and page_title_tag.string
                    else "Unknown_Poll")
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
    start(start_process)
