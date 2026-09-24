import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ==========================================
# 1. GMAIL CSATLAKOZÁSI ADATOK
# ==========================================
# Figyelem: A SENDER_PASSWORD-höz a Google-fiókodban generált 16 jegyű "Alkalmazásjelszó" (App Password) kell!
SENDER_EMAIL = "saját.email@gmail.com"      # A Gmail címed
SENDER_PASSWORD = "xxxx xxxx xxxx xxxx"    # 16 jegyű Gmail App Password
RECEIVER_EMAIL = "saját.email@gmail.com"    # Címzett e-mail címe

# ==========================================
# 2. ADATSZERKEZET: PONTOS VÉTELI TÉTELEK (TAX LOTS)
# ==========================================

trade_lots = [
    # META PLATFORMS (META) vásárlások
    {
        "ticker": "META",
        "name": "Meta Platforms (Lot 1)",
        "buy_date": "2026-08-15",
        "buy_price": 660.52,
        "shares": 1.0
    },
    {
        "ticker": "META",
        "name": "Meta Platforms (Lot 2 - Ma 15:30)",
        "buy_date": "2026-09-24",
        "buy_price": 740.98,     # Mai vételi ár
        "shares": 0.73           # Mai vásárolt darabszám
    },

    # NVIDIA (NVDA) vásárlások
    {
        "ticker": "NVDA",
        "name": "NVIDIA Corp (Lot 1)",
        "buy_date": "2026-07-15",
        "buy_price": 125.50,
        "shares": 0.8
    },
    {
        "ticker": "NVDA",
        "name": "NVIDIA Corp (Lot 2 - BTD)",
        "buy_date": "2026-08-20",
        "buy_price": 118.20,
        "shares": 0.7
    },
    
    # GOOGLE (GOOGL) vásárlások
    {
        "ticker": "GOOGL",
        "name": "Alphabet Inc (Lot 1)",
        "buy_date": "2026-09-09",
        "buy_price": 331.36,
        "shares": 1.0
    },
    {
        "ticker": "GOOGL",
        "name": "Alphabet Inc (Lot 2 - Szept 22)",
        "buy_date": "2026-09-22",
        "buy_price": 352.82,
        "shares": 0.992
    },

    # BROOKFIELD (BN) vásárlás
    {
        "ticker": "BN",
        "name": "Brookfield Corp (Lot 1 - Szept 22)",
        "buy_date": "2026-09-22",
        "buy_price": 38.165,
        "shares": 12.4458
    },

    # TSMC (TSM) vásárlás
    {
        "ticker": "TSM",
        "name": "Taiwan Semi ADR (Lot 1)",
        "buy_date": "2026-08-10",
        "buy_price": 394.585,
        "shares": 0.8895
    }
]

# Aktuális piaci árak (USD)
current_market_prices = {
    "META": 744.35,
    "NVDA": 132.80,
    "GOOGL": 352.37,
    "BN": 38.14,
    "TSM": 427.98
}

# ==========================================
# 3. HTML HÍRLEVÉL FORMÁZÁS ÉS LEVÉLTÖRZS
# ==========================================

