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

# תו כיווניות מימין לשמאל (RLM) - לביטחון נוסף
RLM = "\u200f"

def extract_image(entry):
    for link in entry.get('links', []):
        if 'image' in link.get('type', ''): return link.get('href')
    if 'media_content' in entry: return entry.media_content[0]['url']
    if 'summary' in entry:
        img_match = re.search(r'<img src="([^"]+)"', entry.summary)
        if img_match: return img_match.group(1)
    return None

def get_last_links():
    if os.path.exists(LAST_LINKS_FILE):
        with open(LAST_LINKS_FILE, "r") as f:
            return set(line.strip() for line in f.readlines())
    return set()

def save_last_link(link):
    with open(LAST_LINKS_FILE, "a") as f:
        f.write(link + "\n")

async def process_feed(bot, category, url, seen_links):
    print(f"בודק את קטגוריית {category}...")
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
        
        # בניית ה-Caption עם טקסט מקדים מכובד ללינק.
        # ה-RLM מבטיח שגם אם יש תווים בעייתיים, האייפון יישאר בימין.
        caption = f"{RLM}<b>{title}</b>\n\n{RLM}לכתבה המלאה: {link}"

        try:
            if image_url:
                await bot.send_photo(
                    chat_id=CHAT_ID, 
                    photo=image_url, 
                    caption=caption, 
                    parse_mode='HTML'
                )
            else:
                await bot.send_message(
                    chat_id=CHAT_ID, 
                    text=caption, 
                    parse_mode='HTML'
                )
            
            save_last_link(link)
            await asyncio.sleep(1) 
        except Exception as e:
            print(f"שגיאה: {e}")

async def main():
    if not TELEGRAM_TOKEN or not CHAT_ID: return
    bot = Bot(token=TELEGRAM_TOKEN)
    seen_links = get_last_links()
    async with bot:
        for category, url in FEEDS.items():
            await process_feed(bot, category, url, seen_links)

if __name__ == "__main__":
    asyncio.run(main())
