import pandas as pd

# ANSI Színkódok a terminál formázásához
GRAY = "\033[90m"         # Halvány szürke az egyedi tételekhez (Tax Lots)
WHITE_BOLD = "\033[1;37m" # Félkövér fehér az akkumulált sorokhoz (Total)
RESET = "\033[0m"         # Színbeállítás visszaállítása

# ==========================================
# 1. ADATSZERKEZET: PONTOS VÉTELI TÉTELEK (TAX LOTS)
# ==========================================

trade_lots = [
    # META PLATFORMS (META) vásárlások
    {
        "ticker": "META",
        "name": "Meta Platforms (Lot 1)",
        "buy_date": "2026-08-15",
        "buy_price": 660.52,     # Korábbi vételi ár
        "shares": 1.0
    },
    {
        "ticker": "META",
        "name": "Meta Platforms (Lot 2 - Ma 15:30)",
        "buy_date": "2026-09-24",
        "buy_price": 740.98,     # Mai vételi ár (Szept 24. nyitási ár)
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
# 2. FELDOLGOZÁS ÉS AKKUMULÁCIÓ SZÁMÍTÁS
# ==========================================

def generate_lot_and_total_report(lots, market_prices):
    grouped_lots = {}
    for lot in lots:
        ticker = lot["ticker"]
        grouped_lots.setdefault(ticker, []).append(lot)

    rows = []
    
    # Globális összegzéshez
    global_cost = 0.0
    global_mkt_val = 0.0

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
            
            global_cost += cost
            global_mkt_val += mkt_val

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
        
        # Akkumulált sor generálása (Fehér), ha 1-nél több tétel van az adott részvényből
        if len(lot_list) > 1:
            avg_buy_price = tot_cost / tot_shares
            tot_mkt_val = tot_shares * curr_price
            tot_pnl = tot_mkt_val - tot_cost
            tot_return = ((tot_mkt_val - tot_cost) / tot_cost) * 100 if tot_cost > 0 else 0.0

            rows.append({
                "Típus": "TOTAL",
                "Megnevezés": f">>> {ticker} ÖSSZESÍTVE (Akkumulált)",
                "Ticker": ticker,
                "Dátum": "Összesítés",
                "Darab": f"{tot_shares:.4f}",
                "Vételi Ár": f"${avg_buy_price:.2f} (Átlag)",
                "Piaci Ár": f"${curr_price:.2f}",
                "Befektetett Tőke": f"${tot_cost:.2f}",
                "Piaci Érték": f"${tot_mkt_val:.2f}",
                "P&L ($)": f"${tot_pnl:+.2f}",
                "BTD Hozam (%)": f"{tot_return:+.2f}%"
            })

    return rows, global_cost, global_mkt_val

# ==========================================
# 3. TERMINÁL KIÍRATÁS ÉS RIPORT GENERÁLÁS
# ==========================================

def print_formatted_report():
    report_rows, total_cost, total_val = generate_lot_and_total_report(trade_lots, current_market_prices)
    
    print("\n========================================================================================================================")
    print("                                FALCON PORTFÓLIÓ DIVERZIFIKÁLT BTD RIPORT (TAX LOTS)                                   ")
    print("========================================================================================================================")
    
    header = f"{'Megnevezés':<35} | {'Dátum':<11} | {'Darab':<8} | {'Vételi Ár':<16} | {'Piaci Ár':<10} | {'P&L ($)':<10} | {'Hozam (%)':<10}"
    print(header)
    print("-" * 120)

    for row in report_rows:
        line = f"{row['Megnevezés']:<35} | {row['Dátum']:<11} | {row['Darab']:<8} | {row['Vételi Ár']:<16} | {row['Piaci Ár']:<10} | {row['P&L ($)']:<10} | {row['BTD Hozam (%)']:<10}"
        
        # Színezés: LOT szürke, TOTAL félkövér fehér
        if row["Típus"] == "LOT":
            print(f"{GRAY}{line}{RESET}")
        else:
            print(f"{WHITE_BOLD}{line}{RESET}")

    print("========================================================================================================================")
    
    # TELJES PORTFÓLIÓ ÖSSZESÍTŐ KIÍRÁSA
    total_pnl = total_val - total_cost
    total_return_pct = ((total_val - total_cost) / total_cost) * 100 if total_cost > 0 else 0.0
    
    print("\nTELJES PORTFÓLIÓ ÖSSZESÍTŐ MÉRLEG:")
    print(f" -> Teljes Befektetett Tőke:  ${total_cost:,.2f}")
    print(f" -> Jelenlegi Piaci Érték:   ${total_val:,.2f}")
    print(f" -> Nem Realizált Profit:    ${total_pnl:+,.2f}")
    print(f" -> Súlyozott BTD Hozam:     {total_return_pct:+.2f}%\n")

# A kód automatikus lefuttatása
if __name__ == "__main__":
    print_formatted_report()
