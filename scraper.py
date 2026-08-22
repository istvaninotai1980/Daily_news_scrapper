import os
import smtplib
import datetime
import requests
import feedparser
import yfinance as yf
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIG: RÉSZVÉNYEK & ETF-EK (Javított ticker-struktúra) ---
STOCKS = {
    "Amazon (AMZ)": "AMZN",
    "Defence ETF (ARMY)": "DFEN",
    "Copper ETF (COPG)": "CPER",
    "Constellation Software (CSU)": "CSU.TO",
    "Global Growth ETF (GGRW)": "IWDA.AS",
    "Physical Silver (ISLN)": "SLV",
    "Microsoft (MSF)": "MSFT",
    "OTP Bank (OTP)": "OTP.BU",
    "S&P 500 Info Tech (QDV5)": "XLK",
    "TSMC (TSM)": "TSM",
    "S&P 500 ETF (VUSA)": "VOO"
}

FEEDS = {
    "Telex": "https://telex.hu/rss",
    "Index": "https://index.hu/24ora/rss/",
    "M4 Sport": "https://m4sport.hu/feed/",
    "Nemzeti Sport": "https://www.nemzetisport.hu/rss"
}

def get_stock_trends_and_news():
    """Részvények és ETF-ek stabil adatlekérése YTD és trend mutatókkal"""
    html = "<h3>Tőzsdei Portfólió Trendek & Hírérték</h3>"
    html += "<table border='1' cellpadding='5' style='border-collapse:collapse; width:100%;'>"
    html += "<tr style='background-color:#f2f2f2;'><th>Eszköz</th><th>Ár</th><th>Napi %</th><th>Heti %</th><th>Havi %</th><th>2026 YTD %</th></tr>"
    
    for name, ticker_symbol in STOCKS.items():
        try:
            ticker = yf.Ticker(ticker_symbol)
            hist = ticker.history(period="1y")

            if not hist.empty and len(hist) >= 2:
                current_price = hist['Close'].iloc[-1]
                daily_change = ((current_price - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
                weekly_change = ((current_price - hist['Close'].iloc[-5]) / hist['Close'].iloc[-5]) * 100 if len(hist) >= 5 else 0
                monthly_change = ((current_price - hist['Close'].iloc[-22]) / hist['Close'].iloc[-22]) * 100 if len(hist) >= 22 else 0
                
                # YTD számítás (2026-01-01 óta)
                hist_2026 = hist[hist.index >= '2026-01-01']
                if not hist_2026.empty:
                    start_price = hist_2026['Close'].iloc[0]
                    ytd_change = ((current_price - start_price) / start_price) * 100
                else:
                    ytd_change = daily_change

                def fmt(val):
                    color = "green" if val >= 0 else "red"
                    return f"<span style='color:{color};'>{val:+.2f}%</span>"

                html += f"<tr><td><b>{name}</b></td><td>{current_price:.2f}</td><td>{fmt(daily_change)}</td><td>{fmt(weekly_change)}</td><td>{fmt(monthly_change)}</td><td><b>{fmt(ytd_change)}</b></td></tr>"
            else:
                html += f"<tr><td><b>{name}</b></td><td colspan='5'><i>Adatfrissítés alatt</i></td></tr>"
        except Exception:
            html += f"<tr><td><b>{name}</b></td><td colspan='5'><i>Hiba az adatlekérésnél</i></td></tr>"

    html += "</table>"
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
    categories = {
        "Belpolitika": ["kormány", "parlament", "orbán", "választás", "fidesz", "tisza", "miniszter", "magyarország", "politika"],
        "Külpolitika": ["eu", "usa", "kína", "unió", "brüsszel", "nato", "németország", "franciaország", "közel-kelet", "ukrajna", "orosz"],
        "Gazdaság": ["infláció", "forint", "euró", "mnb", "költségvetés", "adózás", "hitel", "kamat", "bank", "gazdaság"],
        "Tudomány & Tech": ["mesterséges intelligencia", "ai", "nasa", "kutatás", "fejlesztés", "űrkutatás", "szoftver", "chip", "tech", "okostelefon"],
        "Klíma & Környezet": ["klíma", "felmelegedés", "aszály", "megújuló", "szén-dioxid", "környezet", "időjárás", "energia", "zöld", "hulladék"],
        "Sport (Válogatott & Liverpool)": ["szoboszlai", "liverpool", "válogatott", "foci", "eb", "vb", "liga", "bajnokság", "meccs", "főnix", "sport"]
    }
    
    all_entries = []

    # Megszüntettük a szigorú 24 órás dátumszűrést, hogy biztosan meglegyen az 5 cikk kategóriánként!
    for source, url in FEEDS.items():
        feed = feedparser.parse(url)
        for entry in feed.entries:
            all_entries.append({"source": source, "title": entry.title, "link": entry.link})

    html = "<h3>Napi Hírösszefoglaló (Top 5 hír kategóriánként)</h3>"
    
    for cat, kw_list in categories.items():
        matched_items = []
        for item in all_entries:
            title_lower = item["title"].lower()
            
            # Kizárás a Tech kategóriából a tisztaság kedvéért
            if cat == "Tudomány & Tech" and any(bad in title_lower for bad in ["orbán", "fidesz", "tisza", "kormány", "bíróság"]):
                continue
            
            # Külön szabály a Sportra: az M4 Sport és Nemzeti Sport hírei automatikusan bekerülnek
            if cat == "Sport (Válogatott & Liverpool)":
                if item["source"] in ["M4 Sport", "Nemzeti Sport"] or any(kw in title_lower for kw in kw_list):
                    matched_items.append(f"<li>[<b>{item['source']}</b>] <a href='{item['link']}'>{item['title']}</a></li>")
            else:
                if any(kw in title_lower for kw in kw_list):
                    matched_items.append(f"<li>[<b>{item['source']}</b>] <a href='{item['link']}'>{item['title']}</a></li>")
            
            # Keresünk pontosan 5 találatot!
            if len(matched_items) >= 5:
                break

        html += f"<h4>{cat}</h4>"
        if matched_items:
            html += "<ul>" + "".join(matched_items) + "</ul>"
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
    stock_data = get_stock_trends_and_news()
    news_data = get_categorized_news()

    send_email({
        "weather": weather_data,
        "stocks": stock_data,
        "news": news_data
    })







