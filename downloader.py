import requests
import re
import os
import uuid
import bs4

import requests
import json

API_ENDPOINT = "https://thesocialcat.com/api/instagram-download"

headers = {
  'accept': '*/*',
  'accept-language': 'en-US,en;q=0.9,hi;q=0.8',
  'cache-control': 'no-cache',
  'content-type': 'application/json',
  'dnt': '1',
  'origin': 'https://thesocialcat.com',
  'pragma': 'no-cache',
  'priority': 'u=1, i',
  'referer': 'https://thesocialcat.com/tools/instagram-video-downloader',
  'sec-ch-ua': '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
  'sec-ch-ua-mobile': '?0',
  'sec-ch-ua-platform': '"Windows"',
  'sec-fetch-dest': 'empty',
  'sec-fetch-mode': 'cors',
  'sec-fetch-site': 'same-origin',
  'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
  'Cookie': 'BRANDS_DEFAULT_LANDING_VERSION=1; BRANDS_SMALL_BRANDS_LANDING_VERSION=1; BRANDS_UGC_LANDING_VERSION=3; _ga=GA1.1.1111672967.1764614326; _tt_enable_cookie=1; _ttp=01KBDKBJGFCFHNQBJTXQCDQFFV_.tt.1; _ga_ZECYDJ3Y4Y=GS2.1.s1764614326$o1$g0$t1764614340$j46$l0$h0; ttcsid=1764614326807::IRmz1AaB9SEB0Evch6l-.1.1764614340772.0; ttcsid_CFC1MRRC77U0H42CQU6G=1764614326806::nqMalXUBYKEOEcowKHE_.1.1764614340772.0; BRANDS_DEFAULT_LANDING_VERSION=1; BRANDS_SMALL_BRANDS_LANDING_VERSION=1; BRANDS_UGC_LANDING_VERSION=2'
}



def download_instagram_reel(url, output_folder="downloads"):
    """
    Downloads reel using saveig.app API to bypass Instagram login/IP blocks.
    """
    print(f"DEBUG: Processing {url}")
    
    # Headers to mimic a real browser request to the scraper site
    payload = json.dumps({
        "url": url
    })    

    try:
        # 2. Request Video Link
        response = requests.request("POST", API_ENDPOINT, headers=headers, data=payload)

        response.raise_for_status()
        
        # print(response.text)

        response_json = response.json()
        
        video_url = response_json.get("mediaUrls")[0]

        if not video_url:
            print("Error: No video URL found in saveig response.")
            return None, None

        # 4. Download the File
        print(f"DEBUG: Downloading content from {video_url}")
        
        DOWNLOAD_HEADERS = {
            "User-Agent": headers["user-agent"],
            "Accept": "*/*",
            "Referer": "https://www.instagram.com/",
            "Origin": "https://www.instagram.com",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-Mode": "no-cors",
            "Sec-Fetch-Dest": "video",
            "Range": "bytes=0-",  # IMPORTANT FOR video/mp4
        }

        video_response = requests.get(
            video_url,
            stream=True,
            headers=DOWNLOAD_HEADERS,
        )
        video_response.raise_for_status()
        
        # Create output directory
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
            
        filename = f"{uuid.uuid4()}.mp4"
        filepath = os.path.join(output_folder, filename)
        
        with open(filepath, 'wb') as f:
            for chunk in video_response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        caption = response_json.get("caption", "Reel")
        
        print(f"DEBUG: Saved to {filepath}")
        return filepath, caption

    except Exception as e:
        print(f"Scraping Error: {e}")
        return None, None

if __name__ == '__main__':
    download_instagram_reel("https://www.instagram.com/reel/DRTZYoZEnuQ/?igsh=MTBhb2UzOGVod29pcA==")