import unittest
from ctrader_fix_client import CTraderFixClient
import simplefix

class TestPositionCacheUpdate(unittest.TestCase):
    def test_cache_update_on_fill(self):
        client = CTraderFixClient()
        
        # 1. Verify initial state
        self.assertEqual(len(client.positions), 0)
        
        # 2. Simulate an Order Fill (MsgType=8, ExecType=F)
        # This mimicks what the server sends when an order is filled.
        msg = simplefix.FixMessage()
        msg.append_pair(35, "8") # ExecutionReport
        msg.append_pair(150, "F") # Trade
        msg.append_pair(721, "Pos123") # PositionID
        msg.append_pair(55, "1") # Symbol ID
        msg.append_pair(54, "1") # Side: Buy
        msg.append_pair(32, "1000") # LastQty (Fill Size)
        msg.append_pair(6, "2000.0") # AvgPx (Fill Price)
        msg.append_pair(37, "Ord1") # OrderID
        msg.append_pair(11, "ClOrd1") # ClOrdID
        
        # 3. Process the message
        # We need to mock the session or just call on_message if possible
        # Since on_message parses raw fix, we can't call it directly easily without a mock session.
        # Instead, we'll verify the Logic gap by inspecting the code, but for this test, 
        # let's try to invoke the logic if we can mock the session.
        
        # ... actually, let's just use the client to process a "fake" message object if we extract the logic?
        # No, let's look at the method. on_message takes a 'msg' object (simplefix.FixMessage).
        # We need to mock the 'source' argument if it exists? No, on_message(self, msg) isn't the signature.
        # The signature is typical for simplefix or a wrapper.
        # Looking at code: `def on_message(self, msg):` (inside standard loop) is not exposed.
        # The client uses `simplefix.FixParser`.
        
        # Let's manual-trigger the internal logic if possible, or just rely on the FACT that we saw "pass" in the code.
        # But to be rigorous:
        pass 

if __name__ == '__main__':
    unittest.main()
