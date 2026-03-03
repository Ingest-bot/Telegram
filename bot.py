import feedparser
import asyncio
import os
import re
import requests
from telegram import Bot

# --- הגדרות ---
WALLA_FEEDS = {
    "חדשות": "https://rss.walla.co.il/feed/1?type=main",
    "סלבס": "https://rss.walla.co.il/feed/22?type=main",
    "כסף": "https://rss.walla.co.il/feed/2?type=main",
    "טכנולוגיה": "https://rss.walla.co.il/feed/6?type=main"
}
HAMAL_RSS = "https://public-api.hamal.co.il/rss"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
HAMAL_TOKEN = os.getenv("HAMAL_TELEGRAM_TOKEN")
HAMAL_CHAT_ID = os.getenv("HAMAL_CHAT_ID")

LAST_LINKS_FILE = "last_links.txt"
MAX_LINKS_TO_KEEP = 500
PROMO_EVERY_X_MESSAGES = 20 # הוגדר לפעם ב-20 הודעות לבקשתך

RLE = "\u202B" 
PDF = "\u202C" 
RLM = "\u200f" 

# נתיב ישיר ללוגו ב-GitHub שלך
LOGO_URL = "https://raw.githubusercontent.com/Ingest-bot/Telegram/main/Logo.jpeg"

# --- פונקציות עזר ---
def get_history():
    history = {"links": [], "counter": 0}
    if os.path.exists(LAST_LINKS_FILE):
        with open(LAST_LINKS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("COUNTER:"):
                    try:
                        history["counter"] = int(line.replace("COUNTER:", ""))
                    except: history["counter"] = 0
                elif line:
                    history["links"].append(line)
    return history

def save_history(links, counter):
    with open(LAST_LINKS_FILE, "w", encoding="utf-8") as f:
        f.write(f"COUNTER:{counter}\n")
        for link in links[-MAX_LINKS_TO_KEEP:]:
            f.write(f"{link}\n")

def get_short_url(long_url):
    try:
        api_url = f"http://tinyurl.com/api-create.php?url={long_url}"
        response = requests.get(api_url, timeout=10)
        if response.status_code == 200:
            return response.text.replace("http://", "https://")
    except: pass
    return long_url

# --- עיבוד וואלה ---
async def process_walla(bot, seen_links):
    for category, url in WALLA_FEEDS.items():
        feed = feedparser.parse(url)
        new_entries = [e for e in feed.entries if e.link not in seen_links]
        for entry in reversed(new_entries):
            caption = f"{RLE}{RLM}<b>{entry.title}</b>{PDF}\n\n{entry.link}"
            try:
                # שליחה לערוץ וואלה
                await bot.send_message(chat_id=CHAT_ID, text=caption, parse_mode='HTML')
                seen_links.append(entry.link)
                await asyncio.sleep(1)
            except Exception as e: print(f"Walla Error: {e}")
    return seen_links

# --- עיבוד חמ"ל ---
async def process_hamal(seen_links, counter):
    if not HAMAL_TOKEN or not HAMAL_CHAT_ID: return seen_links, counter
    
    hamal_bot = Bot(token=HAMAL_TOKEN)
    async with hamal_bot:
        feed = feedparser.parse(HAMAL_RSS)
        new_entries = [e for e in feed.entries if e.link not in seen_links]
        
        for entry in reversed(new_entries):
            clean_title = re.sub(r'<[^>]+>', '', entry.title)
            short_link = get_short_url(entry.link)
            message = f"{RLE}{RLM}<b>{clean_title}</b>{PDF}\n\n{short_link}"
            
            try:
                # שליחת המבזק לערוץ חמ"ל
                await hamal_bot.send_message(chat_id=HAMAL_CHAT_ID, text=message, parse_mode='HTML', disable_web_page_preview=True)
                seen_links.append(entry.link)
                counter += 1
                
                # שליחת פרסומת בנפרד (רק בחמ"ל)
                if counter >= PROMO_EVERY_X_MESSAGES:
                    promo_caption = f"{RLE}{RLM}<b>הצטרפו לעדכונים מאתר וואלה!</b>{PDF}\n\nhttps://t.me/walla26"
                    try:
                        await hamal_bot.send_photo(chat_id=HAMAL_CHAT_ID, photo=LOGO_URL, caption=promo_caption, parse_mode='HTML')
                    except:
                        await hamal_bot.send_message(chat_id=HAMAL_CHAT_ID, text=promo_caption, parse_mode='HTML')
                    counter = 0 # איפוס המונה
                
                await asyncio.sleep(1)
            except Exception as e: print(f"Hamal Error: {e}")
            
    return seen_links, counter

async def main():
    if not TELEGRAM_TOKEN or not CHAT_ID: return
    
    history = get_history()
    seen_links = history["links"]
    counter = history["counter"]

    # ריצה על וואלה
    bot = Bot(token=TELEGRAM_TOKEN)
    async with bot:
        seen_links = await process_walla(bot, seen_links)
    
    # ריצה על חמ"ל
    seen_links, counter = await process_hamal(seen_links, counter)

    # שמירה לסוף
    save_history(seen_links, counter)

if __name__ == "__main__":
    asyncio.run(main())
