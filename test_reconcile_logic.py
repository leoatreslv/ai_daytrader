
import unittest
from unittest.mock import MagicMock, patch
from ctrader_fix_client import CTraderFixClient
import config

class TestReconcileLogic(unittest.TestCase):
    def setUp(self):
        # Patch standard library things that CTraderFixClient uses
        self.patcher_logger = patch('ctrader_fix_client.setup_logger')
        self.mock_logger = self.patcher_logger.start()
        
        # Initialize client with mocks
        self.client = CTraderFixClient(notifier=MagicMock())
        self.client.trade_session = MagicMock()
        self.client.quote_session = MagicMock()
        
    def tearDown(self):
        self.patcher_logger.stop()

    def test_reconcile_missing_protections(self):
        # Setup: 1 Position, No Orders
        self.client.position_details = {
            '12345': {
                'symbol_id': '41',
                'qty': 1.0,
                'side': 'long',
                'entry_price': 2000.0,
                'position_id': '12345'
            }
        }
        self.client.open_orders = {}
        
        # Trigger reconciliation
        with patch.object(self.client, 'submit_order') as mock_submit:
            self.client.reconcile_protections()
            
            # Should call submit_order twice (SL and TP)
            self.assertEqual(mock_submit.call_count, 2)
            
            # Verify SL call (side 2 for long position, order type 3)
            # Find the SL call
            sl_call = next(c for c in mock_submit.call_args_list if c[1].get('order_type') == '3')
            self.assertEqual(sl_call[0][0], '41') # symbol
            self.assertEqual(sl_call[0][1], 1.0) # qty
            self.assertEqual(sl_call[0][2], '2') # side
            # SL Price for Long: Entry - (Entry * STOP_LOSS_PCT)
            expected_sl = 2000.0 - (2000.0 * config.STOP_LOSS_PCT)
            self.assertEqual(sl_call[1].get('stop_px'), f"{expected_sl:.2f}")
            self.assertEqual(sl_call[1].get('position_id'), '12345')

    def test_reconcile_partial_protections(self):
        # Setup: 1 Position, Only TP exists
        self.client.position_details = {
            '12345': {
                'symbol_id': '41',
                'qty': 1.0,
                'side': 'long',
                'entry_price': 2000.0,
                'position_id': '12345'
            }
        }
        self.client.open_orders = {
            'ORD1': {
                'position_id': '12345',
                'ord_type': '2', # TP
                'side': 'SELL'
            }
        }
        
        # Trigger reconciliation
        with patch.object(self.client, 'submit_order') as mock_submit:
            self.client.reconcile_protections()
            
            # Should call submit_order only once (SL)
            self.assertEqual(mock_submit.call_count, 1)
            self.assertEqual(mock_submit.call_args[1].get('order_type'), '3')

    def test_reconcile_full_protections(self):
        # Setup: 1 Position, SL and TP exist
        self.client.position_details = {
            '12345': {
                'symbol_id': '41',
                'qty': 1.0,
                'side': 'long',
                'entry_price': 2000.0,
                'position_id': '12345'
            }
        }
        self.client.open_orders = {
            'ORD1': {'position_id': '12345', 'ord_type': '2'},
            'ORD2': {'position_id': '12345', 'ord_type': '3'}
        }
        
        # Trigger reconciliation
        with patch.object(self.client, 'submit_order') as mock_submit:
            self.client.reconcile_protections()
            
            # Should call submit_order zero times
            self.assertEqual(mock_submit.call_count, 0)

if __name__ == "__main__":
    unittest.main()
