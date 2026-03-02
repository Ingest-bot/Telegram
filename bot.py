import feedparser
import asyncio
import os
import re
import urllib.request
from telegram import Bot

FEEDS = {
    "חדשות": "https://rss.walla.co.il/feed/1?type=main",
    "סלבס": "https://rss.walla.co.il/feed/22?type=main",
    "כסף": "https://rss.walla.co.il/feed/2?type=main",
    "טכנולוגיה": "https://rss.walla.co.il/feed/6?type=main"
}

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
LAST_LINKS_FILE = "last_links.txt"
RLM = "\u200f"

def shorten_url(long_url):
    """מקצר את הלינק באופן אוטומטי דרך TinyURL"""
    try:
        api_url = "http://tinyurl.com/api-create.php?url=" + long_url
        with urllib.request.urlopen(api_url) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        print(f"שגיאה בקיצור לינק: {e}")
        return long_url # אם נכשל, מחזיר את הלינק המקורי

def upgrade_image_quality(url):
    if not url: return url
    return re.sub(r'w=\d+', 'w=1200', url)

def extract_image(entry):
    image_url = None
    if 'media_content' in entry: image_url = entry.media_content[0]['url']
    elif 'links' in entry:
        for link in entry.links:
            if 'image' in link.get('type', ''):
                image_url = link.get('href')
                break
    return upgrade_image_quality(image_url)

async def process_feed(bot, category, url, seen_links):
    print(f"בודק את {category}...")
    feed = feedparser.parse(url)
    if not feed.entries: return
    
    new_entries = [e for e in feed.entries if e.link not in seen_links]
    
    for entry in reversed(new_entries):
        # 1. מקצרים את הלינק
        short_link = shorten_url(entry.link)
        
        # 2. בונים את ההודעה - כשהלינק קצר, ה-RLM באמת מצליח להצמיד הכל לימין
        caption = f"{RLM}<b>{entry.title}</b>\n\n{RLM}{short_link}"

        try:
            image = extract_image(entry)
            if image:
                await bot.send_photo(chat_id=CHAT_ID, photo=image, caption=caption, parse_mode='HTML')
            else:
                await bot.send_message(chat_id=CHAT_ID, text=caption, parse_mode='HTML')
            
            with open(LAST_LINKS_FILE, "a", encoding="utf-8") as f:
                f.write(entry.link + "\n")
            await asyncio.sleep(1) 
        except Exception as e:
            print(f"Error: {e}")

async def main():
    if not TELEGRAM_TOKEN or not CHAT_ID: return
    bot = Bot(token=TELEGRAM_TOKEN)
    seen_links = set()
    if os.path.exists(LAST_LINKS_FILE):
        with open(LAST_LINKS_FILE, "r", encoding="utf-8") as f:
            seen_links = set(line.strip() for line in f.readlines())

    async with bot:
        for category, url in FEEDS.items():
            await process_feed(bot, category, url, seen_links)

if __name__ == "__main__":
    asyncio.run(main())
