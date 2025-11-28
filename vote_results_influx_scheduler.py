import os
import re
import csv
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from influxdb_client import InfluxDBClient, DeleteApi
from influxdb_client.client.write_api import SYNCHRONOUS
from fake_useragent import UserAgent
import importlib
import app.config as config

# ====== Configuration ======
ProcessToRun = 1  # 1: All Polls; 2: Single Poll; 99: Test
SinglePollIndex = 0
RunPollEveryXsec = 60 * 15

polls = config.polls
INFLUX_URL = config.INFLUX_URL
INFLUX_TOKEN = config.INFLUX_TOKEN
INFLUX_ORG = config.INFLUX_ORG
INFLUX_BUCKET = config.INFLUX_BUCKET

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

def run_all_polls():
    importlib.reload(config) #reload config variables
    polls = config.polls
    for name, pollid, answerid, cat in polls:
        url = f"https://poll.fm/{pollid}/results"
        extract_poll_results(url, pollid)
    pollsdone.clear()
    print_next_run()

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
            stop = datetime.utcnow().isoformat() + "Z"
            delete_api.delete(start, stop, '_measurement="states"', bucket=INFLUX_BUCKET, org=INFLUX_ORG)
            print("Test delete complete.")
    except Exception as e:
        print(f"Test delete failed: {e}")

def extract_poll_results(url, pollid):
    if pollid in pollsdone:
        #print(f"Skipping already processed poll {pollid}")
        return
    pollsdone.append(pollid)

    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        page_title = soup.title.string or "Unknown_Poll"
        poll_title = clean_influx_string(re.sub(r'[^A-Za-z0-9 ]+', '', page_title))
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

            vote_name = clean_influx_string(vote_name)
            vote_school = clean_influx_string(vote_school)

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

        write_to_influx(influx_batch)

    except requests.exceptions.RequestException as e:
        print(f"Request Error: {e}")
    except AttributeError as e:
        print(f"Parsing Error: {e}")

# ====== Main ======

if __name__ == "__main__":
    start()
