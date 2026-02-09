import logging
import time
import os
import threading
from dotenv import load_dotenv
from ctrader_fix_client import CTraderFixClient
from notification import NotificationManager, TelegramProvider
import config

# Setup Logger
logger = logging.getLogger("OrderTest")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

def test_order_execution():
    logger.info("Starting Order Execution Test...")
    
    # Initialize Notification (Optional)
    notifier = NotificationManager()
    if config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID:
        notifier.add_provider(TelegramProvider(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID))
        logger.info("Telegram notifications enabled.")

    # Initialize Client
    client = CTraderFixClient(notifier=notifier)
    
    try:
        # Start
        client.start()
        
        # Wait for Logon
        logger.info("Waiting for Logon...")
        for _ in range(10):
            if client.quote_session.logged_on and client.trade_session.logged_on:
                break
            time.sleep(1)
            
        if not (client.quote_session.logged_on and client.trade_session.logged_on):
            logger.error("❌ Not fully logged on (Quote or Trade missing).")
            return

        logger.info("✅ Logged On (Quote & Trade).")

        # Fetch Symbols
        client.fetch_symbols()
        
        # Resolve Target Symbol
        target_sym = "EURUSD"
        symbol_id = client.get_symbol_id(target_sym)
        
        if not symbol_id:
            logger.error(f"❌ Could not resolve {target_sym}")
            return
            
        logger.info(f"✅ Resolved {target_sym} -> ID {symbol_id}")
        
        # Subscribe to Market Data (Required to get price for protection calculation)
        client.subscribe_market_data(symbol_id, f"req_{symbol_id}")
        logger.info(f"Waiting for market data for {target_sym}...")
        
        # Wait for price
        current_price = None
        for _ in range(10):
            if symbol_id in client.latest_prices:
                current_price = client.latest_prices[symbol_id]
                break
            time.sleep(1)
            
        if not current_price:
            logger.warning("⚠️ No market data received. Using dummy price for logic check only (Order might fail if price deviation is huge).")
            current_price = 1.0500 # Fallback dummy
        
        logger.info(f"Current Price: {current_price}")

        # Simulate Signal
        logger.info("🔹 SIMULATING SIGNAL: BUY EURUSD")
        side = '1' # Buy
        qty = 1000 # Minimum lot for many pairs
        
        # Execute Market Order
        logger.info(f"Placing Market Order (Qty: {qty})...")
        client.submit_order(symbol_id, qty, side, order_type='1')
        
        # Calculate Protection
        stop_dist = current_price * 0.002 # 0.2% SL
        tp_dist = current_price * 0.004 # 0.4% TP
        
        sl_price = current_price - stop_dist
        tp_price = current_price + tp_dist
        
        logger.info(f"Placing Protection (SL: {sl_price:.5f}, TP: {tp_price:.5f})...")
        
        # Opposite Side for Closing
        opp_side = '2' 
        
        # SL (Stop Order)
        client.submit_order(symbol_id, qty, opp_side, order_type='3', stop_px=f"{sl_price:.5f}")
        
        # TP (Limit Order)
        # Note: Take Profit is usually a Limit order at better price
        client.submit_order(symbol_id, qty, opp_side, order_type='2', price=f"{tp_price:.5f}")

        logger.info("✅ Orders Submitted. Check Telegram/cTrader for confirmation.")
        
        # Wait to capture response callbacks
        time.sleep(10)
        
    except Exception as e:
        logger.error(f"Test Failed: {e}")
    finally:
        # Stop
        # client.stop() # No stop method, just let script exit
        logger.info("Test Finished.")

if __name__ == "__main__":
    test_order_execution()
