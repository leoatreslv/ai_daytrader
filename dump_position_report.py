
import logging
import time
import simplefix
from ctrader_fix_client import CTraderFixClient

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("DumpAP")

def dump_ap_tags():
    client = CTraderFixClient(notifier=None)
    
    # Monkey patch to print raw
    original_handle = client.on_message
    
    def on_message_debug(source, msg):
        if msg.get(35) == b'AP':
            print("\n--- POSITION REPORT (AP) ---")
            for tag, val in msg:
                print(f"{tag}={val.decode() if isinstance(val, bytes) else val}")
            print("----------------------------\n")
        original_handle(source, msg)
        
    client.on_message = on_message_debug
    
    try:
        client.start()
        time.sleep(2)
        
        if not client.trade_session.logged_on:
            logger.error("Not logged on.")
            return

        logger.info("Requesting Positions...")
        client.send_positions_request()
        
        time.sleep(5)
        
    except KeyboardInterrupt:
        pass
    finally:
        client.stop()

if __name__ == "__main__":
    dump_ap_tags()
