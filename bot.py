import feedparser
import telegram
import os
import requests
import asyncio

# טעינת משתני סביבה לטלגרם בלבד
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
HAMAL_TOKEN = os.getenv('HAMAL_TELEGRAM_TOKEN')
HAMAL_CHAT_ID = os.getenv('HAMAL_CHAT_ID')

async def send_telegram(token, chat_id, message):
    if not token or not chat_id: return
    try:
        bot = telegram.Bot(token=token)
        await bot.send_message(chat_id=chat_id, text=message, parse_mode='HTML')
        print(f"DEBUG: Telegram success for {chat_id}")
    except Exception as e:
        print(f"DEBUG: Telegram Error for {chat_id} -> {e}")

async def main():
    print("DEBUG: Starting bot (Telegram mode)...")
    
    # User-Agent שגורם לאתרים לחשוב שאנחנו דפדפן רגיל ולא בוט
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}
    
    feeds = {
        'Walla': 'https://rss.walla.co.il/feed/1?type=main',
        'Hamal': 'https://hamal.co.il/rss'
    }

    last_links = []
    if os.path.exists('last_links.txt'):
        with open('last_links.txt', 'r') as f:
            last_links = [l.strip() for l in f.readlines()]

    new_links = []
    for source, url in feeds.items():
        try:
            print(f"DEBUG: Fetching {source}...")
            # שימוש ב-requests עם ה-headers החדשים
            resp = requests.get(url, headers=headers, timeout=15)
            feed = feedparser.parse(resp.content)
            print(f"DEBUG: {source} returned {len(feed.entries)} items")
            
            count = 0
            for entry in feed.entries:
                if count >= 3: break
                if entry.link not in last_links:
                    msg = f"<b>{entry.title}</b>\n\n{entry.link}"
                    
                    if source == 'Walla':
                        await send_telegram(TELEGRAM_TOKEN, CHAT_ID, msg)
                    else:
                        await send_telegram(HAMAL_TOKEN, HAMAL_CHAT_ID, msg)
                    
                    new_links.append(entry.link)
                    count += 1
        except Exception as e:
            print(f"DEBUG: Error with {source} -> {e}")

    if new_links:
        with open('last_links.txt', 'a') as f:
            for l in new_links: f.write(l + '\n')
        print(f"DEBUG: Finished. Saved {len(new_links)} new links.")

if __name__ == "__main__":
    asyncio.run(main())
