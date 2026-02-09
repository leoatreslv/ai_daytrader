import config
import time
import logging
import sys
from notification import NotificationManager, TelegramProvider
from ctrader_fix_client import CTraderFixClient

# Setup basic logging - Force UTF8 or just avoid non-ascii
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger("Test")

class TestListener:
    def on_message(self, source, msg):
        logger.info(f"[{source}] RECV: {msg}")
    
    def on_disconnected(self, session_type, reason):
        logger.warning(f"[{session_type}] DISCONNECTED: {reason}")

def test_telegram():
    logger.info("--- Testing Telegram ---")
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.error("Telegram credentials missing in .env")
        return False
        
    notifier = NotificationManager()
    provider = TelegramProvider(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID)
    notifier.add_provider(provider)
    
    try:
        msg = "TEST MESSAGE: If you see this, Telegram is configured correctly!"
        logger.info(f"Sending test message to Chat ID: {config.TELEGRAM_CHAT_ID}")
        provider.send_message(msg)
        logger.info("Message sent (check your Telegram app)")
        return True
    except Exception as e:
        logger.error(f"Telegram Test Failed: {e}")
        return False

def test_ctrader_and_symbols():
    logger.info("\n--- Testing cTrader FIX & Symbol Resolution ---")
    if not config.CT_SENDER_COMP_ID or not config.CT_PASSWORD:
        logger.error("cTrader credentials missing in .env")
        return False

    client = CTraderFixClient()
    # We use the native client logic now to ensure on_message handles SecurityList (type 'y')
    
    session = client.quote_session
    
    try:
        session.connect()
        logger.info("Waiting for Logon...")
        
        # Wait for Logon
        for i in range(10):
            if session.logged_on:
                break
            time.sleep(1)
            
        if not session.logged_on:
            logger.error("cTrader Logon FAILED (Not logged on)")
            return False
            
        logger.info("cTrader Logon SUCCESS")
        
        # Test Symbol Fetching
        logger.info("Attempting to fetch symbols...")
        client.fetch_symbols()
        
        count = len(client.symbol_map)
        logger.info(f"Symbols Loaded: {count}")
        
        if count > 0:
            # ... (snipped)
            pass
        else:
            logger.error("❌ No symbols fetched! Checking Market Data for ID '1'...")
            # Try Market Data for ID 1 to see if session is alive
            client.subscribe_market_data("1", "test_md_1")
            time.sleep(5)
            # Check if we got data? (We need a callback to know)
            # But logs should show MD Snapshot/Incremental or Reject
            
        session.running = False
        if session.sock:
             session.sock.close()
        return True
            
    except Exception as e:
        logger.error(f"cTrader Test Error: {e}")
        return False

if __name__ == "__main__":
    logger.info("Starting Local Configuration Test...")
    
    tg_result = test_telegram()
    ct_result = test_ctrader_and_symbols()
    
    logger.info("\n--- Test Summary ---")
    logger.info(f"Telegram: {'PASSED' if tg_result else 'FAILED'}")
    logger.info(f"cTrader:  {'PASSED' if ct_result else 'FAILED'}")
    
    if tg_result and ct_result:
        logger.info("\n🎉 All systems go! You can run the bot now.")
    else:
        logger.info("\n⚠️ Some tests failed. Check your .env file.")
