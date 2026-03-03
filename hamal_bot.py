import feedparser
import requests
import os
import re
import time

# Secrets מ-GitHub
WALLA_TOKEN = os.environ.get('TELEGRAM_TOKEN')
WALLA_CHAT_ID = os.environ.get('CHAT_ID')
HAMAL_TOKEN = os.environ.get('HAMAL_TELEGRAM_TOKEN')
HAMAL_CHAT_ID = os.environ.get('HAMAL_CHAT_ID')

HISTORY_FILE = "last_links.txt"

def get_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_history(history):
    # שומרים את 100 הקישורים האחרונים
    list_history = list(history)[-100:]
    with open(HISTORY_FILE, 'w') as f:
        for link in list_history:
            f.write(f"{link}\n")

def get_short_url(long_url):
    """מקצר את הלינק רק עבור חמ"ל באמצעות TinyURL"""
    try:
        api_url = f"http://tinyurl.com/api-create.php?url={long_url}"
        response = requests.get(api_url, timeout=10)
        if response.status_code == 200:
            return response.text.replace("http://", "https://")
    except Exception as e:
        print(f"Error shortening URL: {e}")
    return long_url

def send_telegram(token, chat_id, message):
    if not token or not chat_id: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True # מבטל תצוגת תמונה וטקסט
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

def run_news():
    history = get_history()
    new_found = False

    # --- וואלה (בלי קיצור לינק) ---
    try:
        walla_feed = feedparser.parse("https://rss.walla.co.il/feed/1")
        for entry in reversed(walla_feed.entries[:10]):
            if entry.link not in history:
                # כאן הלינק נשאר מקורי
                msg = f"<b>{entry.title}</b>\n\n{entry.link}"
                send_telegram(WALLA_TOKEN, WALLA_CHAT_ID, msg)
                history.add(entry.link)
                new_found = True
                time.sleep(1)
    except Exception as e:
        print(f"Walla error: {e}")

    # --- חמ"ל (עם קיצור לינק) ---
    try:
        hamal_feed = feedparser.parse("https://public-api.hamal.co.il/rss")
        for entry in reversed(hamal_feed.entries[:10]):
            if entry.link not in history:
                clean_title = re.sub(r'<[^>]+>', '', entry.title)
                # כאן מופעל הקיצור של TinyURL
                short_link = get_short_url(entry.link)
                
                msg = f"<b>{clean_title}</b>\n\n{short_link}"
                send_telegram(HAMAL_TOKEN, HAMAL_CHAT_ID, msg)
                history.add(entry.link)
                new_found = True
                time.sleep(1)
    except Exception as e:
        print(f"Hamal error: {e}")

    if new_found:
        save_history(history)

if __name__ == "__main__":
    run_news()
