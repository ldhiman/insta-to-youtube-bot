import os
import json
import google.generativeai as genai
from uploader import get_authenticated_service
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv
import re
import time
load_dotenv()
# ---------- CONFIG ----------

# Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
GEMINI_MODEL = "gemini-2.5-flash"

# YouTube
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"


# ---------- YOUTUBE STATS CONTEXT ----------
youtube = get_authenticated_service()

def get_channel_id():
    """Get current authenticated channel's ID."""
    resp = youtube.channels().list(part="id", mine=True).execute()
    items = resp.get("items", [])
    if not items:
        return None
    return items[0]["id"]


def build_stats_context(max_videos=8):
    """
    Fetch a few recent videos + stats and build a compact text summary
    to feed into Gemini so it learns what works on your channel.
    """
    try:
        channel_id = get_channel_id()
        if not channel_id:
            return ""

        search_resp = youtube.search().list(
            part="id,snippet",
            channelId=channel_id,
            order="date",         # latest uploads
            type="video",
            maxResults=max_videos,
        ).execute()

        video_ids = [
            item["id"]["videoId"]
            for item in search_resp.get("items", [])
            if item["id"]["kind"] == "youtube#video"
        ]

        if not video_ids:
            return ""

        stats_resp = youtube.videos().list(
            part="snippet,statistics",
            id=",".join(video_ids),
        ).execute()

        lines = []
        for item in stats_resp.get("items", []):
            snippet = item["snippet"]
            stats = item["statistics"]

            title = snippet.get("title", "")[:80]
            views = stats.get("viewCount", "0")
            likes = stats.get("likeCount", "0")
            # take only first line of description to keep things short
            desc = (snippet.get("description", "").split("\n")[0])[:80]

            line = f"- Title: {title} | Views: {views} | Likes: {likes} | Desc: {desc}"
            lines.append(line)

        context = "Recent channel performance (title / views / likes / first line of description):\n"
        context += "\n".join(lines)

        # Keep context relatively short
        return context[:2000]

    except HttpError as e:
        print("YouTube API error while building stats context:", e)
        return ""
    except Exception as e:
        print("Error building stats context:", e)
        return ""


# ---------- GEMINI FILE HANDLING ----------
def upload_video_to_gemini(video_path):
    """Uploads a video file and waits for processing to complete."""
    if not video_path or not os.path.exists(video_path):
        print(f"Video path not found: {video_path}")
        return None

    print(f"Uploading {video_path} to Gemini...")
    video_file = genai.upload_file(path=video_path)
    
    print(f"Completed upload: {video_file.uri}")

    # Check state and wait for processing
    while video_file.state.name == "PROCESSING":
        print('.', end='', flush=True)
        time.sleep(2)
        video_file = genai.get_file(video_file.name)

    print() # Newline after dots

    if video_file.state.name == "FAILED":
        raise ValueError(f"Video processing failed: {video_file.state.name}")
        
    print(f"Video is active and ready for analysis.")
    return video_file

# ---------- GEMINI METADATA GENERATION ----------
def generate_metadata(caption: str, url, video_path: str, stats_context: str = ""):
    """
    Generates viral-optimized YouTube Shorts metadata using Gemini.
    Uses YouTube stats context (if provided) to adapt style.
    Returns dict: title, description, tags, hashtags.
    """

    video_file = upload_video_to_gemini(video_path)


    prompt = f"""
    You are a YouTube Shorts viral strategist. See the caption of the video and recent stats and generate high-CTR metadata.
    Output a JSON object with these exact keys:
        1. "title": A curiosity-gap title (max 60 chars). NO generic titles like "Funny Cat".
        2. "description": A detailed description atleast 20 lines. 
           Line 1: Describe the hook. 
           Line 2: Ask a specific question to the viewer to encourage comments (e.g. "Have you ever tried this?").
        3. "tags": A list of 10 high-traffic keywords mixed with 2 niche keywords.
Here is my channel's recent performance data (titles, views, likes, descriptions).
Use it to understand what style performs well and keep your output aligned with it,
but still improve it for virality and retention.

CHANNEL STATS CONTEXT (may be empty):
{stats_context}

TASK:
Generate highly clickable metadata for a YouTube SHORT.

INPUT CAPTION:
{caption}

RULES FOR OUTPUT:
1) TITLE:
   - Less than 65 characters
   - Strong hook in first 2 seconds
   - Style should be similar to my BEST looking stats above, but improved
   - No clickbait lies

2) DESCRIPTION:
   - First 2 lines must clearly describe the video using strong keywords
   - Then add 4–6 related search phrases in bullet points
   - Add a short call to action
   - Add hashtags at bottom
   - Description must be at least 20 lines long

3) TAGS:
   - Simple keyword list (max 10), no hashtags
   - Mix high-traffic and niche keywords
   - Max 10 tags
   
4) HASHTAGS:
   - Include #shorts and niche tags
   - 5–10 hashtags total

Return ONLY valid JSON:
{{
  "title": "...",
  "description": "...",
  "tags": ["..."],
  "hashtags": ["..."]
}}
"""
    content_payload = [prompt]

    if video_file:
        print("Attaching video file to Gemini prompt for analysis...")
        content_payload.append(video_file)


    response = genai.GenerativeModel(GEMINI_MODEL).generate_content(contents=content_payload)
    raw = (response.text or "").strip()

     # 1) Try direct JSON first
    try:
        return json.loads(raw)
    except:
        pass

    # 2) Try to extract using regex for ```json ... ```
    codeblock = re.search(r"```json\n([\s\S]*?)```", raw, re.IGNORECASE)
    if codeblock:
        try:
            return json.loads(codeblock.group(1))
        except:
            pass

    # 3) Try extracting any JSON-like block (braces)
    brace = re.search(r"(\{[\s\S]*\})", raw)
    if brace:
        try:
            return json.loads(brace.group(1))
        except:
            pass

    
    print("Raw response was:", raw)
        # Fallback in case model adds explanation text
    return {
            "title": caption[:60] or "Amazing Short Video",
            "description": caption + "\n\n#shorts" + f"\nCredit: {url}",
            "tags": ["shorts"],
            "hashtags": ["#shorts"],
        }


if __name__ == "__main__":
    # Example usage
    stats_context = build_stats_context()
    print("Stats Context:", stats_context)
    metadata = generate_metadata(
        caption="@minelampstore #minecraft",
        url="https://www.instagram.com/reel/DN_IuaHDUXB/?igsh=MTkxaDA0eWlwem1iZQ==",
        video_path=r"D:\Projects\insta-to-youtube-bot\downloads\processed_d14f84d7-84a4-4a42-899b-ca9fe6c9e50b.mp4",
        stats_context=stats_context
    )
    print("Generated Metadata:", metadata)