import simplefix
from ctrader_fix_client import CTraderFixClient
import logging

# Setup Logging to Console
logging.basicConfig(level=logging.INFO)

class MockSession:
    def __init__(self):
        self.connected = True
        self.sent_messages = []
        
    def _send_raw(self, msg):
        self.sent_messages.append(msg)
        
    def _add_header(self, msg, msg_type):
        msg.append_pair(35, msg_type)

def test_position_parsing():
    print("Testing Position Report Parsing...")
    
    client = CTraderFixClient(notifier=None)
    
    # Mock Sessions
    client.trade_session = MockSession()
    client.quote_session = MockSession()
    
    # Simulate receiving a Position Report (AP)
    # cTrader Position Report: 
    # 35=AP, 55=SymbolID, 704=LongQty, 705=ShortQty
    
    # Case 1: Long Position of 1000
    msg = simplefix.FixMessage()
    msg.append_pair(35, "AP")
    msg.append_pair(55, "1") # EURUSD
    msg.append_pair(704, "1000") # Long Qty
    msg.append_pair(705, "0")    # Short Qty
    
    print(f"Injecting Legacy Position Report: {msg}")
    client.on_message("TRADE", msg)
    
    print(f"Current Positions: {client.positions}")
    
    if client.positions.get("1") == 1000.0:
        print("PASS: Long Position Parsed Correctly.")
    else:
        print(f"FAIL: Expected 1000, got {client.positions.get('1')}")
        
    # Case 2: Short Position of 500
    msg2 = simplefix.FixMessage()
    msg2.append_pair(35, "AP")
    msg2.append_pair(55, "2") # GBPUSD
    msg2.append_pair(704, "0") 
    msg2.append_pair(705, "500") # Short Qty
    
    print(f"Injecting Short Position Report: {msg2}")
    client.on_message("TRADE", msg2)
    
    print(f"Current Positions: {client.positions}")
    
    if client.positions.get("2") == -500.0:
        print("PASS: Short Position Parsed Correctly.")
    else:
        print(f"FAIL: Expected -500, got {client.positions.get('2')}")
        
    # Case 3: Netting (Long 2000, Short 1000 -> Net 1000)
    # Note: cTrader usually reports aggregated, but let's test the logic
    msg3 = simplefix.FixMessage()
    msg3.append_pair(35, "AP")
    msg3.append_pair(55, "3") 
    msg3.append_pair(704, "2000") 
    msg3.append_pair(705, "1000")
    
    client.on_message("TRADE", msg3)
    if client.positions.get("3") == 1000.0:
        print("PASS: Netting Parsed Correctly.")
    else:
        print(f"FAIL: Expected 1000 (Net), got {client.positions.get('3')}")

if __name__ == "__main__":
    test_position_parsing()
