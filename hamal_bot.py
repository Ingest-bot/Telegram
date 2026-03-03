import requests
import os

# שליחת המשתנים מה-GitHub Secrets
TOKEN = os.environ.get('HAMAL_TELEGRAM_TOKEN') 
CHAT_ID = os.environ.get('HAMAL_CHAT_ID')

def get_hamal_news():
    url = "https://public-api.hamal.co.il/feed/main?limit=5"
    
    # Headers משופרים כדי לדמות דפדפן אמיתי ולמנוע חסימה
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.hamal.co.il/",
        "Origin": "https://www.hamal.co.il",
        "Cache-Control": "no-cache"
    }
    
    try:
        print("Starting request to Hamal API...")
        response = requests.get(url, headers=headers, timeout=15)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            # שליפת רשימת הידיעות מתוך המבנה של חמ"ל
            feed = data.get('feed', {})
            items = feed.get('items', [])
            
            if not items:
                print("Warning: Received JSON but 'items' list is empty.")
                return []
                
            print(f"Successfully found {len(items)} items.")
            return items
        else:
            print(f"Failed to fetch data. Status: {response.status_code}")
            print(f"Response snippet: {response.text[:200]}")
            return []
            
    except Exception as e:
        print(f"An error occurred during API call: {e}")
        return []

def send_to_telegram(title, content):
    if not TOKEN or not CHAT_ID:
        print("CRITICAL ERROR: Telegram Token or Chat ID is missing in environment variables!")
        return

    # עיצוב ההודעה (HTML)
    msg = f"<b>{title}</b>\n\n{content}"
    
    telegram_url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "HTML"
    }
    
    try:
        res = requests.post(telegram_url, json=payload)
        if res.status_code == 200:
            print("Message sent successfully to Telegram!")
        else:
            print(f"Telegram API Error: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")

if __name__ == "__main__":
    print("--- Hamal Bot Started ---")
    
    # שלב 1: משיכת ידיעות
    news_items = get_hamal_news()
    
    if news_items:
        # שלב 2: לקיחת הידיעה הכי חדשה (הראשונה)
        latest = news_items[0]
        
        # חילוץ כותרת ותוכן (עם הגנה אם חסר)
        title = latest.get('title', 'עדכון מחמ"ל')
        content = latest.get('content', '')
        
        # שלב 3: שליחה לטלגרם
        send_to_telegram(title, content)
    else:
        print("No news items to process.")
        
    print("--- Process Finished ---")
