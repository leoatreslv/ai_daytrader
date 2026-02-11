
import logging
import time
import simplefix
from datetime import datetime
from ctrader_fix_client import CTraderFixClient

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CloseTest")

def attempt_close():
    client = CTraderFixClient(notifier=None)
    try:
        client.start()
        
        # Wait for Logon
        logger.info("Waiting for Logon...")
        for _ in range(10):
            if client.trade_session.logged_on: break
            time.sleep(1)
            
        if not client.trade_session.logged_on:
            logger.error("Trade Session not logged on.")
            return

        # Fetch Symbols (to get IDs)
        client.fetch_symbols()
        
        # Request Positions
        logger.info("Requesting Positions...")
        client.clear_state()
        client.send_positions_request()
        # Wait longer for positions to arrive
        time.sleep(5)
        
        print(f"Current Position Details: {client.position_details}")
        
        if not client.position_details:
             logger.info("No detailed positions found (checking summary)...")
             print(f"Summary: {client.positions}")
             if not client.positions:
                 logger.info("No positions found.")
                 return

        # Iterate Position Details
        for pid, pdata in client.position_details.items():
            sym_id = pdata['symbol_id']
            qty = pdata['qty']
            side = pdata['side']
            
            logger.info(f"Checking Position {pid}: {side} {qty} on {sym_id}")
            
            # Close Logic
            # Closing the Short 1000 and Long 1000 on XAUUSD (Symbol 41)
            if sym_id == '41': # XAUUSD
                 logger.info(f"Targeting {side.upper()} {qty} on XAUUSD (ID: {pid})")
                 
                 opp_side = '2' if side == 'long' else '1' # Sell to close Long, Buy to close Short
                 
                 logger.info(f"Sending Close Order: Side={opp_side}, Qty={qty}, Symbol={sym_id}, PosID={pid}")
                 
                 client.submit_order(sym_id, qty, opp_side, order_type='1', position_id=pid)
                 
                 time.sleep(1) # Pace execution

        logger.info("All close orders sent.")
        
        time.sleep(5)
        
        # Check Positions Again
        client.clear_state()
        client.send_positions_request()
        time.sleep(3)
        print(f"Final Positions: {client.positions}")

    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        client.stop()

if __name__ == "__main__":
    attempt_close()
