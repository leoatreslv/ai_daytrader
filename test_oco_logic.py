import unittest
from unittest.mock import MagicMock, patch
import threading
import time
from ctrader_fix_client import CTraderFixClient
import simplefix

class TestOCOLogic(unittest.TestCase):
    def test_oco_cancellation(self):
        client = CTraderFixClient()
        client.trade_session._send_raw = MagicMock()
        client.trade_session.logged_on = True
        
        # 1. Setup Active Position
        pos_id = "Pos123"
        
        # 2. Simulate Active Protections (SL and TP)
        # Order 1: SL
        sl_order_id = "SL_OID"
        sl_cl_id = "SL_CLID"
        client.open_orders[sl_order_id] = {
            "symbol": "1", "side": "SELL", "qty": "1000",
            "position_id": pos_id, "ord_type": "3", # Stop
            "cl_ord_id": sl_cl_id
        }
        
        # Order 2: TP
        tp_order_id = "TP_OID"
        tp_cl_id = "TP_CLID"
        client.open_orders[tp_order_id] = {
            "symbol": "1", "side": "SELL", "qty": "1000",
            "position_id": pos_id, "ord_type": "2", # Limit
            "cl_ord_id": tp_cl_id
        }
        
        # 3. Simulate Fill of SL Order
        # Construct Execution Report (MsgType=8, ExecType=F, OrdStatus=2)
        msg = simplefix.FixMessage()
        msg.append_pair(35, "8")
        msg.append_pair(37, sl_order_id)
        msg.append_pair(11, sl_cl_id)
        msg.append_pair(150, "F") # Trade
        msg.append_pair(39, "2") # Filled
        msg.append_pair(55, "1")
        msg.append_pair(54, "2") # Sell
        msg.append_pair(38, "1000") # Qty
        msg.append_pair(32, "1000") # LastQty
        msg.append_pair(31, "2000.0") # LastPx
        msg.append_pair(721, pos_id) # PositionID
        msg.append_pair(40, "3") # Stop Order
        
        # 4. Process Message
        client.on_message("TRADE", msg)
        
        # 5. Verify Cancel Request Sent for TP Order
        # We expect _send_raw to be called with a Cancel Request (MsgType='F')
        # Check args
        sent_msgs = client.trade_session._send_raw.call_args_list
        found_cancel = False
        for call in sent_msgs:
            raw = call[0][0] # First arg matches
            # Simple check if raw bytes contain "35=F" (Cancel) and "41=TP_CLID" (OrigClOrdID)
            if b"35=F" in raw.encode() and f"41={tp_cl_id}".encode() in raw.encode():
                found_cancel = True
                break
        
        self.assertTrue(found_cancel, "Cancel request for TP order was not sent upon SL fill.")

if __name__ == '__main__':
    unittest.main()
