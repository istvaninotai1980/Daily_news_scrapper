import os
import smtplib
import requests
import feedparser
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from openai import OpenAI
import yfinance as yf

# --- BEÁLLÍTÁSOK & SECRETS ---
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD")
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# --- 1. IDŐJÁRÁS (PÉCS) ---
def fetch_weather():
    try:
        url = "https://wttr.in/Pecs?format=%C+%t+%w"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return f"Pécs: {response.text.strip()}"
    except Exception as e:
        print(f"Hiba az időjárás lekérésekor: {e}")
    return "Pécs: MÉRTA/Adat átmenetileg nem elérhető"

# --- 2. PIACI MUTATÓK ---
def fetch_market_tickers():
    tickers = {
        "S&P 500": "^GSPC",
        "NASDAQ": "^IXIC",
        "BUX": "^BUX",
        "EUR/HUF": "EURHUF=X",
        "USD/HUF": "USDHUF=X"
    }
    summary = []
    for name, symbol in tickers.items():
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period="2d")
            if len(data) >= 2:
                prev_close = data['Close'].iloc[-2]
                curr_close = data['Close'].iloc[-1]
                pct_change = ((curr_close - prev_close) / prev_close) * 100
                color = "#2e7d32" if pct_change >= 0 else "#c62828"
                summary.append(f"<b>{name}:</b> {curr_close:.2f} (<span style='color:{color};'>{pct_change:+.2f}%</span>)")
        except Exception as e:
            print(f"Hiba a {name} lekérésénél: {e}")
    return " &nbsp;|&nbsp; ".join(summary) if summary else "Piaci adatok átmenetileg nem elérhetők."

# --- 3. GAZDASÁGI / TŐZSDEI HÍRGYŰJTŐ ---
def fetch_raw_financial_news():
    raw_news = []
    feed_urls = [
        "https://www.portfolio.hu/rss/all.xml",
        "https://hvg.hu/rss/gazdasag",
        "https://index.hu/24ora/rss/?f=gazdasag"
    ]
    for feed_url in feed_urls:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:8]:
                title = entry.title.strip()
                link = entry.link.strip()
                summary = getattr(entry, 'summary', '')
                clean_summary = BeautifulSoup(summary, "html.parser").text.strip() if summary else ""
                if not any(link in item for item in raw_news):
                    raw_news.append(f"- Cím: {title}\n  Részletek: {clean_summary[:200]}\n  URL: {link}")
        except Exception as e:
            print(f"Hiba a forrás olvasásakor ({feed_url}): {e}")
            
    return "\n\n".join(raw_news[:15])

# --- 4. TOP 3 TŐZSDEI ELEMZÉS (ÚJ QUANT PROMPT) ---
def get_quant_market_summary(raw_news_text, market_data):
    if not client or not raw_news_text:
        return "<p>Tőzsdei elemzés nem érhető el.</p>"

    system_prompt = (
        "Act as a senior quantitative equity analyst and financial journalist. "
        "Your task is to filter a list of raw economic/financial news and generate a highly concentrated, "
        "professional news summary containing exactly the TOP 3 most credible, market-moving stories.\n\n"
        "Focus strictly on information that creates 'alpha' or carries material weight for an investor's portfolio "
        "(e.g., central bank policy shifts, major macroeconomic indicators, corporate earnings surprises of large-cap stocks, "
        "regulatory changes, or structural market trends). Completely eliminate generic PR spin, broad opinion pieces, "
        "and low-impact daily noise.\n\n"
        "Format the output using HTML tags so it renders cleanly in an email body. For each of the top 3 stories use this structure:\n"
        "<div style='margin-bottom: 20px; padding: 12px; border-left: 4px solid #1976d2; background-color: #f8f9fa;'>"
        "<h3 style='margin-top:0; color:#0d47a1;'>[Sorszám]. 📈 [A hír lényegét összefoglaló, szakmai cím]</h3>"
        "<p><b>A hír lényege (Signal):</b> 1-2 rövid, tömör mondatban mutasd be a tényeket. Mit jelent ez a piac számára?</p>"
        "<p><b>Befektetői hatás (Investor Impact):</b> Mi a közvetlen implikációja a hírnek? (Pl. szektorspecifikus kockázatok, eszközallokációs hatás, várható volatilitás).</p>"
        "<p><b>Forrás:</b> <a href='IDE ILLESZD BE AZ ADOTT HÍRHEZ TARTOZÓ EREDETI URL-T' target='_blank'>Kattints a hír eredeti forrásához</a></p>"
        "</div>\n\n"
        "Rules to follow:\n"
        "- Maintain a clinical, objective, and dense financial tone. Avoid emotional language or hype.\n"
        "- Stick strictly to the provided text. If an original URL is not available in the source data for a story, "
        "use the main domain name (e.g., Portfolio.hu, Bloomberg.com) as anchor text and do not hallucinate a fake full link.\n"
        "- Language of the output: Hungarian."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Aktuális piaci mutatók:\n{market_data}\n\nNyers hírek:\n{raw_news_text}"}
            ],
            temperature=0.2
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"LLM hiba: {e}")
        return "<p>Hiba történt a tőzsdei elemzés generálása során.</p>"

