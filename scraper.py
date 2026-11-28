import os
import time
import smtplib
import requests
import feedparser
import pandas as pd
import yfinance as yf
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from openai import OpenAI

# --- SECRETS & SETUP ---
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD")
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL")

# --- PORTFÓLIÓ ESZKÖZÖK PONTOS IBKR ADATOKKAL ÉS BONTÁSSAL ---
PORTFOLIO = [
    # BROADCOM (Többütemű vásárlás - IBKR: 1.54 db)
    {
        "name": "Broadcom Sum (AVGO Sum)", 
        "symbols": ["AVGO"], 
        "is_sum": True, 
        "currency": "USD", 
        "buy_price_override": 368.38,
        "sub_items": [
            {"name": "└─ Broadcom 1 (AVGO 1)", "pos": 0.54, "buy_date": "2026-08-28"},
            {"name": "└─ Broadcom 2 (AVGO 2)", "pos": 1.00, "buy_date": "2026-09-10", "buy_price_override": 363.10}
        ]
    },
    # AMAZON (Többütemű vásárlás - IBKR: 4.4759 db)
    {
        "name": "Amazon Sum (AMZ Sum)", 
        "symbols": ["AMZ.DE", "AMZN"], 
        "is_sum": True, 
        "currency": "EUR", 
        "buy_price_override": 215.90,
        "sub_items": [
            {"name": "└─ Amazon 1 (AMZ 1)", "pos": 2.9759, "buy_date": "2026-07-29"},
            {"name": "└─ Amazon 2 (AMZ 2)", "pos": 1.5000, "buy_date": "2026-09-03", "buy_price_override": 216.47}
        ]
    },
    # ALPHABET / GOOGLE (Split-korrigált dinamikus számítás - IBKR: 1.992 db)
    {
        "name": "Alphabet Sum (GOOGL Sum)", 
        "symbols": ["GOOGL", "GOOG"], 
        "is_sum": True, 
        "currency": "USD", 
        "sub_items": [
            {"name": "└─ Alphabet 1 (GOOGL 1)", "pos": 0.992, "buy_date": "2026-09-09"},
            {"name": "└─ Alphabet 2 (GOOGL 2)", "pos": 1.000, "buy_date": "2026-09-22"}
        ]
    },
    # NVIDIA IBIS (Többütemű vásárlás - IBKR: 2.4 db)
    {
        "name": "Nvidia IBIS Sum (NVD Sum)", 
        "symbols": ["NVD.DE", "NVDA"], 
        "is_sum": True, 
        "currency": "EUR", 
        "sub_items": [
            {"name": "└─ Nvidia 1 (NVD 1)", "pos": 1.50, "buy_date": "2026-08-28", "buy_price_override": 195.80},
            {"name": "└─ Nvidia 2 (NVD 2)", "pos": 0.90, "buy_date": "2026-11-24", "buy_price_override": 150.10}
        ]
    },
    # OTP BANK (Többütemű vásárlás - IBKR: 3 db, súlyozott átlagár: 42,480 HUF)
    {
        "name": "OTP Bank Sum (OTP Sum)", 
        "symbols": ["OTP.BD"], 
        "is_sum": True, 
        "currency": "HUF", 
        "buy_price_override": 42480.0,
        "sub_items": [
            {"name": "└─ OTP 1 (OTP 1)", "pos": 2.0, "buy_date": "2026-10-13", "buy_price_override": 42420.0},
            {"name": "└─ OTP 2 (OTP 2)", "pos": 1.0, "buy_date": "2026-10-13", "buy_price_override": 42600.0}
        ]
    },
    # EGYEDI POZÍCIÓK IBKR AKTUÁLIS LISTA ALAPJÁN
    {"name": "TSMC (TSM)", "symbols": ["TSM"], "pos": 1.6, "currency": "USD", "buy_date": "2026-11-23", "buy_price_override": 366.46},
    {"name": "Meta Platforms (META)", "symbols": ["META"], "pos": 0.71, "currency": "USD", "buy_date": "2026-09-24", "buy_price_override": 750.57},
    {"name": "MercadoLibre (MELI)", "symbols": ["MELI"], "pos": 0.23, "currency": "USD", "buy_date": "2026-10-06", "buy_price_override": 1855.33},
    {"name": "Hermès International (RMS)", "symbols": ["RMS.PA"], "pos": 0.21, "currency": "EUR", "buy_date": "2026-09-21"},
    {"name": "Brookfield Corp (BN)", "symbols": ["BN", "BN.TO"], "pos": 12.4458, "currency": "USD", "buy_date": "2026-09-22", "buy_price_override": 38.23},
    {"name": "S&P 500 Info Tech (QDV5)", "symbols": ["QDV5.DE", "QDV5.L"], "pos": 63.6748, "currency": "EUR", "buy_date": "2026-01-19", "buy_price_override": 8.214},
    {"name": "Global Growth ETF (GGRW)", "symbols": ["GGRW.L", "GGRW"], "pos": 5.5924, "currency": "USD", "buy_date": "2026-01-15", "buy_price_override": 40.0205}
]

