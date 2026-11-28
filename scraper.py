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

SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD")
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL")

PORTFOLIO = [
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
    {"name": "TSMC (TSM)", "symbols": ["TSM"], "pos": 1.6, "currency": "USD", "buy_date": "2026-11-23", "buy_price_override": 366.46},
    {"name": "Meta Platforms (META)", "symbols": ["META"], "pos": 0.71, "currency": "USD", "buy_date": "2026-09-24", "buy_price_override": 750.57},
    {"name": "MercadoLibre (MELI)", "symbols": ["MELI"], "pos": 0.23, "currency": "USD", "buy_date": "2026-10-06", "buy_price_override": 1855.33},
    {"name": "Hermès International (RMS)", "symbols": ["RMS.PA"], "pos": 0.21, "currency": "EUR", "buy_date": "2026-09-21"},
    {"name": "Brookfield Corp (BN)", "symbols": ["BN", "BN.TO"], "pos": 12.4458, "currency": "USD", "buy_date": "2026-09-22", "buy_price_override": 38.23},
    {"name": "S&P 500 Info Tech (QDV5)", "symbols": ["QDV5.DE", "QDV5.L"], "pos": 63.6748, "currency": "EUR", "buy_date": "2026-01-19", "buy_price_override": 8.214},
    {"name": "Global Growth ETF (GGRW)", "symbols": ["GGRW.L", "GGRW"], "pos": 5.5924, "currency": "USD", "buy_date": "2026-01-15", "buy_price_override": 40.0205}
]


def norm_uk(price, sym, curr):
    if sym and sym.endswith(".L") and price > 1000 and curr in ["USD", "GBP"]:
        return price / 100.0
    return price


def fmt_pct(val, sub=False):
    if pd.isna(val) or val is None:
        return "<td style='padding:8px; text-align:center;'>N/A</td>"
    c = "green" if val >= 0 else "red"
    s = "+" if val >= 0 else ""
    op = "opacity:0.85;" if sub else ""
    st = f"padding:8px; text-align:center; color:{c}; font-weight:bold; {op}"
    return f"<td style='{st}'>{s}{val:.2f}%</td>"


def fmt_w(val, sub=False):
    if pd.isna(val) or val is None:
        return "<td style='padding:8px; text-align:center;'>N/A</td>"
    c = "#555555" if sub else "#0d47a1"
    fw = "normal" if sub else "bold"
    st = f"padding:8px; text-align:center; font-weight:{fw}; color:{c};"
    return f"<td style='{st}'>{val:.2f}%</td>"


def get_fx(curr):
    if curr == "HUF":
        return 1.0
    pairs = {"USD": "USDHUF=X", "EUR": "EURHUF=X", "CAD": "CADHUF=X", "GBP": "GBPHUF=X"}
    sym = pairs.get(curr)
    if not sym:
        return 1.0
    try:
        fx = yf.Ticker(sym)
        for p in ["1y", "1mo", "5d"]:
            h = fx.history(period=p)
            if not h.empty and not h["Close"].dropna().empty:
                return float(h["Close"].dropna().iloc[-1])
    except Exception as e:
        print(f"FX Error ({curr}): {e}")
    return 1.0


def fetch_hist(symbols):
    for sym in symbols:
        try:
            time.sleep(0.5)
            t = yf.Ticker(sym)
            for p in ["1y", "1mo", "5d"]:
                h = t.history(period=p)
                if not h.empty:
                    vh = h.dropna(subset=["Close"])
                    if len(vh) >= 2:
                        return vh, sym
        except Exception as e:
            print(f"Symbol error ({sym}): {e}")
    return pd.DataFrame(), None


