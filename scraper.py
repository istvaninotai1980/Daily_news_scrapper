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
    {"name": "Meta Platforms (META)", "symbols": ["META"], "pos": 0.71, "currency": "USD", "buy_date": "2026-09-24", "buy_price_override": 649.10},
    {"name": "MercadoLibre (MELI)", "symbols": ["MELI"], "pos": 0.23, "currency":
