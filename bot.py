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

EXCLUDED_WALLA_CATEGORIES = [
    "/breaking-news"
]

HAMAL_RSS = "https://public-api.hamal.co.il/rss"
HAMAL_GENERIC_IMAGE = "https://hamal.co.il/seo/hamal.png"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
HAMAL_TOKEN = os.getenv("HAMAL_TELEGRAM_TOKEN")
HAMAL_CHAT_ID = os.getenv("HAMAL_CHAT_ID")

LAST_LINKS_FILE = "last_links.txt"
LOCK_FILE = "bot.lock"
IMAGE_HISTORY_FILE = "hamal_image_counts.txt"
MAX_IMAGE_HISTORY = 300
MAX_LINKS_TO_KEEP = 500
MAX_ITEMS_PER_FETCH = 5
MAX_AGE_HOURS = 12

RLM = "\u200f"

# --- פונקציות עזר ---

def is_too_old(entry):
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
    for excluded in EXCLUDED_WALLA_CATEGORIES:
        if excluded in url:
            return True
    return False

def upgrade_image_quality(url):
    if not url: return url
    return re.sub(r'w=\d+', 'w=1200', url).replace("/re-size/", "/").replace("/w/400/", "/w/1200/")

def clean_image_url(url):
    if not url: return url
    return url.split('?')[0].split('#')[0].strip()

def get_feed_default_image(feed):
    try:
        img = feed.feed.get('image', {})
        if isinstance(img, dict):
            return clean_image_url(img.get('href') or img.get('url'))
    except Exception:
        pass
    return None

