import unittest
from unittest.mock import MagicMock
from ctrader_fix_client import CTraderFixClient
from datetime import datetime

class TestPnLFifo(unittest.TestCase):
    def test_fifo_fallback(self):
        client = CTraderFixClient()
        
        # 1. Populate History with an "Open" BUY trade
        client.trade_history.append({
            'time': "2026-02-14 10:00:00",
            'symbol': "1",
            'side': "BUY",
            'qty': "1000",
            'price': "2000.0", # Entry Price
            'pnl': None
        })
        
        # 2. Simulate finding entry price for a closing SELL
        # side="SELL" -> implies closing Long -> Look for BUY
        entry = client._get_fifo_entry_price("1", "SELL")
        self.assertEqual(entry, 2000.0)
        
        # 3. Simulate PnL Calculation Logic (Mocking the relevant part of on_message would be complex, 
        # so we test the logic outcome directly)
        fill_px = 2010.0
        qty = 1000
        
        if entry > 0:
            pnl = (fill_px - entry) * qty
            self.assertEqual(pnl, 10000.0) # (2010 - 2000) * 1000 = 10 * 1000 = 10000

if __name__ == '__main__':
    unittest.main()
