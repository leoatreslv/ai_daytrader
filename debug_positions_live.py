
import logging
import time
import config
from ctrader_fix_client import CTraderFixClient
import simplefix

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("DebugPositions")

def debug_positions():
    logger.info("--- Starting Live Position Debugger ---")
    
    # 1. Initialize Client
    client = CTraderFixClient(notifier=None)
    
    # 2. Monkey Patch handle_message to log RAW AP messages
    original_handle = client.on_message
    
    def debug_on_message(source, msg):
        msg_type = msg.get(35)
        if msg_type == b'AP': # Position Report
            logger.info(f"\n[RAW AP] {msg}")
            try:
                sym_id = msg.get(55).decode()
                long_qty = msg.get(704).decode() if msg.get(704) else "0"
                short_qty = msg.get(705).decode() if msg.get(705) else "0"
                logger.info(f" -> Parsed: Symbol={sym_id}, Long={long_qty}, Short={short_qty}")
            except Exception as e:
                logger.error(f" -> Parse Error: {e}")
        
        elif msg_type == b'y': # Security List
             sym_id = msg.get(55)
             sym_name = msg.get(107)
             if sym_id and sym_name:
                 logger.info(f"[Security] {sym_id.decode()} = {sym_name.decode()}")

        # Call original
        original_handle(source, msg)

    client.on_message = debug_on_message

    try:
        # 3. Connect
        client.start()
        
        if not client.trade_session.logged_on:
            logger.error("Trade Session failed to log on. Exiting.")
            return

        # 4. Fetch Symbols to get Names
        logger.info("Fetching symbols...")
        client.fetch_symbols()
        
        
        
        # 5. Clear State & Request Positions
        logger.info("Clearing state and requesting positions...")
        client.clear_state()
        client.send_positions_request()
        
        # 6. Wait and Listen
        logger.info("Waiting 10 seconds for reports...")
        time.sleep(10)
        
        # 7. Print Summary
        logger.info("\n--- INTERNAL STATE SUMMARY ---")
        # Print dictionary directly to avoid UnicodeEncodeError in console
        print(f"Positions: {client.positions}")
        logger.info("------------------------------")
        
        logger.info("\nDone. You can Ctrl+C to exit if it doesn't stop automatically.")
        
    except KeyboardInterrupt:
        logger.info("Debug interrupted.")
    finally:
        client.stop()

if __name__ == "__main__":
    debug_positions()
