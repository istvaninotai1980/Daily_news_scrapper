import os
import smtplib
import datetime
import requests
import feedparser
import yfinance as yf
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIG: RÉSZVÉNYEK, ETF-EK & VÁSÁRLÁSI DÁTUMOK (BTD) ---
PORTFOLIO = {
    "Amazon (AMZ)": {"ticker": "AMZN", "buy_date": "2026-07-29"},
    "TSMC (TSM)": {"ticker": "TSM", "buy_date": "2026-07-28"},
    "Microsoft (MSF)": {"ticker": "MSFT", "buy_date": "2026-04-16"},
    "OTP Bank (OTP)": {"ticker": "OTP.BU", "buy_date": "2026-03-06"},
    "Physical Silver (ISLN)": {"ticker": "SLV", "buy_date": "2026-03-06"},
    "Constellation Software (CSU)": {"ticker": "CSU.TO", "buy_date": "2026-01-28"},
    "Defence ETF (ARMY)": {"ticker": "DFEN", "buy_date": "2026-01-19"},
    "S&P 500 Info Tech (QDV5)": {"ticker": "XLK", "buy_date": "2026-01-19"},
    "Copper ETF (COPG)": {"ticker": "CPER", "buy_date": "2026-01-19"},
    "Global Growth ETF (GGRW)": {"ticker": "IWDA.AS", "buy_date": "2026-01-15"},
    "S&P 500 ETF (VUSA)": {"ticker": "VOO", "buy_date": "2026-01-15"}
}

EXPECTED_COUNT = 11

# --- CONFIG: ROVAT-SPECIFIKUS RSS FORRÁSOK ---
CATEGORY_FEEDS = {
    "Belpolitika": [
        "https://telex.hu/rss/rovat/belfold",
        "https://index.hu/24ora/rss/?feed=belfold"
    ],
    "Külpolitika": [
        "https://telex.hu/rss/rovat/kulfold",
        "https://index.hu/24ora/rss/?feed=kulfold"
    ],
    "Gazdaság": [
        "https://telex.hu/rss/rovat/gazdasag",
        "https://index.hu/24ora/rss/?feed=gazdasag"
    ],
    "Tudomány & Tech": [
        "https://telex.hu/rss/rovat/techtud",
        "https://index.hu/24ora/rss/?feed=techtud"
    ],
    "Klíma & Környezet": [
        "https://masfelfok.hu/feed/",
        "https://www.greenpeace.org/hungary/feed/"
    ],
    "Sport (Válogatott, Szoboszlai, F1, BL)": [
        "https://telex.hu/rss/rovat/sport",
        "https://index.hu/24ora/rss/?feed=sport",
        "https://m4sport.hu/feed/"
    ]
}

PORTFOLIO_HU_RSS = "https://www.portfolio.hu/rss/tozsde.xml"

