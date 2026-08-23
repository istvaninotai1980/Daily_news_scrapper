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
    """Az RC-Network fórum legfrissebb témáinak beolvasása"""
    req = urllib.request.Request(
        URL, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    )
    html = urllib.request.urlopen(req).read().decode('utf-8')
    soup = BeautifulSoup(html, 'html.parser')
    
    threads = []
    # A XenForo fórum szerkezetének megfelelő címek kiválasztása
    for title_tag in soup.find_all('div', class_='structItem-title'):
        a_tag = title_tag.find('a', href=True)
        if a_tag:
            thread_title = a_tag.text.strip()
            thread_url = "https://www.rc-network.de" + a_tag['href']
            # ID kinyerése az URL-ből a duplikációk elkerülésére
            thread_id = a_tag['href'].split('.')[-1].replace('/', '')
            threads.append({'id': thread_id, 'title': thread_title, 'url': thread_url})
    return threads

def load_last_seen():
    """Az utoljára értesített hirdetés ID-jának betöltése"""
    if os.path.exists(LAST_SEEN_FILE):
        with open(LAST_SEEN_FILE, 'r') as f:
            return f.read().strip()
    return ""

def save_last_seen(thread_id):
    """Az új legfrissebb hirdetés ID-jának elmentése"""
    with open(LAST_SEEN_FILE, 'w') as f:
        f.write(thread_id)

def send_alert(matches):
    """E-mail riasztás küldése találat esetén"""
    sender = os.environ.get("SENDER_EMAIL")
    password = os.environ.get("SENDER_PASSWORD")
    receiver = os.environ.get("RECEIVER_EMAIL")

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
        new_last_seen = last_seen

        for thread in threads:
            if thread['id'] == last_seen:
                break  # Elértük a legutóbb vizsgált hirdetést
            
            title_lower = thread['title'].lower()
            if any(kw in title_lower for kw in KEYWORDS):
                matches.append(thread)
            
            if not new_last_seen and threads:
                new_last_seen = threads[0]['id']

        if matches:
            send_alert(matches)
            save_last_seen(threads[0]['id'])
        elif threads and not last_seen:
            # Első lefutáskor elmentjük a legfrissebbet viszonyítási alapnak
            save_last_seen(threads[0]['id'])

    except Exception as e:
        print(f"Hiba a hirdetések ellenőrzésekor: {e}")
