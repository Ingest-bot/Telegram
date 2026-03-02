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
RLM = "\u200f"

def upgrade_image_quality(url):
    """מנסה להפוך תמונה קטנה לתמונה גדולה ואיכותית ללא שימוש בספריות חיצוניות"""
    if not url or not isinstance(url, str):
        return url
    
    # וואלה משתמשים בפרמטר w לרוחב. ננסה להחליף אותו ל-1000 פיקסלים
    if "w=" in url:
        return re.sub(r'w=\d+', 'w=1000', url)
    
    # לעיתים ב-RSS יש תמונות קטנות בפורמט מסוים, ננסה להסיר הגבלות גודל אם קיימות
    return url

def extract_image(entry):
    image_url = None
    # 1. חיפוש בקישורים
    for link in entry.get('links', []):
        if 'image' in link.get('type', ''): 
            image_url = link.get('href')
            break
    
    # 2. חיפוש ב-media_content
    if not image_url and 'media_content' in entry:
        image_url = entry.media_content[0]['url']
        
    # 3. חיפוש בתוך התיאור (summary)
    if not image_url and 'summary' in entry:
        img_match = re.search(r'<img[^>]+src="([^">]+)"', entry.summary)
        if img_match:
            image_url = img_match.group(1)
    
    return upgrade_image_quality(image_url)

def get_last_links():
    if os.path.exists(LAST_LINKS_FILE):
        with open(LAST_LINKS_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f.readlines())
    return set()

def save_last_link(link):
    with open(LAST_LINKS_FILE, "a", encoding="utf-8") as f:
        f.write(link + "\n")

async def process_feed(bot, category, url, seen_links):
    print(f"בודק את {category}...")
    try:
        feed = feedparser.parse(url)
    except Exception as e:
        print(f"שגיאה בקריאת הפיד {category}: {e}")
        return

    if not feed.entries:
        return
    
    new_entries = []
    for entry in feed.entries:
        if entry.link not in seen_links:
            new_entries.append(entry)
        else:
            break
    
    if not new_entries:
        return

    for entry in reversed(new_entries):
        link = entry.link
        title = entry.title
        image_url = extract_image(entry)
        
        # המבנה שסיכמנו עליו: כותרת מודגשת ולינק עם טקסט מקדים
        caption = f"{RLM}<b>{title}</b>\n\n{RLM}לכתבה המלאה: {link}"

        try:
            if image_url:
                await bot.send_photo(chat_id=CHAT_ID, photo=image_url, caption=caption, parse_mode='HTML')
            else:
                await bot.send_message(chat_id=CHAT_ID, text=caption, parse_mode='HTML')
            
            save_last_link(link)
            print(f"נשלח: {title[:30]}...")
            await asyncio.sleep(1) 
        except Exception as e:
            print(f"שגיאה בשליחת הודעה: {e}")

async def main():
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("חסר טוקן או CHAT_ID")
        return

    bot = Bot(token=TELEGRAM_TOKEN)
    seen_links = get_last_links()

    async with bot:
        for category, url in FEEDS.items():
            await process_feed(bot, category, url, seen_links)

if __name__ == "__main__":
    asyncio.run(main())
