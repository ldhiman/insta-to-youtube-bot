import os
import json
from datetime import date
from uploader import get_authenticated_service
from dotenv import load_dotenv

load_dotenv()

PENDING_FILE = "pending_publish.txt"
STATE_FILE = "publish_state.json"   # to track how many we published today
DAILY_LIMIT = int(os.getenv("DAILY_LIMIT", 3))

def load_state():
    if not os.path.exists(STATE_FILE):
        return {"date": None, "count": 0}
    with open(STATE_FILE, "r") as f:
        return json.load(f)


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def publish(video_id):
    youtube = get_authenticated_service()
    youtube.videos().update(
        part="status",
        body={"id": video_id, "status": {"privacyStatus": "public"}},
    ).execute()
    print(f"[PUBLISHED] {video_id}")


def iterate_publish_queue():
    if not os.path.exists(PENDING_FILE):
        return

    # Load / reset daily state
    state = load_state()
    today_str = date.today().isoformat()

    if state["date"] != today_str:
        # New day → reset counter
        state = {"date": today_str, "count": 0}

    remaining_quota = DAILY_LIMIT - state["count"]
    if remaining_quota <= 0:
        print(f"[INFO] Daily limit of {DAILY_LIMIT} videos already reached.")
        return

    # Read pending IDs
    with open(PENDING_FILE, "r") as f:
        lines = [line.strip() for line in f if line.strip()]

    if not lines:
        return

    to_publish = lines[:remaining_quota]
    remaining = lines[remaining_quota:]

    for video_id in to_publish:
        try:
            publish(video_id)
            state["count"] += 1
        except Exception as e:
            print(f"[ERROR] Failed to publish {video_id}: {e}")

    # Rewrite pending file with leftover IDs
    with open(PENDING_FILE, "w") as f:
        for vid in remaining:
            f.write(vid + "\n")

    # Save updated state
    save_state(state)


if __name__ == "__main__":
    iterate_publish_queue()
