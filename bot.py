import feedparser
import asyncio
import os
import re
import requests
import time
import tweepy
from datetime import datetime, timedelta
from telegram import Bot

# --- הגדרות ---
WALLA_FEEDS = {
    "מבזקים": "https://rss.walla.co.il/feed/22",
    "חדשות": "https://rss.walla.co.il/feed/1?type=main",
    "כסף": "https://rss.walla.co.il/feed/2",
    "טכנולוגיה": "https://rss.walla.co.il/feed/6"
}
HAMAL_RSS = "https://public-api.hamal.co.il/rss"

# טלגרם
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
HAMAL_TOKEN = os.getenv("HAMAL_TELEGRAM_TOKEN")
HAMAL_CHAT_ID = os.getenv("HAMAL_CHAT_ID")

# טוויטר (X)
TW_API_KEY = os.getenv("TWITTER_API_KEY")
TW_API_SECRET = os.getenv("TWITTER_API_SECRET")
TW_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TW_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")

LAST_LINKS_FILE = "last_links.txt"
MAX_LINKS_TO_KEEP = 500
PROMO_EVERY_X_MESSAGES = 40 
MAX_ITEMS_PER_FETCH = 5
MAX_AGE_HOURS = 12

RLE = "\u202B" 
PDF = "\u202C" 
RLM = "\u200f" 
LOGO_URL = "https://raw.githubusercontent.com/Ingest-bot/Telegram/main/Logo2.png"

# --- פונקציות עזר ---

def post_to_twitter(title, link):
    """שולח ציוץ לטוויטר"""
    if not all([TW_API_KEY, TW_API_SECRET, TW_ACCESS_TOKEN, TW_ACCESS_SECRET]):
        return
    try:
        client = tweepy.Client(
            consumer_key=TW_API_KEY, consumer_secret=TW_API_SECRET,
            access_token=TW_ACCESS_TOKEN, access_token_secret=TW_ACCESS_SECRET
        )
        text = f"{title}\n\n{link}"
        client.create_tweet(text=text)
    except Exception as e:
        print(f"Twitter Error: {e}")

def is_too_old(entry):
    try:
        published_struct = entry.get('published_parsed') or entry.get('updated_parsed')
        if not published_struct: return False
        published_time = datetime.fromtimestamp(time.mktime(published_struct))
        return published_time < datetime.now() - timedelta(hours=MAX_AGE_HOURS)
    except: return False

def clean_url(url):
    return url.split('?')[0].split('#')[0].strip()

def get_short_url(long_url):
    try:
        api_url = f"https://is.gd/create.php?format=simple&url={long_url}"
        response = requests.get(api_url, timeout=5)
        if response.status_code == 200: return response.text.strip()
    except: pass
    return long_url

def upgrade_image_quality(url):
    if not url: return url
    return re.sub(r'w=\d+', 'w=1200', url).replace("/re-size/", "/").replace("/w/400/", "/w/1200/")

def extract_image(entry):
    image_url = None
    if 'media_content' in entry: image_url = entry.media_content[0]['url']
    elif 'links' in entry:
        for link in entry.links:
            if 'image' in link.get('type', ''):
                image_url = link.get('href'); break
    if not image_url and 'enclosure' in entry:
        image_url = entry.enclosure.get('url')
    return upgrade_image_quality(image_url)

