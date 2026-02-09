from indicators import Indicators
import config
from datetime import datetime, timedelta
from logger import setup_logger

logger = setup_logger("Strategy")

class Strategy:
    def __init__(self, trading_client, llm_client):
        self.trading = trading_client
        self.llm = llm_client
        self.last_llm_check = None
        self.current_bias = "NEUTRAL"

    def update_llm_bias(self, df):
        """
        Update the biased based on LLM analysis every 30 minutes.
        """
        if df is None or df.empty:
            return

        now = datetime.now()
        if self.last_llm_check is None or (now - self.last_llm_check) > timedelta(minutes=30):
            logger.info("Updating LLM Bias...")
            
            # Create a technical summary from the dataframe
            last_row = df.iloc[-1]
            close = last_row['close']
            rsi = last_row.get('RSI_14', last_row.get('RSI', 'N/A'))
            
            # Trend Check
            trend_slope = Indicators.get_trend_slope(df)
            trend_str = "UP" if trend_slope > 0 else "DOWN"
            
            summary = f"Price: {close:.2f}, RSI: {rsi}, Trend: {trend_str}"
            
            # Send to LLM
            try:
                sentiment = self.llm.get_market_sentiment(summary)
                if sentiment and 'bias' in sentiment:
                    self.current_bias = sentiment['bias'].upper()
                    self.last_llm_check = now
                    logger.info(f"LLM Updated Bias: {self.current_bias} (Reason: {sentiment.get('reasoning', 'N/A')})")
                else:
                    logger.warning("LLM returned no bias.")
            except Exception as e:
                logger.error(f"Failed to update LLM bias: {e}")

    def check_signal(self, df):
        """
        Analyze dataframe and return a trading signal.
        """
        if df is None or df.empty:
            return None

        # Add Indicators
        try:
             df = Indicators.add_all_indicators(df)
        except Exception as e:
             return None # Not enough data
        
        # Update LLM Bias (throttled inside)
        self.update_llm_bias(df)
        
        # Get latest technical signals
        signals = Indicators.check_signals(df)
        
        # Logic for Left-Side Reversal with LLM Confirmation
        # RSI Oversold + Below Lower BB + (Bullish OR Neutral Bias) -> BUY CALL
        if signals.get('rsi_oversold') and signals.get('below_bb'):
            if self.current_bias in ["BULLISH", "NEUTRAL"]:
                return {"action": "BUY_CALL", "reason": f"Oversold + Below BB + Bias {self.current_bias}"}
            else:
                 logger.debug(f"Signal IGNORED: Oversold but Bias is {self.current_bias}")
        
        # RSI Overbought + Above Upper BB + (Bearish OR Neutral Bias) -> BUY PUT
        if signals.get('rsi_overbought') and signals.get('above_bb'):
            if self.current_bias in ["BEARISH", "NEUTRAL"]:
                return {"action": "BUY_PUT", "reason": f"Overbought + Above BB + Bias {self.current_bias}"}
            else:
                 logger.debug(f"Signal IGNORED: Overbought but Bias is {self.current_bias}")

        return None
