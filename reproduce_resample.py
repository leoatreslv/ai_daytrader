import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def reproduce():
    print("Generating simulated tick data...")
    # Create ticks spanning across minutes
    ticks = []
    base_time = datetime(2023, 1, 1, 10, 0, 0)
    
    # Generate ticks with a GAP
    for i in range(10000):
        if 3000 < i < 6000: # Create a gap provided no ticks
             continue
             
        dt = base_time + timedelta(seconds=i*0.5) 
        price = 100 + i*0.01
        ticks.append({'time': dt, 'price': price})
        
    df = pd.DataFrame(ticks)
    df['time'] = pd.to_datetime(df['time'])
    df.set_index('time', inplace=True)
    
    print(f"Total ticks: {len(df)}")
    
    # Simulate data_loader logic
    print("Resampling OHLC...")
    bars = df['price'].resample('1min').ohlc()
    print(f"OHLC Bars: {len(bars)}")
    print(bars.head())
    print(bars.tail())
    
    print("Resampling Volume (Count)...")
    volume = df['price'].resample('1min').count()
    print(f"Volume Bars: {len(volume)}")
    
    if len(bars) != len(volume):
        print(f"MISMATCH! OHLC: {len(bars)}, Volume: {len(volume)}")
    else:
        print("Lengths match.")
        
    print("Assigning volume...")
    try:
        bars['volume'] = volume
        print("Assignment success.")
    except Exception as e:
        print(f"Assignment FAILED: {e}")
        
    print("Testing pandas_ta concat...")
    try:
        import pandas_ta as ta
        rsi = ta.rsi(bars['close'], length=14)
        if rsi is not None:
            print(f"RSI Length: {len(rsi)}")
            bars = pd.concat([bars, rsi], axis=1)
            print("Concat success.")
        else:
            print("RSI is None.")
    except ImportError:
        print("pandas_ta not installed, skipping.")
    except Exception as e:
        print(f"Concat FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    reproduce()
