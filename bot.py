import feedparser
import asyncio
import os
import re
import html
from telegram import Bot

# הגדרות מה-Secrets של GitHub
RSS_URL = os.getenv("RSS_URL", "https://rss.walla.co.il/feed/1?type=main")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def clean_html(raw_html):
    """מנקה תגיות HTML, מפענח ישויות HTML ומנקה רווחים מיותרים"""
    if not raw_html:
        return ""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    cleantext = html.unescape(cleantext)
    cleantext = " ".join(cleantext.split())
    return cleantext

async def send_rss_update():
    feed = feedparser.parse(RSS_URL)
    
    if not feed.entries:
        print("לא נמצאו פריטים בפיד.")
        return

    latest_entry = feed.entries[0]
    link = latest_entry.link
    title = latest_entry.title
    
    summary = clean_html(latest_entry.summary)
    if len(summary) > 200:
        summary = summary[:197] + "..."

    last_link_file = "last_link.txt"
    if os.path.exists(last_link_file):
        with open(last_link_file, "r") as f:
            if f.read().strip() == link:
                print(f"הכתבה '{title}' כבר פורסמה, מדלגים...")
                return

    # בניית ההודעה ללא הכותרת "חדשות וואלה!"
    message = (
        f"*{title}*\n\n"
        f"{summary}\n\n"
        f"{link}"
    )

    bot = Bot(token=TELEGRAM_TOKEN)
    async with bot:
        try:
            await bot.send_message(
                chat_id=CHAT_ID, 
                text=message, 
                parse_mode='Markdown',
                disable_web_page_preview=False
            )
            print(f"נשלח בהצלחה: {title}")
            
            with open(last_link_file, "w") as f:
                f.write(link)
                
        except Exception as e:
            print(f"שגיאה בשליחת ההודעה: {e}")

if __name__ == "__main__":
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("שגיאה: חסר Token או Chat ID ב-Secrets של GitHub!")
    else:
        asyncio.run(send_rss_update())
