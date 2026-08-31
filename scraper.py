import os
import smtplib
import requests
import feedparser
import pandas as pd
import yfinance as yf
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from openai import OpenAI

# --- SECRETS & SETUP ---
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD")
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# --- PORTFÓLIÓ ESZKÖZÖK (IBKR TBSZ-2025) ---
PORTFOLIO = [
    {"name": "Broadcom (AVGO)", "symbol": "AVGO", "pos": 0.54, "currency": "USD", "buy_date": "2026-08-28"},
    {"name": "Nvidia IBIS (NVD)", "symbol": "NVD.DE", "pos": 1.5, "currency": "EUR", "buy_date": "2026-08-28"},
    {"name": "Amazon (AMZ)", "symbol": "AMZN", "pos": 1.4759, "currency": "USD", "buy_date": "2026-07-29"},
    {"name": "TSMC (TSM)", "symbol": "TSM", "pos": 0.8895, "currency": "USD", "buy_date": "2026-07-28"},
    {"name": "Microsoft (MSF)", "symbol": "MSFT", "pos": 1.4114, "currency": "USD", "buy_date": "2026-04-16"},
    {"name": "OTP Bank (OTP)", "symbol": "OTP.BD", "pos": 2.0, "currency": "HUF", "buy_date": "2026-03-06"},
    {"name": "Physical Silver (ISLN)", "symbol": "ISLN.L", "pos": 3.7478, "currency": "USD", "buy_date": "2026-03-06"},
    {"name": "Constellation Software (CSU)", "symbol": "CSU.TO", "pos": 0.3056, "currency": "CAD", "buy_date": "2026-01-28"},
    {"name": "Defence ETF (ARMY)", "symbol": "ARMY.L", "pos": 46.0, "currency": "USD", "buy_date": "2026-01-19"},
    {"name": "S&P 500 Info Tech (QDV5)", "symbol": "QDV5.DE", "pos": 63.6748, "currency": "EUR", "buy_date": "2026-01-19"},
    {"name": "Copper ETF (COPG)", "symbol": "COPG.L", "pos": 9.548, "currency": "USD", "buy_date": "2026-01-19"},
    {"name": "Global Growth ETF (GGRW)", "symbol": "GGRW.L", "pos": 15.0924, "currency": "USD", "buy_date": "2026-01-15"},
    {"name": "S&P 500 ETF (VUSA)", "symbol": "VUSA.L", "pos": 4.5854, "currency": "USD", "buy_date": "2026-01-15"}
]

def format_pct(val):
    if pd.isna(val) or val is None:
        return "<td style='padding:8px; text-align:center;'>N/A</td>"
    color = "green" if val >= 0 else "red"
    sign = "+" if val >= 0 else ""
    return f"<td style='padding:8px; text-align:center; color:{color}; font-weight:bold;'>{sign}{val:.2f}%</td>"

def get_fx_pair(currency):
    if currency == 'HUF':
        return 1.0, None
    symbol_map = {'USD': 'USDHUF=X', 'EUR': 'EURHUF=X', 'CAD': 'CADHUF=X'}
    fx_symbol = symbol_map.get(currency)
    if not fx_symbol:
        return 1.0, None
    try:
        fx = yf.Ticker(fx_symbol)
        hist = fx.history(period="1y")
        if not hist.empty:
            return hist['Close'].iloc[-1], hist
    except Exception as e:
        print(f"FX Error ({currency}): {e}")
    return 1.0, None

