#Type code himport pandas as pd
import numpy as np
from datetime import datetime, timedelta
from enum import Enum

class UnderlyingSymbol(Enum):
    SPY = "SPY"
    QQQ = "QQQ"

class LeveragedETF(Enum):
    SPXU = "SPXU"  # -3x S&P 500
    SQQQ = "SQQQ"  # -3x NASDAQ-100
    UPRO = "UPRO"  # 3x S&P 500
    TQQQ = "TQQQ"  # 3x NASDAQ-100

class KlingerLeveragedStrategy:
    def __init__(self,
                 short_term=34,
                 long_term=55,
                 signal_period=13,
                 volume_factor=0.7,
                 hist_threshold=2.0,
                 trend_threshold=0.2,
                 market_open_hour=9,
                 market_close_hour=16):
        """
        Initialize strategy parameters
        
        Parameters:
        short_term (int): Short-term Klinger period
        long_term (int): Long-term Klinger period
        signal_period (int): Signal line period
        volume_factor (float): Volume impact factor
        hist_threshold (float): Histogram threshold for signals
        trend_threshold (float): Trend strength threshold
        """
        self.short_term = short_term
        self.long_term = long_term
        self.signal_period = signal_period
        self.volume_factor = volume_factor
        self.hist_threshold = hist_threshold
        self.trend_threshold = trend_threshold
        self.market_open_hour = market_open_hour
        self.market_close_hour = market_close_hour

    def calculate_time_normalized_volume(self, df):
        """
        Calculate volume normalized by time of day patterns
        """
        df['hour'] = df['datetime'].dt.hour
        
        # Calculate average volume for each hour
        hourly_avg_volume = df.groupby('hour')['Volume'].mean()
        
        # Normalize volume by hour of day
        df['norm_volume'] = df.apply(
            lambda x: x['Volume'] / hourly_avg_volume[x['hour']], axis=1
        )
        
        return df

    def calculate_klinger(self, df):
        """
        Calculate time-normalized Klinger Volume Oscillator
        """
        # Normalize volume first
        df = self.calculate_time_normalized_volume(df)
        
        # Calculate trend direction
        df['trend'] = np.where(df['Close'] > df['Close'].shift(1), 1, -1)
        
        # Calculate daily high/low range
        df['dm'] = df['High'] - df['Low']
        
        # Calculate Volume Force
        df['vf'] = df['norm_volume'] * abs(df['dm']) * df['trend'] * self.volume_factor
        
        # Calculate EMAs of Volume Force
        df['short_ema'] = df['vf'].ewm(span=self.short_term, adjust=False).mean()
        df['long_ema'] = df['vf'].ewm(span=self.long_term, adjust=False).mean()
        
        # Calculate Klinger Oscillator
        df['kvo'] = df['short_ema'] - df['long_ema']
        
        # Calculate Signal Line
        df['signal_line'] = df['kvo'].ewm(span=self.signal_period, adjust=False).mean()
        
        # Calculate Histogram
        df['histogram'] = df['kvo'] - df['signal_line']
        
        # Normalize histogram
        df['norm_histogram'] = (df['histogram'] - df['histogram'].rolling(window=55).mean()) / \
                              df['histogram'].rolling(window=55).std()
        
        return df

    def identify_divergences(self, df):
        """
        Identify price and Klinger divergences
        """
        window = 5  # Look back period for divergence
        
        df['price_high'] = df['Close'].rolling(window=window, center=True).max()
        df['kvo_high'] = df['kvo'].rolling(window=window, center=True).max()
        
        df['price_low'] = df['Close'].rolling(window=window, center=True).min()
        df['kvo_low'] = df['kvo'].rolling(window=window, center=True).min()
        
        # Bearish divergence
        df['bearish_div'] = (df['Close'] >= df['price_high']) & \
                           (df['kvo'] < df['kvo_high'])
        
        # Bullish divergence
        df['bullish_div'] = (df['Close'] <= df['price_low']) & \
                           (df['kvo'] > df['kvo_low'])
        
        return df

    def get_leveraged_etf(self, underlying: UnderlyingSymbol, direction: str) -> str:
        """
        Map underlying and direction to appropriate leveraged ETF
        """
        if direction == 'up':
            return LeveragedETF.UPRO.value if underlying == UnderlyingSymbol.SPY else LeveragedETF.TQQQ.value
        else:
            return LeveragedETF.SPXU.value if underlying == UnderlyingSymbol.SPY else LeveragedETF.SQQQ.value

    def calculate_position_size(self, df, vix_level=None):
        """
        Calculate position size based on signal strength and market conditions
        """
        # Get latest histogram value
        hist_strength = abs(df['norm_histogram'].iloc[-1])
        
        # Base size on histogram strength
        base_size = min(1.0, hist_strength / self.hist_threshold)
        
        # Adjust for VIX if available
        if vix_level is not None:
            vix_scalar = 1.0 - (vix_level - 15) * 0.02  # Reduce size as VIX increases
            base_size *= max(0.2, min(1.0, vix_scalar))
        
        return round(base_size, 2)

    def generate_signals(self, df, underlying: UnderlyingSymbol, vix_data=None):
        """
        Generate trading signals based on Klinger analysis
        """
        # Calculate Klinger indicators
        df = self.calculate_klinger(df)
        df = self.identify_divergences(df)
        
        current_hour = df['datetime'].iloc[-1].hour
        if current_hour < self.market_open_hour or current_hour >= self.market_close_hour:
            return {'signal': 'NONE', 'reason': 'Outside trading hours'}
        
        # Get latest values
        current_hist = df['norm_histogram'].iloc[-1]
        current_kvo = df['kvo'].iloc[-1]
        current_price = df['Close'].iloc[-1]
        
        # Initialize signal dictionary
        signal = {
            'signal': 'NONE',
            'underlying': underlying.value,
            'leveraged_etf': None,
            'histogram_value': current_hist,
            'kvo_value': current_kvo,
            'entry_price': current_price,
            'position_size': 0
        }
        
        # Check for strong histogram signals
        if abs(current_hist) > self.hist_threshold:
            # Long signal
            if current_hist > 0 and current_kvo > 0:
                if df['bullish_div'].iloc[-1]:  # Confirm with bullish divergence
                    signal['signal'] = 'BUY'
                    signal['leveraged_etf'] = self.get_leveraged_etf(underlying, 'up')
            
            # Short signal
            elif current_hist < 0 and current_kvo < 0:
                if df['bearish_div'].iloc[-1]:  # Confirm with bearish divergence
                    signal['signal'] = 'SELL'
                    signal['leveraged_etf'] = self.get_leveraged_etf(underlying, 'down')
        
        # If we have a signal, calculate position size and levels
        if signal['signal'] != 'NONE':
            vix_level = vix_data['Close'].iloc[-1] if vix_data is not None else None
            signal['position_size'] = self.calculate_position_size(df, vix_level)
            
            # Calculate stop and target based on recent volatility
            volatility = df['Close'].pct_change().std() * np.sqrt(252)
            signal['stop_loss'] = current_price * (1 - volatility * 1.5)
            signal['profit_target'] = current_price * (1 + volatility * 2.5)
            
        return signal

