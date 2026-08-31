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

# --- 1. IDŐJÁRÁS ELŐREJELZÉS ---
def fetch_weather():
    try:
        # Pécs / Regionális időjárás lekérése
        url = "https://wttr.in/Pecs?format=3"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.text.strip()
    except Exception as e:
        print(f"Hiba az időjárás lekérésekor: {e}")
    return "Időjárás adatok átmenetileg nem érhetők el."

# --- 2. RÉSZVÉNY & PIACI STATISZTIKÁK ---
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
                summary.append(f"{name}: {curr_close:.2f} ({pct_change:+.2f}%)")
        except Exception as e:
            print(f"Hiba a {name} lekérésénél: {e}")
    return " | ".join(summary) if summary else "Piaci adatok nem érhetők el."

# --- 3. TŐZSDEI / GAZDASÁGI NYERS HÍREK ---
def fetch_raw_financial_news():
    raw_news = []
    feed_urls = [
        "https://www.portfolio.hu/rss/all.xml",
        "https://hvg.hu/rss/gazdasag"
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

# --- 4. KVANTITATÍV TOP 3 TŐZSDEI ELEMZÉS (ÚJ PROMPT) ---
def get_quant_market_summary(raw_news_text, market_data):
    if not client or not raw_news_text:
        return "Tőzsdei elemzés nem érhető el."

    system_prompt = (
        "Act as a senior quantitative equity analyst and financial journalist. "
        "Your task is to filter a list of raw economic/financial news and generate a highly concentrated, "
        "professional news summary containing exactly the TOP 3 most credible, market-moving stories.\n\n"
        "Focus strictly on information that creates 'alpha' or carries material weight for an investor's portfolio "
        "(e.g., central bank policy shifts, major macroeconomic indicators, corporate earnings surprises of large-cap stocks, "
        "regulatory changes, or structural market trends). Completely eliminate generic PR spin, broad opinion pieces, "
        "and low-impact daily noise.\n\n"
        "Format the output exactly as follows for each of the top 3 stories:\n"
        "1. 📈 [A hír lényegét összefoglaló, szakmai cím]\n"
        "   • A hír lényege (Signal): 1-2 rövid, tömör mondatban mutasd be a tényeket. Mit jelent ez a piac számára?\n"
        "   • Befektetői hatás (Investor Impact): Mi a közvetlen implikációja a hírnek? (Pl. szektorspecifikus kockázatok, eszközallokációs hatás, várható volatilitás).\n"
        "   • Forrás: [Kattints a hír eredeti forrásához](IDE ILLESZD BE AZ ADOTT HÍRHEZ TARTOZÓ EREDETI URL-T) - "
        "Fontos: Csak és kizárólag azt az URL-t használd, ami a fenti nyers szövegben az adott hír mellett szerepelt. Ne találj ki linket!\n\n"
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
        return "Hiba történt a tőzsdei elemzés generálása során."

# --- 5. BELFÖLDI ÉS KÜLFÖLDI HÍREK GYŰJTÉSE ---
def fetch_general_category(feed_url, limit=4):
    items = []
    try:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:limit]:
            title = entry.title.strip()
            link = entry.link.strip()
            items.append(f"• {title}\n  Link: {link}")
    except Exception as e:
        print(f"Hiba a(z) {feed_url} lekérésekor: {e}")
    return "\n\n".join(items) if items else "Nincsenek elérhető hírek."

# --- 6. TELJES HÍRLEVÉL STRUKTÚRA ÖSSZEÁLLÍTÁSA ---
def build_full_newsletter():
    weather = fetch_weather()
    market_tickers = fetch_market_tickers()
    
    # Gazdaság
    raw_fin = fetch_raw_financial_news()
    quant_summary = get_quant_market_summary(raw_fin, market_tickers)
    
    # Belföld és Külföld
    belfold_news = fetch_general_category("https://index.hu/24ora/rss/?f=belfold")
    kulfold_news = fetch_general_category("https://index.hu/24ora/rss/?f=kulfold")

    newsletter_body = f"""NAPI AUTOMATIZÁLT HÍRLEVÉL

========================================
🌤️ IDŐJÁRÁS
========================================
{weather}

========================================
📊 RÉSZVÉNY & PIACI STATISZTIKÁK
========================================
{market_tickers}

========================================
📈 TOP 3 TŐZSDEI & GAZDASÁGI ELEMZÉS (ALPHA FOCUS)
========================================
{quant_summary}

========================================
🇭🇺 BELFÖLDI HÍREK
========================================
{belfold_news}

========================================
🌍 KÜLFÖLDI HÍREK
========================================
{kulfold_news}

----------------------------------------
A hírlevél automatikusan frissült a GitHub Actions segítségével.
"""
    return newsletter_body

# --- 7. E-MAIL KÜLDÉS ---
def send_email(content):
    if not content:
        return

    msg = MIMEText(content, 'plain', 'utf-8')
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL
    msg['Subject'] = "Napi Hírlevél & Kvantitatív Piaci Összefoglaló"

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
    full_content = build_full_newsletter()
    send_email(full_content)
