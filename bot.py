import feedparser
import asyncio
import os
import re
import requests
from telegram import Bot

# הגדרות וואלה
WALLA_FEEDS = {
    "חדשות": "https://rss.walla.co.il/feed/1?type=main",
    "סלבס": "https://rss.walla.co.il/feed/22?type=main",
    "כסף": "https://rss.walla.co.il/feed/2?type=main",
    "טכנולוגיה": "https://rss.walla.co.il/feed/6?type=main"
}

# הגדרות חמ"ל
HAMAL_RSS = "https://public-api.hamal.co.il/rss"

# טוקנים וזהויות (מ-GitHub Secrets)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
HAMAL_TOKEN = os.getenv("HAMAL_TELEGRAM_TOKEN")
HAMAL_CHAT_ID = os.getenv("HAMAL_CHAT_ID")

LAST_LINKS_FILE = "last_links.txt"
MAX_LINKS_TO_KEEP = 500 

# תווי יישור לימין (RTL)
RLE = "\u202B" 
PDF = "\u202C" 
RLM = "\u200f" 

# --- פונקציות עזר לוואלה ---
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
    return upgrade_image_quality(image_url)

# --- פונקציות עזר לחמ"ל ---
def get_short_url(long_url):
    try:
        api_url = f"http://tinyurl.com/api-create.php?url={long_url}"
        response = requests.get(api_url, timeout=10)
        if response.status_code == 200:
            return response.text.replace("http://", "https://")
    except: pass
    return long_url

# --- עיבוד וואלה ---
async def process_walla(bot, seen_links):
    for category, url in WALLA_FEEDS.items():
        feed = feedparser.parse(url)
        new_entries = [e for e in feed.entries if e.link not in seen_links]
        for entry in reversed(new_entries):
            caption = f"{RLE}{RLM}<b>{entry.title}</b>{PDF}\n\n{entry.link}"
            try:
                image = extract_image(entry)
                if image:
                    await bot.send_photo(chat_id=CHAT_ID, photo=image, caption=caption, parse_mode='HTML')
                else:
                    await bot.send_message(chat_id=CHAT_ID, text=caption, parse_mode='HTML')
                seen_links.append(entry.link)
                await asyncio.sleep(1)
            except Exception as e: print(f"Walla Error: {e}")
    return seen_links

# --- עיבוד חמ"ל ---
async def process_hamal(bot, seen_links):
    if not HAMAL_TOKEN or not HAMAL_CHAT_ID: return seen_links
    
    # בוט נפרד לחמ"ל (או אותו בוט אם הטוקן זהה, אבל נשתמש בטוקן הייעודי)
    hamal_bot = Bot(token=HAMAL_TOKEN)
    async with hamal_bot:
        feed = feedparser.parse(HAMAL_RSS)
        new_entries = [e for e in feed.entries if e.link not in seen_links]
        for entry in reversed(new_entries):
            clean_title = re.sub(r'<[^>]+>', '', entry.title)
            short_link = get_short_url(entry.link)
            # יישור לימין גם לחמ"ל
            message = f"{RLE}{RLM}<b>{clean_title}</b>{PDF}\n\n{short_link}"
            
            try:
                await hamal_bot.send_message(
                    chat_id=HAMAL_CHAT_ID, 
                    text=message, 
                    parse_mode='HTML', 
                    disable_web_page_preview=True
                )
                seen_links.append(entry.link)
                await asyncio.sleep(1)
            except Exception as e: print(f"Hamal Error: {e}")
    return seen_links

async def main():
    if not TELEGRAM_TOKEN or not CHAT_ID: return
    
    # טעינת היסטוריה
    if os.path.exists(LAST_LINKS_FILE):
        with open(LAST_LINKS_FILE, "r", encoding="utf-8") as f:
            seen_links = [line.strip() for line in f.readlines() if line.strip()]
    else:
        seen_links = []

    # הרצת וואלה
    bot = Bot(token=TELEGRAM_TOKEN)
    async with bot:
        seen_links = await process_walla(bot, seen_links)
    
    # הרצת חמ"ל
    seen_links = await process_hamal(None, seen_links)

    # שמירת היסטוריה מוגדלת
    with open(LAST_LINKS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(seen_links[-MAX_LINKS_TO_KEEP:]))

if __name__ == "__main__":
    asyncio.run(main())
