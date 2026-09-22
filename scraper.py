import pandas as pd

# ANSI Színkódok a terminál / hírlevél formázáshoz
GRAY = "\033[90m"      # Halvány szürke az egyedi tételekhez (Lots)
WHITE_BOLD = "\033[1;37m" # Félkövér fehér az akkumulált sorokhoz (Total)
RESET = "\033[0m"      # Színbeállítás visszaállítása

# ==========================================
# 1. ADATSZERKEZET: PONTOS VÉTELI TÉTELEK (TAX LOTS)
# ==========================================

trade_lots = [
    # NVIDIA (NVDA) vásárlások
    {
        "ticker": "NVDA",
        "name": "NVIDIA Corp (Lot 1)",
        "buy_date": "2026-07-15",
        "buy_price": 125.50,
        "shares": 0.8,
        "is_total_row": False
    },
    {
        "ticker": "NVDA",
        "name": "NVIDIA Corp (Lot 2 - BTD)",
        "buy_date": "2026-08-20",
        "buy_price": 118.20,
        "shares": 0.7,
        "is_total_row": False
    },
    
    # GOOGLE (GOOGL) vásárlások
    {
        "ticker": "GOOGL",
        "name": "Alphabet Inc (Lot 1)",
        "buy_date": "2026-09-09",
        "buy_price": 331.36,
        "shares": 1.0,
        "is_total_row": False
    },
    {
        "ticker": "GOOGL",
        "name": "Alphabet Inc (Lot 2 - Ma)",
        "buy_date": "2026-09-22",
        "buy_price": 352.82,     # Ma vásárolt ár
        "shares": 0.992,         # Ma vásárolt darabszám
        "is_total_row": False
    },

    # BROOKFIELD (BN) vásárlás
    {
        "ticker": "BN",
        "name": "Brookfield Corp (Lot 1 - Ma)",
        "buy_date": "2026-09-22",
        "buy_price": 38.165,     # Ma vásárolt ár
        "shares": 12.4458,       # Ma vásárolt darabszám
        "is_total_row": False
    },

    # TSMC (TSM) vásárlás
    {
        "ticker": "TSM",
        "name": "Taiwan Semi ADR (Lot 1)",
        "buy_date": "2026-08-10",
        "buy_price": 394.585,
        "shares": 0.8895,
        "is_total_row": False
    }
]

# Aktuális piaci árak (USD)
current_market_prices = {
    "NVDA": 132.80,
    "GOOGL": 352.37,   # Friss piaci ár a képernyőképed alapján
    "BN": 38.14,       # Friss piaci ár a képernyőképed alapján
    "TSM": 427.98
}

# ==========================================
# 2. FELDOLGOZÁS ÉS AKKUMULÁCIÓ SZÁMÍTÁS
# ==========================================

def generate_lot_and_total_report(lots, market_prices):
    # Csoportosítás ticker szerint az akkumuláláshoz
    grouped_lots = {}
    for lot in lots:
        ticker = lot["ticker"]
        grouped_lots.setdefault(ticker, []).append(lot)

    rows = []

    for ticker, lot_list in grouped_lots.items():
        curr_price = market_prices.get(ticker, 0.0)
        
        tot_shares = 0.0
        tot_cost = 0.0
        
        # Egyedi tételek feldolgozása (Halvány szürke)
        for lot in lot_list:
            shares = lot["shares"]
            buy_price = lot["buy_price"]
            cost = shares * buy_price
            mkt_val = shares * curr_price
            pnl = mkt_val - cost
            btd_return = ((curr_price - buy_price) / buy_price) * 100 if buy_price > 0 else 0.0
            
            tot_shares += shares
            tot_cost += cost

            rows.append({
                "Típus": "LOT",
                "Megnevezés": lot["name"],
                "Ticker": ticker,
                "Dátum": lot["buy_date"],
                "Darab": f"{shares:.4f}",
                "Vételi Ár": f"${buy_price:.2f}",
                "Piaci Ár": f"${curr_price:.2f}",
                "Befektetett Tőke": f"${cost:.2f}",
                "Piaci Érték": f"${mkt_val:.2f}",
                "P&L ($)": f"${pnl:+.2f}",
                "BTD Hozam (%)": f"{btd_return:+.2f}%"
            })
        
        # Ha több mint 1 tétel van az adott részvényből, akkumulált sor generálása (Fehér)
        if len(lot_list) > 1:
            avg_buy_price = tot_cost / tot_shares
            tot_mkt_val = tot_shares * curr_price
            tot_pnl = tot_mkt_val - tot_cost
            tot_return = ((tot_mkt_val - tot_cost) / tot_cost) * 100 if tot_cost > 0 else 0.0

            rows.append({
                "Típus": "TOTAL",
                "Megnevezés": f">>> {ticker} ÖSSZESÍTVE (Akkumulált)",
                "Ticker": ticker,
                "Dátum": "Összesített",
                "Darab": f"{tot_shares:.4f}",
                "Vételi Ár": f"${avg_buy_price:.2f} (Átlag)",
                "Piaci Ár": f"${curr_price:.2f}",
                "Befektetett Tőke": f"${tot_cost:.2f}",
                "Piaci Érték": f"${tot_mkt_val:.2f}",
                "P&L ($)": f"${tot_pnl:+.2f}",
                "BTD Hozam (%)": f"{tot_return:+.2f}%"
            })

    return rows

# ==========================================
# 3. TERMINÁL KIÍRATÁS SZÍNEZÉSSEL
# ==========================================

def print_formatted_report():
    report_rows = generate_lot_and_total_report(trade_lots, current_market_prices)
    
    print("========================================================================================================================")
    print("                                FALCON PORTFÓLIÓ DIVERZIFIKÁLT BTD RIPORT (TAX LOTS)                                   ")
    print("========================================================================================================================")
    
    header = f"{'Megnevezés':<32} | {'Dátum':<11} | {'Darab':<8} | {'Vételi Ár':<15} | {'Piaci Ár':<10} | {'P&L ($)':<10} | {'Hozam (%)':<10}"
    print(header)
    print("-" * 120)

    for row in report_rows:
        line = f"{row['Megnevezés']:<32} | {row['Dátum']:<11} | {row['Darab']:<8} | {row['Vételi Ár']:<15} | {row['Piaci Ár']:<10} | {row['P&L ($)']:<10} | {row['BTD Hozam (%)']:<10}"
        
        # Színezési logika: Egyedi tételek szürkék, Akkumulált sorok félkövér fehérek
        if row["Típus"] == "LOT":
            print(f"{GRAY}{line}{RESET}")
        else:
            print(f"{WHITE_BOLD}{line}{RESET}")

    print("========================================================================================================================")

if __name__ == "__main__":
    print_formatted_report()