def fetch_og_image(article_url):
    """שולף תמונת og:image ישירות מדף הכתבה במידה ואין תמונה ב-RSS"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        }
        r = requests.get(article_url, headers=headers, timeout=4)
        if r.status_code == 200:
            match = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', r.text, re.IGNORECASE)
            if not match:
                match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', r.text, re.IGNORECASE)
            if match:
                return match.group(1)
    except Exception as e:
        print(f"Failed to fetch OG image for {article_url}: {e}")
    return None

def extract_raw_image(entry):
    """שולף את כתובת התמונה הגולמית מהאייטם"""
    image_url = None
    
    # 1. בדיקת media_content
    if 'media_content' in entry and entry.media_content:
        image_url = entry.media_content[0].get('url')
        
    # 2. בדיקת media_thumbnail
    if not image_url and 'media_thumbnail' in entry and entry.media_thumbnail:
        image_url = entry.media_thumbnail[0].get('url')

    # 3. בדיקת מפתח links
    if not image_url and 'links' in entry:
        for link in entry.links:
            if 'image' in link.get('type', ''):
                image_url = link.get('href')
                break
                
    # 4. בדיקת enclosure (רק אם זה לא וידאו m3u8)
    if not image_url and 'enclosure' in entry:
        enc_url = entry.enclosure.get('url', '')
        enc_type = entry.enclosure.get('type', '')
        if 'video' not in enc_type and not enc_url.endswith('.m3u8'):
            image_url = enc_url
        
    # 5. חילוץ תמונה מתוך ה-summary / description
    if not image_url:
        content_to_search = entry.get('summary', '') or entry.get('description', '') or entry.get('content', [{}])[0].get('value', '')
        if content_to_search:
            match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content_to_search, re.IGNORECASE)
            if match:
                image_url = match.group(1)
            else:
                match_url = re.search(r'https?://[^\s"\'>]+\.(?:jpg|jpeg|png|webp)', content_to_search, re.IGNORECASE)
                if match_url:
                    image_url = match_url.group(0)

    # 6. אם עדיין אין תמונה - חילוץ מדף הכתבה בלייב (og:image)
    if not image_url and entry.get('link'):
        image_url = fetch_og_image(entry.link)

    return image_url

def extract_image(entry, feed_default_image=None):
    image_url = extract_raw_image(entry)

    if not image_url:
        return None

    if feed_default_image and clean_image_url(image_url) == feed_default_image:
        return None

    return upgrade_image_quality(image_url)

def acquire_lock():
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
    history = {}
    if os.path.exists(IMAGE_HISTORY_FILE):
        with open(IMAGE_HISTORY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or "\t" not in line:
                    continue
                url, count = line.rsplit("\t", 1)
                try:
                    history[url] = int(count)
                except ValueError:
                    history[url] = 1
    return history

def save_image_history(history):
    items = list(history.items())[-MAX_IMAGE_HISTORY:]
    with open(IMAGE_HISTORY_FILE, "w", encoding="utf-8") as f:
        for url, count in items:
            f.write(f"{url}\t{count}\n")

# --- עיבוד וואלה ---
async def process_walla(bot, seen_links_set, links_list):
    for category, base_url in WALLA_FEEDS.items():
        url = f"{base_url}?t={int(time.time())}"
        feed = feedparser.parse(url)
        
        if not feed.entries:
            continue

        feed_default_image = get_feed_default_image(feed)
        latest_entries = feed.entries[:MAX_ITEMS_PER_FETCH]
        
        new_entries = [
            e for e in latest_entries 
            if clean_url(e.link) not in seen_links_set and not is_too_old(e)
        ]
        
        for entry in reversed(new_entries):
            cleaned_link = clean_url(entry.link)
            
            if is_excluded_category(cleaned_link):
                seen_links_set.add(cleaned_link)
                continue

            safe_title = html.escape(entry.title)
            caption = f'{RLM}<b>{safe_title}</b>{RLM}\n\n{cleaned_link}'
            
            try:
                image = extract_image(entry, feed_default_image)
                sent = False
                if image:
                    try:
                        await bot.send_photo(chat_id=CHAT_ID, photo=image, caption=caption, parse_mode='HTML')
                        sent = True
                    except Exception as photo_err:
                        print(f"Walla photo failed ({photo_err}), falling back to text")
                
                if not sent:
                    await bot.send_message(chat_id=CHAT_ID, text=caption, parse_mode='HTML', disable_web_page_preview=True)
                
                seen_links_set.add(cleaned_link)
                links_list.append(cleaned_link)
                await asyncio.sleep(0.5)
            except Exception as e: 
                print(f"Walla Error in {category}: {e}")
            
    return links_list

# --- עיבוד חמ"ל ---
async def process_hamal(seen_links_set, links_list, image_history):
    if not HAMAL_TOKEN or not HAMAL_CHAT_ID: return links_list
    
    hamal_bot = Bot(token=HAMAL_TOKEN)
    async with hamal_bot:
        url = f"{HAMAL_RSS}?t={int(time.time())}"
        feed = feedparser.parse(url)

        latest_entries = feed.entries[:MAX_ITEMS_PER_FETCH]
        
        new_entries = [
            e for e in latest_entries 
            if clean_url(e.link) not in seen_links_set and not is_too_old(e)
        ]
        
        for entry in reversed(new_entries):
            cleaned_link = clean_url(entry.link)
            
            raw_title = re.sub(r'<[^>]+>', '', entry.title)
            clean_title = re.sub(r'^חמ"?ל\s*[-:]?\s*חדשות\s*מתפרצות\s*[-:]?\s*', '', raw_title).strip()
            clean_title = clean_title.lstrip(" :")
            safe_title = html.escape(clean_title)

            message = f'{RLM}<b>{safe_title}</b>{RLM}\n\n{RLM}<a href="{cleaned_link}">{RLM}<b>לכתבה המלאה</b>{RLM}</a>{RLM}'

            raw_image = extract_raw_image(entry)
            image_to_send = None
            if raw_image:
                normalized = clean_image_url(raw_image)
                if normalized == clean_image_url(HAMAL_GENERIC_IMAGE):
                    pass
                else:
                    prior_count = image_history.get(normalized, 0)
                    if prior_count == 0:
                        image_to_send = upgrade_image_quality(raw_image)
                    image_history[normalized] = prior_count + 1
            
            try:
                sent = False
                if image_to_send:
                    try:
                        await hamal_bot.send_photo(chat_id=HAMAL_CHAT_ID, photo=image_to_send, caption=message, parse_mode='HTML')
                        sent = True
                    except Exception as photo_err:
                        print(f"Hamal photo failed ({photo_err}), falling back to text")
                if not sent:
                    await hamal_bot.send_message(chat_id=HAMAL_CHAT_ID, text=message, parse_mode='HTML', disable_web_page_preview=True)
                seen_links_set.add(cleaned_link)
                links_list.append(cleaned_link)
                
                await asyncio.sleep(0.5)
            except Exception as e: print(f"Hamal Error: {e}")
            
    return links_list

async def main():
    if not TELEGRAM_TOKEN or not CHAT_ID: return

    lock_fd = acquire_lock()

    links_list = get_history()
    seen_links_set = {clean_url(l) for l in links_list}
    image_history = get_image_history()

    bot = Bot(token=TELEGRAM_TOKEN)
    async with bot:
        links_list = await process_walla(bot, seen_links_set, links_list)
        links_list = await process_hamal(seen_links_set, links_list, image_history)

    save_history(links_list)
    save_image_history(image_history)

if __name__ == "__main__":
    asyncio.run(main())
