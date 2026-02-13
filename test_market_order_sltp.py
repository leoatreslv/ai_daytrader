
import logging
import time
import simplefix
from ctrader_fix_client import CTraderFixClient
import config

# Setup Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TestSLTP")

def test_market_order_with_sltp():
    logger.info("Starting Market Order + SL/TP Test...")
    
    # 1. Initialize Client
    client = CTraderFixClient()
    
    try:
        # Start Connection
        client.start()
        
        # Wait for Logon
        logger.info("Waiting for Logon...")
        for _ in range(10):
            if client.trade_session.logged_on: break
            time.sleep(1)
            
        if not client.trade_session.logged_on:
            logger.error("❌ Failed to log on.")
            return

        # Fetch Symbols (needed for ID resolution)
        client.fetch_symbols()
        
        # Target Symbol: XAUUSD (ID 41)
        # Use config or fallback
        target_sym = "XAUUSD"
        res_id = client.get_symbol_id(target_sym)
        
        if not res_id:
            logger.warning(f"Could not resolve {target_sym}, trying '41' directly.")
            res_id = "41"
        else:
            logger.info(f"Resolved {target_sym} -> {res_id}")
            
        # Get Current Price (for SL/TP calc) - Rough Estimate or wait for Market Data
        # For test, we can just use a recent known price or wait for a Quote.
        # Let's subscribe and wait briefly.
        client.subscribe_market_data(res_id, "test_req")
        logger.info("Waiting for market data...")
        current_price = 0.0
        for _ in range(10):
            if res_id in client.latest_prices:
                current_price = client.latest_prices[res_id]
                break
            # Try string key too
            if str(res_id) in client.latest_prices:
                current_price = client.latest_prices[str(res_id)]
                break
            time.sleep(1)
            
        if current_price == 0.0:
            logger.warning("⚠️ No price received. Using 2000.0 as fallback.")
            current_price = 2000.0
            
        logger.info(f"Current Price: {current_price}")
        
        # Parameters
        qty = 1 # Smallest qty
        side = '1' # Buy
        
        # Calculate SL/TP
        stop_loss_pct = 0.005 # 0.5%
        take_profit_pct = 0.005 # 0.5%
        
        sl_price = current_price * (1 - stop_loss_pct)
        tp_price = current_price * (1 + take_profit_pct)
        
        # Format prices (2 decimal places for XAUUSD usually)
        sl_str = f"{sl_price:.2f}"
        tp_str = f"{tp_price:.2f}"
        
        logger.info(f"Submitting BUY Market Order for {target_sym} Qty={qty} with SL={sl_str} TP={tp_str}")
        
        # Submit Order using the method that caches protections
        client.submit_order(
            res_id, qty, side, order_type='1',
            sl_price=sl_str, tp_price=tp_str
        )
        
        logger.info("✅ Order Submitted. Watching for Execution and SL/TP submission...")
        
        # Wait and watch logs
        time.sleep(15)
        
        # Check if protections were submitted
        # We can inspect client.open_orders to see if new orders appeared linked to a PositionID
        logger.info("\n--- Post-Execution Status ---")
        open_orders = client.get_orders_string()
        logger.info(f"Open Orders:\n{open_orders}")
        
        positions = client.get_positions_string()
        logger.info(f"Positions:\n{positions}")
        
    except KeyboardInterrupt:
        logger.info("Interrupted.")
    except Exception as e:
        logger.error(f"Test Failed: {e}")
    finally:
        client.stop()

if __name__ == "__main__":
    test_market_order_with_sltp()
