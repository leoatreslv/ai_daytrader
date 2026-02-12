import sys
import os
from datetime import datetime, timedelta

# Add parent dir to path to import config and client
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

import config

def test_session_start_logic(offset, now_utc_mock=None):
    print(f"\n--- Testing with Offset: {offset} ---")
    
    # Mock config offset
    config.TIMEZONE_OFFSET = offset
    
    # Use provided mock time or actual UTC
    now_utc = now_utc_mock if now_utc_mock else datetime.utcnow()
    now_user_local = now_utc + timedelta(hours=config.TIMEZONE_OFFSET)
    
    print(f"Current UTC: {now_utc.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"User Local:  {now_user_local.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Open Time logic from ctrader_fix_client.py
    open_time_local = now_user_local.replace(
        hour=config.MARKET_OPEN_HOUR, 
        minute=config.MARKET_OPEN_MINUTE, 
        second=0, microsecond=0
    )
    
    if now_user_local >= open_time_local:
        session_start_local = open_time_local
    else:
        session_start_local = open_time_local - timedelta(days=1)
        
    session_start_utc = session_start_local - timedelta(hours=config.TIMEZONE_OFFSET)
    
    print(f"Market Open (Local): {open_time_local.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Session Start (Local): {session_start_local.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Session Start (UTC):   {session_start_utc.strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    # Test 1: User's reported scenario (roughly 00:30 GMT+8 on Feb 13)
    # This corresponds to Feb 12 16:30 UTC.
    mock_now_utc = datetime(2026, 2, 12, 16, 30)
    test_session_start_logic(offset=8, now_utc_mock=mock_now_utc)
    
    # Test 2: Current actual time
    test_session_start_logic(offset=8)
    
    # Test 3: Edge case - Just before open
    # If open is 23:01 Local. Mock local as 22:50 Feb 12.
    # UTC would be 14:50 Feb 12.
    mock_before_open = datetime(2026, 2, 12, 14, 50)
    test_session_start_logic(offset=8, now_utc_mock=mock_before_open)
