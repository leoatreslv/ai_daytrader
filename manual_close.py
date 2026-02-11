
import logging
import time
from ctrader_fix_client import CTraderFixClient

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ManualClose")

def manual_close():
    logger.info("--- Manual Position Closer ---")
    
    client = CTraderFixClient(notifier=None)
    
    try:
        client.start()
        
        # Wait for Logon
        logger.info("Waiting for Logon...")
        for _ in range(10):
            if client.trade_session.logged_on and client.quote_session.logged_on:
                break
            time.sleep(1)
            
        if not client.trade_session.logged_on:
            logger.error("Could not log on to Trade Session.")
            return

        # Fetch Symbols
        logger.info("Fetching symbols...")
        client.fetch_symbols()
        
        # Sync Positions
        logger.info("requesting positions...")
        client.clear_state()
        client.send_positions_request()
        time.sleep(5)
        
        print(f"\nCurrent Positions: {client.positions}")
        
        if not client.positions:
            logger.info("No positions to close.")
        else:
            confirm = input(f"Found {len(client.positions)} positions. Close ALL? (yes/no): ")
            if confirm.lower() == "yes":
                client.close_all_positions()
                logger.info("Close commands sent. Waiting 5s...")
                time.sleep(5)
                
                # Check again
                client.clear_state()
                client.send_positions_request()
                time.sleep(5)
                print(f"Remaining Positions: {client.positions}")
            else:
                logger.info("Aborted.")

    except KeyboardInterrupt:
        logger.info("Interrupted.")
    finally:
        client.stop()

if __name__ == "__main__":
    manual_close()