def example_usage():
    # Create sample hourly data
    dates = pd.date_range(start='2024-01-01 09:30:00', 
                         end='2024-01-10 16:00:00', 
                         freq='H')
    
    np.random.seed(42)
    
    # Generate more realistic price movement
    returns = np.random.normal(0.0001, 0.001, len(dates))
    price = 100 * np.exp(np.cumsum(returns))
    
    # Sample SPY data with realistic volume pattern
    spy_data = pd.DataFrame({
        'datetime': dates,
        'Close': price,
        'High': price * (1 + abs(np.random.normal(0, 0.001, len(dates)))),
        'Low': price * (1 - abs(np.random.normal(0, 0.001, len(dates)))),
        'Volume': np.abs(np.random.normal(1000000, 200000, len(dates))) * \
                 (1 + np.sin(np.pi * dates.hour / 8)) # Volume pattern
    })
    
    # Sample VIX data
    vix_data = pd.DataFrame({
        'datetime': dates,
        'Close': np.abs(np.random.normal(20, 5, len(dates)))
    })
    
    # Initialize strategy
    strategy = KlingerLeveragedStrategy()
    
    # Generate signals
    signals = strategy.generate_signals(spy_data, UnderlyingSymbol.SPY, vix_data)
    
    return signals

def analyze_signals(df, strategy):
    """
    Analyze signal frequency and quality
    """
    df = strategy.calculate_klinger(df)
    df = strategy.identify_divergences(df)
    
    signals = pd.DataFrame({
        'datetime': df['datetime'],
        'histogram': df['norm_histogram'],
        'signal': np.where(df['norm_histogram'] > strategy.hist_threshold, 1,
                 np.where(df['norm_histogram'] < -strategy.hist_threshold, -1, 0))
    })
    
    signal_stats = {
        'total_signals': len(signals[signals['signal'] != 0]),
        'avg_signals_per_day': len(signals[signals['signal'] != 0]) / len(signals['datetime'].dt.date.unique()),
        'avg_signal_duration': len(signals[signals['signal'] != 0]) / \
                             len(signals[signals['signal'].diff().fillna(0) != 0])
    }
    
    return signal_stats