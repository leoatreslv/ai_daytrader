import os
from dotenv import load_dotenv

load_dotenv()

# cTrader FIX Configuration
CT_HOST = "demo-uk-eqx-01.p.c-trader.com"
CT_QUOTE_PORT = 5211 # SSL
CT_TRADE_PORT = 5212 # SSL
CT_SENDER_COMP_ID = os.getenv("CT_SENDER_COMP_ID")
if not CT_SENDER_COMP_ID:
    raise ValueError("MISSING CONFIG: CT_SENDER_COMP_ID is not set in .env")

CT_TARGET_COMP_ID = "cServer"

CT_PASSWORD = os.getenv("CT_PASSWORD")
if not CT_PASSWORD:
    raise ValueError("MISSING CONFIG: CT_PASSWORD is not set in .env")

# LLM Configuration
LLM_API_URL = os.getenv("LLM_API_URL", "http://localhost:8000/v1") 
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "facebook/opt-125m")
LLM_CONTEXT_WINDOW = int(os.getenv("LLM_CONTEXT_WINDOW", "4096"))

# Notification Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Trading Parameters
# Trading Parameters
MARKET_OPEN_HOUR = int(os.getenv("MARKET_OPEN_HOUR", "7")) 
MARKET_OPEN_MINUTE = int(os.getenv("MARKET_OPEN_MINUTE", "1"))
MARKET_CLOSE_HOUR = int(os.getenv("MARKET_CLOSE_HOUR", "5")) 
MARKET_CLOSE_MINUTE = int(os.getenv("MARKET_CLOSE_MINUTE", "55"))

TARGET_SYMBOLS = ["41"] # XAUUSD (ID 41)
# TARGET_SYMBOLS = ["1"] # cTrader Symbol IDs (e.g. 1 might be EURUSD, need to map SPY/NSA equivalent)
# NOTE: cTrader uses integer Symbol IDs. User needs to find IDs for "US Indices".
# For Demo: EURUSD is often 1. User wants Indices. 
# We'll need a mapping or lookup. For now, we will use a placeholder.

# Common Symbols (Fallbacks)
SYMBOLS = {
    "EURUSD": "1", "GBPUSD": "2", "USDJPY": "4", "GBPJPY": "6", 
    "AUDUSD": "9", "NZDUSD": "13", "USDCAD": "14", "USDCHF": "15",
    "XAUUSD": "41", "ETHUSD": "1002", "BTCUSD": "1001"
}

TRADE_QTY = 1000 
RISK_REWARD_RATIO = 2.0
STOP_LOSS_PCT = 0.005
TAKE_PROFIT_PCT = 0.01

# Charting Configuration
CHART_INTERVAL = int(os.getenv("CHART_INTERVAL", "7200")) # Default 2 hours
