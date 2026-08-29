import os
import re
import smtplib
import urllib.request
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIG ---
URL = "https://www.rc-network.de/forums/biete-flugmodelle.132/"
KEYWORDS = ["ccm toy", "toy", "f5d", "fw", "funcub", "funcup", "pilatus", "asg"]

def extract_thread_id(href):
    """Kinyeri a tiszta numerikus ID-t a XenForo URL-ből (pl. .12133992/ -> 12133992)"""
    match = re.search(r'\.(\d+)/?$', href)
    if match:
        return match.group(1)
    return None

def get_forum_threads():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7'
    }
    req = urllib.request.Request(URL, headers=headers)
    
    with urllib.request.urlopen(req) as response:
        html = response.read().decode('utf-8')
        
    soup = BeautifulSoup(html, 'html.parser')
    
    threads = []
    for title_tag in soup.find_all('div', class_='structItem-title'):
        a_tag = title_tag.find('a', href=True)
        if a_tag:
            href = a_tag['href']
            thread_id = extract_thread_id(href)
            if thread_id:
                thread_title = a_tag.text.strip()
                thread_url = "https://www.rc-network.de" + href if not href.startswith("http") else href
                threads.append({'id': thread_id, 'title': thread_title, 'url': thread_url})
    return threads

def send_alert(matches):
    sender = os.environ.get("SENDER_EMAIL")
    password = os.environ.get("SENDER_PASSWORD")
    receiver = os.environ.get("RECEIVER_EMAIL")

    if not sender or not password or not receiver:
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🚨 RC-Network HIRDETÉS RIASZTÁS ({len(matches)} találat az 1. oldalon)"
    msg["From"] = sender
    msg["To"] = receiver

    items_html = "".join([f"<li><a href='{m['url']}'><b>{m['title']}</b></a></li>" for m in matches])

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif;">
        <h2 style="color: #d9534f;">Aktuális találatok az RC-Network apróhirdetések között!</h2>
        <p>A(z) <b>{', '.join(KEYWORDS)}</b> kulcsszavak alapján az alábbi hirdetés(ek) szerepelnek a fórum 1. oldalán:</p>
        <ul>
          {items_html}
        </ul>
      </body>
    </html>
    """
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, receiver, msg.as_string())

if __name__ == "__main__":
    try:
        threads = get_forum_threads()
        if not threads:
            exit()

        keywords_lower = [kw.lower() for kw in KEYWORDS]
        matches = []

        # Végigmegyünk az 1. oldal összes hirdetésén, és kigyűjtjük az összes találatot
        for thread in threads:
            title_lower = thread['title'].lower()
            if any(kw in title_lower for kw in keywords_lower):
                matches.append(thread)

        # Ha van legalább egy meccselő hirdetés a címlapon, elküldjük a levelet
        if matches:
            send_alert(matches)

    except Exception as e:
        print(f"Hiba az ellenőrzés során: {e}")
