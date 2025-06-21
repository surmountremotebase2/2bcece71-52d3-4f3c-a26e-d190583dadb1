#Type code here// crypto-trading-bot-with-klinger.js
const axios = require('axios');
const crypto = require('crypto');
const KlingerOscillator = require('./klinger-oscillator');

class CryptoTradingBot {
  constructor(config) {
    this.exchange = config.exchange;
    this.apiKey = config.apiKey;
    this.apiSecret = config.apiSecret;
    this.symbol = config.symbol; // e.g., 'BTCUSDT'
    this.interval = config.interval; // e.g., '1h'
    this.lastSignal = null;
    this.historicalData = [];
    
    // Initialize Klinger Oscillator with configuration
    this.klingerOscillator = new KlingerOscillator({
      shortPeriod: config.klingerShortPeriod || 34,
      longPeriod: config.klingerLongPeriod || 55,
      signalPeriod: config.klingerSignalPeriod || 13
    });
    
    // Minimum data points needed for the indicator
    this.minDataPoints = Math.max(
      this.klingerOscillator.longPeriod + this.klingerOscillator.signalPeriod, 
      100 // Ensure we have enough data for reliable signals
    );
    
    // Risk management
    this.maxPositionSize = config.maxPositionSize || 0.1; // Maximum portion of balance to use
    this.stopLossPercent = config.stopLossPercent || 0.03; // 3% stop loss
    this.takeProfitPercent = config.takeProfitPercent || 0.06; // 6% take profit
    
    // Track positions
    this.positions = [];
  }

  async start() {
    console.log(`Starting Klinger Oscillator trading bot for ${this.symbol} on ${this.exchange}...`);
    console.log(`Using Klinger settings: Short=${this.klingerOscillator.shortPeriod}, Long=${this.klingerOscillator.longPeriod}, Signal=${this.klingerOscillator.signalPeriod}`);
    
    // Initial data load
    try {
      await this.loadHistoricalData();
      console.log(`Loaded ${this.historicalData.length} historical data points`);
    } catch (error) {
      console.error('Failed to load historical data:', error.message);
      return;
    }
    
    // Set up recurring check
    setInterval(async () => {
      try {
        await this.checkAndTrade();
      } catch (error) {
        console.error('Error in trading cycle:', error.message);
      }
    }, this.getIntervalInMs());
    
    // Initial check
    await this.checkAndTrade();
  }

  async loadHistoricalData() {
    // Load enough historical data for our calculations
    const response = await this.fetchCandlestickData(this.minDataPoints);
    
    this.historicalData = response.map(candle => ({
      timestamp: candle[0],
      open: parseFloat(candle[1]),
      high: parseFloat(candle[2]),
      low: parseFloat(candle[3]),
      close: parseFloat(candle[4]),
      volume: parseFloat(candle[5])
    }));
  }

  async checkAndTrade() {
    // 1. Update data with the latest candle
    await this.updateLatestData();
    
    // 2. Calculate Klinger Oscillator
    try {
      const klingerResult = this.klingerOscillator.calculate(this.historicalData);
      
      // 3. Generate signal based on Klinger Oscillator with critical levels
      const signalData = this.klingerOscillator.generateSignal(klingerResult, this.historicalData);
      
      // 4. Execute trades based on signal
      if (signalData && signalData.signal !== this.lastSignal) {
        // Calculate dynamic levels for better trade management
        const enhancedLevels = this.klingerOscillator.calculateDynamicLevels(
          signalData.criticalLevels, 
          this.historicalData
        );
        
        await this.executeTrade(signalData.signal, enhancedLevels);
        this.lastSignal = signalData.signal;
      }
      
      // 5. Check and manage existing positions using critical levels
      await this.managePositionsWithLevels();
      
      // 6. Log current state
      this.logCurrentState(klingerResult, signalData);
    } catch (error) {
      console.error('Error calculating Klinger Oscillator:', error.message);
    }
  }

