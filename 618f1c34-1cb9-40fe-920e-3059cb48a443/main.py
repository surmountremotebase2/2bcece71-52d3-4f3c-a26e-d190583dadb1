from surmount.base_class import Strategy, TargetAllocation
from surmount.technical_indicators import SMA, MACD
from surmount.logging import log

class TradingStrategy(Strategy):
    def __init__(self):
        self.tickers = ["AAPL", "MSFT"]  # Example equities
        # Define any initialization parameters here

    @property
    def interval(self):
        return "1day"  # Choose appropriate interval

    @property
    def assets(self):
        return self.tickers

    def run(self, data):
        allocation_dict = {}
        
        for ticker in self.tickers:
            # Calculate Short and Long SMAs for volume to approximate significant changes
            short_sma_vol = SMA(ticker, data, length=10)  # Short-term SMA for volume
            long_sma_vol = SMA(ticker, data, length=30)  # Long-term SMA for volume
            
            # MACD for price trend indication
            macd_data = MACD(ticker, data, fast=12, slow=26)
            macd_line = macd_data["MACD"]
            signal_line = macd_data["signal"]

            # Decision logic
            if len(short_sma_vol) > 0 and len(long_sma_vol) > 0:
                current_volume_change = short_sma_vol[-1] - long_sma_vol[-1]
                # Criteria for a buy signal
                if current_volume_change > 0 and macd_line[-1] > signal_line[-1]:
                    allocation_dict[ticker] = 0.5  # Allocate 50% to this asset
                # Criteria for a sell/avoid signal
                elif current_volume_change < 0 or macd_line[-1] < signal_line[-1]:
                    allocation_dict[ticker] = 0  # Do not allocate to this asset
                else:
                    allocation_dict[ticker] = 0.1  # Maintain a minimal position
            else:
                # Default allocation if not enough data
                allocation_dict[ticker] = 0.1  # Minimal position

        return TargetAllocation(allocation_dict)