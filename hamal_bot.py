import requests
import feedparser
import os

# משיכת משתנים מ-GitHub Secrets
TOKEN = os.environ.get('HAMAL_TELEGRAM_TOKEN') 
CHAT_ID = os.environ.get('HAMAL_CHAT_ID')

def get_hamal_news():
    # כתובת ה-RSS הרשמית של חמ"ל
    url = "https://www.hamal.co.il/rss"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            feed = feedparser.parse(response.content)
            return feed.entries
    except Exception as e:
        print(f"Error fetching RSS: {e}")
    return []

def send_to_telegram(title, summary, link):
    # ניקוי קצר של התוכן (חמ"ל לפעמים מוסיפים תגיות HTML ב-RSS)
    clean_summary = summary.split('<')[0] if '<' in summary else summary
    
    msg = f"<b>{title}</b>\n\n{clean_summary}\n\n<a href='{link}'>לידיעה המלאה בחמ\"ל</a>"
    
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "HTML"
    }
    requests.post(url, json=payload)

if __name__ == "__main__":
    print("Fetching news...")
    items = get_hamal_news()
    
    if items:
        # לוקח את הידיעה הכי חדשה
        latest = items[0]
        send_to_telegram(latest.title, latest.summary, latest.link)
        print("Success! News sent to Telegram.")
    else:
        print("No news found.")
