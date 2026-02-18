import feedparser
import asyncio
import os
import re
import html
from telegram import Bot

# הגדרות מה-Secrets של GitHub
RSS_URL = os.getenv("RSS_URL", "https://rss.walla.co.il/feed/3?type=main")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def clean_html(raw_html):
    """מנקה תגיות HTML"""
    if not raw_html:
        return ""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    cleantext = html.unescape(cleantext)
    cleantext = " ".join(cleantext.split())
    return cleantext

def extract_image(entry):
    """מנסה למצוא תמונה בתוך האייטם של ה-RSS"""
    # בדיקה בתוך ה-links (נפוץ בוואלה)
    for link in entry.get('links', []):
        if 'image' in link.get('type', ''):
            return link.get('href')
    
    # בדיקה בתוך ה-media content
    if 'media_content' in entry:
        return entry.media_content[0]['url']
    
    # בדיקה בתוך ה-summary (חיפוש תגית img)
    if 'summary' in entry:
        img_match = re.search(r'<img src="([^"]+)"', entry.summary)
        if img_match:
            return img_match.group(1)
            
    return None

async def send_rss_update():
    feed = feedparser.parse(RSS_URL)
    
    if not feed.entries:
        return

    latest_entry = feed.entries[0]
    link = latest_entry.link
    title = latest_entry.title
    image_url = extract_image(latest_entry)
    
    last_link_file = "last_link.txt"
    if os.path.exists(last_link_file):
        with open(last_link_file, "r") as f:
            if f.read().strip() == link:
                print(f"הכתבה '{title}' כבר פורסמה.")
                return

    # בניית הטקסט שיופיע מתחת לתמונה
    caption = (
        f"*{title}*\n\n"
        f"{link}"
    )

    bot = Bot(token=TELEGRAM_TOKEN)
    async with bot:
        try:
            if image_url:
                # שליחת תמונה עם טקסט צמוד
                await bot.send_photo(
                    chat_id=CHAT_ID,
                    photo=image_url,
                    caption=caption,
                    parse_mode='Markdown'
                )
            else:
                # גיבוי: אם לא נמצאה תמונה, שלח רק טקסט
                await bot.send_message(
                    chat_id=CHAT_ID,
                    text=caption,
                    parse_mode='Markdown',
                    disable_web_page_preview=False
                )
            
            print(f"נשלח בהצלחה: {title}")
            with open(last_link_file, "w") as f:
                f.write(link)
                
        except Exception as e:
            print(f"שגיאה: {e}")

if __name__ == "__main__":
    if TELEGRAM_TOKEN and CHAT_ID:
        asyncio.run(send_rss_update())
