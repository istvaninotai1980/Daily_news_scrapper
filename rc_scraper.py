import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

# Pontos repülőgép adok-veszek fórum URL (.132)
BASE_URL = "https://www.rc-network.de/forums/biete-flugmodelle.132/"
PAGES_TO_SCRAPE = 6
KEYWORDS = ["toy", "fw", "pilatus", "asg"]
SEEN_FILE = "seen_urls.txt"

SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD")
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL")

def load_seen_urls():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                return set(line.strip() for line in f if line.strip())
        except Exception as e:
            print(f"Hiba a seen_urls olvasásakor: {e}")
    return set()

def save_seen_urls(urls):
    try:
        with open(SEEN_FILE, "a", encoding="utf-8") as f:
            for url in urls:
                f.write(f"{url}\n")
    except Exception as e:
        print(f"Hiba a seen_urls mentésekor: {e}")

def fetch_and_parse():
    seen_urls = load_seen_urls()
    new_items = []
    current_run_urls = set()

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }

    for page in range(1, PAGES_TO_SCRAPE + 1):
        url = BASE_URL if page == 1 else f"{BASE_URL}page-{page}"
        print(f"Oldal feldolgozása: {url}")
        
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                print(f"Hiba az oldal letöltésekor ({page}. oldal): {response.status_code}")
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            # Kizárólag a hirdetések címeit és elsődleges linkjeit gyűjtjük ki
            thread_items = soup.select("div.structItem--thread div.structItem-title a[data-tp-primary='on']")

            for link_tag in thread_items:
                title = link_tag.text.strip()
                full_url = "https://www.rc-network.de" + link_tag['href']
                clean_url = full_url.split('/unread')[0].split('/page-')[0]

                if clean_url in seen_urls or clean_url in current_run_urls:
                    continue

                title_lower = title.lower()
                for kw in KEYWORDS:
                    if kw in title_lower:
                        new_items.append((title, clean_url))
                        current_run_urls.add(clean_url)
                        break
        except Exception as e:
            print(f"Hiba a(z) {page}. oldal feldolgozása során: {e}")

    return new_items, current_run_urls

def send_email(items):
    if not items:
        print("Nincs új hirdetés.")
        return

    subject = f"RC-Network: {len(items)} új repülőgép hirdetés"
    body = "Új hirdetések a Biete Flugmodelle (.132) fórumból:\n\n"
    for title, url in items:
        body += f"• {title}\n  Link: {url}\n\n"

    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("E-mail sikeresen elküldve!")
    except Exception as e:
        print(f"Hiba az e-mail küldésekor: {e}")

if __name__ == "__main__":
    matches, new_urls = fetch_and_parse()
    if matches:
        send_email(matches)
        save_seen_urls(new_urls)
