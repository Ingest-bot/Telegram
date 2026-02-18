import feedparser
import asyncio
import os
import re
from telegram import Bot

# הגדרות מה-Secrets של GitHub
RSS_URL = os.getenv("RSS_URL", "https://rss.walla.co.il/feed/1?type=main")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def clean_html(raw_html):
    """מנקה תגיות HTML מהתיאור של וואלה"""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext

async def send_rss_update():
    # משיכת הנתונים
    feed = feedparser.parse(RSS_URL)
    
    if not feed.entries:
        print("לא נמצאו פריטים בפיד.")
        return

    # לוקחים את הכתבה הכי חדשה
    latest_entry = feed.entries[0]
    link = latest_entry.link
    title = latest_entry.title
    summary = clean_html(latest_entry.summary)[:150] + "..." # לוקחים רק התחלה של תקציר

    # בדיקה אם הלינק כבר נשלח בעבר
    if os.path.exists("last_link.txt"):
        with open("last_link.txt", "r") as f:
            if f.read().strip() == link:
                print("הכתבה כבר פורסמה, מדלגים...")
                return

    # בניית ההודעה
    message = (
        f"🔴 *חדשות וואלה!* 🔴\n\n"
        f"*{title}*\n\n"
        f"{summary}\n\n"
        f"[לכתבה המלאה לחצו כאן]({link})"
    )

    # שליחה לטלגרם
    bot = Bot(token=TELEGRAM_TOKEN)
    async with bot:
        await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode='Markdown')
        print(f"נשלח בהצלחה: {title}")
    
    # עדכון הלינק האחרון בקובץ
    with open("last_link.txt", "w") as f:
        f.write(link)

if __name__ == "__main__":
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("שגיאה: חסר Token או Chat ID ב-Secrets!")
    else:
        asyncio.run(send_rss_update())
