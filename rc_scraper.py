import os
import smtplib
import urllib.request
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIG ---
URL = "https://www.rc-network.de/forums/biete-flugmodelle.132/"
KEYWORDS = ["ccm toy", "toy"]
LAST_SEEN_FILE = "last_seen_id.txt"

def get_forum_threads():
    """Az RC-Network fórum legfrissebb témáinak beolvasása fejlett fejlécekkel"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
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
            thread_title = a_tag.text.strip()
            thread_url = "https://www.rc-network.de" + a_tag['href']
            thread_id = a_tag['href'].split('.')[-1].replace('/', '')
            threads.append({'id': thread_id, 'title': thread_title, 'url': thread_url})
    return threads

def load_last_seen():
    if os.path.exists(LAST_SEEN_FILE):
        try:
            with open(LAST_SEEN_FILE, 'r') as f:
                return f.read().strip()
        except Exception:
            return ""
    return ""

def save_last_seen(thread_id):
    try:
        with open(LAST_SEEN_FILE, 'w') as f:
            f.write(str(thread_id))
    except Exception as e:
        print(f"Nem sikerült menteni a statuszt: {e}")

def send_alert(matches):
    sender = os.environ.get("SENDER_EMAIL")
    password = os.environ.get("SENDER_PASSWORD")
    receiver = os.environ.get("RECEIVER_EMAIL")

    if not sender or not password or not receiver:
        print("Hiányzó e-mail környezeti változók!")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🚨 RC-Network HIRDETÉS RIASZTÁS: {matches[0]['title']}"
    msg["From"] = sender
    msg["To"] = receiver

    items_html = "".join([f"<li><a href='{m['url']}'><b>{m['title']}</b></a></li>" for m in matches])

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif;">
        <h2 style="color: #d9534f;">Új találat az RC-Network apróhirdetések között!</h2>
        <p>A(z) <b>{', '.join(KEYWORDS)}</b> kulcsszavak alapján az alábbi új hirdetés(ek) jelentek meg:</p>
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
        last_seen = load_last_seen()
        
        matches = []
        
        for thread in threads:
            if thread['id'] == last_seen:
                break
            
            title_lower = thread['title'].lower()
            if any(kw in title_lower for kw in KEYWORDS):
                matches.append(thread)

        if matches:
            send_alert(matches)
            save_last_seen(threads[0]['id'])
        elif threads:
            save_last_seen(threads[0]['id'])

    except Exception as e:
        print(f"Hiba a hirdetések ellenőrzésekor: {e}")
