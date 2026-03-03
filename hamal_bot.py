import requests
import os

# --- תיקון חשוב כאן ---
# אנחנו אומרים לפייתון: "לך ל-GitHub ותביא את מה ששמור תחת השם הזה"
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
            # מוודאים שאנחנו מושכים את רשימת הפריטים הנכונה
            items = data.get('feed', {}).get('items', [])
            return items
    except Exception as e:
        print(f"Error fetching Hamal: {e}")
    return []

def send_to_telegram(title, content):
    # בדיקה שהמשתנים לא ריקים
    if not TOKEN or not CHAT_ID:
        print("Error: TOKEN or CHAT_ID is missing!")
        return

    msg = f"<b>{title}</b>\n\n{content}"
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
    
    try:
        res = requests.post(url, json=payload)
        print(f"Telegram response: {res.status_code}")
    except Exception as e:
        print(f"Error sending to Telegram: {e}")

if __name__ == "__main__":
    news_items = get_hamal_news()
    if news_items:
        # לוקח את האייטם הכי חדש (הראשון ברשימה)
        latest = news_items[0]
        title = latest.get('title', 'עדכון חמ"ל')
        content = latest.get('content', '')
        
        send_to_telegram(title, content)
        print("Process finished!")
    else:
        print("No news items found.")
