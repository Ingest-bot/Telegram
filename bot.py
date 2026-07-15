import feedparser
import asyncio
import os
import re
import requests
import time
from datetime import datetime, timedelta
from telegram import Bot

# --- הגדרות ---
WALLA_FEEDS = {
    "מבזקים": "https://rss.walla.co.il/feed/22",
    "חדשות": "https://rss.walla.co.il/feed/1?type=main",
    "כסף": "https://rss.walla.co.il/feed/2",
    "טכנולוגיה": "https://rss.walla.co.il/feed/6"
}
HAMAL_RSS = "https://public-api.hamal.co.il/rss"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
HAMAL_TOKEN = os.getenv("HAMAL_TELEGRAM_TOKEN")
HAMAL_CHAT_ID = os.getenv("HAMAL_CHAT_ID")

LAST_LINKS_FILE = "last_links.txt"
MAX_LINKS_TO_KEEP = 500
MAX_ITEMS_PER_FETCH = 5  # הגבלה ל-5 אייטמים אחרונים בכל בדיקה
MAX_AGE_HOURS = 12       # לא לשלוח אייטמים ישנים יותר מ-12 שעות

RLE = "\u202B" 
PDF = "\u202C" 
RLM = "\u200f"

# --- פונקציות עזר ---

def is_too_old(entry):
    """בודק אם האייטם ישן מדי מכדי להישלח"""
    try:
        published_struct = entry.get('published_parsed') or entry.get('updated_parsed')
        if not published_struct: return False
        
        published_time = datetime.fromtimestamp(time.mktime(published_struct))
        if published_time < datetime.now() - timedelta(hours=MAX_AGE_HOURS):
            return True
    except: pass
    return False

def clean_url(url):
    return url.split('?')[0].split('#')[0].strip()

def _try_isgd(long_url):
    encoded_url = requests.utils.quote(long_url, safe='')
    api_url = f"https://is.gd/create.php?format=simple&url={encoded_url}"
    r = requests.get(api_url, timeout=5)
    text = r.text.strip()
    if r.status_code == 200 and text and not text.startswith("Error") and text.startswith("http"):
        return text
    raise ValueError(f"is.gd: {text}")

def _try_vgd(long_url):
    # v.gd הוא אותו שירות/צוות כמו is.gd, אבל תשתית נפרדת - גיבוי טוב
    encoded_url = requests.utils.quote(long_url, safe='')
    api_url = f"https://v.gd/create.php?format=simple&url={encoded_url}"
    r = requests.get(api_url, timeout=5)
    text = r.text.strip()
    if r.status_code == 200 and text and not text.startswith("Error") and text.startswith("http"):
        return text
    raise ValueError(f"v.gd: {text}")

def _try_dagd(long_url):
    # da.gd - שירות מינימלי שמיועד ל-API, בלי מסכי ביניים/פרסומות
    encoded_url = requests.utils.quote(long_url, safe='')
    api_url = f"https://da.gd/shorten?url={encoded_url}"
    r = requests.get(api_url, timeout=5)
    text = r.text.strip()
    if r.status_code == 200 and text.startswith("http"):
        return text
    raise ValueError(f"da.gd: {text}")

def _try_cleanuri(long_url):
    # cleanuri.com - הפניה ישירה (301), בלי מסך ביניים/אזהרה
    r = requests.post(
        "https://cleanuri.com/api/v1/shorten",
        json={"url": long_url},
        timeout=5,
    )
    data = r.json()
    if r.status_code == 200 and data.get("result_url", "").startswith("http"):
        return data["result_url"]
    raise ValueError(f"cleanuri: {data}")

