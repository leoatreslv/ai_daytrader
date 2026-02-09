import pandas as pd
from datetime import datetime

class DataLoader:
    def __init__(self, client):
        self.client = client
        self.ticks = {} # symbol -> list of {time, price}
        self.bars = {} # symbol -> list of bars
        
        # Hook up callback
        self.client.market_data_callbacks.append(self.on_tick)

    def on_tick(self, symbol_id, price):
        now = datetime.now()
        if symbol_id not in self.ticks:
            self.ticks[symbol_id] = []
        
        self.ticks[symbol_id].append({'time': now, 'price': price})
        print(f"[{now.strftime('%H:%M:%S')}] Tick: {symbol_id} @ {price}")
        
        # Simple aggregation: If > 60 ticks or > 1 min, make a bar (Simulated)
        # Real impl would bucket by time.
        pass

    def get_latest_bars(self, symbol_id, length=50):
        # Convert ticks to dataframe
        if symbol_id not in self.ticks or not self.ticks[symbol_id]:
            return None
        
        df = pd.DataFrame(self.ticks[symbol_id])
        df['close'] = df['price']
        # Resample to 1min bars
        # For demo, just return ticks as "bars" if we have enough
        return df.tail(length)
