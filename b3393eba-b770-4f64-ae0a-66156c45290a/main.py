from surmount.base_class import Strategy, TargetAllocation
from surmount.data import CboeVolatilityIndexVix
from surmount.logging import log
from surmount.technical_indicators import SMA, RSI

class TradingStrategy(Strategy):
    def __init__(self):
        self.tickers = ["TQQQ", "SQQQ"]  # Leveraged ETFs for NASDAQ-100
        self.data_list = [CboeVolatilityIndexVix()]

    @property
    def interval(self):
        return "1hour"

    @property
    def assets(self):
        return self.tickers

    @property
    def data(self):
        return self.data_list

    def run(self, data):
        # Access VIX data to determine market volatility
        vix_data = data[("cboe_volatility_index_vix",)][-1]["value"]
        log(f"Current VIX: {vix_data}")

        allocation_dict = {}
        
        # Define the VIX thresholds for trading decisions
        vix_low_threshold = 12
        vix_high_threshold = 20

        if vix_data < vix_low_threshold:
            # Lower volatility, favor long positions in TQQQ
            allocation_dict["TQQQ"] = 0.5  # Allocate 50% to TQQQ
            allocation_dict["SQQQ"] = 0.0  # No allocation to SQQQ
        elif vix_data > vix_high_threshold:
            # Higher volatility, favor short positions or hedge with SQQQ
            allocation_dict["TQQQ"] = 0.0  # No allocation to TQQQ
            allocation_dict["SQQQ"] = 0.5  # Allocate 50% to SQQQ
        else:
            # Neutral or in-between volatility, hold positions
            allocation_dict["TQQQ"] = 0.25  # Allocate 25% to TQQQ
            allocation_dict["SQQQ"] = 0.25  # Allocate 25% to SQQQ

        return TargetAllocation(allocation_dict)