def _verify_short_url(short_url, original_url):
    """
    מוודא שהקישור המקוצר באמת מפנה ליעד המקורי.
    חלק מהשירותים (בעיקר cleanuri) מזהים לפעמים לא נכון URL-ים עם
    תווים בעברית מקודדים (%D7%9B וכו') ומייצרים הפניה שבורה
    (למשל מוחקים לגמרי את קטע העברית ומשאירים רק מקפים) -
    מה שמוביל בסוף לעמוד שגיאה. הבדיקה כאן תופסת מקרה כזה
    ותגרום לקוד לנסות את המקצר הבא, ובסוף - אם כולם נכשלים -
    לשלוח את הקישור המקורי המלא, שתמיד עובד.
    """
    try:
        r = requests.get(short_url, allow_redirects=True, timeout=6, stream=True)
        r.close()
        resolved = clean_url(r.url)
        if resolved != clean_url(original_url):
            raise ValueError(f"redirect mismatch: got '{resolved}', expected '{original_url}'")
    except requests.RequestException as e:
        raise ValueError(f"verification request failed: {e}")

def get_short_url(long_url):
    # cleanuri ראשון - הפניה ישירה בלי מסך ביניים, נראה שהיחיד שעובד כרגע
    shorteners = (_try_cleanuri, _try_dagd, _try_isgd, _try_vgd)
    for shortener in shorteners:
        try:
            short_url = shortener(long_url)
            _verify_short_url(short_url, long_url)
            return short_url
        except Exception as e:
            print(f"get_short_url [{shortener.__name__}] failed for {long_url}: {e}")
    return long_url

def upgrade_image_quality(url):
    if not url: return url
    return re.sub(r'w=\d+', 'w=1200', url).replace("/re-size/", "/").replace("/w/400/", "/w/1200/")

def clean_image_url(url):
    """מנרמל URL של תמונה לצורך השוואה (מוריד פרמטרים כמו גודל/timestamp)"""
    if not url: return url
    return url.split('?')[0].split('#')[0].strip()

def get_feed_default_image(feed):
    """התמונה ברמת הערוץ (הלוגו הכללי של הפיד), אם קיימת"""
    try:
        img = feed.feed.get('image', {})
        if isinstance(img, dict):
            return clean_image_url(img.get('href') or img.get('url'))
    except Exception:
        pass
    return None

def extract_image(entry, feed_default_image=None):
    image_url = None
    if 'media_content' in entry: image_url = entry.media_content[0]['url']
    elif 'links' in entry:
        for link in entry.links:
            if 'image' in link.get('type', ''):
                image_url = link.get('href'); break
    if not image_url and 'enclosure' in entry:
        image_url = entry.enclosure.get('url')

    if not image_url:
        return None

    print(f"DEBUG image url for '{entry.get('title', '')[:40]}': {image_url}")

    # אם התמונה זהה ללוגו הכללי של הפיד - זה לא תמונה אמיתית של הכתבה, נתעלם ממנה
    if feed_default_image and clean_image_url(image_url) == feed_default_image:
        print(f"  -> matches feed default/logo image, skipping")
        return None

    return upgrade_image_quality(image_url)

