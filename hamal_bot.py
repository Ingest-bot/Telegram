import requests
import feedparser
import os

# משיכת משתנים מ-GitHub Secrets
TOKEN = os.environ.get('HAMAL_TELEGRAM_TOKEN') 
CHAT_ID = os.environ.get('HAMAL_CHAT_ID')

def get_hamal_news():
    # כתובת ה-RSS הרשמית של חמ"ל - הרבה יותר עמידה בפני חסימות
    url = "https://www.hamal.co.il/rss"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        print(f"Connecting to Hamal RSS: {url}")
        # מושכים את תוכן ה-RSS
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            # מפרקים את ה-RSS בעזרת feedparser
            feed = feedparser.parse(response.content)
            items = feed.entries
            print(f"Successfully found {len(items)} items.")
            return items
        else:
            print(f"Failed to fetch RSS. Status: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"Error during fetching: {e}")
        return []

def send_to_telegram(title, link, description):
    if not TOKEN or not CHAT_ID:
        print("Missing Telegram Credentials")
        return

    # ניקוי תגיות HTML בסיסי אם יש
    clean_desc = description.split('<')[0] if '<' in description else description
    
    # עיצוב ההודעה
    msg = f"<b>{title}</b>\n\n{clean_desc}\n\n<a href='{link}'>לידיעה המלאה בחמ\"ל</a>"
    
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    
    try:
        res = requests.post(url, json=payload)
        if res.status_code == 200:
            print("Message sent to Telegram!")
        else:
            print(f"Telegram error: {res.text}")
    except Exception as e:
        print(f"Failed to send: {e}")

if __name__ == "__main__":
    print("--- Hamal RSS Bot Started ---")
    news_items = get_hamal_news()
    
    if news_items:
        # לוקחים את הידיעה הכי חדשה
        latest = news_items[0]
        
        # ב-RSS השדות נקראים title, link, summary
        title = latest.get('title', 'עדכון חמ"ל')
        link = latest.get('link', 'https://www.hamal.co.il')
        description = latest.get('summary', '')
        
        send_to_telegram(title, link, description)
    else:
        print("No news found.")
    
    print("--- Process Finished ---")
