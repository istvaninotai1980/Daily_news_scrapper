import os
import smtplib
import urllib.request
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import feedparser

# --- 1. CONFIG: HÍROLDALAK (RSS FEEDS) ---
RSS_FEEDS = [
    "https://telex.hu/rss",
    "https://hvg.hu/rss"
]

# --- 2. CONFIG: HIRDETÉSFIGYELŐ ---
KEYWORD = "laptop"  # Cseréld ki arra a kulcsszóra, amit keresel!
AD_URL = "https://www.jofogas.hu/magyarorszag?q=" + KEYWORD

def get_news():
    """Hírek gyűjtése RSS csatornákból"""
    news_items = []
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        source = feed.feed.get('title', 'Hírek')
        # Az legfrissebb 3 cikket vesszük ki forrásonként
        for entry in feed.entries[:3]:
            news_items.append(f"<li><b>[{source}]</b> <a href='{entry.link}'>{entry.title}</a></li>")
    return "".join(news_items)

def check_advertisements():
    """Kulcsszó keresése egy megadott hirdetési oldalon"""
    try:
        req = urllib.request.Request(AD_URL, headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req).read().decode('utf-8')
        
        # Egyszerű kulcsszó ellenőrzés az oldalon
        if re.search(r'\b' + re.escape(KEYWORD) + r'\b', html, re.IGNORECASE):
            return f"<p>Találat a(z) <b>'{KEYWORD}'</b> kulcsszóra ezen az oldalon: <a href='{AD_URL}'>Megtekintés</a></p>"
        else:
            return f"<p>A(z) '{KEYWORD}' kulcsszóra jelenleg nincs új kiemelt találat.</p>"
    except Exception as e:
        return f"<p>Nem sikerült lekérni a hirdetési oldalt: {e}</p>"

def send_email(content):
    """HTML E-mail küldése Gmail SMTP-n keresztül"""
    sender = os.environ.get("SENDER_EMAIL")
    password = os.environ.get("SENDER_PASSWORD")
    receiver = os.environ.get("RECEIVER_EMAIL")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Napi Hír- és Hirdetésösszefoglaló"
    msg["From"] = sender
    msg["To"] = receiver

    html_body = f"""
    <html>
      <body>
        <h2>Napi Hírek</h2>
        <ul>
          {content['news']}
        </ul>
        <hr>
        <h2>Hirdetésfigyelő</h2>
        {content['ads']}
      </body>
    </html>
    """
    
    msg.attach(MIMEText(html_body, "html"))

    # SMTP Kapcsolat
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, receiver, msg.as_string())
    print("E-mail sikeresen elküldve!")

if __name__ == "__main__":
    news_content = get_news()
    ads_content = check_advertisements()
    
    email_data = {
        "news": news_content,
        "ads": ads_content
    }
    
    send_email(email_data)
