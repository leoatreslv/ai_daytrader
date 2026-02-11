
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
        time.sleep(3)
        
        if not client.positions:
            logger.info("No positions found to close.")
            return

        print(f"Current Positions: {client.positions}")
        
        # Find the target position (Short 10?)
        target_sym_id = None
        target_qty = 0.0
        target_side = None # 'short' or 'long'
        
        for sym_id, pos in client.positions.items():
            if pos.get('short', 0.0) > 0:
                target_sym_id = sym_id
                target_qty = pos['short']
                target_side = 'short'
                break
            elif pos.get('long', 0.0) > 0:
                target_sym_id = sym_id
                target_qty = pos['long']
                target_side = 'long'
                break
        
        if not target_sym_id:
            logger.info("No active positions found.")
            return
            
        sym_name = client.get_symbol_name(target_sym_id)
        print(f"Found Position: {target_side.upper()} {target_qty} on {sym_name} (ID: {target_sym_id})")
        
        # confirm = input("Attempt to CLOSE this position? (yes/no): ")
        # if confirm.lower() != "yes":
        #    return
        print("bypassing confirmation... Attempting CLOSE.")
            
        # Construct Closing Order
        side = '1' if target_side == 'short' else '2' # Buy if Short, Sell if Long
        
        logger.info(f"Sending Close Order: Side={side}, Qty={target_qty}, Symbol={target_sym_id}")
        
        msg = simplefix.FixMessage()
        client.trade_session._add_header(msg, "D")
        
        cls_ord_id = f"close_{int(time.time())}"
        msg.append_pair(11, cls_ord_id) 
        msg.append_pair(55, target_sym_id)
        msg.append_pair(54, side) 
        msg.append_pair(60, datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3])
        msg.append_pair(38, str(int(target_qty))) 
        msg.append_pair(40, "1") # Market
        msg.append_pair(59, "1") # GTC
        
        # Remove Tag 77 (Not Supported)
        # Just send standard opposite order.
        # If Hedging account, this might create a new position.
        # msg.append_pair(58, "Auto Close Standard") # Removed Tag 58
        
        client.trade_session._send_raw(msg)
        logger.info("Order Sent.")
        
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

# Monkey patch handle_message to see raw rejects
def attempt_close_with_debug():
    # ... logic is same, but let's just run attempt_close() 
    # and rely on standard logging which I previously customized in debug_positions_live?
    # No, I should use the client as is, but maybe increase log level or patch on_message
    
    # Let's verify if client logs raw reject details.
    # ctrader_fix_client.py: logger.warning(f"[{source}] REJECT: {msg.get(58)}")
    # It doesn't log RefTagID.
    pass

if __name__ == "__main__":
    attempt_close()
