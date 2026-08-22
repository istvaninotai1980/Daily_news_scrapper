import os
import smtplib
import datetime
import requests
import feedparser
import yfinance as yf
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIG: RÉSZVÉNYEK & ETF-EK ---
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

FEEDS = {
    "Telex": "https://telex.hu/rss",
    "Index": "https://index.hu/24ora/rss/",
    "M4 Sport": "https://m4sport.hu/feed/",
    "Nemzeti Sport": "https://www.nemzetisport.hu/rss"
}

def get_stock_trends_and_news():
    """Részvények, ETF-ek teljesítménye (Napi, Heti, Havi, YTD) és cégspecifikus hírek"""
    html = "<h3>Tőzsdei Portfólió Trendek & Hírérték</h3>"
    html += "<table border='1' cellpadding='5' style='border-collapse:collapse; width:100%;'>"
    html += "<tr style='background-color:#f2f2f2;'><th>Eszköz</th><th>Ár</th><th>Napi %</th><th>Heti %</th><th>Havi %</th><th>2026 YTD %</th></tr>"
    
    stock_news_html = "<h4>Friss Tőzsdei / Cégspecifikus Hírek</h4><ul>"
    has_stock_news = False

    for name, ticker_symbol in STOCKS.items():
        try:
            ticker = yf.Ticker(ticker_symbol)
            # Adatok lekérése 2026. január 1-től
            hist = ticker.history(start="2026-01-01")
            
            if hist.empty or len(hist) < 2:
                alt_symbol = ticker_symbol.split('.')[0]
                ticker = yf.Ticker(alt_symbol)
                hist = ticker.history(start="2026-01-01")

            if not hist.empty and len(hist) >= 2:
                current_price = hist['Close'].iloc[-1]
                daily_change = ((current_price - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
                weekly_change = ((current_price - hist['Close'].iloc[-5]) / hist['Close'].iloc[-5]) * 100 if len(hist) >= 5 else 0
                monthly_change = ((current_price - hist['Close'].iloc[-22]) / hist['Close'].iloc[-22]) * 100 if len(hist) >= 22 else 0
                ytd_change = ((current_price - hist['Close'].iloc[0]) / hist['Close'].iloc[0]) * 100
                
                def fmt(val):
                    color = "green" if val >= 0 else "red"
                    return f"<span style='color:{color};'>{val:+.2f}%</span>"

                html += f"<tr><td><b>{name}</b></td><td>{current_price:.2f}</td><td>{fmt(daily_change)}</td><td>{fmt(weekly_change)}</td><td>{fmt(monthly_change)}</td><td><b>{fmt(ytd_change)}</b></td></tr>"
            else:
                html += f"<tr><td><b>{name}</b></td><td colspan='5'><i>Adatfrissítés alatt / Piac zárva</i></td></tr>"

            # Cégspecifikus hírek lekérése
            news = ticker.news
            if news:
                for item in news[:1]:
                    title = item.get('title')
                    link = item.get('link')
                    if title and link:
                        stock_news_html += f"<li>[<b>{name}</b>] <a href='{link}'>{title}</a></li>"
                        has_stock_news = True

        except Exception:
            html += f"<tr><td><b>{name}</b></td><td colspan='5'><i>Hiba az adatlekérésnél</i></td></tr>"

    html += "</table>"
    stock_news_html += "</ul>"
    
    if not has_stock_news:
        stock_news_html = "<p><i>Nincs friss piaci hír az érintett részvényekhez.</i></p>"

    return html + stock_news_html

def get_weather():
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
    categories = {
        "Belpolitika": ["kormány", "parlament", "orbán", "választás", "fidesz", "tisza párt", "miniszter"],
        "Külpolitika": ["ukrajna", "orosz", "usa", "putyin", "zelenszkij", "unió", "brüsszel", "nato"],
        "Gazdaság": ["infláció", "forint", "euró", "mnb", "költségvetés", "adózás", "hitel", "kamat"],
        "Tudomány & Tech": ["mesterséges intelligencia", "ai", "nasa", "kutatás", "fejlesztés", "űrkutatás"],
        "Klíma & Környezet": ["klímaváltozás", "felmelegedés", "aszály", "megújuló", "szén-dioxid"],
        "Sport (Válogatott & Liverpool)": ["szoboszlai", "liverpool", "magyar válogatott", "foci válogatott", "foci eb", "foci vb"]
    }
    
    all_entries = []
    now = datetime.datetime.now(datetime.timezone.utc)

    for source, url in FEEDS.items():
        feed = feedparser.parse(url)
        for entry in feed.entries:
            published = entry.get('published_parsed') or entry.get('updated_parsed')
            if published:
                pub_dt = datetime.datetime(*published[:6], tzinfo=datetime.timezone.utc)
                if (now - pub_dt).total_seconds() > 86400:
                    continue
            all_entries.append({"source": source, "title": entry.title, "link": entry.link})

    html = "<h3>Napi Hírösszefoglaló (Mixelt forrásokból)</h3>"
    
    for cat, kw_list in categories.items():
        matched_items = []
        for item in all_entries:
            title_lower = item["title"].lower()
            if any(kw in title_lower for kw in kw_list):
                matched_items.append(f"<li>[<b>{item['source']}</b>] <a href='{item['link']}'>{item['title']}</a></li>")
                if len(matched_items) >= 3:
                    break

        html += f"<h4>{cat}</h4>"
        if matched_items:
            html += "<ul>" + "".join(matched_items) + "</ul>"
        else:
            html += "<p><i>Nincs kiemelt friss hír ebben a témában az elmúlt 24 órában.</i></p>"
            
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
    stock_data = get_stock_trends_and_news()
    news_data = get_categorized_news()

    send_email({
        "weather": weather_data,
        "stocks": stock_data,
        "news": news_data
    })



