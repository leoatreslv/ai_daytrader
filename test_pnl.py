import unittest
from ctrader_fix_client import CTraderFixClient

class TestPnL(unittest.TestCase):
    def test_pnl_calculation_long(self):
        client = CTraderFixClient()
        # Mock Long Position: 10 Lots @ 2000.00
        client.positions['XAUUSD'] = {
            'long': 10.0, 'short': 0.0,
            'long_avg_px': 2000.00, 'short_avg_px': 0.0
        }
        client.symbol_map['Gold'] = 'XAUUSD'
        
        # Scenario A: Price goes up to 2001.00 (+1.00 diff)
        client.latest_prices['XAUUSD'] = 2001.00
        output = client.get_position_pnl_string()
        
        print(f"\n[Test Long Profit]\n{output}")
        self.assertIn("PnL: 🟢 10.00", output) # 1.00 * 10.0 = 10.00

        # Scenario B: Price goes down to 1999.00 (-1.00 diff)
        client.latest_prices['XAUUSD'] = 1999.00
        output = client.get_position_pnl_string()
        print(f"\n[Test Long Loss]\n{output}")
        self.assertIn("PnL: 🔴 -10.00", output)

    def test_pnl_calculation_short(self):
        client = CTraderFixClient()
        # Mock Short Position: 5 Lots @ 1.1000
        client.positions['EURUSD'] = {
            'long': 0.0, 'short': 5.0,
            'long_avg_px': 0.0, 'short_avg_px': 1.1000
        }
        
        # Scenario A: Price goes down to 1.0900 (+0.0100 diff)
        client.latest_prices['EURUSD'] = 1.0900
        output = client.get_position_pnl_string()
        print(f"\n[Test Short Profit]\n{output}")
        
        # Diff = 0.0100 * 5.0 = 0.05
        # 1.1000 - 1.0900 = 0.01
        self.assertIn("PnL: 🟢 0.05", output)

if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    unittest.main()
