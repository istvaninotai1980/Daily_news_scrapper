import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import openai  # Vagy ahogy a Gemini/OpenAI API-t hívod a projektedben

# --- BEÁLLÍTÁSOK ---
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD")
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") # Vagy a használt LLM kulcsa

def fetch_raw_financial_news():
    """
    Ide gyűjtöd be a nyers cikkeket és linkeket a Portfolio-ról vagy más forrásokból.
    Példaként egy listát hozunk létre (cím + URL párokkal).
    """
    raw_news = []
    
    # Példa scraping logika (cseréld le a saját hírgyűjtő rutinodra)
    url = "https://www.portfolio.hu/uzlet"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            # Példa szelektálás (igazítsd a Portfolio aktuális DOM struktúrájához)
            articles = soup.select("a.article-title, div.article-card h3 a")
            
            for art in articles[:15]: # Az első 15 nyers hír vizsgálata
                title = art.text.strip()
                link = art.get("href", "")
                if link and not link.startswith("http"):
                    link = "https://www.portfolio.hu" + link
                if title and link:
                    raw_news.append(f"- Cím: {title}\n  Forrás URL: {link}")
    except Exception as e:
        print(f"Hiba a hírek letöltésekor: {e}")
        
    return "\n".join(raw_news)

def generate_quantitative_summary(raw_news_text):
    """
    Lefuttatja a kvantitatív elemző promptot a nyers híreken az LLM segítségével.
    """
    if not raw_news_text:
        return "Nem érkeztek elegendő nyers adatok a mai elemzéshez."

    system_prompt = (
        "Act as a senior quantitative equity analyst and financial journalist. "
        "Your task is to filter a list of raw economic/financial news and generate a highly concentrated, "
        "professional news summary containing exactly the TOP 3 most credible, market-moving stories.\n\n"
        "Focus strictly on information that creates 'alpha' or carries material weight for an investor's portfolio "
        "(e.g., central bank policy shifts, major macroeconomic indicators, corporate earnings surprises of large-cap stocks, "
        "regulatory changes, or structural market trends). Completely eliminate generic PR spin, broad opinion pieces, "
        "and low-impact daily noise.\n\n"
        "Format the output exactly as follows for each of the top 3 stories:\n"
        "### [Sorszám]. 📈 [A hír lényegét összefoglaló, szakmai cím]\n"
        "*   **A hír lényege (Signal):** 1-2 rövid, tömör mondatban mutasd be a tényeket. Mit jelent ez a piac számára?\n"
        "*   **Befektetői hatás (Investor Impact):** Mi a közvetlen implikációja a hírnek? (Pl. szektorspecifikus kockázatok, "
        "eszközallokációs hatás, várható volatilitás).\n"
        "*   **Forrás:** [Kattints a hír eredeti forrásához](IDE ILLESZD BE AZ ADOTT HÍRHEZ TARTOZÓ EREDETI URL-T) - "
        "Fontos: Csak és kizárólag azt az URL-t használd, ami a fenti nyers szövegben az adott hír mellett szerepelt. Ne találj ki linket!\n\n"
        "Rules to follow:\n"
        "- Maintain a clinical, objective, and dense financial tone. Avoid emotional language or hype.\n"
        "- Stick strictly to the provided text. If an original URL is not available in the source data for a story, "
        "use the main domain name (e.g., Portfolio.hu, Bloomberg.com) as anchor text and do not hallucinate a fake full link.\n"
        "- Language of the output: Hungarian."
    )

    user_content = f"Please review the following raw news/text:\n\n{raw_news_text}"

    try:
        # Példa OpenAI hívásra (ha Gemini/más API-t használsz, cseréld le a hívási struktúrát)
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o", # Vagy a kedvenc modellod
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.2 # Alacsony hőmérséklet a klinikai, objektív stílushoz
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Hiba az LLM hívása során: {e}")
        return f"Hiba történt az elemzés generálásakor: {e}"

def send_email(content):
    if not content:
        return

    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL
    msg['Subject'] = "Napi Kvantitatív Piaci Elemzés (Top 3 Alpha)"
    msg.attach(MIMEText(content, 'plain', 'utf-8'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("Napi elemzés e-mailben sikeresen elküldve!")
    except Exception as e:
        print(f"Hiba az e-mail küldésekor: {e}")

if __name__ == "__main__":
    raw_data = fetch_raw_financial_news()
    market_summary = generate_quantitative_summary(raw_data)
    send_email(market_summary)
