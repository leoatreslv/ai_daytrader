import time
import logging
import config
from ctrader_fix_client import CTraderFixClient
import simplefix

# Setup Logger
logger = logging.getLogger("DebugFIX")
logger.setLevel(logging.INFO)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def run_debug():
    print("Starting FIX Capabilities Debug...")
    
    # Initialize Client
    client = CTraderFixClient(notifier=None)
    
    # Overwrite on_message to just log everything
    def debug_on_message(source, msg):
        msg_type = msg.get(35)
        print(f"[{source}] RECV: {msg}")
        
        if msg_type == b'AP':
            print(f"SUCCESS! Received Position Report: {msg}")
        elif msg_type == b'3':
             print(f"REJECT: {msg.get(58)}")
        elif msg_type == b'j':
             print(f"BUSINESS REJECT: {msg.get(58)}")
            
    client.on_message = debug_on_message
    
    # Connect Trade Session Only
    print("Connecting Trade Session...")
    client.trade_session.connect()
    
    # Wait for Logon
    for i in range(10):
        if client.trade_session.logged_on:
            print("Logged On!")
            break
        time.sleep(1)
        
    if not client.trade_session.logged_on:
        print("Failed to Logon. Check credentials.")
        return

    # Test 1: Standard AN (Current implementation)
    print("\nTest 1: Sending AN (Only PosReqID)...")
    msg = simplefix.FixMessage()
    client.trade_session._add_header(msg, "AN")
    msg.append_pair(710, f"req_1_{int(time.time())}")
    client.trade_session._send_raw(msg)
    time.sleep(3)

    # Test 2: AN with PosReqType=0 (Positions for specific date)
    print("\nTest 2: Sending AN (PosReqID + PosReqType=0)...")
    msg = simplefix.FixMessage()
    client.trade_session._add_header(msg, "AN")
    msg.append_pair(710, f"req_2_{int(time.time())}")
    msg.append_pair(724, "0")
    client.trade_session._send_raw(msg)
    time.sleep(3)

    # Test 3: AN with PosReqType=1 (Trades)
    # print("\nTest 3: Sending AN (PosReqID + PosReqType=1)...")
    # msg = simplefix.FixMessage()
    # client.trade_session._add_header(msg, "AN")
    # msg.append_pair(710, f"req_3_{int(time.time())}")
    # msg.append_pair(724, "1")
    # client.trade_session._send_raw(msg)
    # time.sleep(3)
    
    print("Debug Complete. Check logs above for 'AP' responses or Rejects.")
    client.trade_session.running = False
    
if __name__ == "__main__":
    run_debug()
