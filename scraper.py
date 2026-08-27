import os
import smtplib
import datetime
import requests
import feedparser
import yfinance as yf
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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

NEWS_FEEDS = {
    "Telex": "https://telex.hu/rss",
    "Index": "https://index.hu/24ora/rss/",
    "Másfélfok": "https://masfelfok.hu/feed/",
    "Greenpeace": "https://www.greenpeace.org/hungary/feed/"
}

SPORT_FEEDS = {
    "Nemzeti Sport": "https://www.nemzetisport.hu/rss",
    "M4 Sport": "https://m4sport.hu/feed/"
}

CATEGORY_KEYWORDS = {
    "Belpolitika": ["kormány", "parlament", "orbán", "választás", "fidesz", "tisza", "miniszter", "belföld", "magyarország", "politika", "bíróság", "törvény"],
    "Külpolitika": ["eu", "usa", "kína", "unió", "brüsszel", "nato", "németország", "franciaország", "közel-kelet", "ukrajna", "orosz", "trump", "putyin", "zelenszkij", "külföld"],
    "Gazdaság": ["infláció", "forint", "euró", "mnb", "költségvetés", "adózás", "hitel", "kamat", "bank", "gazdaság", "gdp", "áremelés", "befektetés"],
    "Tudomány & Tech": ["mesterséges intelligencia", "ai", "nasa", "kutatás", "fejlesztés", "űrkutatás", "szoftver", "chip", "tech", "okostelefon", "tudomány", "innováció", "kiber"],
    "Klíma & Környezet": ["klíma", "felmelegedés", "aszály", "megújuló", "szén-dioxid", "környezet", "időjárás", "energia", "zöld", "hulladék", "emisszió"]
}

SPORT_KEYWORDS = ["szoboszlai", "magyar válogatott", "f1", "formula1", "forma1", "bajnokok ligája", "bl", "eb", "vb", "bajnokság", "foci", "liverpool", "magyar"]

PORTFOLIO_HU_RSS = "https://www.portfolio.hu/rss/befektetes.xml"

def get_fx_rate(currency_code, date_str=None):
    """Deviza/HUF árfolyam lekérdezése yfinance-szel"""
    if currency_code == "HUF":
        return 1.0
    
    pair = f"{currency_code}HUF=X"
    try:
        ticker = yf.Ticker(pair)
        hist = ticker.history(period="1y")
        if hist.empty:
            return 1.0
        
        if date_str:
            hist_sub = hist[hist.index.astype(str) >= date_str]
            if not hist_sub.empty:
                return float(hist_sub['Close'].iloc[0])
        return float(hist['Close'].iloc[-1])
    except Exception:
        return 1.0

def get_portfolio_hu_top3():
    items = []
    try:
        p_feed = feedparser.parse(PORTFOLIO_HU_RSS)
        for entry in p_feed.entries:
            items.append(f"<li><a href='{entry.link}'>{entry.title}</a></li>")
            if len(items) >= 3:
                break
    except Exception:
        pass

    if len(items) < 3:
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            res = requests.get("https://www.portfolio.hu/cimke/T%C5%91zsde", headers=headers, timeout=5)
            soup = BeautifulSoup(res.text, 'html.parser')
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                title = a_tag.text.strip()
                if href.startswith('https://www.portfolio.hu/') and len(title) > 25:
                    item_html = f"<li><a href='{href}'>{title}</a></li>"
                    if item_html not in items:
                        items.append(item_html)
                if len(items) >= 3:
                    break
        except Exception:
            pass

    if items:
        return "<h4>Top 3 Tőzsdei Hír (Portfolio.hu)</h4><ul>" + "".join(items[:3]) + "</ul>"
    else:
        return "<p><i>A Portfolio.hu tőzsdei hírei jelenleg nem érhetőek el.</i></p>"