# --- 5. BELFÖLDI / KÜLFÖLDI HÍREK ---
def fetch_general_category_html(feed_url, limit=4):
    html_items = []
    try:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:limit]:
            title = entry.title.strip()
            link = entry.link.strip()
            html_items.append(f"<li style='margin-bottom: 8px;'><a href='{link}' style='color: #1a0dab; text-decoration: none; font-weight: bold;' target='_blank'>{title}</a></li>")
    except Exception as e:
        print(f"Hiba a(z) {feed_url} lekérésekor: {e}")
    return f"<ul style='padding-left: 20px; margin: 0;'>{''.join(html_items)}</ul>" if html_items else "<p>Nincsenek elérhető hírek.</p>"

# --- 6. TELJES HTML HÍRLEVÉL KÓD ---
def build_full_newsletter_html():
    weather = fetch_weather()
    market_tickers = fetch_market_tickers()
    
    raw_fin = fetch_raw_financial_news()
    quant_summary = get_quant_market_summary(raw_fin, market_tickers)
    
    belfold_html = fetch_general_category_html("https://index.hu/24ora/rss/?f=belfold")
    kulfold_html = fetch_general_category_html("https://index.hu/24ora/rss/?f=kulfold")

    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #f4f6f9; color: #333333; margin: 0; padding: 20px; }}
            .container {{ max-width: 680px; margin: 0 auto; background: #ffffff; border-radius: 8px; padding: 25px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }}
            .header {{ text-align: center; border-bottom: 2px solid #e0e0e0; padding-bottom: 15px; margin-bottom: 20px; }}
            .header h1 {{ margin: 0; color: #1a237e; font-size: 24px; }}
            .section {{ margin-bottom: 25px; }}
            .section-title {{ font-size: 18px; color: #1565c0; border-bottom: 1px solid #bbdefb; padding-bottom: 5px; margin-bottom: 12px; }}
            .market-box {{ background: #eef2f7; padding: 12px; border-radius: 6px; font-size: 14px; line-height: 1.6; text-align: center; }}
            .footer {{ text-align: center; font-size: 12px; color: #777777; margin-top: 30px; border-top: 1px solid #eeeeee; padding-top: 10px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📰 Napi Automatizált Hírlevél</h1>
                <p style="margin: 5px 0 0 0; color: #666666; font-size: 14px;">🌤️ {weather}</p>
            </div>

            <div class="section">
                <div class="section-title">📊 Friss Piaci Mutatók</div>
                <div class="market-box">{market_tickers}</div>
            </div>

            <div class="section">
                <div class="section-title">📈 TOP 3 Tőzsdei & Gazdasági Elemzés (Alpha Focus)</div>
                {quant_summary}
            </div>

            <div class="section">
                <div class="section-title">🇭🇺 Belföldi Hírek</div>
                {belfold_html}
            </div>

            <div class="section">
                <div class="section-title">🌍 Külföldi Hírek</div>
                {kulfold_html}
            </div>

            <div class="footer">
                A hírlevél automatikusan frissült a GitHub Actions segítségével.
            </div>
        </div>
    </body>
    </html>
    """
    return html_template

# --- 7. E-MAIL KÜLDÉS (MIME HTML) ---
def send_email(html_content):
    if not html_content:
        return

    msg = MIMEMultipart('alternative')
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL
    msg['Subject'] = "Napi Hírlevél & Kvantitatív Piaci Összefoglaló"

    part_html = MIMEText(html_content, 'html', 'utf-8')
    msg.attach(part_html)

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("E-mail sikeresen elküldve!")
    except Exception as e:
        print(f"Hiba az e-mail küldésekor: {e}")

if __name__ == "__main__":
    html_body = build_full_newsletter_html()
    send_email(html_body)
