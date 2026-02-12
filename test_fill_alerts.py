import unittest
from unittest.mock import MagicMock
from ctrader_fix_client import CTraderFixClient
import simplefix

class TestFillAlerts(unittest.TestCase):
    def setUp(self):
        # Mock Notifier
        self.mock_notifier = MagicMock()
        self.client = CTraderFixClient(notifier=self.mock_notifier)
        
        # Pre-load positions for PnL calculation
        # Long: 10 @ 2000.00
        self.client.positions['XAUUSD'] = {
            'long': 10.0, 'short': 0.0,
            'long_avg_px': 2000.00, 'short_avg_px': 0.0
        }
        self.client.symbol_map['Gold'] = 'XAUUSD'

    def test_stop_loss_fill_long(self):
        # Simulate SL Fill (Selling to close Long)
        # Price 1990.00 (Loss of 10.00 per unit * 10 units = -100.00)
        
        msg = simplefix.FixMessage()
        msg.append_pair(35, "8") # Execution Report
        msg.append_pair(150, "F") # Trade
        msg.append_pair(37, "ord123")
        msg.append_pair(55, "XAUUSD")
        msg.append_pair(54, "2") # Sell (Close Long)
        msg.append_pair(38, "10") # Qty
        msg.append_pair(31, "1990.00") # Fill Px
        msg.append_pair(32, "10") # Fill Qty
        msg.append_pair(40, "3") # Stop Order
        
        # Process
        self.client.on_message("TRADE", msg)
        
        # Verify Notification
        args, _ = self.mock_notifier.notify.call_args
        notification = args[0]
        
        print(f"\n[Test SL Fill]\n{notification}")
        
        self.assertIn("STOP LOSS FILLED", notification)
        self.assertIn("Realized PnL: 🔴 -100.00", notification)

    def test_take_profit_fill_long(self):
        # Simulate TP Fill (Selling to close Long)
        # Price 2010.00 (Profit of 10.00 per unit * 10 units = +100.00)
        
        msg = simplefix.FixMessage()
        msg.append_pair(35, "8") # Execution Report
        msg.append_pair(150, "F") # Trade
        msg.append_pair(40, "2") # Limit Order (TP)
        msg.append_pair(54, "2") # Sell
        msg.append_pair(55, "XAUUSD")
        msg.append_pair(31, "2010.00")
        msg.append_pair(32, "10")
        
        self.client.on_message("TRADE", msg)
        
        args, _ = self.mock_notifier.notify.call_args
        notification = args[0]
        
        print(f"\n[Test TP Fill]\n{notification}")
        
        self.assertIn("TAKE PROFIT / LIMIT FILLED", notification)
        self.assertIn("Realized PnL: 🟢 100.00", notification)

if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    unittest.main()
