import unittest
import time
from unittest.mock import MagicMock
from ctrader_fix_client import CTraderFixClient
import simplefix

class TestCTraderFixClient(unittest.TestCase):
    def setUp(self):
        self.mock_notifier = MagicMock()
        self.client = CTraderFixClient(notifier=self.mock_notifier)
        # Mock sessions
        self.client.trade_session = MagicMock()
        self.client.quote_session = MagicMock()
        self.client.trade_session.connected = True
        self.client.trade_session._add_header = MagicMock()
        self.client.trade_session._send_raw = MagicMock()

    def test_position_accumulation(self):
        print("Testing Position Accumulation...")
        # Simulate receiving multiple AP messages for same symbol (Hedging)
        
        # Msg 1: Long 1000
        msg1 = simplefix.FixMessage()
        msg1.append_pair(35, "AP")
        msg1.append_pair(55, "1") # EURUSD
        msg1.append_pair(704, "1000") # Long
        msg1.append_pair(705, "0") # Short
        
        self.client.on_message("TRADE", msg1)
        print(f"Pos after Msg 1: {self.client.positions}")
        self.assertEqual(self.client.positions["1"], 1000.0)
        
        # Msg 2: Long 500 (Separate trade)
        msg2 = simplefix.FixMessage()
        msg2.append_pair(35, "AP")
        msg2.append_pair(55, "1") # EURUSD
        msg2.append_pair(704, "500") # Long
        msg2.append_pair(705, "0") # Short
        
        self.client.on_message("TRADE", msg2)
        print(f"Pos after Msg 2: {self.client.positions}")
        self.assertEqual(self.client.positions["1"], 1500.0) # Should sum to 1500
        
    def test_unique_clordid(self):
        print("Testing Unique ClOrdID...")
        # Call submit_order twice rapidly
        self.client.submit_order("1", 1000, "1")
        self.client.submit_order("1", 1000, "1")
        
        # Check args passed to _send_raw
        calls = self.client.trade_session._send_raw.call_args_list
        self.assertEqual(len(calls), 2)
        
        # Extract ClOrdID (Tag 11) from messages
        msg1 = calls[0][0][0] # First arg of first call
        msg2 = calls[1][0][0] # First arg of second call
        
        id1 = msg1.get(11)
        id2 = msg2.get(11)
        
        print(f"ID 1: {id1}")
        print(f"ID 2: {id2}")
        
        self.assertNotEqual(id1, id2)
        self.assertTrue("_" in str(id1)) # Check counter suffix

if __name__ == '__main__':
    unittest.main()
