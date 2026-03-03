import requests
import os

# ב-GitHub נשתמש ב-Secrets, במחשב זה ימשוך ריק אלא אם תגדיר
TOKEN = os.environ.get('8300619828:AAEskXCl21-7bEYaLaT9c4f97mlDytPahDc') 
CHAT_ID = os.environ.get('-1001278471006')

def get_hamal_news():
    url = "https://public-api.hamal.co.il/feed/main?limit=5"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            items = data.get('feed', {}).get('items', [])
            return items
    except Exception as e:
        print(f"Error fetching Hamal: {e}")
    return []

def send_to_telegram(title, content):
    msg = f"<b>{title}</b>\n\n{content}"
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
    requests.post(url, json=payload)

if __name__ == "__main__":
    news_items = get_hamal_news()
    if news_items:
        # לצורך הבדיקה הראשונית - שולח רק את האייטם הכי חדש
        latest = news_items[0]
        send_to_telegram(latest.get('title'), latest.get('content'))
        print("Sent latest news to Telegram!")
