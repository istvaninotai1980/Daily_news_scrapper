import os
import smtplib
import datetime
import requests
import feedparser
import yfinance as yf
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIG: RÉSZVÉNYEK (Tickerek) ---
STOCKS = {
    "Amazon (AMZ)": "AMZN",
    "Defence ETF (ARMY)": "ARMY.PA",
    "Copper ETF (COPG)": "COPG.L",
    "Constellation Software (CSU)": "CSU.TO",
    "Global Growth ETF (GGRW)": "GGRW.L",
    "Physical Silver (ISLN)": "ISLN.L",
    "Microsoft (MSF)": "MSFT",
    "OTP Bank (OTP)": "OTP.BU",
    "S&P 500 Info Tech (QDV5)": "QDV5.DE",
    "TSMC (TSM)": "TSM",
    "S&P 500 ETF (VUSA)": "VUSA.L"
}

# --- CONFIG: RSS FORRÁSOK ---
FEEDS = {
    "Telex": "https://telex.hu/rss",
    "Index": "https://index.hu/24ora/rss/",
    "M4 Sport": "https://m4sport.hu/feed/",
    "Nemzeti Sport": "https://www.nemzetisport.hu/rss"
}

def get_stock_trends():
    """Részvények napi, heti és havi teljesítményének lekérése"""
    html = "<h3>Tőzsdei Portfólió Trendek</h3><table border='1' cellpadding='5' style='border-collapse:collapse; width:100%;'>"
    html += "<tr style='background-color:#f2f2f2;'><th>Eszköz</th><th>Ár</th><th>Napi %</th><th>Heti %</th><th>Havi %</th></tr>"
    
    for name, ticker_symbol in STOCKS.items():
        try:
            ticker = yf.Ticker(ticker_symbol)
            hist = ticker.history(period="1mo")
            if len(hist) > 0:
                current_price = hist['Close'].iloc[-1]
                daily_change = ((current_price - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100 if len(hist) > 1 else 0
                weekly_change = ((current_price - hist['Close'].iloc[-5]) / hist['Close'].iloc[-5]) * 100 if len(hist) >= 5 else 0
                monthly_change = ((current_price - hist['Close'].iloc[0]) / hist['Close'].iloc[0]) * 100
                
                def fmt(val):
                    color = "green" if val >= 0 else "red"
                    return f"<span style='color:{color};'>{val:+.2f}%</span>"

                html += f"<tr><td><b>{name}</b></td><td>{current_price:.2f}</td><td>{fmt(daily_change)}</td><td>{fmt(weekly_change)}</td><td>{fmt(monthly_change)}</td></tr>"
        except Exception:
            html += f"<tr><td><b>{name}</b></td><td colspan='4'>Adat nem elérhető</td></tr>"
    html += "</table>"
    return html

def get_weather():
    """Pécs, Baja és Magyarország időjárás előrejelzése"""
    locations = {"Pécs": (46.0727, 18.2323), "Baja": (46.1749, 18.9563)}
    html = "<h3>Időjárás Előrejelzés</h3>"
    
    for city, (lat, lon) in locations.items():
        try:
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max&timezone=Europe%2FBudapest"
            res = requests.get(url).json()
            daily = res['daily']
            max_t = daily['temperature_2m_max'][0]
            min_t = daily['temperature_2m_min'][0]
            rain = daily['precipitation_probability_max'][0]
            html += f"<p><b>{city}:</b> Max: {max_t}°C, Min: {min_t}°C | Csapadék esélye: {rain}%</p>"
        except Exception:
            html += f"<p><b>{city}:</b> Nem érhető el az időjárás adat.</p>"
    return html

def get_categorized_news():
    """Hírek gyűjtése témakörök szerint az elmúlt 24 órából"""
    keywords = {
        "Belpolitika": ["kormány", "parlament", "orban", "magyarország", "választás", "fidesz", "tisza"],
        "Külpolitika": ["eu", "usa", "ukrajna", "orosz", "kína", "háború", "unió", "külföld"],
        "Gazdaság": ["infláció", "hitel", "bank", "ft", "forint", "euró", "költségvetés", "adalom"],
        "Tudomány & Tech": ["ai", "mesterséges intelligencia", "űrhajó", "nasa", "tech", "kutatás", "tudomány"],
        "Klíma & Környezet": ["klíma", "melegedés", "környezetvédelem", "aszály", "megújuló", "napelem"],
        "Sport (Válogatott & Liverpool)": ["válogatott", "szoboszlai", "liverpool", "foci", "eb", "vb", "magyar"]
    }
    
    collected_news = {cat: [] for cat in keywords}
    now = datetime.datetime.now(datetime.timezone.utc)

    for source, url in FEEDS.items():
        feed = feedparser.parse(url)
        for entry in feed.entries:
            # Utolsó 24 óra szűrése
            published = entry.get('published_parsed') or entry.get('updated_parsed')
            if published:
                pub_dt = datetime.datetime(*published[:6], tzinfo=datetime.timezone.utc)
                if (now - pub_dt).total_seconds() > 86400:
                    continue

            title = entry.title
            link = entry.link
            
            for cat, kw_list in keywords.items():
                if len(collected_news[cat]) < 3:
                    if any(kw in title.lower() for kw in kw_list):
                        collected_news[cat].append(f"<li>[<b>{source}</b>] <a href='{link}'>{title}</a></li>")

    html = "<h3>Napi Hírösszefoglaló (Top találatok az elmúlt 24 órából)</h3>"
    for cat, items in collected_news.items():
        html += f"<h4>{cat}</h4>"
        if items:
            html += "<ul>" + "".join(items) + "</ul>"
        else:
            html += "<p><i>Nincs kiemelt friss hír ebben a témában.</i></p>"
    return html

def send_email(body_content):
    sender = os.environ.get("SENDER_EMAIL")
    password = os.environ.get("SENDER_PASSWORD")
    receiver = os.environ.get("RECEIVER_EMAIL")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Napi Személyre Szabott Hír- és Portfólió Jelentés - {datetime.date.today().strftime('%Y.%m.%d')}"
    msg["From"] = sender
    msg["To"] = receiver

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6;">
        <h2>Reggeli Összefoglaló</h2>
        <hr>
        {body_content['weather']}
        <hr>
        {body_content['stocks']}
        <hr>
        {body_content['news']}
      </body>
    </html>
    """
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, receiver, msg.as_string())

if __name__ == "__main__":
    weather_data = get_weather()
    stock_data = get_stock_trends()
    news_data = get_categorized_news()

    send_email({
        "weather": weather_data,
        "stocks": stock_data,
        "news": news_data
    })

