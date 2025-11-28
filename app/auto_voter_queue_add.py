import os
import json
import app.config as config
import time

polls = config.polls
QUEUE_FILE = 'queue.json'

def start():
    #add_to_queue(0, "KevinOzulumbaAshland", 16056139, 70642739, 10000, 100, 10, 70)
    add_to_queue(6, "", 0, 0, 17000, 100, 10, 70)
    #add_to_queue(0, "random", 16059307, 70656036, 2000, 100, 10, 70)


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
        pollid = polls[poll_index_to_run][1]
        answerid = polls[poll_index_to_run][2]
        jobname = polls[poll_index_to_run][0]

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

if __name__ == "__main__":
    start()