def get_stock_trends_and_news():
    """Részvények és ETF-ek BTD (Buy To Date) mutatói és Portfolio.hu hírek"""
    html = "<h3>Tőzsdei Portfólió Trendek & BTD Teljesítmény</h3>"
    
    # Hiányellenőrzés
    if len(PORTFOLIO) < EXPECTED_COUNT:
        html += f"<p style='color:red;'><b>Figyelem:</b> A beállított portfólióban csak {len(PORTFOLIO)} eszköz szerepel a várt {EXPECTED_COUNT} helyett!</p>"

    html += "<table border='1' cellpadding='5' style='border-collapse:collapse; width:100%;'>"
    html += "<tr style='background-color:#f2f2f2;'><th>Eszköz</th><th>Vásárlás dátuma</th><th>Ár</th><th>Napi %</th><th>Heti %</th><th>Havi %</th><th>BTD % (Vásárlás óta)</th></tr>"
    
    for name, data in PORTFOLIO.items():
        try:
            ticker_symbol = data["ticker"]
            buy_date = data["buy_date"]
            
            ticker = yf.Ticker(ticker_symbol)
            hist = ticker.history(period="max")

            if not hist.empty and len(hist) >= 2:
                current_price = hist['Close'].iloc[-1]
                daily_change = ((current_price - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
                weekly_change = ((current_price - hist['Close'].iloc[-5]) / hist['Close'].iloc[-5]) * 100 if len(hist) >= 5 else 0
                monthly_change = ((current_price - hist['Close'].iloc[-22]) / hist['Close'].iloc[-22]) * 100 if len(hist) >= 22 else 0
                
                # BTD (Buy To Date) számítás a megadott dátum óta
                hist_buy = hist[hist.index >= buy_date]
                if not hist_buy.empty:
                    buy_price = hist_buy['Close'].iloc[0]
                    btd_change = ((current_price - buy_price) / buy_price) * 100
                else:
                    btd_change = daily_change

                def fmt(val):
                    color = "green" if val >= 0 else "red"
                    return f"<span style='color:{color};'>{val:+.2f}%</span>"

                html += f"<tr><td><b>{name}</b></td><td>{buy_date}</td><td>{current_price:.2f}</td><td>{fmt(daily_change)}</td><td>{fmt(weekly_change)}</td><td>{fmt(monthly_change)}</td><td><b>{fmt(btd_change)}</b></td></tr>"
            else:
                html += f"<tr><td><b>{name}</b></td><td>{buy_date}</td><td colspan='5'><i>Adatfrissítés alatt</i></td></tr>"
        except Exception:
            html += f"<tr><td><b>{name}</b></td><td>{data.get('buy_date','-')}</td><td colspan='5'><i>Hiba az adatlekérésnél</i></td></tr>"

    html += "</table>"

    # Top 3 Portfolio.hu Tőzsde hír
    try:
        p_feed = feedparser.parse(PORTFOLIO_HU_RSS)
        html += "<h4>Top 3 Tőzsdei Hír (Portfolio.hu)</h4><ul>"
        count = 0
        for entry in p_feed.entries:
            html += f"<li><a href='{entry.link}'>{entry.title}</a></li>"
            count += 1
            if count >= 3:
                break
        html += "</ul>"
    except Exception:
        html += "<p><i>A Portfolio.hu hírei nem érhetőek el.</i></p>"

    return html

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
    """Rovat-specifikus hírek gyűjtése 5-ös limittel, BL és sport szűrővel"""
    sport_keywords = [
        "szoboszlai", "magyar válogatott", "magyar", "f1", "formula1", "forma1", 
        "bajnokok ligája", "bl", "eb", "vb", "bajnokság", "foci"
    ]
    bl_keywords = ["bajnokok ligája", "bl"]

    html = "<h3>Napi Hírösszefoglaló (Rovatok szerinti bontásban)</h3>"

    for cat_name, rss_list in CATEGORY_FEEDS.items():
        matched_items = []
        bl_items = []
        other_sport_items = []

        for feed_url in rss_list:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries:
                    title = entry.title
                    link = entry.link
                    
                    if "telex" in feed_url:
                        source = "Telex"
                    elif "index" in feed_url:
                        source = "Index"
                    elif "m4sport" in feed_url:
                        source = "M4 Sport"
                    elif "masfelfok" in feed_url:
                        source = "Másfélfok"
                    elif "greenpeace" in feed_url:
                        source = "Greenpeace"
                    else:
                        source = "Hírek"

                    item_html = f"<li>[<b>{source}</b>] <a href='{link}'>{title}</a></li>"

                    if cat_name.startswith("Sport"):
                        title_lower = title.lower()
                        if any(kw in title_lower for kw in bl_keywords):
                            if item_html not in bl_items:
                                bl_items.append(item_html)
                        elif any(kw in title_lower for kw in sport_keywords):
                            if item_html not in other_sport_items:
                                other_sport_items.append(item_html)
                    else:
                        if item_html not in matched_items:
                            matched_items.append(item_html)

                    if not cat_name.startswith("Sport") and len(matched_items) >= 5:
                        break
            except Exception:
                continue

        if cat_name.startswith("Sport"):
            matched_items = (bl_items + other_sport_items)[:5]

        html += f"<h4>{cat_name}</h4>"
        if matched_items:
            html += "<ul>" + "".join(matched_items[:5]) + "</ul>"
        else:
            html += "<p><i>Nincs friss hír ebben a rovatban.</i></p>"

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
