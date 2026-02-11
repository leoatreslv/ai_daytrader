import pandas as pd
import threading
from datetime import datetime

class DataLoader:
    def __init__(self, client):
        self.client = client
        self.ticks = {} # symbol -> list of {time, price}
        self.bars = {} # symbol -> list of bars
        self.lock = threading.RLock()
        
        # Hook up callback
        self.client.market_data_callbacks.append(self.on_tick)

    def on_tick(self, symbol_id, price):
        if isinstance(symbol_id, bytes):
            symbol_id = symbol_id.decode()
            
        now = datetime.now()
        with self.lock:
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
        with self.lock:
            if symbol_id not in self.ticks or not self.ticks[symbol_id]:
                return None
            
            # Create a copy to minimize lock holding time and avoid modification during DF creation
            data = list(self.ticks[symbol_id])
        
        try:
            df = pd.DataFrame(data)
            df['time'] = pd.to_datetime(df['time'])
            df.set_index('time', inplace=True)
            # Ensure unique index
            df = df[~df.index.duplicated(keep='last')]
            
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
        except Exception as e:
            print(f"Error creating DataFrame for {symbol_id}: {e}")
            return None
