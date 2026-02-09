import time
import pandas as pd
from datetime import datetime
from data_loader import DataLoader

# Mock Client
class MockFixClient:
    def __init__(self):
        self.market_data_callbacks = []

# Setup
client = MockFixClient()
loader = DataLoader(client)

# Simulate Ticks for Symbol "41"
print("Simulating ticks for '41'...")
symbol = "41"

# T=0: First tick
loader.on_tick(symbol, 2000.0)
print("Tick 1 added.")

# T=60s: Second tick (should start new bar)
# We can't easily jump time in `datetime.now()` inside `DataLoader` without mocking datetime.
# Instead, we will inspect `loader.ticks` and manually modify timestamps for testing.

loader.on_tick(symbol, 2001.0) # Tick 2
loader.on_tick(symbol, 2002.0) # Tick 3

# Manually retain the ticks but skew their times to simulate elapsed time
# Tick 1: T-3 min
# Tick 2: T-2 min
# Tick 3: T-1 min
# Tick 4: Now

now = pd.Timestamp.now()
loader.ticks[symbol] = [
    {'time': now - pd.Timedelta(minutes=3), 'price': 2000.0},
    {'time': now - pd.Timedelta(minutes=2), 'price': 2001.0}, # New Bar
    {'time': now - pd.Timedelta(minutes=2, seconds=30), 'price': 2001.5}, # Same Bar
    {'time': now - pd.Timedelta(minutes=1), 'price': 2002.0}, # New Bar
    {'time': now, 'price': 2003.0} # New Bar
]

print(f"Injecting {len(loader.ticks[symbol])} ticks spanning 3 minutes.")

# Try to get bars
df = loader.get_latest_bars(symbol)
if df is not None:
    print("\n✅ Bars Generated:")
    print(df)
else:
    print("\n❌ Not enough data (None returned)")

# Check threshold logic
if df is not None and len(df) >= 2:
    print("\n✅ Chart would be generated.")
else:
    print("\n❌ Chart would NOT be generated (len < 2).")
