import feedparser
import asyncio
import fcntl
import html
import os
import re
import requests
import sys
import time
from datetime import datetime, timedelta
from telegram import Bot

# --- הגדרות ---
WALLA_FEEDS = {
    "חדשות": "https://www.walla.co.il/rss/feed/news",
    "כסף": "https://rss.walla.co.il/feed/2",
    "טכנולוגיה": "https://rss.walla.co.il/feed/6"
}

# תתי-קטגוריות שלא נרצה להציג בערוץ
EXCLUDED_WALLA_CATEGORIES = [
    "/breaking-news"
]

HAMAL_RSS = "https://public-api.hamal.co.il/rss"
HAMAL_GENERIC_IMAGE = "https://hamal.co.il/seo/hamal.png"  # תמונת ברירת מחדל של חמ"ל - לא תמונה אמיתית של כתבה, לא לשלוח

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
HAMAL_TOKEN = os.getenv("HAMAL_TELEGRAM_TOKEN")
HAMAL_CHAT_ID = os.getenv("HAMAL_CHAT_ID")

LAST_LINKS_FILE = "last_links.txt"
LOCK_FILE = "bot.lock"
IMAGE_HISTORY_FILE = "hamal_image_counts.txt"
MAX_IMAGE_HISTORY = 300
MAX_LINKS_TO_KEEP = 500
MAX_ITEMS_PER_FETCH = 5  # הגבלה ל-5 אייטמים אחרונים בכל בדיקה
MAX_AGE_HOURS = 12       # לא לשלוח אייטמים ישנים יותר מ-12 שעות

# RLM (Right-to-Left Mark) בתחילת הטקסט וגם בסופו - לאלץ יישור ימני בקפציות תמונות
RLM = "\u200f"

# --- פונקציות עזר ---

def is_too_old(entry):
    """בודק אם האייטם ישן מדי מכדי להישלח"""
    try:
        published_struct = entry.get('published_parsed') or entry.get('updated_parsed')
        if not published_struct: return False
        
        published_time = datetime.fromtimestamp(time.mktime(published_struct))
        if published_time < datetime.now() - timedelta(hours=MAX_AGE_HOURS):
            return True
    except: pass
    return False

def clean_url(url):
    return url.split('?')[0].split('#')[0].strip()

def is_excluded_category(url):
    """בודק אם הקישור שייך לתת-קטגוריה שנמצאת ברשימת ההחרמות"""
    for excluded in EXCLUDED_WALLA_CATEGORIES:
        if excluded in url:
            return True
    return False

def _try_isgd(long_url):
    encoded_url = requests.utils.quote(long_url, safe='')
    api_url = f"https://is.gd/create.php?format=simple&url={encoded_url}"
    r = requests.get(api_url, timeout=5)
    text = r.text.strip()
    if r.status_code == 200 and text and not text.startswith("Error") and text.startswith("http"):
        return text
    raise ValueError(f"is.gd: {text}")

def _try_vgd(long_url):
    encoded_url = requests.utils.quote(long_url, safe='')
    api_url = f"https://v.gd/create.php?format=simple&url={encoded_url}"
    r = requests.get(api_url, timeout=5)
    text = r.text.strip()
    if r.status_code == 200 and text and not text.startswith("Error") and text.startswith("http"):
        return text
    raise ValueError(f"v.gd: {text}")

def _try_dagd(long_url):
    encoded_url = requests.utils.quote(long_url, safe='')
    api_url = f"https://da.gd/shorten?url={encoded_url}"
    r = requests.get(api_url, timeout=5)
    text = r.text.strip()
    if r.status_code == 200 and text.startswith("http"):
        return text
    raise ValueError(f"da.gd: {text}")

def _try_cleanuri(long_url):
    r = requests.post(
        "https://cleanuri.com/api/v1/shorten",
        json={"url": long_url},
        timeout=5,
    )
    data = r.json()
    if r.status_code == 200 and data.get("result_url", "").startswith("http"):
        return data["result_url"]
    raise ValueError(f"cleanuri: {data}")

def _verify_short_url(short_url, original_url):
    """מוודא שהקישור המקוצר באמת מפנה ליעד המקורי"""
    try:
        r = requests.get(short_url, allow_redirects=True, timeout=6, stream=True)
        r.close()
        resolved = clean_url(r.url)
        if resolved != clean_url(original_url):
            raise ValueError(f"redirect mismatch: got '{resolved}', expected '{original_url}'")
    except requests.RequestException as e:
        raise ValueError(f"verification request failed: {e}")

def get_short_url(long_url):
    shorteners = (_try_cleanuri, _try_dagd, _try_isgd, _try_vgd)
    for shortener in shorteners:
        try:
            short_url = shortener(long_url)
            _verify_short_url(short_url, long_url)
            return short_url
        except Exception as e:
            print(f"get_short_url [{shortener.__name__}] failed for {long_url}: {e}")
    return long_url

def upgrade_image_quality(url):
    if not url: return url
    return re.sub(r'w=\d+', 'w=1200', url).replace("/re-size/", "/").replace("/w/400/", "/w/1200/")

def clean_image_url(url):
    """מנרמל URL של תמונה לצורך השוואה (מוריד פרמטרים כמו גודל/timestamp)"""
    if not url: return url
    return url.split('?')[0].split('#')[0].strip()

def get_feed_default_image(feed):
    """התמונה ברמת הערוץ (הלוגו הכללי של הפיד), אם קיימת"""
    try:
        img = feed.feed.get('image', {})
        if isinstance(img, dict):
            return clean_image_url(img.get('href') or img.get('url'))
    except Exception:
        pass
    return None

def extract_raw_image(entry):
    """שולף את כתובת התמונה הגולמית מהאייטם, בלי שום סינון"""
    image_url = None
    if 'media_content' in entry: image_url = entry.media_content[0]['url']
    elif 'links' in entry:
        for link in entry.links:
            if 'image' in link.get('type', ''):
                image_url = link.get('href'); break
    if not image_url and 'enclosure' in entry:
        image_url = entry.enclosure.get('url')
    return image_url

def extract_image(entry, feed_default_image=None):
    image_url = extract_raw_image(entry)

    if not image_url:
        return None

    print(f"DEBUG image url for '{entry.get('title', '')[:40]}': {image_url}")

    # אם התמונה זהה ללוגו הכללי של הפיד - זה לא תמונה אמיתית של הכתבה, נתעלם ממנה
    if feed_default_image and clean_image_url(image_url) == feed_default_image:
        print(f"  -> matches feed default/logo image, skipping")
        return None

    return upgrade_image_quality(image_url)

def acquire_lock():
    """מונע הרצה כפולה במקביל"""
    lock_fd = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (IOError, OSError):
        print("ריצה אחרת כבר פעילה - יוצא כדי למנוע שליחה כפולה")
        sys.exit(0)
    return lock_fd

def get_history():
    links = []
    if os.path.exists(LAST_LINKS_FILE):
        with open(LAST_LINKS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("COUNTER:"):
                    links.append(line)
    return links

def save_history(links_list):
    recent_links = links_list[-MAX_LINKS_TO_KEEP:]
    with open(LAST_LINKS_FILE, "w", encoding="utf-8") as f:
        for link in recent_links:
            f.write(f"{link}\n")

def get_image_history():
