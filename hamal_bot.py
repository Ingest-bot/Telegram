import requests
import os

# משיכת משתנים מ-GitHub Secrets
TOKEN = os.environ.get('HAMAL_TELEGRAM_TOKEN') 
CHAT_ID = os.environ.get('HAMAL_CHAT_ID')

def get_hamal_news():
    # כתובת ה-Endpoint הישירה של הפיד הראשי
    url = "https://public-api.hamal.co.il/feed/main"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.hamal.co.il",
        "Referer": "https://www.hamal.co.il/"
    }
    
    params = {"limit": 5}
    
    try:
        print(f"Connecting to: {url}")
        response = requests.get(url, headers=headers, params=params, timeout=15)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # חמ"ל מחזירים אובייקט שבתוכו יש 'feed' ובתוכו 'items'
            # אנחנו בודקים את כל האפשרויות כדי שלא נפספס
            items = []
            if 'feed' in data and 'items' in data['feed']:
                items = data['feed']['items']
            elif 'items' in data:
                items = data['items']
            elif isinstance(data, list):
                items = data
                
            print(f"Successfully found {len(items)} items.")
            return items
        else:
            print(f"Failed. Response: {response.text[:150]}")
            return []
            
    except Exception as e:
        print(f"Error during fetching: {e}")
        return []

def send_to_telegram(title, content):
    if not TOKEN or not CHAT_ID:
        print("Missing Telegram Credentials (TOKEN or CHAT_ID)")
        return

    # ניקוי תגיות HTML אם יש בתוכן כדי למנוע שגיאות בטלגרם
    msg = f"<b>{title}</b>\n\n{content}"
    
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "HTML"
    }
    
    try:
        res = requests.post(url, json=payload)
        if res.status_code == 200:
            print("Message sent to Telegram successfully!")
        else:
            print(f"Telegram error: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"Failed to send to Telegram: {e}")

if __name__ == "__main__":
    print("--- Hamal Bot Started ---")
    news_items = get_hamal_news()
    
    if news_items:
        # לקיחת הידיעה הראשונה (הכי חדשה)
        latest = news_items[0]
        
        # חילוץ כותרת ותוכן
        title = latest.get('title') or latest.get('text', 'עדכון חמ"ל')
        content = latest.get('content') or latest.get('body', '')
        
        # אם יש קישור לתמונה, אפשר להוסיף אותו בעתיד, כרגע שולחים טקסט
        send_to_
