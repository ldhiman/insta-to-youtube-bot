from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from googleapiclient.errors import HttpError
import socket
import os
import time
import pickle

SCOPES = ['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/youtube.readonly', 'https://www.googleapis.com/auth/yt-analytics.readonly']


def get_authenticated_service():
    """
    Handles OAuth2 refresh tokens so the bot runs 24/7 without you logging in.
    First run requires manual browser login; subsequent runs use token.pickle.
    """
    creds = None

    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # refresh silently
            creds.refresh(Request())
        else:
            # FIRST TIME ONLY: this opens a browser locally.
            flow = InstalledAppFlow.from_client_secrets_file(
                'client_secrets.json', SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    # On EC2: make sure token.pickle + client_secrets.json exist
    return build('youtube', 'v3', credentials=creds)
    # (if you ever hit discovery cache issues, add cache_discovery=False)


def upload_video(file_path, title, description, tags, max_retries=5):
    youtube = get_authenticated_service()

    body = {
        'snippet': {
            'title': title[:100],  # YouTube limit
            'description': (description or '') + "\n\n#shorts",
            'categoryId': '24',
            'tags': tags,
        },
        'status': {
            'privacyStatus': 'private',  # Start private to check for copyright
            'selfDeclaredMadeForKids': False,
        },
    }

    # 1 MB chunks are OK; you can try 2–8 MB if your network is stable
    media = MediaFileUpload(
        file_path,
        chunksize=1024 * 1024,
        resumable=True,
    )

    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    response = None
    error = None
    retry = 0

    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                print(f"Uploaded {int(status.progress() * 100)}%")

        except HttpError as e:
            # 5xx errors or rate limits: retry
            if e.resp.status in [500, 502, 503, 504]:
                error = f"HttpError {e.resp.status}: {e}"
            else:
                # Non-retryable error → re-raise
                raise

        except (TimeoutError, socket.timeout, OSError) as e:
            # Network / timeout issues
            error = f"Network/timeout error: {e}"

        if error:
            retry += 1
            if retry > max_retries:
                print(f"FAILED: giving up after {max_retries} retries. Last error: {error}")
                raise RuntimeError(error)

            sleep_time = 2 ** retry  # exponential backoff: 2,4,8,...
            print(f"WARNING: {error}. Retrying #{retry} in {sleep_time} seconds...")
            time.sleep(sleep_time)
            error = None  # reset and retry loop

    video_id = response["id"]

    # Save schedule info
    with open("pending_publish.txt", "a") as f:
        f.write(f"{video_id}\n")
    print("Upload complete. Video ID:", video_id)
    
    return video_id


if __name__ == '__main__':
    # Just tests auth; comment out on EC2 once token.pickle is generated locally
    get_authenticated_service()