def get_history():
    history = {"links": [], "counter": 0}
    if os.path.exists(LAST_LINKS_FILE):
        with open(LAST_LINKS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("COUNTER:"):
                    try: history["counter"] = int(line.split(":")[1])
                    except: history["counter"] = 0
                elif line: history["links"].append(line)
    return history

def save_history(links_list, counter):
    recent_links = links_list[-MAX_LINKS_TO_KEEP:]
    with open(LAST_LINKS_FILE, "w", encoding="utf-8") as f:
        f.write(f"COUNTER:{counter}\n")
        for link in recent_links: f.write(f"{link}\n")

# --- עיבוד וואלה ---
async def process_walla(bot, seen_links_set, links_list):
    for category, base_url in WALLA_FEEDS.items():
        url = f"{base_url}?t={int(time.time())}"
        feed = feedparser.parse(url)
        if not feed.entries: continue
        
        latest_entries = feed.entries[:MAX_ITEMS_PER_FETCH]
        new_entries = [e for e in latest_entries if clean_url(e.link) not in seen_links_set and not is_too_old(e)]
        
        for entry in reversed(new_entries):
            cleaned_link = clean_url(entry.link)
            is_mivzak = (category == "מבזקים")
            
            # 1. שליחה לטלגרם של וואלה (תמיד)
            prefix = "🚨 " if is_mivzak else ""
            caption = f"{RLE}{RLM}<b>{prefix}{entry.title}</b>{PDF}\n\n{cleaned_link}"
            try:
                if is_mivzak:
                    await bot.send_message(chat_id=CHAT_ID, text=caption, parse_mode='HTML', disable_web_page_preview=True)
                else:
                    image = extract_image(entry)
                    if image: await bot.send_photo(chat_id=CHAT_ID, photo=image, caption=caption, parse_mode='HTML')
                    else: await bot.send_message(chat_id=CHAT_ID, text=caption, parse_mode='HTML')
                
                # 2. שליחה לטוויטר (רק אם זה לא ערוץ מבזקים)
                if not is_mivzak:
                    post_to_twitter(entry.title, cleaned_link)
                
                seen_links_set.add(cleaned_link)
                links_list.append(cleaned_link)
                await asyncio.sleep(1)
            except Exception as e: print(f"Walla Error: {e}")
    return links_list

# --- עיבוד חמ"ל (טלגרם בלבד) ---
async def process_hamal(seen_links_set, links_list, counter):
    if not HAMAL_TOKEN or not HAMAL_CHAT_ID: return links_list, counter
    hamal_bot = Bot(token=HAMAL_TOKEN)
    async with hamal_bot:
        url = f"{HAMAL_RSS}?t={int(time.time())}"
        feed = feedparser.parse(url)
        latest_entries = feed.entries[:MAX_ITEMS_PER_FETCH]
        new_entries = [e for e in latest_entries if clean_url(e.link) not in seen_links_set and not is_too_old(e)]
        
        for entry in reversed(new_entries):
            cleaned_link = clean_url(entry.link)
            short_link = get_short_url(cleaned_link)
            raw_title = re.sub(r'<[^>]+>', '', entry.title)
            clean_title = re.sub(r'^חמ"?ל\s*[-:]?\s*חדשות\s*מתפרצות\s*[-:]?\s*', '', raw_title).strip().lstrip(" :")
            
            message = f"{RLE}{RLM}<b>{clean_title}</b>{PDF}\n\n{short_link}"
            try:
                # שליחה לטלגרם של חמ"ל בלבד (ללא טוויטר)
                await hamal_bot.send_message(chat_id=HAMAL_CHAT_ID, text=message, parse_mode='HTML', disable_web_page_preview=True)
                
                seen_links_set.add(cleaned_link)
                links_list.append(cleaned_link)
                counter += 1
                if counter >= PROMO_EVERY_X_MESSAGES:
                    promo = f"{RLE}{RLM}<b>הצטרפו לעדכונים מאתר וואלה</b>{PDF}\n\nhttps://t.me/walla26"
                    try: await hamal_bot.send_photo(chat_id=HAMAL_CHAT_ID, photo=LOGO_URL, caption=promo, parse_mode='HTML')
                    except: await hamal_bot.send_message(chat_id=HAMAL_CHAT_ID, text=promo, parse_mode='HTML')
                    counter = 0 
                await asyncio.sleep(1)
            except Exception as e: print(f"Hamal Error: {e}")
    return links_list, counter

async def main():
    if not TELEGRAM_TOKEN or not CHAT_ID: return
    history = get_
