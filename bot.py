import feedparser
import asyncio
import os
import re
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
MAX_LINKS_TO_KEEP = 200 

# תווי הכוח של היישור
RLE = "\u202B" # התחלת פסקה ימנית חסינה
PDF = "\u202C" # סגירת הפסקה
RLM = "\u200f" # תו עברי שקוף

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

async def process_feed(bot, category, url, seen_links_list):
    feed = feedparser.parse(url)
    if not feed.entries: return
    
    seen_links_set = set(seen_links_list)
    new_entries = [e for e in feed.entries if e.link not in seen_links_set]
    
    for entry in reversed(new_entries):
        link = entry.link
        
        # התיקון: עוטפים את כל הכותרת ב-RLE אחד חזק שכולל בתוכו RLM.
        # זה יוצר "קופסה" ימנית שמונעת מהאייפון להזיז את השורות הראשונות.
        caption = f"{RLE}{RLM}<b>{entry.title}</b>{PDF}\n\n{link}"

        try:
            image = extract_image(entry)
            if image:
                await bot.send_photo(chat_id=CHAT_ID, photo=image, caption=caption, parse_mode='HTML')
            else:
                await bot.send_message(chat_id=CHAT_ID, text=caption, parse_mode='HTML')
            
            seen_links_list.append(link)
            await asyncio.sleep(1) 
        except Exception as e:
            print(f"Error: {e}")
    
    return seen_links_list

async def main():
    if not TELEGRAM_TOKEN or not CHAT_ID: return
    bot = Bot(token=TELEGRAM_TOKEN)
    
    if os.path.exists(LAST_LINKS_FILE):
        with open(LAST_LINKS_FILE, "r", encoding="utf-8") as f:
            seen_links = [line.strip() for line in f.readlines() if line.strip()]
    else:
        seen_links = []

    async with bot:
        for category, url in FEEDS.items():
            seen_links = await process_feed(bot, category, url, seen_links)
        
    with open(LAST_LINKS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(seen_links[-MAX_LINKS_TO_KEEP:]))

if __name__ == "__main__":
    asyncio.run(main())