def build_email_html():
    grouped_lots = {}
    for lot in trade_lots:
        grouped_lots.setdefault(lot["ticker"], []).append(lot)

    table_rows_html = ""
    total_cost_all = 0.0
    total_mkt_val_all = 0.0

    for ticker, lot_list in grouped_lots.items():
        curr_price = current_market_prices.get(ticker, 0.0)
        tot_shares = 0.0
        tot_cost = 0.0
        
        # Egyedi tételek sora (Halvány szürke szöveg)
        for lot in lot_list:
            shares = lot["shares"]
            buy_price = lot["buy_price"]
            cost = shares * buy_price
            mkt_val = shares * curr_price
            pnl = mkt_val - cost
            btd_return = ((curr_price - buy_price) / buy_price) * 100 if buy_price > 0 else 0.0
            
            tot_shares += shares
            tot_cost += cost
            total_cost_all += cost
            total_mkt_val_all += mkt_val

            table_rows_html += f"""
            <tr style="color: #a0a0a0; font-size: 13px;">
                <td style="padding: 8px; border-bottom: 1px solid #333;">{lot['name']}</td>
                <td style="padding: 8px; border-bottom: 1px solid #333;">{lot['buy_date']}</td>
                <td style="padding: 8px; border-bottom: 1px solid #333;">{shares:.4f}</td>
                <td style="padding: 8px; border-bottom: 1px solid #333;">${buy_price:.2f}</td>
                <td style="padding: 8px; border-bottom: 1px solid #333;">${curr_price:.2f}</td>
                <td style="padding: 8px; border-bottom: 1px solid #333; color: {'#4CAF50' if pnl>=0 else '#F44336'};">${pnl:+.2f}</td>
                <td style="padding: 8px; border-bottom: 1px solid #333; color: {'#4CAF50' if btd_return>=0 else '#F44336'};">{btd_return:+.2f}%</td>
            </tr>
            """

        # Akkumulált sor (Félkövér fehér kiemelés sötét háttérrel), ha több tétel van
        if len(lot_list) > 1:
            avg_buy_price = tot_cost / tot_shares
            tot_mkt_val = tot_shares * curr_price
            tot_pnl = tot_mkt_val - tot_cost
            tot_return = ((tot_mkt_val - tot_cost) / tot_cost) * 100 if tot_cost > 0 else 0.0

            table_rows_html += f"""
            <tr style="color: #ffffff; font-weight: bold; background-color: #252830; font-size: 14px;">
                <td style="padding: 10px; border-bottom: 2px solid #555;">&gt;&gt;&gt; {ticker} ÖSSZESÍTVE (Akkumulált)</td>
                <td style="padding: 10px; border-bottom: 2px solid #555;">Összesítés</td>
                <td style="padding: 10px; border-bottom: 2px solid #555;">{tot_shares:.4f}</td>
                <td style="padding: 10px; border-bottom: 2px solid #555;">${avg_buy_price:.2f} (Átlag)</td>
                <td style="padding: 10px; border-bottom: 2px solid #555;">${curr_price:.2f}</td>
                <td style="padding: 10px; border-bottom: 2px solid #555; color: {'#4CAF50' if tot_pnl>=0 else '#F44336'};">${tot_pnl:+.2f}</td>
                <td style="padding: 10px; border-bottom: 2px solid #555; color: {'#4CAF50' if tot_return>=0 else '#F44336'};">{tot_return:+.2f}%</td>
            </tr>
            """

    total_pnl_all = total_mkt_val_all - total_cost_all
    total_return_all = ((total_mkt_val_all - total_cost_all) / total_cost_all) * 100 if total_cost_all > 0 else 0.0

    html_template = f"""
    <html>
    <body style="background-color: #1a1a1a; color: #ffffff; font-family: Arial, sans-serif; padding: 20px;">
        <h2 style="color: #ffffff; text-align: center;">FALCON PORTFÓLIÓ DIVERZIFIKÁLT BTD RIPORT</h2>
        <table style="width: 100%; border-collapse: collapse; background-color: #222222; margin-top: 20px;">
            <thead>
                <tr style="background-color: #333333; color: #ffffff; text-align: left; font-size: 14px;">
                    <th style="padding: 10px;">Megnevezés</th>
                    <th style="padding: 10px;">Dátum</th>
                    <th style="padding: 10px;">Darab</th>
                    <th style="padding: 10px;">Vételi Ár</th>
                    <th style="padding: 10px;">Piaci Ár</th>
                    <th style="padding: 10px;">P&L ($)</th>
                    <th style="padding: 10px;">Hozam (%)</th>
                </tr>
            </thead>
            <tbody>
                {table_rows_html}
            </tbody>
        </table>
        
        <div style="margin-top: 30px; background-color: #2d2d2d; padding: 15px; border-radius: 5px;">
            <h3 style="margin-top: 0; color: #ffffff;">TELJES PORTFÓLIÓ ÖSSZESÍTŐ MÉRLEG</h3>
            <p><strong>Teljes Befektetett Tőke:</strong> ${total_cost_all:,.2f}</p>
            <p><strong>Jelenlegi Piaci Érték:</strong> ${total_mkt_val_all:,.2f}</p>
            <p><strong>Nem Realizált Profit:</strong> <span style="color: {'#4CAF50' if total_pnl_all>=0 else '#F44336'};">${total_pnl_all:+,.2f}</span></p>
            <p><strong>Súlyozott BTD Hozam:</strong> <span style="color: {'#4CAF50' if total_return_all>=0 else '#F44336'};">{total_return_all:+.2f}%</span></p>
        </div>
    </body>
    </html>
    """
    return html_template

# ==========================================
# 4. LEVÉL KÜLDÉSE GMAIL SMTP-N KERESZTÜL
# ==========================================

def send_gmail_newsletter():
    html_content = build_email_html()
    
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Falcon Portfólió Frissítés & Tax Lots Riport"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL

    msg.attach(MIMEText(html_content, "html"))

    try:
        print("Csatlakozás a Gmail SMTP szerverhez...")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        print("SIKER! A hírlevél sikeresen megérkezett a Gmail fiókodba.")
    except Exception as e:
        print(f"Hiba történt a kiküldés során: {e}")

if __name__ == "__main__":
    send_gmail_newsletter()
