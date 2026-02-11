import pandas as pd
import numpy as np
from strategy import Strategy
from indicators import Indicators
import time

# Mock Classes
class MockTradingClient:
    pass

class MockLLMClient:
    def get_market_sentiment(self, summary):
        return {
            "bias": "BULLISH",
            "confidence": 8,
            "reasoning": "Mock reasoning"
        }

def create_oversold_data():
    # Create 100 bars of data ending in an oversold state
    dates = pd.date_range(end=pd.Timestamp.now(), periods=100, freq="1min")
    df = pd.DataFrame(index=dates)
    
    # Generate price data
    prices = [100.0] * 100
    # Drop significantly at the end to trigger oversold and below BB
    prices[-1] = 80.0
    prices[-2] = 90.0
    prices[-3] = 95.0
    
    df['close'] = prices
    df['high'] = [p + 0.1 for p in prices]
    df['low'] = [p - 0.1 for p in prices]
    df['open'] = prices 
    df['volume'] = 1000
    
    return df

def reproduce_issue():
    print("reproducing Duplicate Signal Issue...")
    
    # Setup
    mock_trade = MockTradingClient()
    mock_llm = MockLLMClient()
    strategy = Strategy(mock_trade, mock_llm)
    
    # Data that triggers a signal
    df = create_oversold_data()
    
    # Simulate main loop running multiple times on the SAME data (or same candle)
    print("\n--- Simulation Start ---")
    signals_received = 0
    test_symbol = "TEST_SYM"
    for i in range(3):
        print(f"Iteration {i+1}: Checking signal...")
        signal = strategy.check_signal(df, test_symbol)
        
        if signal:
            print(f"SIGNAL DETECTED: {signal['action']}")
            signals_received += 1
        else:
            print("No Signal")
            
        time.sleep(0.1)
        
    print("\n--- Simulation End ---")
    if signals_received > 1:
        print(f"FAIL: Strategy returned {signals_received} signals for the same data!")
    else:
        print("PASS: Strategy handled duplicates correctly.")

if __name__ == "__main__":
    reproduce_issue()
