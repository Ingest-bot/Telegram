import feedparser
import asyncio
import os
import re
import html
from telegram import Bot

# רשימת הפידים של וואלה
FEEDS = {
    "חדשות": "https://rss.walla.co.il/feed/1?type=main",
    "ספורט": "https://rss.walla.co.il/feed/3?type=main",
    "סלבס": "https://rss.walla.co.il/feed/23?type=main"
}

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
LAST_LINKS_FILE = "last_links.txt"

def clean_html(raw_html):
    if not raw_html: return ""
    cleantext = re.sub(re.compile('<.*?>'), '', raw_html)
    return html.unescape(" ".join(cleantext.split()))

def extract_image(entry):
    for link in entry.get('links', []):
        if 'image' in link.get('type', ''): return link.get('href')
    if 'media_content' in entry: return entry.media_content[0]['url']
    if 'summary' in entry:
        img_match = re.search(r'<img src="([^"]+)"', entry.summary)
        if img_match: return img_match.group(1)
    return None

def get_last_links():
    """טוען את רשימת הלינקים האחרונים שנשמרו"""
    if os.path.exists(LAST_LINKS_FILE):
        with open(LAST_LINKS_FILE, "r") as f:
            return set(line.strip() for line in f.readlines())
    return set()

def save_last_link(link):
    """מוסיף לינק חדש לקובץ ההיסטוריה"""
    with open(LAST_LINKS_FILE, "a") as f:
        f.write(link + "\n")

async def process_feed(bot, category, url, seen_links):
    print(f"בודק את קטגוריית {category}...")
    feed = feedparser.parse(url)
    if not feed.entries: return

    latest_entry = feed.entries[0]
    link = latest_entry.link
    title = latest_entry.title

    if link in seen_links:
        print(f"אין חדש ב-{category}.")
        return

    image_url = extract_image(latest_entry)
    # הוספת שם הקטגוריה לכותרת למען הסדר הטוב
    caption = f"*{category}: {title}*\n\n{link}"

    try:
        if image_url:
            await bot.send_photo(chat_id=CHAT_ID, photo=image_url, caption=caption, parse_mode='Markdown')
        else:
            await bot.send_message(chat_id=CHAT_ID, text=caption, parse_mode='Markdown')
        
        save_last_link(link)
        print(f"נשלח: {title}")
    except Exception as e:
        print(f"שגיאה ב-{category}: {e}")

async def main():
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("חסרים פרטי גישה!")
        return

    bot = Bot(token=TELEGRAM_TOKEN)
    seen_links = get_last_links()

    async with bot:
        for category, url in FEEDS.items():
            await process_feed(bot, category, url, seen_links)

if __name__ == "__main__":
    asyncio.run(main())
