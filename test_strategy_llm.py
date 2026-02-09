
import pandas as pd
import numpy as np
from strategy import Strategy
from indicators import Indicators

# Mock Classes
class MockTradingClient:
    pass

class MockLLMClient:
    def get_market_sentiment(self, summary):
        print(f"[MockLLM] Received Summary: {summary}")
        # Return a Bullish Bias
        return {
            "bias": "BULLISH",
            "confidence": 8,
            "reasoning": "RSI is low and trend is up."
        }
        
def create_dummy_data():
    # Create a DataFrame that generates a Buy Signal (Oversold + Below BB)
    dates = pd.date_range(start="2024-01-01", periods=100, freq="1min")
    df = pd.DataFrame(index=dates)
    
    # Generate price data
    # We want the last price to be low (Oversold)
    prices = [100 + np.sin(i/10) * 2 for i in range(100)]
    # Drop the price significantly at the end to trigger oversold and below BB
    prices[-1] = 80 
    prices[-2] = 90
    
    df['close'] = prices
    df['high'] = [p + 0.1 for p in prices]
    df['low'] = [p - 0.1 for p in prices]
    df['open'] = prices # simplified
    
    return df

def test_strategy():
    print("Testing Strategy with LLM Bias...")
    
    # Setup
    mock_trade = MockTradingClient()
    mock_llm = MockLLMClient()
    strategy = Strategy(mock_trade, mock_llm)
    
    print(f"Initial Bias: {strategy.current_bias}")
    
    # Data
    df = create_dummy_data()
    
    # Run Check Signal
    # This should trigger update_llm_bias -> BULLISH
    # And since data is Oversold, it should return BUY_CALL
    
    # DEBUG: Check indicators manually
    df = Indicators.add_all_indicators(df)
    print("Columns:", df.columns)
    print("Last Row:", df.iloc[-1])
    signals = Indicators.check_signals(df)
    print(f"Signals: {signals}")

    signal = strategy.check_signal(df)
    
    print(f"Post-Check Bias: {strategy.current_bias}")
    print(f"Signal: {signal}")
    
    if signal and signal['action'] == 'BUY_CALL':
        print("TEST PASSED: Buy Signal Generated with Bullish Bias.")
    else:
        print("TEST FAILED: No Signal or Wrong Signal.")
        
    # Test Bearish Constraint
    print("\nTesting Bearish Constraint...")
    # Force Bias to BEARISH manually or via mock
    strategy.current_bias = "BEARISH"
    strategy.last_llm_check = pd.Timestamp.now() # Prevent update
    
    signal = strategy.check_signal(df)
    print(f"Signal (Expect None): {signal}")
    
    if signal is None:
        print("TEST PASSED: Buy Signal Blocked by Bearish Bias.")
    else:
         print(f"TEST FAILED: Signal {signal} should have been blocked.")

if __name__ == "__main__":
    test_strategy()
