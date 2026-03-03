import requests
import feedparser
import os

# Secrets מ-GitHub
TOKEN = os.environ.get('HAMAL_TELEGRAM_TOKEN') 
CHAT_ID = os.environ.get('HAMAL_CHAT_ID')

def get_hamal_news():
    # הכתובת המדויקת שאתה מצאת
    url = "https://public-api.hamal.co.il/rss"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        print(f"Connecting to: {url}")
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            # פירוח ה-RSS
            feed = feedparser.parse(response.content)
            return feed.entries
        else:
            print(f"Status Code: {response.status_code}")
            return []
    except Exception as e:
        print(f"Error: {e}")
        return []

def send_to_telegram(title, link, description):
    if not TOKEN or not CHAT_ID:
        print("Missing Credentials")
        return

    # חמ"ל שמים לפעמים HTML בתיאור, ננקה אותו קצת
    import re
    clean_desc = re.sub(r'<[^>]+>', '', description)
    
    msg = f"<b>{title}</b>\n\n{clean_desc}\n\n<a href='{link}'>לידיעה המלאה בחמ\"ל</a>"
    
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID, 
        "text": msg, 
        "parse_mode": "HTML"
    }
    
    res = requests.post(url, json=payload)
    if res.status_code == 200:
        print("Sent successfully!")
    else:
        print(f"Failed: {res.text}")

if __name__ == "__main__":
    print("Checking Hamal RSS...")
    items = get_hamal_news()
    
    if items:
        # לוקח את המבזק הראשון (הכי חדש)
        latest = items[0]
        send_to_telegram(latest.title, latest.link, latest.summary)
    else:
        print("No news items found.")
