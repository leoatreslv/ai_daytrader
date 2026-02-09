import mplfinance as mpf
import pandas as pd
import os
import matplotlib
# Use Agg backend for non-GUI (Docker/Headless) environment
matplotlib.use('Agg')

def generate_candlestick_chart(df, symbol, filename="chart.png"):
    """
    Generates a candlestick chart from the dataframe and saves it to filename.
    df must have proper DatetimeIndex and columns: Open, High, Low, Close.
    """
    if df is None or df.empty:
        return None
    
    # Ensure index is datetime
    if not isinstance(df.index, pd.DatetimeIndex):
        try:
            # Assuming there's a 'time' or 'timestamp' column if index isn't set,
            # or if it was reset. But DataLoader usually sets it?
            # Actually DataLoader returns bars with implicit index or 'time' col?
            if 'time' in df.columns:
                df = df.set_index('time')
            df.index = pd.to_datetime(df.index)
        except:
            return None

    # Conform columns to mplfinance expectations (Capitalized)
    # Our df usually has lowercase 'open', 'high', 'low', 'close'
    plot_df = df.copy()
    rename_map = {
        'open': 'Open', 
        'high': 'High', 
        'low': 'Low', 
        'close': 'Close',
        'volume': 'Volume'
    }
    plot_df.rename(columns=rename_map, inplace=True)
    
    # Validation
    required = ['Open', 'High', 'Low', 'Close']
    if not all(col in plot_df.columns for col in required):
        return None

    # Style
    s = mpf.make_mpf_style(base_mpf_style='charles', rc={'font.size': 10})
    
    # Save
    filepath = os.path.abspath(filename)
    mpf.plot(
        plot_df, 
        type='candle', 
        style=s, 
        title=f"{symbol} Chart",
        ylabel='Price',
        volume=False, # Add volume if available
        savefig=filepath
    )
    
    return filepath
