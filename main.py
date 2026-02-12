import time
import config
from ctrader_fix_client import CTraderFixClient
from data_loader import DataLoader
from strategy import Strategy
from llm_client import LLMClient
from datetime import datetime
from logger import setup_logger

from notification import NotificationManager, TelegramProvider
from charting import generate_candlestick_chart

logger = setup_logger("Main")

# Shared state for dynamic control
active_symbols = list(config.TARGET_SYMBOLS)
running = True
last_chart_time = time.time()

def listen_for_commands(notifier, fix_client, loader): # Added loader to args
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
                    msg = f"ℹ️ **STATUS**\nComputed Active Symbol: {active_symbols}\nConnected: {fix_client.quote_session.connected}"
                    
                    if active_symbols:
                        sym = active_symbols[0]
                        # Debug: Print what we are looking for vs what we have
                        logger.info(f"STATUS DEBUG: Looking for '{sym}' (type: {type(sym)}) in keys: {list(fix_client.latest_prices.keys())}")
                        
                        price = fix_client.latest_prices.get(sym, "Waiting...")
                        t_check = fix_client.last_price_times.get(sym)
                        t_str = t_check.strftime("%H:%M:%S") if t_check else "N/A"
                        msg += f"\n\nPrice: {price}\nUpdated: {t_str}"
                        
                    notifier.notify(msg)
                
                elif cmd == "/help":
                    notifier.notify(f"🤖 **AVAILABLE COMMANDS**\n`/status` - Check connection\n`/orders` - List active orders\n`/positions` - List open positions\n`/sync` - Manual State Sync\n`/chart` - Generate Price Chart\n`/symbol <id>` - Switch instrument\n`/help` - Show this menu")
                
                elif cmd == "/orders":
                    notifier.notify(fix_client.get_orders_string())

                elif cmd in ["/positions", "/pos"]:
                    notifier.notify(fix_client.get_position_pnl_string())

                elif cmd == "/sync":
                    notifier.notify("🔄 **SYNCING STATE**\nClearing local cache & Requesting fresh data...")
                    fix_client.clear_state()
                    fix_client.send_order_mass_status_request()
                    fix_client.send_positions_request()
                    
                    # Give it a moment to populate, then confirm
                    time.sleep(3) 
                    notifier.notify(f"✅ **SYNC COMPLETE**\n\n{fix_client.get_orders_string()}\n\n{fix_client.get_position_pnl_string()}")

                elif cmd == "/report":
                    notifier.notify(fix_client.get_daily_report())

                elif cmd == "/chart":
                    sym = active_symbols[0] if active_symbols else None
                    if sym:
                        notifier.notify(f"📊 Generating chart for {sym}...")
                        df = loader.get_latest_bars(sym, length=100)
                        
                        if df is not None:
                            logger.info(f"Chart Request: Retrieved {len(df)} bars for {sym}")
                        else:
                             logger.info(f"Chart Request: No bars for {sym}")

                        if df is not None and len(df) >= 1:
                            fpath = generate_candlestick_chart(df, sym)
                            if fpath:
                                notifier.notify_image(fpath, f"Chart: {sym}")
                            else:
                                notifier.notify("❌ Failed to generate chart (File error).")
                        else:
                             notifier.notify("⚠️ Not enough data for chart.")
                    else:
                        notifier.notify("⚠️ No active symbol.")

                else:
                     notifier.notify(f"❓ **UNKNOWN COMMAND**\nI didn't understand `{cmd}`.\nTry `/help`.")

            time.sleep(2) # Poll interval
        except Exception as e:
            logger.error(f"Listener error: {e}")
            time.sleep(5)


import signal
import sys