def get_stock_trends_and_news():
    html = "<h3>Tőzsdei Portfólió Trendek, BTD & HUF Nettó Balansz</h3>"
    
    if len(PORTFOLIO) < EXPECTED_COUNT:
        html += f"<p style='color:red;'><b>Figyelem:</b> A beállított portfólióban csak {len(PORTFOLIO)} eszköz szerepel a várt {EXPECTED_COUNT} helyett!</p>"

    html += "<table border='1' cellpadding='5' style='border-collapse:collapse; width:100%;'>"
    html += "<tr style='background-color:#f2f2f2;'><th>Eszköz</th><th>Vásárlás dátuma</th><th>Ár</th><th>Napi %</th><th>Heti %</th><th>Havi %</th><th>Devizás BTD %</th><th>HUF BTD % (Devizakorrigált)</th></tr>"
    
    for name, data in PORTFOLIO.items():
        try:
            ticker_symbol = data["ticker"]
            buy_date = data["buy_date"]
            
            ticker = yf.Ticker(ticker_symbol)
            hist = ticker.history(period="1y")

            if not hist.empty and len(hist) >= 2:
                current_price = float(hist['Close'].iloc[-1])
                daily_change = ((current_price - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
                weekly_change = ((current_price - hist['Close'].iloc[-5]) / hist['Close'].iloc[-5]) * 100 if len(hist) >= 5 else 0
                monthly_change = ((current_price - hist['Close'].iloc[-22]) / hist['Close'].iloc[-22]) * 100 if len(hist) >= 22 else 0
                
                # Devizanem meghatározása (alapértelmezett USD, ha .BU = HUF, .TO = CAD, .AS = EUR)
                currency = "USD"
                if ticker_symbol.endswith(".BU"):
                    currency = "HUF"
                elif ticker_symbol.endswith(".TO"):
                    currency = "CAD"
                elif ticker_symbol.endswith(".AS"):
                    currency = "EUR"

                hist_buy = hist[hist.index.astype(str) >= buy_date]
                if not hist_buy.empty:
                    buy_price = float(hist_buy['Close'].iloc[0])
                    btd_change = ((current_price - buy_price) / buy_price) * 100
                else:
                    buy_price = current_price
                    btd_change = daily_change

                # HUF devizakorrigált BTD % számítása
                buy_fx = get_fx_rate(currency, buy_date)
                current_fx = get_fx_rate(currency)
                
                buy_price_huf = buy_price * buy_fx
                current_price_huf = current_price * current_fx
                huf_btd_change = ((current_price_huf - buy_price_huf) / buy_price_huf) * 100

                def fmt(val):
                    color = "green" if val >= 0 else "red"
                    return f"<span style='color:{color};'>{val:+.2f}%</span>"

                html += f"<tr><td><b>{name}</b></td><td>{buy_date}</td><td>{current_price:.2f} {currency}</td><td>{fmt(daily_change)}</td><td>{fmt(weekly_change)}</td><td>{fmt(monthly_change)}</td><td><b>{fmt(btd_change)}</b></td><td><b>{fmt(huf_btd_change)}</b></td></tr>"
            else:
                html += f"<tr><td><b>{name}</b></td><td>{buy_date}</td><td colspan='6'><i>Adatfrissítés alatt</i></td></tr>"
        except Exception:
            html += f"<tr><td><b>{name}</b></td><td>{data.get('buy_date','-')}</td><td colspan='6'><i>Hiba az adatlekérésnél</i></td></tr>"

    html += "</table>"
    html += get_portfolio_hu_top3()
    return html

def get_weather():
    locations = {"Pécs": (46.0727, 18.2323), "Baja": (46.1749, 18.9563)}
    html = "<h3>Időjárás Előrejelzés</h3>"
    
    for city, (lat, lon) in locations.items():
        try:
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max&timezone=Europe%2FBudapest"
            res = requests.get(url, timeout=5).json()
            daily = res['daily']
            max_t = daily['temperature_2m_max'][0]
            min_t = daily['temperature_2m_min'][0]
            rain = daily['precipitation_probability_max'][0]
            html += f"<p><b>{city}:</b> Max: {max_t}°C, Min: {min_t}°C | Csapadék esélye: {rain}%</p>"
        except Exception:
            html += f"<p><b>{city}:</b> Nem érhető el az időjárás adat.</p>"
    return html

def fetch_feed_safe(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        resp = requests.get(url, headers=headers, timeout=8)
        return feedparser.parse(resp.text)
    except Exception:
        return feedparser.parse(url)

def is_hungarian_text(text):
    """Kizárólag magyar cikkek átengedése (angol szavak és karakterek kiszűrése)"""
    english_stopwords = [" the ", " in ", " of ", " for ", " and ", " to ", " with ", " on ", " at "]
    text_lower = f" {text.lower()} "
    if any(stop in text_lower for stop in english_stopwords):
        return False
    return True

def get_categorized_news():
    all_articles = []
    for source_name, feed_url in NEWS_FEEDS.items():
        try:
            feed = fetch_feed_safe(feed_url)
            for entry in feed.entries:
                if is_hungarian_text(entry.title):
                    all_articles.append({
                        "source": source_name,
                        "title": entry.title,
                        "link": entry.link
                    })
        except Exception:
            continue

    used_links = set()
    html = "<h3>Napi Hírösszefoglaló</h3>"

    for cat_name, keywords in CATEGORY_KEYWORDS.items():
        matched_items = []
        for article in all_articles:
            if article["link"] in used_links:
                continue
            title_lower = article["title"].lower()

            if cat_name.startswith("Klíma") and article["source"] in ["Másfélfok", "Greenpeace"]:
                matched_items.append(article)
                used_links.add(article["link"])
            elif any(kw in title_lower for kw in keywords):
                if cat_name == "Tudomány & Tech" and any(bad in title_lower for bad in ["orbán", "fidesz", "tisza", "kormány", "bíróság"]):
                    continue
                matched_items.append(article)
                used_links.add(article["link"])

            if len(matched_items) >= 5:
                break

        html += f"<h4>{cat_name}</h4>"
        if matched_items:
            html += "<ul>"
            for item in matched_items[:5]:
                html += f"<li>[<b>{item['source']}</b>] <a href='{item['link']}'>{item['title']}</a></li>"
            html += "</ul>"
        else:
            html += "<p><i>Nincs friss hír ebben a témában.</i></p>"

    # Dedikált Sport gyűjtő - Kizárólag magyar nyelvű cikkek
    sport_articles = []
    for source_name, feed_url in SPORT_FEEDS.items():
        try:
            feed = fetch_feed_safe(feed_url)
            for entry in feed.entries:
                if is_hungarian_text(entry.title):
                    sport_articles.append({
                        "source": source_name,
                        "title": entry.title,
                        "link": entry.link
                    })
        except Exception:
            continue

    if len(sport_articles) < 5:
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            res = requests.get("https://www.nemzetisport.hu/", headers=headers, timeout=5)
            soup = BeautifulSoup(res.text, 'html.parser')
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                title = a_tag.text.strip()
                if len(title) > 30 and ("202" in href or ".html" in href or "/cikk/" in href or "/labdarugas/" in href or "/f1/" in href):
                    if is_hungarian_text(title):
                        full_link = href if href.startswith("http") else "https://www.nemzetisport.hu" + href
                        sport_articles.append({
                            "source": "Nemzeti Sport",
                            "title": title,
                            "link": full_link
                        })
                if len(sport_articles) >= 15:
                    break
        except Exception:
            pass

    sport_matches = []
    sport_links = set()

    for article in sport_articles:
        title_lower = article["title"].lower()
        if any(kw in title_lower for kw in SPORT_KEYWORDS):
            if article["link"] not in sport_links:
                sport_matches.append(article)
                sport_links.add(article["link"])
        if len(sport_matches) >= 5:
            break

    if len(sport_matches) < 5:
        for article in sport_articles:
            if article["link"] not in sport_links:
                sport_matches.append(article)
                sport_links.add(article["link"])
            if len(sport_matches) >= 5:
                break

    html += "<h4>Sport (Válogatott, Szoboszlai, F1, BL)</h4>"
    if sport_matches:
        html += "<ul>"
        for item in sport_matches[:5]:
            html += f"<li>[<b>{item['source']}</b>] <a href='{item['link']}'>{item['title']}</a></li>"
        html += "</ul>"
    else:
        html += "<p><i>Nincs friss sporthír az elmúlt 24 órában.</i></p>"

    return html

def send_email(body_content):
    sender = os.environ.get("SENDER_EMAIL")
    password = os.environ.get("SENDER_PASSWORD")
    receiver = os.environ.get("RECEIVER_EMAIL")

    if not sender or not password or not receiver:
        return

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