  async updateLatestData() {
    // Fetch the latest candle
    const latestCandles = await this.fetchCandlestickData(2); // Get 2 most recent candles
    
    if (latestCandles.length > 0) {
      const latestCandle = latestCandles[latestCandles.length - 1];
      const latestTimestamp = latestCandle[0];
      
      // Check if we already have this candle
      const existingIndex = this.historicalData.findIndex(
        candle => candle.timestamp === latestTimestamp
      );
      
      if (existingIndex >= 0) {
        // Update existing candle
        this.historicalData[existingIndex] = {
          timestamp: latestCandle[0],
          open: parseFloat(latestCandle[1]),
          high: parseFloat(latestCandle[2]),
          low: parseFloat(latestCandle[3]),
          close: parseFloat(latestCandle[4]),
          volume: parseFloat(latestCandle[5])
        };
      } else {
        // Add new candle and remove oldest if necessary
        this.historicalData.push({
          timestamp: latestCandle[0],
          open: parseFloat(latestCandle[1]),
          high: parseFloat(latestCandle[2]),
          low: parseFloat(latestCandle[3]),
          close: parseFloat(latestCandle[4]),
          volume: parseFloat(latestCandle[5])
        });
        
        // Keep data size manageable
        if (this.historicalData.length > this.minDataPoints * 1.5) {
          this.historicalData = this.historicalData.slice(-this.minDataPoints);
        }
      }
    }
  }

  async fetchCandlestickData(limit) {
    // Implementation depends on exchange
    // This example is for Binance
    try {
      const response = await axios.get(`https://api.binance.com/api/v3/klines`, {
        params: {
          symbol: this.symbol,
          interval: this.interval,
          limit: limit
        }
      });
      
      return response.data;
    } catch (error) {
      console.error('Error fetching candlestick data:', error.message);
      throw error;
    }
  }

  async executeTrade(signal) {
    console.log(`Executing ${signal} order for ${this.symbol}`);
    
    try {
      // Get current account balance for position sizing
      const balance = await this.getAvailableBalance();
      
      if (signal === 'BUY') {
        // Calculate position size
        const positionSize = this.calculatePositionSize(balance);
        if (positionSize <= 0) return;
        
        // Get current price
        const currentPrice = this.historicalData[this.historicalData.length - 1].close;
        
        // Calculate stop loss and take profit levels
        const stopLoss = currentPrice * (1 - this.stopLossPercent);
        const takeProfit = currentPrice * (1 + this.takeProfitPercent);
        
        // Place buy order
        const order = await this.placeBuyOrder(positionSize);
        
        // Track this position
        this.positions.push({
          id: order.orderId,
          symbol: this.symbol,
          entryPrice: currentPrice,
          quantity: positionSize,
          stopLoss: stopLoss,
          takeProfit: takeProfit,
          timestamp: Date.now()
        });
        
        console.log(`Buy order placed for ${positionSize} ${this.symbol} at ${currentPrice}`);
        console.log(`Stop loss: ${stopLoss}, Take profit: ${takeProfit}`);
      } 
      else if (signal === 'SELL') {
        // Check if we have any open positions
        if (this.positions.length > 0) {
          // Close all positions
          for (let position of this.positions) {
            await this.placeSellOrder(position.quantity);
            console.log(`Sold ${position.quantity} ${this.symbol} based on sell signal`);
          }
          
          this.positions = [];
        } else {
          // Option: You could implement short selling here
          console.log('No open positions to sell. Ignoring sell signal.');
        }
      }
    } catch (error) {
      console.error('Error executing trade:', error.message);
    }
  }

  async managePositions() {
    if (this.positions.length === 0) return;
    
    const currentPrice = this.historicalData[this.historicalData.length - 1].close;
    const positionsToClose = [];
    
    // Check each position for stop loss or take profit
    for (let i = 0; i < this.positions.length; i++) {
      const position = this.positions[i];
      
      if (currentPrice <= position.stopLoss) {
        console.log(`Stop loss triggered for position ${position.id} at ${currentPrice}`);
        positionsToClose.push(i);
      } 
      else if (currentPrice >= position.takeProfit) {
        console.log(`Take profit triggered for position ${position.id} at ${currentPrice}`);
        positionsToClose.push(i);
      }
    }
    
    // Close triggered positions
    for (let i = positionsToClose.length - 1; i >= 0; i--) {
      const position = this.positions[positionsToClose[i]];
      try {
        await this.placeSellOrder(position.quantity);
        console.log(`Closed position ${position.id}: ${position.quantity} ${this.symbol}`);
        this.positions.splice(positionsToClose[i], 1);
      } catch (error) {
        console.error(`Error closing position ${position.id}:`, error.message);
      }
    }
  }