def main():
    global active_symbols, running, last_chart_time
    logger.info("Starting AI Day Trader (cTrader FIX)...")
    
    # Log Configuration (Safe)
    logger.info(f"CONFIG: Market Hours: {config.MARKET_OPEN_HOUR}:{config.MARKET_OPEN_MINUTE:02d} - {config.MARKET_CLOSE_HOUR}:{config.MARKET_CLOSE_MINUTE:02d}")
    logger.info(f"CONFIG: Chart Interval: {config.CHART_INTERVAL}s")
    logger.info(f"CONFIG: Max Open Positions: {config.MAX_OPEN_POSITIONS}")
    logger.info(f"CONFIG: CompID: {config.CT_SENDER_COMP_ID} -> {config.CT_TARGET_COMP_ID}")
    
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
    
    import os

    # --- Signal Handling ---
    def shutdown_handler(signum, frame):
        print(f"\nSignal {signum} received. Forcing exit...")
        # Force exit immediately, skipping cleanup that might hang
        os._exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    # -----------------------

    try:
        # Start Connection
        fix_client.start()
        
        # Fetch all symbols (Name -> ID)
        fix_client.fetch_symbols()
        
        # Request Initial Positions - Wait for connection first
        logger.info("Waiting for Trade Session to be ready for Position Request...")
        retries = 20
        while not fix_client.trade_session.logged_on and retries > 0:
            time.sleep(1)
            retries -= 1
            # Note: No need to check 'running' here if signal handler kills process
            
        if fix_client.trade_session.logged_on:
            fix_client.clear_state()
            fix_client.send_positions_request()
        else:
            logger.error("Trade Session not logged on after wait. Skipping initial position request.")

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
        # Pass 'loader' to listener for chart generation
        cmd_thread = threading.Thread(target=listen_for_commands, args=(notifier, fix_client, loader), daemon=True)
        cmd_thread.start()
        
        logger.info("Entering Main Loop...")
        while running:
            try:
                # Check Stop
                if check_stop():
                    running = False
                    break
                
                # Market Hours Check
                now = datetime.now()
                market_open = now.replace(hour=config.MARKET_OPEN_HOUR, minute=config.MARKET_OPEN_MINUTE, second=0, microsecond=0)
                market_close = now.replace(hour=config.MARKET_CLOSE_HOUR, minute=config.MARKET_CLOSE_MINUTE, second=0, microsecond=0)
                
                # Check for cross-midnight schedule (e.g. Open 07:00, Close 05:55 next day)
                # In this case, Open > Close isn't strictly true if we just compare hours, 
                # but semantically it is cross-day if Open is 7am and Close is 5am.
                # However, if Close is 5am, it usually means the *next* day.
                
                if config.MARKET_OPEN_HOUR > config.MARKET_CLOSE_HOUR or \
                   (config.MARKET_OPEN_HOUR == config.MARKET_CLOSE_HOUR and config.MARKET_OPEN_MINUTE > config.MARKET_CLOSE_MINUTE):
                    # Cross-midnight: 
                    # If it's 04:00 (before Close), it's open.
                    # If it's 08:00 (after Open), it's open.
                    # If it's 06:00 (between Close and Open), it's closed.
                    is_open = now >= market_open or now < market_close
                else:
                    # Standard day (e.g. 09:00 to 17:00)
                    is_open = market_open <= now < market_close
                
                if not is_open:
                    if active_symbols: # If we have active symbols or open positions, we might need to close/pause
                         # Check if we just crossed the close time (e.g. within last minute)
                         # Simple logic: If outside hours and positions > 0 -> Close positions
                         if fix_client.positions:
                             logger.warning("Outside Trading Hours. Closing all positions.")
                             notifier.notify("🛑 **MARKET CLOSE**\nClosing positions and pausing trading.")
                             fix_client.close_all_positions()
                    
                    # Pause Logic
                    logger.info(f"Market Closed. Waiting for Open ({config.MARKET_OPEN_HOUR}:{config.MARKET_OPEN_MINUTE:02d})...")
                    if smart_sleep(60): # Check stop every 60s
                        running = False
                        break
                    continue # Skip strategy loop
                
                # --- Trading Logic (Only runs if is_open) ---

                # Periodic Chart Check (Default 2 Hours = 7200s, Configurable)
                if time.time() - last_chart_time > config.CHART_INTERVAL:
                    last_chart_time = time.time()
                    sym = active_symbols[0] if active_symbols else None
                    if sym:
                        logger.info(f"Auto-generating periodic chart for {sym}...")
                        df = loader.get_latest_bars(sym, length=100)
                        
                        if df is not None:
                             logger.info(f"Periodic Chart: Retrieved {len(df)} bars for {sym}")
                        else:
                             logger.info(f"Periodic Chart: No bars for {sym}")

                        if df is not None and len(df) >= 1:
                            fpath = generate_candlestick_chart(df, sym)
                            if fpath:
                                notifier.notify_image(fpath, f"🕑 Periodic Chart: {sym}")

                # Main strategy loop
                # Use copy of active_symbols to handle dynamic changes safely
                current_targets = list(active_symbols)
                
                # Check Global Position Limit
                # Check Global Position Limit - MOVED inside signal
                # open_pos_count = fix_client.get_open_position_count()
                # if open_pos_count >= config.MAX_OPEN_POSITIONS:
                #      ... continue

                for symbol in current_targets:
                    df = loader.get_latest_bars(symbol)
                    if df is not None and len(df) > 20:
                         # Run Strategy
                         signal_data = strategy.check_signal(df, symbol)
                         if signal_data:
                             symbol_name = fix_client.get_symbol_name(symbol)
                             msg = f"🚨 **SIGNAL DETECTED** 🚨\nSymbol: {symbol_name}\nAction: {signal_data['action']}\nReason: {signal_data['reason']}"
                             logger.info(msg)
                             notifier.notify(msg)

                             # Check Max Positions
                             open_count = fix_client.get_open_position_count()
                             if open_count >= config.MAX_OPEN_POSITIONS:
                                 logger.warning(f"Skipping trade execution: Max Open Positions ({open_count}/{config.MAX_OPEN_POSITIONS})")
                                 notifier.notify(f"⚠️ **TRADE SKIPPED**\nMax Open Positions Reached ({open_count}/{config.MAX_OPEN_POSITIONS})")
                                 continue
                             
                             # Determine Side
                             if signal_data['action'] == 'BUY_CALL':
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
                             
                             entry_msg = f"🚀 **ORDER PLACED** 🚀\nSide: {'BUY' if side=='1' else 'SELL'}\nQty: {config.TRADE_QTY}\nSymbol: {symbol_name}"
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
                             # XAUUSD usually requires 2 decimal places
                             fix_client.submit_order(symbol, config.TRADE_QTY, opp_side, order_type='3', stop_px=f"{sl_price:.2f}")
                             fix_client.submit_order(symbol, config.TRADE_QTY, opp_side, order_type='2', price=f"{tp_price:.2f}")
                             
                             notifier.notify(f"🛡️ **PROTECTION PLACED**\nSL: {sl_price:.2f}\nTP: {tp_price:.2f}")
                             
                             if smart_sleep(60):
                                 running = False
                                 break
                
                if smart_sleep(1):
                    running = False
                    break
                    
            except Exception as e:
                import traceback
                logger.error(f"Error in Main Loop: {e}")
                logger.error(traceback.format_exc())
                if smart_sleep(5): # Wait a bit before retry to avoid rapid loops
                     pass

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
    finally:
        logger.info("Cleaning up...")
        fix_client.stop()


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
    """Sleep for `seconds` but check for stop signal every 0.5s."""
    for _ in range(int(seconds * 2)):
        if not running: return True
        if check_stop():
            return True
        time.sleep(0.5)
    return False

if __name__ == "__main__":
    main()


# Need to update main() to use smart_sleep and check_stop
# Since I can't easily jump around, I will provide a new main that uses these.
# Actually I need to replace the whole file or a large chunk to invoke smart_sleep correctly.
# Let's replace the loop.

