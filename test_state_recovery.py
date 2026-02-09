import logging
import time
import simplefix
from ctrader_fix_client import CTraderFixClient
import config

# Setup Logger
logging.getLogger().setLevel(logging.DEBUG) # Root logger
logger = logging.getLogger("RecoveryTest")
logger.setLevel(logging.DEBUG)
logging.getLogger("FixClient").setLevel(logging.DEBUG) # Client logger

handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)
logging.getLogger("FixClient").addHandler(handler)

def test_state_recovery():
    logger.info("Starting State Recovery Test...")
    client = CTraderFixClient()
    
    # 1. Start & Logon
    client.start()
    
    if not (client.quote_session.logged_on and client.trade_session.logged_on):
        logger.error("❌ Not Logged On.")
        return

    logger.info("✅ Logged On. Attempting State Sync...")

    # 2. Test Order Mass Status Request (MsgType AF)
    # This should return ExecutionReports for all active orders
    logger.info("Sending OrderMassStatusRequest (AF)...")
    req_id = f"mass{int(time.time())}"
    msg = simplefix.FixMessage()
    client.trade_session._add_header(msg, "AF")
    msg.append_pair(584, req_id) # MassStatusReqID
    msg.append_pair(585, "7")    # MassStatusReqType: 7 = Status for all orders
    client.trade_session._send_raw(msg)
    
    # 3. Test Request for Positions (MsgType AN)
    # This should return PositionReports (AP)
    logger.info("Sending RequestForPositions (AN)...")
    pos_req_id = f"pos{int(time.time())}"
    msg_pos = simplefix.FixMessage()
    client.trade_session._add_header(msg_pos, "AN")
    msg_pos.append_pair(710, pos_req_id) # PosReqID
    # msg_pos.append_pair(724, "0")      # Removed: caused rejection
    # msg_pos.append_pair(263, "0")      # Removed: caused rejection
    client.trade_session._send_raw(msg_pos)

    # 4. Wait for Responses
    logger.info("Waiting 10s for responses...")
    time.sleep(10)
    
    # Check internal state (if client handles handlers well, they might map, but we mainly check logs)
    logger.info("Test Finished. Check logs for 'ExecutionReport' or 'PositionReport'.")

if __name__ == "__main__":
    test_state_recovery()