def build_portfolio_table():
    calc = []
    tot_huf = 0.0

    for item in PORTFOLIO:
        hist, sym = fetch_hist(item["symbols"])
        if not hist.empty and len(hist) >= 2:
            cp = norm_uk(float(hist["Close"].iloc[-1]), sym, item["currency"])
            fx = get_fx(item["currency"])
            pos = sum(s["pos"] for s in item["sub_items"]) if item.get("is_sum") else item["pos"]
            val_huf = pos * cp * fx
            tot_huf += val_huf
            calc.append({"item": item, "hist": hist, "sym": sym, "cp": cp, "fx": fx, "val": val_huf})
        else:
            calc.append({"item": item, "hist": pd.DataFrame(), "sym": None, "cp": None, "fx": 1.0, "val": 0.0})

    rows = ""
    for d in calc:
        item, hist, sym, cp, fx, val_huf = d["item"], d["hist"], d["sym"], d["cp"], d["fx"], d["val"]
        if hist.empty or len(hist) < 2:
            rows += f"<tr><td style='padding:8px;'>{item['name']}</td><td colspan='7'>Adatfrissítés alatt</td></tr>"
            continue

        c = hist["Close"]
        d_pct = ((cp - c.iloc[-2]) / c.iloc[-2]) * 100
        w_pct = ((cp - c.iloc[-5]) / c.iloc[-5]) * 100 if len(hist) >= 5 else d_pct
        m_pct = ((cp - c.iloc[-22]) / c.iloc[-22]) * 100 if len(hist) >= 22 else w_pct

        if item.get("is_sum"):
            sw = (val_huf / tot_huf) * 100 if tot_huf > 0 else 0.0
            tot_cost, tot_pos, subs = 0.0, 0.0, []
            for s in item["sub_items"]:
                if s.get("buy_price_override"):
                    bp = s["buy_price_override"]
                else:
                    hb = hist.loc[hist.index >= s["buy_date"]]
                    raw = float(hb["Close"].iloc[0]) if not hb.empty else cp
                    bp = norm_uk(raw, sym, item["currency"])
                tot_cost += s["pos"] * bp
                tot_pos += s["pos"]
                subs.append((s, bp))

            wbp = item.get("buy_price_override") or (tot_cost / tot_pos if tot_pos > 0 else cp)
            sbtd = ((cp - wbp) / wbp) * 100 if wbp > 0 else 0.0

            rows += (
                f"<tr style='background-color:#e8f4f8;'>"
                f"<td style='padding:8px; font-weight:bold;'>{item['name']}</td>"
                f"<td style='padding:8px; text-align:center; font-weight:bold;'>Aggregált</td>"
                f"<td style='padding:8px; text-align:center; font-weight:bold;'>{cp:.2f} {item['currency']}</td>"
                f"{fmt_pct(d_pct)}{fmt_pct(w_pct)}{fmt_pct(m_pct)}{fmt_pct(sbtd)}{fmt_w(sw)}</tr>"
            )
            for s, bp in subs:
                sub_w = ((s["pos"] * cp * fx) / tot_huf) * 100 if tot_huf > 0 else 0.0
                sub_btd = ((cp - bp) / bp) * 100 if bp > 0 else 0.0
                rows += (
                    f"<tr style='color:#666666; font-size:12px;'>"
                    f"<td style='padding:6px 8px 6px 20px;'>{s['name']} ({s['pos']} db)</td>"
                    f"<td style='padding:6px; text-align:center;'>{s['buy_date']}</td>"
                    f"<td style='padding:6px; text-align:center;'>{cp:.2f} {item['currency']}</td>"
                    f"{fmt_pct(d_pct, True)}{fmt_pct(w_pct, True)}{fmt_pct(m_pct, True)}"
                    f"{fmt_pct(sub_btd, True)}{fmt_w(sub_w, True)}</tr>"
                )
        else:
            wp = (val_huf / tot_huf) * 100 if tot_huf > 0 else 0.0
            if item.get("buy_price_override"):
                bp = item["buy_price_override"]
            else:
                hb = hist.loc[hist.index >= item["buy_date"]]
                bp = norm_uk(float(hb["Close"].iloc[0]), sym, item["currency"]) if not hb.empty else cp
            btd = ((cp - bp) / bp) * 100 if bp > 0 else 0.0
            rows += (
                f"<tr><td style='padding:8px; font-weight:bold;'>{item['name']}</td>"
                f"<td style='padding:8px; text-align:center;'>{item['buy_date']}</td>"
                f"<td style='padding:8px; text-align:center;'>{cp:.2f} {item['currency']}</td>"
                f"{fmt_pct(d_pct)}{fmt_pct(w_pct)}{fmt_pct(m_pct)}{fmt_pct(btd)}{fmt_w(wp)}</tr>"
            )

    return (
        "<table border='1' style='border-collapse:collapse; width:100%; font-size:13px; font-family:sans-serif;'>"
        "<thead style='background-color:#f2f2f2;'><tr>"
        "<th style='padding:8px;'>Eszköz</th><th style='padding:8px;'>Vásárlás dátuma</th>"
        "<th style='padding:8px;'>Ár</th><th style='padding:8px;'>Napi %</th>"
        "<th style='padding:8px;'>Heti %</th><th style='padding:8px;'>Havi %</th>"
        "<th style='padding:8px;'>Devizás BTD %</th><th style='padding:8px;'>Portfólió Súly %</th>"
        f"</tr></thead><tbody>{rows}</tbody></table>"
    )


