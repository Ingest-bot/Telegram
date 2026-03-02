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
MAX_LINKS_TO_KEEP = 100  # שומרים רק את ה-100 האחרונים כדי שהקובץ לא יתנפח

# תווי שליטה חזקים ליישור
RLE = "\u202B" # כפיית ימין (כותרת)
LRE = "\u202A" # כפיית שמאל (לינק)
PDF = "\u202C" # סגירת פקודה
RLM = "\u200f" # תו עברי שקוף

def upgrade_image_quality(url):
    if not url: return url
    return re.sub(r'w=\d+', 'w=1200', url)

def extract_image(entry):
    image_url = None
    if 'media_content' in entry: image_url = entry.media_content[0]['url']
    elif 'links' in entry:
        for link in entry.links:
            if 'image' in link.get('type', ''):
                image_url = link.get('href'); break
    return upgrade_image_quality(image_url)

def get_seen_links():
    if not os.path.exists(LAST_LINKS_FILE):
        return []
    with open(LAST_LINKS_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f.readlines() if line.strip()]

def save_links(links):
    # שומר רק את ה-X האחרונים ברשימה
    with open(LAST_LINKS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(links[-MAX_LINKS_TO_KEEP:]))

async def process_feed(bot, category, url, seen_links_list):
    feed = feedparser.parse(url)
    if not feed.entries: return
    
    seen_links_set = set(seen_links_list)
    new_entries = [e for e in feed.entries if e.link not in seen_links_set]
    
    for entry in reversed(new_entries):
        link = entry.link
        # יישור: כותרת לימין, לינק לשמאל (בלי קיצור)
        caption = f"{RLE}{RLM}<b>{entry.title}</b>{PDF}\n\n{LRE}{link}{PDF}"

        try:
            image = extract_image(entry)
            if image:
                await bot.send_photo(chat_id=CHAT_ID, photo=image, caption=caption, parse_mode='HTML')
            else:
                await bot.send_message(chat_id=CHAT_ID, text=caption, parse_mode='HTML')
            
            seen_links_list.append(link)
            print(f"נשלח: {entry.title[:30]}")
            await asyncio.sleep(1) 
        except Exception as e:
            print(f"Error: {e}")
    
    return seen_links_list

async def main():
    if not TELEGRAM_TOKEN or not CHAT_ID: return
    bot = Bot(token=TELEGRAM_TOKEN)
    seen_links = get_seen_links()

    async with bot:
        for category, url in FEEDS.items():
            seen_links = await process_feed(bot, category, url, seen_links)
        
    save_links(seen_links)

if __name__ == "__main__":
    asyncio.run(main())
