import feedparser
import asyncio
import os
import re
from telegram import Bot

# רשימת הפידים
FEEDS = {
    "חדשות": "https://rss.walla.co.il/feed/1?type=main",
    "סלבס": "https://rss.walla.co.il/feed/22?type=main",
    "כסף": "https://rss.walla.co.il/feed/2?type=main",
    "טכנולוגיה": "https://rss.walla.co.il/feed/6?type=main"
}

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
LAST_LINKS_FILE = "last_links.txt"

# תווי כיווניות
RLM = "\u200f" # תו עברי שקוף
LRE = "\u202A" # תחילת בלוק שמאלי (אנגלית)
PDF = "\u202C" # סגירת בלוק

def upgrade_image_quality(url):
    """משדרג את התמונה לרזולוציה מקסימלית (1200 פיקסלים)"""
    if not url or not isinstance(url, str): return url
    if "w=" in url:
        url = re.sub(r'w=\d+', 'w=1200', url)
    url = url.replace("/re-size/", "/").replace("/w/400/", "/w/1200/")
    return url

def extract_image(entry):
    image_url = None
    if 'media_content' in entry:
        image_url = entry.media_content[0]['url']
    elif 'links' in entry:
        for link in entry.links:
            if 'image' in link.get('type', ''):
                image_url = link.get('href')
                break
    if not image_url and 'summary' in entry:
        img_match = re.search(r'<img[^>]+src="([^">]+)"', entry.summary)
        if img_match: image_url = img_match.group(1)
    
    return upgrade_image_quality(image_url)

async def process_feed(bot, category, url, seen_links):
    print(f"בודק את {category}...")
    feed = feedparser.parse(url)
    if not feed.entries: return
    
    new_entries = []
    for entry in feed.entries:
        if entry.link not in seen_links:
            new_entries.append(entry)
        else:
            break
    
    if not new_entries: return

    for entry in reversed(new_entries):
        link = entry.link
        title = entry.title
        image_url = extract_image(entry)
        
        # בניית ההודעה:
        # הכותרת עטופה ב-RLM כדי להיצמד לימין הקיצוני.
        # הקישור עטוף ב-LRE כדי להיצמד לשמאל הקיצוני (ולא "להימרח" על העברית).
        caption = (
            f"{RLM}<b>{title}</b>{RLM}\n\n"
            f"{LRE}{link}{PDF}"
        )

        try:
            if image_url:
                await bot.send_photo(chat_id=CHAT_ID, photo=image_url, caption=caption, parse_mode='HTML')
            else:
                await bot.send_message(chat_id=CHAT_ID, text=caption, parse_mode='HTML')
            
            with open(LAST_LINKS_FILE, "a", encoding="utf-8") as f:
                f.write(link + "\n")
            
            await asyncio.sleep(1) 
        except Exception as e:
            print(f"שגיאה: {e}")

async def main():
    if not TELEGRAM_TOKEN or not CHAT_ID: return
    bot = Bot(token=TELEGRAM_TOKEN)
    if os.path.exists(LAST_LINKS_FILE):
        with open(LAST_LINKS_FILE, "r", encoding="utf-8") as f:
            seen_links = set(line.strip() for line in f.readlines())
    else:
        seen_links = set()

    async with bot:
        for category, url in FEEDS.items():
            await process_feed(bot, category, url, seen_links)

if __name__ == "__main__":
    asyncio.run(main())
