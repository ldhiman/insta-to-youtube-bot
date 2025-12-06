import os
import json
from datetime import date, datetime
from zoneinfo import ZoneInfo  # built-in in Python 3.9+
from uploader import get_authenticated_service
from dotenv import load_dotenv

load_dotenv()

PENDING_FILE = "pending_publish.txt"
STATE_FILE = "publish_state.json"   # to track how many we published today
DAILY_LIMIT = int(os.getenv("DAILY_LIMIT", 3))
# Only publish at/after this hour (24h format, IST)
PUBLISH_AFTER_HOUR_IST = 17  # 17 = 5 PM


def load_state():
    if not os.path.exists(STATE_FILE):
        return {"date": None, "count": 0}
    with open(STATE_FILE, "r") as f:
        return json.load(f)


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def publish(video_id: str):
    youtube = get_authenticated_service()
    youtube.videos().update(
        part="status",
        body={"id": video_id, "status": {"privacyStatus": "public"}},
    ).execute()
    print(f"[PUBLISHED] {video_id}")


def iterate_publish_queue():
    # 1) Time gate: only after 5 PM IST
    now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
    if now_ist.hour < PUBLISH_AFTER_HOUR_IST:
        print(f"[INFO] It's {now_ist.strftime('%H:%M')} IST. "
              f"Publishing allowed only after {PUBLISH_AFTER_HOUR_IST}:00.")
        return

    if not os.path.exists(PENDING_FILE):
        print("[INFO] No pending_publish.txt found.")
        return

    # 2) Load / reset daily state
    state = load_state()
    today_str = date.today().isoformat()

    if state["date"] != today_str:
        # New day → reset counter
        state = {"date": today_str, "count": 0}

    remaining_quota = DAILY_LIMIT - state["count"]
    if remaining_quota <= 0:
        print(f"[INFO] Daily limit of {DAILY_LIMIT} videos already reached.")
        save_state(state)
        return

    # 3) Read pending IDs
    with open(PENDING_FILE, "r") as f:
        lines = [line.strip() for line in f if line.strip()]

    if not lines:
        print("[INFO] No video IDs in queue.")
        return

    # 4) Only publish ONE video per run (the first in queue)
    video_id = lines[0]
    remaining = lines[1:]

    if remaining_quota <= 0:
        print(f"[INFO] No remaining quota today. Skipping {video_id}.")
        return

    try:
        publish(video_id)
        state["count"] += 1
        print(f"[INFO] Today's publish count: {state['count']}/{DAILY_LIMIT}")

        # Rewrite pending file without the published ID
        with open(PENDING_FILE, "w") as f:
            for vid in remaining:
                f.write(vid + "\n")

    except Exception as e:
        print(f"[ERROR] Failed to publish {video_id}: {e}")
        # On failure, keep the queue unchanged so we can retry later
        with open(PENDING_FILE, "w") as f:
            for vid in lines:
                f.write(vid + "\n")

    # 5) Save updated state
    save_state(state)


if __name__ == "__main__":
    iterate_publish_queue()
