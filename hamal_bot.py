import feedparser
import requests
import os
import re

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
    # שומרים 100 אחרונים
    list_history = list(history)[-100:]
    with open(HISTORY_FILE, 'w') as f:
        for link in list_history:
            f.write(f"{link}\n")

def send_telegram(token, chat_id, message):
    if not token or not chat_id: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True # מבטל את התמונה והטקסט הכפול
    }
    requests.post(url, json=payload, timeout=10)

def shorten_hamal_link(long_url):
    # מוציא את המספר הסידורי מסוף הלינק של חמ"ל
    match = re.search(r'-(\d+)$', long_url)
    if match:
        item_id = match.group(1)
        return f"https://hamal.co.il/main/{item_id}"
    return long_url

def run_news():
    history = get_history()
    new_found = False

    # --- WALLA ---
    walla_feed = feedparser.parse("https://rss.walla.co.il/feed/1")
    for entry in reversed(walla_feed.entries[:10]):
        if entry.link not in history:
            msg = f"<b>{entry.title}</b>\n\n{entry.link}"
            send_telegram(WALLA_TOKEN, WALLA_CHAT_ID, msg)
            history.add(entry.link)
            new_found = True

    # --- HAMAL ---
    hamal_feed = feedparser.parse("https://public-api.hamal.co.il/rss")
    for entry in reversed(hamal_feed.entries[:10]):
        if entry.link not in history:
            clean_title = re.sub(r'<[^>]+>', '', entry.title)
            short_link = shorten_hamal_link(entry.link)
            msg = f"<b>{clean_title}</b>\n\n{short_link}"
            send_telegram(HAMAL_TOKEN, HAMAL_CHAT_ID, msg)
            history.add(entry.link)
            new_found = True

    if new_found:
        save_history(history)

if __name__ == "__main__":
    run_news()
