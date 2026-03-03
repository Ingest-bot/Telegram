import requests
import os

# שליחת המשתנים מה-GitHub Secrets
TOKEN = os.environ.get('HAMAL_TELEGRAM_TOKEN') 
CHAT_ID = os.environ.get('HAMAL_CHAT_ID')

def get_hamal_news():
    # שים לב: השורה הזו חייבת להיות עם 4 רווחים בדיוק מהקצה
    url = "https://public-api.hamal.co.il/api/v1/feed?limit=5"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://www.hamal.co.il/",
        "Origin": "https://www.hamal.co.il"
    }
    
    try:
        print(f"Connecting to: {url}")
        response = requests.get(url, headers=headers, timeout=15)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            # בדיקה אם המבנה הוא רשימה או אובייקט
            if isinstance(data, list):
                items = data
            else:
                items = data.get('feed', {}).get('items', data.get('items', []))
            
            return items
        else:
            print(f"Failed. Response: {response.text[:100]}")
            return []
    except Exception as e:
        print(f"Error: {e}")
        return []

def send_to_telegram(title, content):
    if not TOKEN or not CHAT_ID:
        print("Missing Credentials")
        return

    msg = f"<b>{title}</b>\n\n{content}"
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
    
    try:
        requests.post(url, json=payload)
        print("Message sent!")
    except Exception as e:
        print(f"Telegram error: {e}")

if __name__ == "__main__":
    print("Starting...")
    news_items = get_hamal_news()
    if news_items:
        latest = news_items[0]
        # חילוץ נתונים - בחלק מה-APIs זה נקרא 'title' ובחלק 'text'
        title = latest.get('title') or latest.get('text', 'עדכון חמ"ל')
        content = latest.get('content') or latest.get('body', '')
        send_to_telegram(title, content)
    else:
        print("No news found.")