def build_portfolio_table():
    rows_html = ""
    for item in PORTFOLIO:
        try:
            ticker = yf.Ticker(item["symbol"])
            hist = ticker.history(period="1y")
            
            if hist.empty or len(hist) < 2:
                # Fallback szimbólum próbálkozás
                alt_symbol = item["symbol"].replace(".L", ".DE")
                ticker = yf.Ticker(alt_symbol)
                hist = ticker.history(period="1y")

            if not hist.empty and len(hist) >= 2:
                curr_price = hist['Close'].iloc[-1]
                
                # Londoni penny / dollár korrekció
                if item["symbol"].endswith(".L") and curr_price > 1000 and item["currency"] == "USD":
                    curr_price = curr_price / 100.0

                daily_pct = ((curr_price - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
                weekly_pct = ((curr_price - hist['Close'].iloc[-5]) / hist['Close'].iloc[-5]) * 100 if len(hist) >= 5 else daily_pct
                monthly_pct = ((curr_price - hist['Close'].iloc[-22]) / hist['Close'].iloc[-22]) * 100 if len(hist) >= 22 else weekly_pct
                
                # Devizás BTD
                hist_btd = hist.loc[hist.index >= item["buy_date"]]
                if not hist_btd.empty:
                    buy_price = hist_btd['Close'].iloc[0]
                    if item["symbol"].endswith(".L") and buy_price > 1000 and item["currency"] == "USD":
                        buy_price = buy_price / 100.0
                    dev_btd_pct = ((curr_price - buy_price) / buy_price) * 100
                else:
                    buy_price = curr_price
                    dev_btd_pct = monthly_pct

                # Tényleges HUF BTD kiszámítása
                curr_fx, fx_hist = get_fx_pair(item["currency"])
                if fx_hist is not None and not fx_hist.empty:
                    fx_btd = fx_hist.loc[fx_hist.index >= item["buy_date"]]
                    buy_fx = fx_btd['Close'].iloc[0] if not fx_btd.empty else curr_fx
                else:
                    buy_fx = 1.0
                    curr_fx = 1.0

                buy_val_huf = item["pos"] * buy_price * buy_fx
                curr_val_huf = item["pos"] * curr_price * curr_fx
                
                huf_btd_pct = ((curr_val_huf - buy_val_huf) / buy_val_huf) * 100 if buy_val_huf > 0 else 0.0

                rows_html += f"""
                <tr>
                    <td style="padding:8px; font-weight:bold;">{item['name']}</td>
                    <td style="padding:8px; text-align:center;">{item['buy_date']}</td>
                    <td style="padding:8px; text-align:center;">{curr_price:.2f} {item['currency']}</td>
                    {format_pct(daily_pct)}
                    {format_pct(weekly_pct)}
                    {format_pct(monthly_pct)}
                    {format_pct(dev_btd_pct)}
                    {format_pct(huf_btd_pct)}
                </tr>
                """
            else:
                rows_html += f"<tr><td style='padding:8px;'>{item['name']}</td><td style='padding:8px;'>{item['buy_date']}</td><td colspan='6' style='text-align:center;'>Adatfrissítés alatt</td></tr>"
        except Exception as e:
            print(f"Hiba {item['name']}: {e}")
            rows_html += f"<tr><td style='padding:8px;'>{item['name']}</td><td style='padding:8px;'>{item['buy_date']}</td><td colspan='6' style='text-align:center;'>Adatfrissítés alatt</td></tr>"

    return f"""
    <table border="1" style="border-collapse:collapse; width:100%; font-size:13px; font-family:sans-serif;">
        <thead style="background-color:#f2f2f2;">
            <tr>
                <th style="padding:8px;">Eszköz</th>
                <th style="padding:8px;">Vásárlás dátuma</th>
                <th style="padding:8px;">Ár</th>
                <th style="padding:8px;">Napi %</th>
                <th style="padding:8px;">Heti %</th>
                <th style="padding:8px;">Havi %</th>
                <th style="padding:8px;">Devizás BTD %</th>
                <th style="padding:8px;">HUF BTD %</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
    """

# --- TOP 3 ELEMZÉS & HÍREK ---
def get_quant_summary():
    raw_news = []
    feeds = ["https://www.portfolio.hu/rss/all.xml", "https://hvg.hu/rss/gazdasag"]
    for f in feeds:
        try:
            parsed = feedparser.parse(f)
            for e in parsed.entries[:6]:
                raw_news.append(f"- Cím: {e.title}\n  Link: {e.link}")
        except Exception:
            continue

    if not client or not raw_news:
        return "<p>Tőzsdei elemzés átmenetileg nem elérhető.</p>"

    prompt = """
    Act as a senior quantitative equity analyst and financial journalist. 
    Filter raw news and generate a concentrated news summary containing exactly the TOP 3 most credible, market-moving stories.
    Format strictly as HTML:
    <div style='margin-bottom:15px; padding:10px; border-left:4px solid #1976d2; background:#f8f9fa;'>
        <h4 style='margin:0; color:#0d47a1;'>[Sorszám]. 📈 [Cím]</h4>
        <p><b>A hír lényege (Signal):</b> [1-2 mondat]</p>
        <p><b>Befektetői hatás (Investor Impact):</b> [Implikáció]</p>
        <p><b>Forrás:</b> <a href='[Eredeti URL]'>Kattints az eredeti cikkhez</a></p>
    </div>
    Rules: Hungarian language. Clinical, objective tone. Stick strictly to provided text links.
    """
    try:
        res = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": "\n".join(raw_news)}],
            temperature=0.2
        )
        return res.choices[0].message.content
    except Exception as e:
        return f"<p>Hiba az elemzéskor: {e}</p>"

def fetch_top_news(feed_urls, limit=5):
    items = []
    seen_titles = set()
    for url in feed_urls:
        try:
            parsed = feedparser.parse(url)
            for entry in parsed.entries:
                title = entry.title.strip()
                if title not in seen_titles:
                    seen_titles.add(title)
                    items.append(f"<li style='margin-bottom:6px;'><a href='{entry.link}' style='text-decoration:none; color:#1a0dab; font-weight:bold;'>{title}</a></li>")
                if len(items) >= limit:
                    break
        except Exception:
            continue
        if len(items) >= limit:
            break
    return f"<ul style='padding-left:20px;'>{''.join(items)}</ul>" if items else "<p>Nincs elérhető hír.</p>"

def build_newsletter():
    portfolio_table = build_portfolio_table()
    quant_analysis = get_quant_summary()
    
    belfold = fetch_top_news(["https://hvg.hu/rss/itthon", "https://telex.hu/rss/belfold"], 5)
    kulfold = fetch_top_news(["https://hvg.hu/rss/vilag", "https://telex.hu/rss/kulfold"], 5)
    tech = fetch_top_news(["https://hvg.hu/rss/tudomany", "https://telex.hu/rss/tech"], 5)
    klima = fetch_top_news(["https://hvg.hu/rss/zold", "https://telex.hu/rss/zold"], 5)
    sport = fetch_top_news(["https://hvg.hu/rss/sport", "https://telex.hu/rss/sport"], 5)

    return f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family:Arial, sans-serif; color:#333; padding:20px;">
        <h2>Balansz</h2>
        {portfolio_table}
        <br><hr><br>
        <h3>📈 TOP 3 Tőzsdei & Gazdasági Elemzés (Alpha Focus)</h3>
        {quant_analysis}
        <br><hr><br>
        <h3>🇭🇺 Belföld (Top 5)</h3>{belfold}
        <h3>🌍 Külföld (Top 5)</h3>{kulfold}
        <h3>💻 Tudomány & Tech (Top 5)</h3>{tech}
        <h3>🌱 Klíma & Zöld (Top 5)</h3>{klima}
        <h3>⚽ Sport (Top 5)</h3>{sport}
    </body>
    </html>
    """

def send_email(html_content):
    msg = MIMEMultipart('alternative')
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL
    msg['Subject'] = "Napi Hírlevél & Balansz Portfólió"
    msg.attach(MIMEText(html_content, 'html', 'utf-8'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("E-mail sikeresen elküldve!")
    except Exception as e:
        print(f"Hiba küldéskor: {e}")

if __name__ == "__main__":
    content = build_newsletter()
    send_email(content)