def get_economic_report():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return "<p style='color:red;'><b>Hiba:</b> Hiányzó OPENAI_API_KEY!</p>"

    client = OpenAI(api_key=api_key)
    feeds = [
        "https://www.portfolio.hu/rss/all.xml",
        "https://hvg.hu/rss/gazdasag",
        "https://telex.hu/rss/gazdasag",
        "https://index.hu/24ora/rss/?f=gazdasag",
        "https://g7.hu/feed/",
        "https://www.vg.hu/feed/"
    ]
    headers = {"User-Agent": "Mozilla/5.0"}
    raw_news, seen = [], set()

    for url in feeds:
        try:
            r = requests.get(url, headers=headers, timeout=8)
            if r.status_code == 200:
                parsed = feedparser.parse(r.content)
                for e in parsed.entries[:10]:
                    t = getattr(e, "title", "").strip()
                    lk = getattr(e, "link", "").strip()
                    sm = getattr(e, "summary", "").strip()
                    if t and lk and t not in seen:
                        seen.add(t)
                        raw_news.append(f"Cím: {t}\nKivonat: {sm[:200]}\nURL: {lk}")
        except Exception as err:
            print(f"RSS hiba ({url}): {err}")

    prompt = """Te egy szenior makrogazdasági és tőkepiaci elemző vagy.
A megadott nyers hírekből válogasd ki a TOP 10 legfontosabb gazdasági és tőzsdei eseményt, és készíts belőlük elemzői riportot!
Szabályok:
1. PONTOSAN 10 riportblokkot készíts (1-től 10-ig).
2. Minden blokkban a bemenetben lévő PONTOS 'URL'-re mutató HTML link szerepeljen. Ne használj Markdown szintaxist.
3. Magyarázd el az esemény gazdasági és tőzsdei jelentőségét (kamatok, infláció, árfolyamok, szektorális hatások).

Formátum (tisztán HTML):
<div style='margin-bottom:16px; padding:14px; border-left:4px solid #0d47a1; background:#f8f9fa;'>
  <h4 style='margin:0 0 8px 0; color:#0d47a1;'>[Sorszám]. 📈 [Cím]</h4>
  <p style='margin:5px 0;'><b>Mi történt? (Tények):</b> [1-2 mondat]</p>
  <p style='margin:5px 0;'><b>Gazdasági & Piaci Jelentőség:</b> [2-3 mondatos elemzés]</p>
  <p style='margin:6px 0 0 0; font-size:12px;'><b>Forrás:</b> <a href="PONTOS_URL" target="_blank">Teljes cikk &rarr;</a></p>
</div>"""

    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": "\n\n".join(raw_news)}],
            temperature=0.2
        )
        return res.choices[0].message.content
    except Exception as e:
        return f"<p style='color:red;'><b>API Hiba:</b> {e}</p>"


def send_email():
    table = build_portfolio_table()
    report = get_economic_report()
    html = f"""<!DOCTYPE html><html><body style="font-family:Arial,sans-serif; color:#333; padding:20px; max-width:900px; margin:auto;">
    <h2 style="color:#0d47a1;">Balansz Portfólió</h2>{table}
    <br><hr><br>
    <h2 style="color:#0d47a1;">📊 TOP 10 Gazdasági & Tőzsdei Riport</h2>{report}
    </body></html>"""

    msg = MIMEMultipart("alternative")
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL
    msg["Subject"] = "Balansz Portfólió & TOP 10 Gazdasági Riport"
    msg.attach(MIMEText(html, "html", "utf-8"))

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(SENDER_EMAIL, SENDER_PASSWORD)
    server.send_message(msg)
    server.quit()
    print("E-mail sikeresen elküldve!")


if __name__ == "__main__":
    send_email()
