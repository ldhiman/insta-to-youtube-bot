import os
import json
import google.generativeai as genai
from uploader import get_authenticated_service
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv
import re
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


# ---------- GEMINI METADATA GENERATION ----------

def generate_metadata(caption: str, url, niche: str = "", stats_context: str = ""):
    """
    Generates viral-optimized YouTube Shorts metadata using Gemini.
    Uses YouTube stats context (if provided) to adapt style.
    Returns dict: title, description, tags, hashtags.
    """

    prompt = f"""
You are an expert YouTube Shorts SEO optimizer.

Here is my channel's recent performance data (titles, views, likes, descriptions).
Use it to understand what style performs well and keep your output aligned with it,
but still improve it for virality and retention.

CHANNEL STATS CONTEXT (may be empty):
{stats_context}

TASK:
Generate highly clickable metadata for a YouTube SHORT.

INPUT CAPTION:
{caption}

NICHE:
{niche}

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

3) TAGS:
   - Simple keyword list (max 10), no hashtags

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

    response = genai.GenerativeModel(GEMINI_MODEL).generate_content(prompt)
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
        caption="This is an amazing short video about cats!",
        url="https://instagram.com/reel/xyz",
        niche="Cats",
        stats_context=stats_context
    )
    print("Generated Metadata:", metadata)