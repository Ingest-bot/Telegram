import requests
import os

# משיכת משתנים מ-GitHub Secrets
TOKEN = os.environ.get('HAMAL_TELEGRAM_TOKEN') 
CHAT_ID = os.environ.get('HAMAL_CHAT_ID')

def send_test():
    print(f"Checking credentials...")
    print(f"Token exists: {bool(TOKEN)}")
    print(f"Chat ID: {CHAT_ID}")
    
    if not TOKEN or not CHAT_ID:
        print("Missing credentials!")
        return

    # הודעת בדיקה פשוטה
    msg = "🚀 בוט חמ\"ל: בדיקת חיבור ל-GitHub Actions הצליחה!"
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg}
    
    try:
        res = requests.post(url, json=payload)
        print(f"Telegram response: {res.status_code}")
        print(f"Response text: {res.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    send_test()
