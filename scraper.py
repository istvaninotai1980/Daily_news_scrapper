import os
import time
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

# --- PORTFÓLIÓ ESZKÖZÖK PONTOS IBKR ADATOKKAL ÉS BONTÁSSAL ---
PORTFOLIO = [
    # BROADCOM (Többütemű vásárlás - IBKR: 1.54 db, -0.8% Unrealized)
    {
        "name": "Broadcom Sum (AVGO Sum)", 
        "symbols": ["AVGO"], 
        "is_sum": True, 
        "currency": "USD", 
        "buy_price_override": 368.38, # IBKR pontos átlagár a -0.8%-hoz
        "sub_items": [
            {"name": "└─ Broadcom 1 (AVGO 1)", "pos": 0.54, "buy_date": "2026-08-28"},
            {"name": "└─ Broadcom 2 (AVGO 2)", "pos": 1.00, "buy_date": "2026-09-10", "buy_price_override": 363.10}
        ]
    },
    # AMAZON (Többütemű vásárlás - IBKR: 4.4759 db, +3.3% Unrealized)
    {
        "name": "Amazon Sum (AMZ Sum)", 
        "symbols": ["AMZ.DE", "AMZN"], 
        "is_sum": True, 
        "currency": "EUR", 
        "buy_price_override": 215.90, # IBKR pontos átlagár a +3.3%-hoz
        "sub_items": [
            {"name": "└─ Amazon 1 (AMZ 1)", "pos": 2.9759, "buy_date": "2026-07-29"},
            {"name": "└─ Amazon 2 (AMZ 2)", "pos": 1.5000, "buy_date": "2026-09-03", "buy_price_override": 216.47}
        ]
    },
    # ALPHABET / GOOGLE (Többütemű vásárlás - IBKR: 1.992 db, +3.0% Unrealized)
    {
        "name": "Alphabet Sum (GOOGL Sum)", 
        "symbols": ["GOOGL", "GOOG"], 
        "is_sum": True, 
        "currency": "USD", 
        "buy_price_override": 342.96, # IBKR pontos átlagár a +3.0%-hoz
        "sub_items": [
            {"name": "└─ Alphabet 1 (GOOGL 1)", "pos": 0.992, "buy_date": "2026-09-09"},
            {"name": "└─ Alphabet 2 (GOOGL 2)", "pos": 1.000, "buy_date": "2026-09-22"}
        ]
    },
    # META PLATFORMS
    {"name": "Meta Platforms (META)", "symbols": ["META"], "pos": 0.71, "currency": "USD", "buy_date": "2026-09-24"},
    
    # MERCADOLIBRE (Új pozíció a TSMC helyett)
    {"name": "MercadoLibre (MELI)", "symbols": ["MELI"], "pos": 0.23, "currency": "USD", "buy_date": "2026-10-06", "buy_price_override": 1850.98},

    # EGYEDI POZÍCIÓK IBKR KÉPERNYŐKÉP ALAPJÁN
    {"name": "Nvidia IBIS (NVD)", "symbols": ["NVD.DE", "NVDA"], "pos": 1.5, "currency": "EUR", "buy_date": "2026-08-28", "buy_price_override": 195.80},
    {"name": "Hermès International (RMS)", "symbols": ["RMS.PA", "RMS.DE"], "pos": 0.21, "currency": "EUR", "buy_date": "2026-09-21"},
    {"name": "Brookfield Corp (BN)", "symbols": ["BN", "BN.TO"], "pos": 12.4458, "currency": "USD", "buy_date": "2026-09-22"},
    {"name": "Constellation Software (CSU)", "symbols": ["CSU.TO"], "pos": 0.3056, "currency": "CAD", "buy_date": "2026-01-28", "buy_price_override": 2786.85},
    {"name": "S&P 500 Info Tech (QDV5)", "symbols": ["QDV5.DE", "QDV5.L"], "pos": 63.6748, "currency": "EUR", "buy_date": "2026-01-19", "buy_price_override": 8.214},
    {"name": "Global Growth ETF (GGRW)", "symbols": ["GGRW.L", "GGRW"], "pos": 15.0924, "currency": "USD", "buy_date": "2026-01-15", "buy_price_override": 40.0205}
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
            time.sleep(0.5) # Yahoo Finance Rate Limit elkerülése
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
                        if used_symbol and used_symbol.endswith(".L") and sub_buy_p > 1000 and item["currency"] in ["USD", "GBP"]:
                            sub_buy_p = sub_buy_p / 100.0

                    total_cost_currency += sub_pos * sub_buy_p
                    total_sub_pos += sub_pos
                    sub_calc_list.append({"sub": sub, "buy_price": sub_buy_p})

                if item.get("buy_price_override"):
                    weighted_buy_price = item["buy_price_override"]
                else:
                    weighted_buy_price = (total_cost_currency / total_sub_pos) if total_sub_pos > 0 else curr_price

                sum_dev_btd_pct = ((curr_price - weighted_buy_price) / weighted_buy_price) * 100 if weighted_buy_price > 0 else 0.0

                # Aggregált Fősor (Kiemelt kék háttérrel)
                rows_html += f"""
                <tr style="background-color:#e8f4f8;">
                    <td style="padding:8px; font-weight:bold;">{item['name']}</td>
                    <td style="padding:8px; text-align:center; font-weight:bold;">Aggregált</td>
                    <td style="padding:8px; text-align:center; font-weight:bold;">{curr_price:.2f} {item['currency']}</td>
                    {format_pct(daily_pct)}
                    {format_pct(weekly_pct)}
                    {format_pct(monthly_pct)}
                    {format_pct(sum_dev_btd_pct)}
                    {format_weight(sum_weight_pct)}
                </tr>
                """

                # Egyedi vásárlási pontok (AL-SOROK SZÜRKE BETŰS ÍRÁSSAL)
                for sc in sub_calc_list:
                    sub = sc["sub"]
                    sub_buy_p = sc["buy_price"]
                    sub_pos = sub["pos"]
                    sub_mkt_val_huf = sub_pos * curr_price * curr_fx
                    sub_weight_pct = (sub_mkt_val_huf / total_calculated_huf) * 100 if total_calculated_huf > 0 else 0.0
                    sub_btd_pct = ((curr_price - sub_buy_p) / sub_buy_p) * 100 if sub_buy_p > 0 else 0.0

                    rows_html += f"""
                    <tr style="color:#666666; font-size:12px;">
                        <td style="padding:6px 8px 6px 20px; color:#666666;">{sub['name']} ({sub_pos} db)</td>
                        <td style="padding:6px; text-align:center; color:#666666;">{sub['buy_date']}</td>
                        <td style="padding:6px; text-align:center; color:#666666;">{curr_price:.2f} {item['currency']}</td>
                        {format_pct(daily_pct, is_sub=True)}
                        {format_pct(weekly_pct, is_sub=True)}
                        {format_pct(monthly_pct, is_sub=True)}
                        {format_pct(sub_btd_pct, is_sub=True)}
                        {format_weight(sub_weight_pct, is_sub=True)}
                    </tr>
                    """

            # STANDARD EGYEDI POZÍCIÓK
            else:
                weight_pct = (pos_mkt_val_huf / total_calculated_huf) * 100 if total_calculated_huf > 0 else 0.0

                if item.get("buy_price_override"):
                    buy_price = item["buy_price_override"]
                else:
                    hist_btd = hist.loc[hist.index >= item["buy_date"]]
                    if not hist_btd.empty:
                        buy_price = hist_btd['Close'].iloc[0]
                        if used_symbol and used_symbol.endswith(".L") and buy_price > 1000 and item["currency"] in ["USD", "GBP"]:
                            buy_price = buy_price / 100.0
                    else:
                        buy_price = curr_price

                dev_btd_pct = ((curr_price - buy_price) / buy_price) * 100 if buy_price > 0 else 0.0
                buy_date_str = item["buy_date"]

                rows_html += f"""
                <tr>
                    <td style="padding:8px; font-weight:bold;">{item['name']}</td>
                    <td style="padding:8px; text-align:center;">{buy_date_str}</td>
                    <td style="padding:8px; text-align:center;">{curr_price:.2f} {item['currency']}</td>
                    {format_pct(daily_pct)}
                    {format_pct(weekly_pct)}
                    {format_pct(monthly_pct)}
                    {format_pct(dev_btd_pct)}
                    {format_weight(weight_pct)}
                </tr>
                """
        else:
            rows_html += f"<tr><td style='padding:8px;'>{item['name']}</td><td style='padding:8px;'>{item.get('buy_date', 'N/A')}</td><td colspan='6' style='text-align:center;'>Adatfrissítés alatt</td></tr>"

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
                <th style="padding:8px;">Portfólió Súly %</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
    """

# --- TOP 3 ALPHA FOCUS GAZDASÁGI ELEMZÉS ---
def get_quant_summary():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return "<p style='color:red;'><b>Hiba:</b> Az OPENAI_API_KEY hiányzik a GitHub Secrets beállításokból!</p>"

    local_client = OpenAI(api_key=api_key)

    raw_news = []
    feeds = [
        "https://www.portfolio.hu/rss/all.xml",
        "https://hvg.hu/rss/gazdasag",
        "https://telex.hu/rss/gazdasag",
        "https://index.hu/24ora/rss/?f=gazdasag"
    ]
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

    for f in feeds:
        try:
            resp = requests.get(f, headers=headers, timeout=8)
            if resp.status_code == 200:
                parsed = feedparser.parse(resp.content)
                for e in parsed.entries[:6]:
                    title = getattr(e, 'title', '').strip()
                    link = getattr(e, 'link', '').strip()
                    if title and link:
                        raw_news.append(f"Cím: {title}\nURL: {link}")
        except Exception as err:
            print(f"Hiba a csatorna olvasásakor ({f}): {err}")
            continue

    if not raw_news:
        raw_news = [
            "Cím: Globális piaci mozgások és kamatpolitikai várakozások\nURL: https://www.portfolio.hu/gazdasag",
            "Cím: Európai és amerikai részvénypiaci összefoglaló\nURL: https://hvg.hu/gazdasag",
            "Cím: Makrogazdasági indikátorok és devizapiaci elemzés\nURL: https://telex.hu/gazdasag"
        ]

