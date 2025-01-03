from surmount.base_class import Strategy, TargetAllocation
from surmount.technical_indicators import SMA
from surmount.logging import log

class TradingStrategy(Strategy):
    @property
    def assets(self):
        # Define the assets to trade; in this case, QQQ.
        return ["QQQ"]

    @property
    def interval(self):
        # Set the interval for data collection; changing to '1hour' since '15min' is not supported.
        return "1hour"

    def run(self, data):
        # Access closing price data for QQQ
        closing_prices = [i["QQQ"]["close"] for i in data["ohlcv"]]
        
        # Compute short-term and long-term SMAs as a proxy for the HiLoActivator
        short_sma = SMA("QQQ", data["ohlcv"], length=5)  # Short-term SMA
        long_sma = SMA("QQQ", data["ohlcv"], length=20)  # Long-term SMA
        
        allocation = 0

        # Assuming the strategy to buy when the short-term SMA crosses above the long-term SMA (bullish signal)
        # and to sell (not holding the position, i.e., allocation=0) when the opposite is true.
        if len(short_sma) > 0 and len(long_sma) > 0:  # Ensure there's enough data for both SMAs
            if short_sma[-1] > long_sma[-1]:  # Checking for the bullish crossover condition
                allocation = 1  # Full allocation to QQQ
            else:
                allocation = 0  # No allocation to QQQ

        # Log the decision (for debugging/verification purposes)
        log("QQQ allocation: " + str(allocation))

        # Return the target allocation
        return TargetAllocation({"QQQ": allocation})