import os
import smtplib
import requests
import feedparser
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from openai import OpenAI
import yfinance as yf

# --- BEÁLLÍTÁSOK & SECRETS ---
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD")
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# --- 1. FRISS PIACI ADATOK LEKÉRÉSE ---
def fetch_market_tickers():
    tickers = {
        "S&P 500": "^GSPC",
        "NASDAQ": "^IXIC",
        "BUX": "^BUX",
        "EUR/HUF": "EURHUF=X"
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
    return " | ".join(summary) if summary else "Piac-specifikus adatok átmenetileg nem elérhetők."

# --- 2. MULTI-FEED TŐZSDEI HÍRGYŰJTŐ ---
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

    if not raw_news:
        raw_news.append("- Cím: Global Market Movement Summary\n  Részletek: Macroeconomic policy and market shifts.\n  URL: https://www.bloomberg.com")

    return "\n\n".join(raw_news[:20])

# --- 3. KVANTITATÍV PIACI ELEMZÉS ---
def get_quant_market_summary(raw_news_text, market_data):
    if not client:
        return "Az API kulcs hiányzik a tőzsdei elemzés generálásához."

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

    user_content = f"Aktuális piaci mutatók:\n{market_data}\n\nNyers hírek:\n{raw_news_text}"

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.2
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"LLM hiba: {e}")
        return "Hiba történt a tőzsdei elemzés generálása során."

# --- 4. ÁLTALÁNOS HÍREK LEKÉRÉSE ---
def fetch_general_news():
    general_news = []
    feed_urls = [
        "https://hvg.hu/rss",
        "https://index.hu/24ora/rss/"
    ]
    for url in feed_urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:
                general_news.append(f"• {entry.title}\n  Link: {entry.link}")
        except Exception as e:
            print(f"Hiba az általános híreknél ({url}): {e}")
            
    return "\n\n".join(general_news) if general_news else "Általános hírek átmenetileg nem érhetők el."

# --- 5. HÍRLEVÉL ÖSSZEÁLLÍTÁSA ---
def build_full_newsletter():
    print("Piaci mutatók és hírek gyűjtése...")
    market_tickers = fetch_market_tickers()
    raw_news = fetch_raw_financial_news()
    quant_summary = get_quant_market_summary(raw_news, market_tickers)
    
    print("Általános hírek gyűjtése...")
    gen_news = fetch_general_news()

    newsletter_body = f"""NAPI AUTOMATIZÁLT HÍRLEVÉL

========================================
FRISS PIACI MUTATÓK
========================================
{market_tickers}

========================================
TOP 3 TŐZSDEI & GAZDASÁGI ELEMZÉS (ALPHA FOCUS)
========================================

{quant_summary}

========================================
FŐBB ÁLTALÁNOS HÍREK
========================================

{gen_news}

----------------------------------------
A hírlevél automatikusan frissült a GitHub Actions segítségével.
"""
    return newsletter_body

# --- 6. E-MAIL KÜLDÉS ---
def send_email(content):
    if not content:
        print("Üres tartalom, e-mail nem kerül kiküldésre.")
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
