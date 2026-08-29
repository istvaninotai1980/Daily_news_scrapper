import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

# --- BEÁLLÍTÁSOK ---
BASE_URL = "https://www.rc-network.de/forums/biete-flugmodelle.62/"
PAGES_TO_SCRAPE = 6  # Az első 6 oldal átfésülése

# Kulcsszavak (kisbetűsítve a pontos egyezéshez)
KEYWORDS = ["toy", "fw", "pilatus", "asg"]

# E-mail beállítások (GitHub Secrets-ből)
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD")
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL")

def fetch_and_parse():
    found_items = []
    seen_urls = set()  # Duplikációk kiszűrésére
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }

    # Első 6 oldal bejárása (page-1, page-2, ...)
    for page in range(1, PAGES_TO_SCRAPE + 1):
        url = BASE_URL if page == 1 else f"{BASE_URL}page-{page}"
        print(f"Oldal feldolgozása: {url}")
        
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"Hiba az oldal letöltésekor ({page}. oldal): {response.status_code}")
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        threads = soup.find_all("div", class_="structItem-title")

        for thread in threads:
            link_tag = thread.find("a", href=True)
            if link_tag:
                title = link_tag.text.strip()
                full_url = "https://www.rc-network.de" + link_tag['href']
                
                # Ellenőrizzük, hogy láttuk-e már ezt a hirdetést
                if full_url in seen_urls:
                    continue

                # Keresés a kulcsszavak között
                title_lower = title.lower()
                for kw in KEYWORDS:
                    if kw in title_lower:
                        found_items.append((title, full_url))
                        seen_urls.add(full_url)  # Elmentjük, hogy többször ne kerüljön be
                        break

    return found_items

def send_email(items):
    if not items:
        print("Nincs új találat, e-mail nem kerül kiküldésre.")
        return

    subject = f"RC-Network Riasztás: {len(items)} találat az első {PAGES_TO_SCRAPE} oldalon"
    
    body = f"A következő hirdetéseket találtam a megadott kulcsszavak alapján (Toy, FW, Pilatus, ASG):\n\n"
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
        print(f"Hiba az e-mail küldése során: {e}")

if __name__ == "__main__":
    matches = fetch_and_parse()
    send_email(matches)
