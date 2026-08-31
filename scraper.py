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

# --- PORTFÓLIÓ ESZKÖZÖK (BALANSZ) ---
PORTFOLIO = [
    {"name": "Broadcom (AVGO)", "symbol": "AVGO", "buy_date": "2026-08-28"},
    {"name": "Nvidia IBIS (NVD)", "symbol": "NVD.DE", "buy_date": "2026-08-28"},
    {"name": "Amazon (AMZ)", "symbol": "AMZN", "buy_date": "2026-07-29"},
    {"name": "TSMC (TSM)", "symbol": "TSM", "buy_date": "2026-07-28"},
    {"name": "Microsoft (MSF)", "symbol": "MSFT", "buy_date": "2026-04-16"},
    {"name": "OTP Bank (OTP)", "symbol": "OTP.BD", "buy_date": "2026-03-06"},
    {"name": "Physical Silver (ISLN)", "symbol": "ISLN.L", "buy_date": "2026-03-06"},
    {"name": "Constellation Software (CSU)", "symbol": "CSU.TO", "buy_date": "2026-01-28"},
    {"name": "Defence ETF (ARMY)", "symbol": "ARMY.L", "buy_date": "2026-01-19"},
    {"name": "S&P 500 Info Tech (QDV5)", "symbol": "QDV5.DE", "buy_date": "2026-01-19"},
    {"name": "Copper ETF (COPG)", "symbol": "COPG.L", "buy_date": "2026-01-19"},
    {"name": "Global Growth ETF (GGRW)", "symbol": "GGRW.L", "buy_date": "2026-01-15"},
    {"name": "S&P 500 ETF (VUSA)", "symbol": "VUSA.L", "buy_date": "2026-01-15"}
]

def format_pct(val):
    if pd.isna(val) or val is None:
        return "<td style='padding:8px; text-align:center;'>N/A</td>"
    color = "green" if val >= 0 else "red"
    sign = "+" if val >= 0 else ""
    return f"<td style='padding:8px; text-align:center; color:{color}; font-weight:bold;'>{sign}{val:.2f}%</td>"

def build_portfolio_table():
    rows_html = ""
    for item in PORTFOLIO:
        try:
            ticker = yf.Ticker(item["symbol"])
            hist = ticker.history(period="3mo")
            if not hist.empty and len(hist) >= 2:
                curr_price = hist['Close'].iloc[-1]
                currency = ticker.info.get('currency', 'USD')
                
                daily_pct = ((curr_price - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
                weekly_pct = ((curr_price - hist['Close'].iloc[-5]) / hist['Close'].iloc[-5]) * 100 if len(hist) >= 5 else 0.0
                monthly_pct = ((curr_price - hist['Close'].iloc[0]) / hist['Close'].iloc[0]) * 100
                
                rows_html += f"""
                <tr>
                    <td style="padding:8px; font-weight:bold;">{item['name']}</td>
                    <td style="padding:8px; text-align:center;">{item['buy_date']}</td>
                    <td style="padding:8px; text-align:center;">{curr_price:.2f} {currency}</td>
                    {format_pct(daily_pct)}
                    {format_pct(weekly_pct)}
                    {format_pct(monthly_pct)}
                    {format_pct(monthly_pct)}
                    {format_pct(monthly_pct)}
                </tr>
                """
            else:
                rows_html += f"<tr><td style='padding:8px;'>{item['name']}</td><td style='padding:8px;'>{item['buy_date']}</td><td colspan='6' style='text-align:center;'>Adatfrissítés alatt</td></tr>"
        except Exception:
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

# --- GARANTÁLT TOP 3 GAZDASÁGI ELEMZÉS ---
def get_quant_summary():
    raw_news = []
    feeds = [
        "https://www.portfolio.hu/rss/all.xml",
        "https://hvg.hu/rss/gazdasag",
        "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"
    ]
    for f in feeds:
        try:
            parsed = feedparser.parse(f)
            for e in parsed.entries[:8]:
                raw_news.append(f"- Cím: {e.title}\n  Link: {e.link}")
        except Exception:
            continue

    if not raw_news:
        raw_news.append("- Cím: Globális piaci makrogazdasági változások\n  Link: https://www.bloomberg.com")

    if not client:
        return "<p>API kulcs hiányzik az elemzéshez.</p>"

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
        return f"<p>Hiba az elemzés generálása során: {e}</p>"

# --- ROVAT HÍREK ---
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

# --- BUILD & SEND ---
def build_newsletter():
    portfolio_table = build_portfolio_table()
    quant_analysis = get_quant_summary()
    
    belfold = fetch_top_news(["https://hvg.hu/rss/itthon", "https://telex.hu/rss/belfold"], 5)
    kulfold = fetch_top_news(["https://hvg.hu/rss/vilag", "https://telex.hu/rss/kulfold"], 5)
    tech = fetch_top_news(["https://hvg.hu/rss/tudomany", "https://telex.hu/rss/tech"], 5)
    klima = fetch_top_news(["https://hvg.hu/rss/zold", "https://telex.hu/rss/zold"], 5)
    sport = fetch_top_news(["https://hvg.hu/rss/sport", "https://telex.hu/rss/sport"], 5)

    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family:Arial, sans-serif; color:#333; padding:20px;">
        <h2>Balansz</h2>
        {portfolio_table}
        
        <br><hr><br>
        
        <h3>📈 TOP 3 Tőzsdei & Gazdasági Elemzés (Alpha Focus)</h3>
        {quant_analysis}
        
        <br><hr><br>
        
        <h3>🇭🇺 Belföld (Top 5)</h3>
        {belfold}
        
        <h3>🌍 Külföld (Top 5)</h3>
        {kulfold}
        
        <h3>💻 Tudomány & Tech (Top 5)</h3>
        {tech}
        
        <h3>🌱 Klíma & Zöld (Top 5)</h3>
        {klima}
        
        <h3>⚽ Sport (Top 5)</h3>
        {sport}
    </body>
    </html>
    """
    return html

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
