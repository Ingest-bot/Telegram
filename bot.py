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

# תווי שליטה חזקים - אלו לא משתנים, הם פקודות למערכת ההפעלה
RLE = "\u202B" # כפיית כיוון ימין-שמאל (לכותרת)
LRE = "\u202A" # כפיית כיוון שמאל-ימין (ללינק)
PDF = "\u202C" # סגירת הפקודה
RLM = "\u200f" # תו עברי שקוף לחיזוק

def upgrade_image_quality(url):
    if not url: return url
    # החלפת רוחב ל-1200 לחדות מקסימלית
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
        link = entry.link
        
        # בניית הודעה עם הפרדה מוחלטת:
        # 1. הכותרת מקבלת RLE (ימין) ו-RLM (עברית) כדי שגם מרכאות לא יזיזו אותה.
        # 2. הלינק המקורי מקבל LRE (שמאל) כדי שלא ינסה "להידחף" לימין ולשבור את העברית.
        caption = (
            f"{RLE}{RLM}<b>{entry.title}</b>{PDF}\n\n"
            f"{LRE}{link}{PDF}"
        )

        try:
            image = extract_image(entry)
            if image:
                await bot.send_photo(chat_id=CHAT_ID, photo=image, caption=caption, parse_mode='HTML')
            else:
                await bot.send_message(chat_id=CHAT_ID, text=caption, parse_mode='HTML')
            
            with open(LAST_LINKS_FILE, "a", encoding="utf-8") as f:
                f.write(link + "\n")
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
