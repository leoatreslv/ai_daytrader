import pandas as pd
try:
    import pandas_ta as ta
except ImportError:
    try:
        import pandas_ta_classic as ta
    except ImportError:
        raise ImportError("Could not import pandas_ta or pandas_ta_classic")

class Indicators:
    @staticmethod
    def add_all_indicators(df):
        """
        Add RSI, Bollinger Bands, and MACD to the dataframe.
        """
        if df is None or df.empty:
            return df

        # RSI
        # Check for RSI or RSI_14
        cols = df.columns
        if 'RSI' not in cols and 'RSI_14' not in cols:
            rsi = ta.rsi(df['close'], length=14)
            if rsi is not None:
                df = pd.concat([df, rsi], axis=1)

        # Bollinger Bands
        # Check if BBL/BBU exist
        cols = df.columns
        if not any(c.startswith('BBL') for c in cols):
            bbands = ta.bbands(df['close'], length=20, std=2)
            if bbands is not None:
                 df = pd.concat([df, bbands], axis=1)

        # MACD
        if not any(c.startswith('MACD') for c in cols):
            macd = ta.macd(df['close'])
            if macd is not None:
                df = pd.concat([df, macd], axis=1)

        return df

    @staticmethod
    def check_signals(df):
        """
        Return a simple signal dictionary based on the last row.
        """
        if df is None or df.empty:
            return {}

        last_row = df.iloc[-1]
        
        # Check standard pandas_ta column names
        # RSI
        rsi = last_row.get('RSI_14') if 'RSI_14' in last_row else last_row.get('RSI')
        
        # Bollinger Bands
        # Bollinger Bands
        # Find BBL and BBU columns
        cols = df.columns
        bbl_col = next((c for c in cols if c.startswith('BBL')), None)
        bbu_col = next((c for c in cols if c.startswith('BBU')), None)
        
        bbl = last_row.get(bbl_col) if bbl_col else None
        bbu = last_row.get(bbu_col) if bbu_col else None
        close = last_row['close']

        signal = {
            'rsi_oversold': bool(rsi < 30) if rsi is not None else False,
            'rsi_overbought': bool(rsi > 70) if rsi is not None else False,
            'below_bb': bool(close < bbl) if bbl is not None else False,
            'above_bb': bool(close > bbu) if bbu is not None else False
        }
        
        return signal

    @staticmethod
    def get_trend_slope(df, length=20):
        """
        Calculate the slope of the linear regression line for the last 'length' closing prices.
        Positive slope = Uptrend, Negative = Downtrend.
        """
        import numpy as np
        
        if df is None or len(df) < length:
            return 0.0

        y = df['close'].iloc[-length:].values
        x = np.arange(len(y))
        
        # Linear regression: y = mx + c
        slope, intercept = np.polyfit(x, y, 1)
        
        return slope
