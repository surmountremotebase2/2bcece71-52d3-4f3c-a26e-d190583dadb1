from surmount.base_class import Strategy, TargetAllocation
from surmount.technical_indicators import RSI, SMA, EMA
from surmount.logging import log
from surmount.data import Asset, FinancialStatement, InsiderTrading


class TradingStrategy(Strategy):
    
    def __init__(self):
        # Defining the tickers based on the provided strategy complexity
        self.tickers = ["SPY", "TQQQ", "UVXY", "SPXL", "SQQQ", "TECL", "SMH", "SOXL", "UDOW", "UPRO", "QQQ", "TLT", "PSQ"]
        self.data_list = []
        for ticker in self.tickers:
            self.data_list.extend([FinancialStatement(ticker), InsiderTrading(ticker)])
    
    @property
    def interval(self):
        # Daily rebalance frequency as stated in the strategy's requirement
        return "1day"
    
    @property
    def assets(self):
        return self.tickers
    
    @property
    def data(self):
        return self.data_list

    def run(self, data):
        # Placeholder for complex decision making based on the various conditions mentioned
        allocation_dict = {}
        
        # Example condition checks (Pseudocode, will need actual implementation)
        spy_sma_200 = SMA("SPY", data, 200)
        spy_current_price = data["SPY"]["close"][-1]  # Simplified access
        
        # Decision-making based on the SPY's price relative to its 200-day SMA
        if spy_sma_200 and spy_current_price > spy_sma_200[-1]:  # Bull Market Logic
            # Additional conditions based on RSI and cumulative return
            tqqq_rsi_10 = RSI("TQQQ", data, 10)
            if tqqq_rsi_10 and tqqq_rsi_10[-1] > 79:
                allocation_dict["UVXY"] = 0.1  # Example allocation
            # Further logic can include additional conditions and allocations similarly
        else:  # Bear Market Logic
            # Similar checks and allocations for bear market conditions
            qqq_rsi_10 = RSI("QQQ", data, 10)
            if qqq_rsi_10 and qqq_rsi_10[-1] < 31:
                allocation_dict["TECL"] = 0.1  # Example allocation
        
        # Ensuring allocations do not exceed 100%
        total_allocation = sum(allocation_dict.values())
        if total_allocation > 1.0:
            # Normalize allocations
            for k in allocation_dict:
                allocation_dict[k] = allocation_dict[k] / total_allocation
        
        return TargetAllocation(allocation_dict)