  calculatePositionSize(balance) {
    // Implement your position sizing logic with risk management
    const currentPrice = this.historicalData[this.historicalData.length - 1].close;
    const availableFunds = balance * this.maxPositionSize;
    
    // Calculate quantity based on available funds and current price
    const quantity = availableFunds / currentPrice;
    
    // Return the position size rounded to appropriate precision
    return this.roundToAppropriateDecimals(quantity);
  }

  roundToAppropriateDecimals(value) {
    // Different exchanges and pairs have different rules for decimal places
    // This is a simplified version - you may need to adjust based on the specific trading pair
    if (this.symbol.includes('BTC')) {
      return Math.floor(value * 100000) / 100000; // 5 decimal places
    } else if (this.symbol.includes('ETH')) {
      return Math.floor(value * 10000) / 10000; // 4 decimal places
    } else {
      return Math.floor(value * 100) / 100; // 2 decimal places
    }
  }

  async getAvailableBalance() {
    // In a real implementation, you would fetch this from the exchange API
    // This is a placeholder for demonstration
    return 1000; // Simulate having 1000 USDT available
  }

  async placeBuyOrder(quantity) {
    // In a real implementation, you would make an API call to the exchange
    // This is a placeholder
    console.log(`[SIMULATION] Placing buy order for ${quantity} ${this.symbol}`);
    
    // Simulate a successful order
    return {
      orderId: 'order-' + Date.now(),
      status: 'FILLED',
      executedQty: quantity
    };
  }

  async placeSellOrder(quantity) {
    // In a real implementation, you would make an API call to the exchange
    // This is a placeholder
    console.log(`[SIMULATION] Placing sell order for ${quantity} ${this.symbol}`);
    
    // Simulate a successful order
    return {
      orderId: 'order-' + Date.now(),
      status: 'FILLED',
      executedQty: quantity
    };
  }

  logCurrentState(klingerResult) {
    const latestData = this.historicalData[this.historicalData.length - 1];
    const latestKlinger = klingerResult.klingerOscillator[klingerResult.klingerOscillator.length - 1];
    const latestSignal = klingerResult.signalLine[klingerResult.signalLine.length - 1];
    const latestHistogram = klingerResult.histogram[klingerResult.histogram.length - 1];
    
    console.log('---- Current State ----');
    console.log(`Time: ${new Date(latestData.timestamp).toLocaleString()}`);
    console.log(`Price: ${latestData.close}`);
    console.log(`Klinger Oscillator: ${latestKlinger.toFixed(2)}`);
    console.log(`Signal Line: ${latestSignal.toFixed(2)}`);
    console.log(`Histogram: ${latestHistogram.toFixed(2)}`);
    console.log(`Last Signal: ${this.lastSignal || 'NONE'}`);
    console.log(`Open Positions: ${this.positions.length}`);
    console.log('----------------------');
  }

  getIntervalInMs() {
    // Convert interval string to milliseconds
    const unit = this.interval.slice(-1);
    const value = parseInt(this.interval.slice(0, -1));
    
    switch (unit) {
      case 'm': return value * 60 * 1000;
      case 'h': return value * 60 * 60 * 1000;
      case 'd': return value * 24 * 60 * 60 * 1000;
      default: return 60 * 1000; // default to 1 minute
    }
  }
}

// Usage example
const runBot = async () => {
  const bot = new CryptoTradingBot({
    exchange: 'binance',
    apiKey: 'YOUR_API_KEY',
    apiSecret: 'YOUR_API_SECRET',
    symbol: 'BTCUSDT',
    interval: '1h', // Hourly data
    klingerShortPeriod: 34,
    klingerLongPeriod: 55,
    klingerSignalPeriod: 13,
    maxPositionSize: 0.1, // Use maximum 10% of available balance per trade
    stopLossPercent: 0.03, // 3% stop loss
    takeProfitPercent: 0.06 // 6% take profit
  });

  await bot.start();
};

runBot().catch(error => {
  console.error('Error running bot:', error.message);
});

module.exports = CryptoTradingBot;