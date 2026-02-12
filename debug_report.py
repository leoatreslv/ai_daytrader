from ctrader_fix_client import CTraderFixClient
from datetime import datetime
import logging

# Configure Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

def test_report():
    print("Initializing Client...")
    # Initialize with dummy args
    client = CTraderFixClient(notifier=None)
    
    print(f"Loaded {len(client.trade_history)} trades.")
    
    print("\n--- Generating Report ---")
    report = client.get_daily_report()
    print(report)
    print("-------------------------")

    print(f"\nCurrent System Time: {datetime.now()}")

if __name__ == "__main__":
    import sys
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
    test_report()
