import requests
import feedparser
import os
import re

# Secrets מ-GitHub
TOKEN = os.environ.get('HAMAL_TELEGRAM_TOKEN') 
CHAT_ID = os.environ.get('HAMAL_CHAT_ID')

def get_hamal_news():
    url = "https://public-api.hamal.co.il/rss"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            feed = feedparser.parse(response.content)
            return feed.entries
    except Exception as e:
        print(f"Error: {e}")
    return []

def send_to_telegram(title, link):
    if not TOKEN or not CHAT_ID:
        return

    # פורמט וואלה: כותרת מודגשת ומתחתיה הקישור
    msg = f"<b>{title}</b>\n\n{link}"
    
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID, 
        "text": msg, 
        "parse_mode": "HTML"
    }
    
    requests.post(url, json=payload)

if __name__ == "__main__":
    items = get_hamal_news()
    if items:
        # לוקח את הידיעה הכי חדשה
        latest = items[0]
        
        # ניקוי תגיות מהכותרת אם יש (לפעמים חמ"ל מכניסים HTML בכותרת)
        clean_title = re.sub(r'<[^>]+>', '', latest.title)
        
        send_to_telegram(clean_title, latest.link)
        print("Sent in Walla format!")