def format_pct(val, is_sub=False):
    if pd.isna(val) or val is None:
        return "<td style='padding:8px; text-align:center;'>N/A</td>"
    color = "green" if val >= 0 else "red"
    sign = "+" if val >= 0 else ""
    opacity_style = "opacity: 0.85;" if is_sub else ""
    return f"<td style='padding:8px; text-align:center; color:{color}; font-weight:bold; {opacity_style}'>{sign}{val:.2f}%</td>"

def format_weight(val, is_sub=False):
    if pd.isna(val) or val is None:
        return "<td style='padding:8px; text-align:center;'>N/A</td>"
    text_color = "#555555" if is_sub else "#0d47a1"
    font_weight = "normal" if is_sub else "bold"
    return f"<td style='padding:8px; text-align:center; font-weight:{font_weight}; color:{text_color};'>{val:.2f}%</td>"

def get_fx_pair(currency):
    if currency == 'HUF':
        return 1.0, None
    symbol_map = {'USD': 'USDHUF=X', 'EUR': 'EURHUF=X', 'CAD': 'CADHUF=X', 'GBP': 'GBPHUF=X'}
    fx_symbol = symbol_map.get(currency)
    if not fx_symbol:
        return 1.0, None
    try:
        fx = yf.Ticker(fx_symbol)
        for p in ["1y", "1mo", "5d"]:
            hist = fx.history(period=p)
            if not hist.empty:
                valid_closes = hist['Close'].dropna()
                if not valid_closes.empty:
                    return valid_closes.iloc[-1], hist
    except Exception as e:
        print(f"FX Error ({currency}): {e}")
    return 1.0, None

def fetch_history_with_fallback(symbols):
    """Lekéri a szimbólumokat. Ha a legfrissebb nap hiányzik/zárva a piac, az utolsó érvényes lezárt értéket adja vissza."""
    for sym in symbols:
        try:
            time.sleep(0.5)
            ticker = yf.Ticker(sym)
            for p in ["1y", "1mo", "5d"]:
                hist = ticker.history(period=p)
                if not hist.empty:
                    valid_hist = hist.dropna(subset=['Close'])
                    if len(valid_hist) >= 2:
                        return valid_hist, sym
        except Exception as e:
            print(f"Hiba a szimbólum lekérésekor ({sym}): {e}")
            continue
    return pd.DataFrame(), None

def build_portfolio_table():
    calc_data = []
    total_calculated_huf = 0.0

    for item in PORTFOLIO:
        hist, used_symbol = fetch_history_with_fallback(item["symbols"])
        if not hist.empty and len(hist) >= 2:
            curr_price = hist['Close'].iloc[-1]
            if used_symbol and used_symbol.endswith(".L") and curr_price > 1000 and item["currency"] in ["USD", "GBP"]:
                curr_price = curr_price / 100.0

            curr_fx, fx_hist = get_fx_pair(item["currency"])
            active_fx = curr_fx if curr_fx else 1.0

            if item.get("is_sum"):
                total_pos = sum(sub["pos"] for sub in item["sub_items"])
                pos_mkt_val_huf = total_pos * curr_price * active_fx
            else:
                pos_mkt_val_huf = item["pos"] * curr_price * active_fx

            total_calculated_huf += pos_mkt_val_huf

            calc_data.append({
                "item": item,
                "hist": hist,
                "used_symbol": used_symbol,
                "curr_price": curr_price,
                "curr_fx": active_fx,
                "fx_hist": fx_hist,
                "pos_mkt_val_huf": pos_mkt_val_huf
            })
        else:
            calc_data.append({
                "item": item,
                "hist": pd.DataFrame(),
                "used_symbol": None,
                "curr_price": None,
                "curr_fx": 1.0,
                "fx_hist": None,
                "pos_mkt_val_huf": 0.0
            })

    rows_html = ""
    for data in calc_data:
        item = data["item"]
        hist = data["hist"]
        used_symbol = data["used_symbol"]
        curr_price = data["curr_price"]
        curr_fx = data["curr_fx"]
        pos_mkt_val_huf = data["pos_mkt_val_huf"]

        if not hist.empty and len(hist) >= 2:
            daily_pct = ((curr_price - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
            weekly_pct = ((curr_price - hist['Close'].iloc[-5]) / hist['Close'].iloc[-5]) * 100 if len(hist) >= 5 else daily_pct
            monthly_pct = ((curr_price - hist['Close'].iloc[-22]) / hist['Close'].iloc[-22]) * 100 if len(hist) >= 22 else weekly_pct

            # AGGREGÁLT CSOPORT MEGJELENÍTÉSE
            if item.get("is_sum"):
                sum_weight_pct = (pos_mkt_val_huf / total_calculated_huf) * 100 if total_calculated_huf > 0 else 0.0
                
                total_cost_currency = 0.0
                total_sub_pos = 0.0
                sub_calc_list = []

                for sub in item["sub_items"]:
                    sub_pos = sub["pos"]
                    if sub.get("buy_price_override"):
                        sub_buy_p = sub["buy_price_override"]
                    else:
                        hist_btd = hist.loc[hist.index >= sub["buy_date"]]
                        sub_buy_p = hist_btd['Close'].iloc[0] if not hist_btd.empty else curr_price
                        if used_symbol and used_symbol.endswith(".L") and sub
