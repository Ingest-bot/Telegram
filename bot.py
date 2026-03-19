import feedparser
import telegram
import os
import requests
import tweepy
import asyncio

# טעינת משתני סביבה
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
HAMAL_TOKEN = os.getenv('HAMAL_TELEGRAM_TOKEN')
HAMAL_CHAT_ID = os.getenv('HAMAL_CHAT_ID')

TW_API_KEY = os.getenv('TWITTER_API_KEY')
TW_API_SECRET = os.getenv('TWITTER_API_SECRET')
TW_ACCESS_TOKEN = os.getenv('TWITTER_ACCESS_TOKEN')
TW_ACCESS_SECRET = os.getenv('TWITTER_ACCESS_SECRET')

def post_to_twitter(title, link):
    try:
        client = tweepy.Client(
            consumer_key=TW_API_KEY, consumer_secret=TW_API_SECRET,
            access_token=TW_ACCESS_TOKEN, access_token_secret=TW_ACCESS_SECRET
        )
        client.create_tweet(text=f"{title}\n\n{link}")
        print(f"DEBUG: Twitter post successful for {title}")
    except Exception as e:
        print(f"DEBUG: Twitter Error -> {e}")

async def send_telegram(token, chat_id, message):
    try:
        bot = telegram.Bot(token=token)
        await bot.send_message(chat_id=chat_id, text=message, parse_mode='HTML')
        print(f"DEBUG: Telegram sent to {chat_id}")
    except Exception as e:
        print(f"DEBUG: Telegram Error for {chat_id} -> {e}")

def get_last_links():
    if not os.path.exists('last_links.txt'):
        return []
    with open('last_links.txt', 'r') as f:
        return [line.strip() for line in f.readlines()]

async def main():
    print("DEBUG: Script started...")
    last_links = get_last_links()
    new_links = []
    
    feeds = {
        'Walla': 'https://rss.walla.co.il/feed/1?type=main',
        'Hamal': 'https://hamal.co.il/rss'
    }

    for source, url in feeds.items():
        print(f"DEBUG: Checking {source} at {url}...")
        feed = feedparser.parse(url)
        print(f"DEBUG: Found {len(feed.entries)} entries in {source}")
        
        count = 0
        for entry in feed.entries:
            if count >= 5: break
            link = entry.link
            
            if link not in last_links:
                print(f"DEBUG: New item found: {entry.title}")
                msg = f"<b>{entry.title}</b>\n\n{link}"
                
                # שליחה לפי מקור
                if source == 'Walla':
                    await send_telegram(TELEGRAM_TOKEN, CHAT_ID, msg)
                    post_to_twitter(entry.title, link)
                else:
                    await send_telegram(HAMAL_TOKEN, HAMAL_CHAT_ID, msg)
                
                new_links.append(link)
                count += 1

    # עדכון קובץ הזיכרון
    if new_links:
        with open('last_links.txt', 'a') as f:
            for link in new_links:
                f.write(link + '\n')
        print(f"DEBUG: Updated last_links.txt with {len(new_links)} items")
    else:
        print("DEBUG: No new items to update.")

if __name__ == "__main__":
    asyncio.run(main())
