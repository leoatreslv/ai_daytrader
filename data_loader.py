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
        if isinstance(symbol_id, bytes):
            symbol_id = symbol_id.decode()
            
        now = datetime.now()
        if symbol_id not in self.ticks:
            self.ticks[symbol_id] = []
        
        self.ticks[symbol_id].append({'time': now, 'price': price})
        # logger.debug(f"[{now.strftime('%H:%M:%S')}] Tick: {symbol_id} @ {price}")
        print(f"[{now.strftime('%H:%M:%S')}] Tick: {symbol_id} @ {price}")
        
        # Simple aggregation: If > 60 ticks or > 1 min, make a bar (Simulated)
        # Real impl would bucket by time.
        pass

    def get_latest_bars(self, symbol_id, length=50):
        # Convert ticks to dataframe
        if symbol_id not in self.ticks or not self.ticks[symbol_id]:
            return None
        
        df = pd.DataFrame(self.ticks[symbol_id])
        df['time'] = pd.to_datetime(df['time'])
        df.set_index('time', inplace=True)
        
        # Resample to 1-minute OHLC bars
        bars = df['price'].resample('1min').ohlc()
        
        # Add Volume (count of ticks)
        bars['volume'] = df['price'].resample('1min').count()
        
        # Drop empty intervals (no ticks)
        bars.dropna(inplace=True)
        
        # Rename columns to lowercase for consistency
        bars.columns = ['open', 'high', 'low', 'close', 'volume']
        
        if len(bars) < 2:
            # If not enough aggregated bars, return distinct None to signal "Waiting for more data"
            return None
            
        return bars.tail(length)
