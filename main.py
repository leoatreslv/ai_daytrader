import time
import config
from ctrader_fix_client import CTraderFixClient
from data_loader import DataLoader
from strategy import Strategy
from llm_client import LLMClient
from datetime import datetime
from logger import setup_logger

from notification import NotificationManager, TelegramProvider

logger = setup_logger("Main")

def main():
    logger.info("Starting AI Day Trader (cTrader FIX)...")
    
    # Initialize Clients
    # Strategy would need updates to handle integer symbol IDs, but logic remains
    fix_client = CTraderFixClient(notifier=notifier)
    llm = LLMClient()
    loader = DataLoader(fix_client)
    
    # Initialize Notifications
    notifier = NotificationManager()
    if config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID:
        notifier.add_provider(TelegramProvider(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID))
        logger.info("Telegram notifications enabled.")
    
    # Strategy would need updates to handle integer symbol IDs, but logic remains
    strategy = Strategy(fix_client, llm) 
    
    # Start Connection
    fix_client.start()

    # Subscribe to Market Data
    # Assuming "1" is EURUSD (Symbol ID). 
    # NOTE: User needs to find correct IDs for SPY/QQQ equivalent on cTrader Demo.
    for symbol in config.TARGET_SYMBOLS:
        logger.info(f"Subscribing to {symbol}...")
        fix_client.subscribe_market_data(symbol, f"req_{symbol}")
    
    logger.info("Entering Main Loop...")
    while True:
        try:
            # Check Stop
            if check_stop():
                break

            # Main strategy loop
            # FIX is event-driven (callbacks), but we can poll aggregated bars here
            
            for symbol in config.TARGET_SYMBOLS:
                df = loader.get_latest_bars(symbol)
                if df is not None and len(df) > 20:
                     # Run Strategy
                     signal = strategy.check_signal(df)
                     if signal:
                         msg = f"🚨 **SIGNAL DETECTED** 🚨\nSymbol: {symbol}\nAction: {signal['action']}\nReason: {signal['reason']}"
                         logger.info(msg)
                         notifier.notify(msg)
                         
                         # Determine Side
                         if signal['action'] == 'BUY_CALL':
                             side = '1' # Buy
                             opp_side = '2' # Sell
                             bias = 1
                         else:
                             side = '2' # Sell
                             opp_side = '1' # Buy
                             bias = -1
                         
                         # Execute Entry (Market)
                         fix_client.submit_order(symbol, config.TRADE_QTY, side, order_type='1')
                         
                         entry_msg = f"🚀 **ORDER PLACED** 🚀\nSide: {'BUY' if side=='1' else 'SELL'}\nQty: {config.TRADE_QTY}\nSymbol: {symbol}"
                         logger.info(entry_msg)
                         notifier.notify(entry_msg)
                         
                         # Calculate Risk Management Prices
                         # Get current price (approximate from bar close)
                         current_price = df.iloc[-1]['close']
                         
                         stop_dist = current_price * config.STOP_LOSS_PCT
                         tp_dist = current_price * config.TAKE_PROFIT_PCT
                         
                         if side == '1': # Long
                             sl_price = current_price - stop_dist
                             tp_price = current_price + tp_dist
                         else: # Short
                             sl_price = current_price + stop_dist
                             tp_price = current_price - tp_dist
                             
                         # Place Protection Orders (Blindly for now, assuming entry fills)
                         # STOP LOSS (Stop Order)
                         fix_client.submit_order(symbol, config.TRADE_QTY, opp_side, order_type='3', stop_px=f"{sl_price:.5f}")
                         logger.info(f"Placed STOP LOSS at {sl_price:.5f}")
                         
                         # TAKE PROFIT (Limit Order)
                         fix_client.submit_order(symbol, config.TRADE_QTY, opp_side, order_type='2', price=f"{tp_price:.5f}")
                         logger.info(f"Placed TAKE PROFIT at {tp_price:.5f}")
                         
                         notifier.notify(f"🛡️ **PROTECTION PLACED**\nSL: {sl_price:.5f}\nTP: {tp_price:.5f}")
                         
                         # Sleep to avoid spamming signals
                         if smart_sleep(60):
                             break
            
            # Heartbeat Log
            if int(time.time()) % 10 == 0:
                 pass
            
            if smart_sleep(1):
                break

        except KeyboardInterrupt:
            logger.info("Stopping...")
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            if smart_sleep(1):
                break


def check_stop():
    import os
    if os.path.exists("stop.txt"):
        logger.info("Stop signal received (stop.txt). Stopping...")
        try:
            os.remove("stop.txt")
        except:
            pass
        return True
    return False

def smart_sleep(seconds):
    """Sleep for `seconds` but check for stop signal every 1s."""
    for _ in range(int(seconds)):
        if check_stop():
            return True
        time.sleep(1)
    return False

if __name__ == "__main__":
    main()

# Need to update main() to use smart_sleep and check_stop
# Since I can't easily jump around, I will provide a new main that uses these.
# Actually I need to replace the whole file or a large chunk to invoke smart_sleep correctly.
# Let's replace the loop.

