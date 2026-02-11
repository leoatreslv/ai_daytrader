
import config
from datetime import datetime

def check_market_hours():
    print("--- Market Hours Debug ---")
    
    now = datetime.now()
    print(f"Current System Time: {now}")
    print(f"Current Date: {now.date()}")
    print(f"Current Time: {now.time()}")
    
    # Reload config values to be sure
    market_open_h = config.MARKET_OPEN_HOUR
    market_open_m = config.MARKET_OPEN_MINUTE
    market_close_h = config.MARKET_CLOSE_HOUR
    market_close_m = config.MARKET_CLOSE_MINUTE
    
    print(f"Configured Open: {market_open_h:02d}:{market_open_m:02d}")
    print(f"Configured Close: {market_close_h:02d}:{market_close_m:02d}")
    
    market_open = now.replace(hour=market_open_h, minute=market_open_m, second=0, microsecond=0)
    market_close = now.replace(hour=market_close_h, minute=market_close_m, second=0, microsecond=0)
    
    print(f"Today's Open Datetime: {market_open}")
    print(f"Today's Close Datetime: {market_close}")
    
    # Check for cross-midnight schedule
    is_cross_midnight = False
    if market_open_h > market_close_h or \
       (market_open_h == market_close_h and market_open_m > market_close_m):
        is_cross_midnight = True
        print("Schedule Type: Cross-Midnight (Next Day Close)")
    else:
        print("Schedule Type: Standard Day")

    if is_cross_midnight:
        # Cross-midnight logic
        is_open = now >= market_open or now < market_close
        print(f"Logic: now >= open ({now >= market_open}) OR now < close ({now < market_close})")
    else:
        # Standard logic
        is_open = market_open <= now < market_close
        print(f"Logic: open <= now < close ({market_open <= now < market_close})")
        
    print(f"RESULT: IS OPEN = {is_open}")
    print("--------------------------")

if __name__ == "__main__":
    check_market_hours()