def get_history():
    links = []
    if os.path.exists(LAST_LINKS_FILE):
        with open(LAST_LINKS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # תאימות לאחור: מדלג על שורת COUNTER ישנה מגרסאות קודמות
                if line and not line.startswith("COUNTER:"):
                    links.append(line)
    return links

def save_history(links_list):
    recent_links = links_list[-MAX_LINKS_TO_KEEP:]
    with open(LAST_LINKS_FILE, "w", encoding="utf-8") as f:
        for link in recent_links:
            f.write(f"{link}\n")

# --- עיבוד וואלה ---
async def process_walla(bot, seen_links_set, links_list):
    for category, base_url in WALLA_FEEDS.items():
        url = f"{base_url}?t={int(time.time())}"
        feed = feedparser.parse(url)
        
        if not feed.entries:
            continue

        feed_default_image = get_feed_default_image(feed)
            
        # לוקח רק את 5 האייטמים הראשונים בפיד
        latest_entries = feed.entries[:MAX_ITEMS_PER_FETCH]
        
        # מסנן מה שכבר ראינו ומה שישן מדי
        new_entries = [
            e for e in latest_entries 
            if clean_url(e.link) not in seen_links_set and not is_too_old(e)
        ]
        
        for entry in reversed(new_entries):
            is_mivzak = (category == "מבזקים")
            cleaned_link = clean_url(entry.link)
            
            prefix = "🚨 " if is_mivzak else ""
            link_html = f'<a href="{cleaned_link}">📖 לכתבה המלאה</a>'
            caption = f"{RLE}{RLM}<b>{prefix}{entry.title}</b>{PDF}\n\n{link_html}"
            
            try:
                if is_mivzak:
                    await bot.send_message(
                        chat_id=CHAT_ID, 
                        text=caption, 
                        parse_mode='HTML', 
                        disable_web_page_preview=True
                    )
                else:
                    image = extract_image(entry, feed_default_image)
                    if image:
                        await bot.send_photo(chat_id=CHAT_ID, photo=image, caption=caption, parse_mode='HTML')
                    else:
                        await bot.send_message(chat_id=CHAT_ID, text=caption, parse_mode='HTML', disable_web_page_preview=False)
                
                seen_links_set.add(cleaned_link)
                links_list.append(cleaned_link)
                await asyncio.sleep(0.5)
            except Exception as e: 
                print(f"Walla Error in {category}: {e}")
            
    return links_list

# --- עיבוד חמ"ל ---
async def process_hamal(seen_links_set, links_list):
    if not HAMAL_TOKEN or not HAMAL_CHAT_ID: return links_list
    
    hamal_bot = Bot(token=HAMAL_TOKEN)
    async with hamal_bot:
        url = f"{HAMAL_RSS}?t={int(time.time())}"
        feed = feedparser.parse(url)

        feed_default_image = get_feed_default_image(feed)
        
        # לוקח רק את 5 האייטמים הראשונים בפיד
        latest_entries = feed.entries[:MAX_ITEMS_PER_FETCH]
        
        new_entries = [
            e for e in latest_entries 
            if clean_url(e.link) not in seen_links_set and not is_too_old(e)
        ]
        
        for entry in reversed(new_entries):
            cleaned_link = clean_url(entry.link)
            # לא משתמשים יותר בשירותי קיצור חיצוניים (cleanuri/is.gd/v.gd/da.gd) -
            # הם הוכיחו שהם לא אמינים (חלקם מובילים לפרסומות/ספאם, חלקם לא זמינים,
            # ואצל אחד מהם קישורים עם עברית בנתיב נשברו ולא הובילו ליעד הנכון).
            # הקישור המקורי המלא תמיד עובד, ומכיוון שהוא מוצג כהיפרלינק מוסתר
            # (טקסט קליק במקום ה-URL עצמו), האורך שלו כבר לא משנה בכלל.
            
            raw_title = re.sub(r'<[^>]+>', '', entry.title)
            clean_title = re.sub(r'^חמ"?ל\s*[-:]?\s*חדשות\s*מתפרצות\s*[-:]?\s*', '', raw_title).strip()
            clean_title = clean_title.lstrip(" :")
            
            link_html = f'<a href="{cleaned_link}">📖 לכתבה המלאה</a>'
            message = f"{RLE}{RLM}<b>{clean_title}</b>{PDF}\n\n{link_html}"
            
            try:
                image = extract_image(entry, feed_default_image)
                if image:
                    try:
                        await hamal_bot.send_photo(chat_id=HAMAL_CHAT_ID, photo=image, caption=message, parse_mode='HTML')
                    except Exception as photo_err:
                        print(f"Hamal photo failed ({photo_err}), falling back to text")
                        await hamal_bot.send_message(chat_id=HAMAL_CHAT_ID, text=message, parse_mode='HTML', disable_web_page_preview=True)
                else:
                    await hamal_bot.send_message(chat_id=HAMAL_CHAT_ID, text=message, parse_mode='HTML', disable_web_page_preview=True)
                seen_links_set.add(cleaned_link)
                links_list.append(cleaned_link)
                
                await asyncio.sleep(0.5)
            except Exception as e: print(f"Hamal Error: {e}")
            
    return links_list

async def main():
    if not TELEGRAM_TOKEN or not CHAT_ID: return
    links_list = get_history()
    seen_links_set = {clean_url(l) for l in links_list}

    bot = Bot(token=TELEGRAM_TOKEN)
    async with bot:
        links_list = await process_walla(bot, seen_links_set, links_list)
        links_list = await process_hamal(seen_links_set, links_list)

    save_history(links_list)

if __name__ == "__main__":
    asyncio.run(main())
