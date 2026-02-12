import unittest
import os
import json
from unittest.mock import MagicMock
from ctrader_fix_client import CTraderFixClient

class TestReport(unittest.TestCase):
    def setUp(self):
        # Clean up previous test file
        if os.path.exists("trades.json"):
            os.remove("trades.json")
            
        self.mock_notifier = MagicMock()
        self.client = CTraderFixClient(notifier=self.mock_notifier)

    def tearDown(self):
        if os.path.exists("trades.json"):
           os.remove("trades.json")

    def test_save_and_load_trades(self):
        # Simulate a trade
        trade = {
            'time': "2025-10-25 14:00:00",
            'symbol': "XAUUSD",
            'side': "SELL",
            'qty': "10",
            'price': "2025.50",
            'pnl': 50.0,
            'type': "TP"
        }
        
        # Add and Save
        self.client.trade_history.append(trade)
        self.client._save_trades()
        
        # Check File
        self.assertTrue(os.path.exists("trades.json"))
        
        # Reload Client
        new_client = CTraderFixClient()
        self.assertEqual(len(new_client.trade_history), 1)
        loaded_trade = new_client.trade_history[0]
        self.assertEqual(loaded_trade['symbol'], "XAUUSD")
        
    def test_report_generation(self):
        # Add some trades (Today and Yesterday)
        from datetime import datetime, timedelta
        today_str = datetime.now().strftime("%Y-%m-%d")
        yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        t1 = {
            'time': f"{today_str} 10:00:00",
            'symbol': "EURUSD",
            'side': "BUY",
            'qty': "5",
            'price': "1.1000",
            'pnl': -10.0,
            'type': "SL"
        }
        
        t2 = {
            'time': f"{yesterday_str} 10:00:00", # Should be ignored
            'symbol': "GBPUSD", 
            'pnl': 100.0
        }
        
        self.client.trade_history = [t1, t2]
        
        report = self.client.get_daily_report()
        print(f"\n[Report Output]\n{report}")
        
        self.assertIn("DAILY REPORT", report)
        self.assertIn("EURUSD", report)
        self.assertNotIn("GBPUSD", report) # Yesterday should filter out
        self.assertIn("Total Daily PnL: 🔴 -10.00", report)

if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    unittest.main()
