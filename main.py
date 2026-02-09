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

# Shared state for dynamic control
active_symbols = list(config.TARGET_SYMBOLS)
running = True

def listen_for_commands(notifier, fix_client):
    """Background thread to listen for Telegram commands."""
    global active_symbols, running
    
    logger.info("Command listener started.")
    
    while running:
        try:
            cmds = notifier.check_commands()
            for cmd in cmds:
                # Handle Telegram group syntax (e.g., /status@my_bot -> /status)
                if "@" in cmd:
                    cmd_parts = cmd.split()
                    cmd_parts[0] = cmd_parts[0].split('@')[0]
                    cmd = " ".join(cmd_parts)
                
                if cmd.startswith("/symbol"):
                    # Format: /symbol 1
                    try:
                        parts = cmd.split()
                        if len(parts) == 2:
                            raw_input = parts[1]
                            
                            # Try to resolve name -> ID
                            resolved_id = fix_client.get_symbol_id(raw_input)
                            
                            if resolved_id:
                                new_symbol = resolved_id
                                logger.info(f"Resolved command '{raw_input}' -> ID {new_symbol}")
                            else:
                                # Assume it's a raw ID
                                new_symbol = raw_input
                            
                            # Normalize (remove old, add new - simplified single symbol mode for now)
                            old_symbol = active_symbols[0] if active_symbols else "None"
                            active_symbols = [new_symbol] 
                            
                            logger.info(f"Command received: Switch {old_symbol} -> {new_symbol} ({raw_input})")
                            notifier.notify(f"🔄 **SWITCHING INSTRUMENT**\nOld: {old_symbol}\nNew: {new_symbol} ({raw_input})")
                            
                            # Subscribe to new symbol
                            fix_client.subscribe_market_data(new_symbol, f"req_{new_symbol}")
                            
                        else:
                            notifier.notify("❌ Invalid format. Use: `/symbol <id>`")
                    except Exception as e:
                        logger.error(f"Command processing error: {e}")
                        notifier.notify(f"❌ Error processing command: {e}")
                
                elif cmd == "/status" or cmd == "/statis": # Handle typo
                    notifier.notify(f"ℹ️ **STATUS**\nActive Symbol: {active_symbols}\nConnected: {fix_client.quote_session.connected}")
                
                elif cmd == "/help":
                    notifier.notify(f"🤖 **AVAILABLE COMMANDS**\n`/status` - Check connection\n`/symbol <id>` - Switch instrument\n`/help` - Show this menu")
                
                else:
                    notifier.notify(f"❓ **UNKNOWN COMMAND**\nI didn't understand `{cmd}`.\nTry `/help`.")

            time.sleep(2) # Poll interval
        except Exception as e:
            logger.error(f"Listener error: {e}")
            time.sleep(5)

def main():
    global active_symbols, running
    logger.info("Starting AI Day Trader (cTrader FIX)...")
    
    # Initialize Notifications
    notifier = NotificationManager()
    if config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID:
        notifier.add_provider(TelegramProvider(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID))
        logger.info("Telegram notifications enabled.")
    
    # Initialize Clients
    fix_client = CTraderFixClient(notifier=notifier)
    llm = LLMClient()
    loader = DataLoader(fix_client)
    
    # Strategy
    strategy = Strategy(fix_client, llm) 
    
    try:
        # Start Connection
        fix_client.start()
        
        # Fetch all symbols (Name -> ID)
        fix_client.fetch_symbols()

        # Initial Subscription
        # Resolve initial symbols if they are names
        initial_ids = []
        for s in active_symbols:
            res_id = fix_client.get_symbol_id(s)
            if res_id:
                logger.info(f"Resolved {s} -> {res_id}")
                initial_ids.append(res_id)
            else:
                 # Assume it's already an ID if not found, or user config error
                 logger.warning(f"Could not resolve {s}, assuming it's an ID.")
                 initial_ids.append(s)
                 
        active_symbols = initial_ids

        for symbol in active_symbols:
            logger.info(f"Subscribing to {symbol}...")
            fix_client.subscribe_market_data(symbol, f"req_{symbol}")
        
        # Start Command Listener
        import threading
        cmd_thread = threading.Thread(target=listen_for_commands, args=(notifier, fix_client), daemon=True)
        cmd_thread.start()
        
        logger.info("Entering Main Loop...")
        while running:
            try:
                # Check Stop
                if check_stop():
                    running = False
                    break

                # Main strategy loop
                # Use copy of active_symbols to handle dynamic changes safely
                current_targets = list(active_symbols)
                
                for symbol in current_targets:
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
                             # Use timestamp for unique ClOrdID to avoid duplicates
                             fix_client.submit_order(symbol, config.TRADE_QTY, side, order_type='1')
                             
                             entry_msg = f"🚀 **ORDER PLACED** 🚀\nSide: {'BUY' if side=='1' else 'SELL'}\nQty: {config.TRADE_QTY}\nSymbol: {symbol}"
                             logger.info(entry_msg)
                             notifier.notify(entry_msg)
                             
                             # Calculate Risk
                             current_price = df.iloc[-1]['close']
                             stop_dist = current_price * config.STOP_LOSS_PCT
                             tp_dist = current_price * config.TAKE_PROFIT_PCT
                             
                             if side == '1': # Long
                                 sl_price = current_price - stop_dist
                                 tp_price = current_price + tp_dist
                             else: # Short
                                 sl_price = current_price + stop_dist
                                 tp_price = current_price - tp_dist
                                 
                             # Protection
                             fix_client.submit_order(symbol, config.TRADE_QTY, opp_side, order_type='3', stop_px=f"{sl_price:.5f}")
                             fix_client.submit_order(symbol, config.TRADE_QTY, opp_side, order_type='2', price=f"{tp_price:.5f}")
                             
                             notifier.notify(f"🛡️ **PROTECTION PLACED**\nSL: {sl_price:.5f}\nTP: {tp_price:.5f}")
                             
                             if smart_sleep(60):
                                 running = False
                                 break
                
                if smart_sleep(1):
                    running = False
                    break

            except KeyboardInterrupt:
                logger.info("Stopping...")
                running = False
                break
            except Exception as e:
                logger.error(f"Error in Main Loop: {e}")
                # Don't break, just sleep and retry
                if smart_sleep(5):
                    running = False
                    break

    except Exception as e:
        logger.critical(f"Fatal Startup Error: {e}")
        notifier.notify(f"❌ **FATAL ERROR**\nBot crashed:\n{e}")
        time.sleep(10) # Wait before exit to allow notification to send


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

