# Trading Strategy Analyzer Frontend

A comprehensive web-based frontend for analyzing stocks using RSI and SMA trading strategies.

## Features

### Strategy Analysis
- **SMA (Simple Moving Average) Strategy**: Crossover signals between fast and slow moving averages
- **RSI (Relative Strength Index) Strategy**: Momentum-based signals with overbought/oversold levels
- **Combined Analysis**: View both strategies simultaneously

### Interactive Charts
- Candlestick price charts with strategy indicators
- Buy/sell signal markers
- RSI oscillator with threshold levels
- SMA lines with crossover visualization

### Key Metrics
- Real-time price data
- Signal counts and current recommendations
- Volume and price change information
- Customizable strategy parameters

## Quick Start

### Option 1: Run with Batch File (Windows)
```bash
# Simply double-click the run_frontend.bat file
# or run from command line:
run_frontend.bat
```

### Option 2: Manual Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
streamlit run app.py
```

## Usage

1. **Enter Stock Symbol**: Type any valid ticker symbol (AAPL, GOOGL, TSLA, etc.)
2. **Choose Time Period**: Select from 1 month to 2 years of historical data
3. **Select Strategy**: Choose SMA, RSI, or both strategies
4. **Adjust Parameters**: 
   - SMA: Fast and slow period lengths
   - RSI: Period, upper and lower thresholds
5. **Click Analyze**: View detailed charts and signal analysis

## Strategy Details

### SMA Strategy
- **Buy Signal**: Fast SMA crosses above Slow SMA
- **Sell Signal**: Fast SMA crosses below Slow SMA
- **Parameters**: Fast period (default: 10), Slow period (default: 20)

### RSI Strategy
- **Buy Signal**: RSI > lower threshold (30) with positive momentum
- **Sell Signal**: RSI > upper threshold (70) or negative momentum
- **Parameters**: Period (default: 14), Lower threshold (30), Upper threshold (70)

## Data Source

- Uses Yahoo Finance for real-time and historical data
- Updates automatically during market hours
- Supports all major stock exchanges

## Requirements

- Python 3.7+
- Internet connection for data fetching
- Web browser for Streamlit interface

## Troubleshooting

- **No data found**: Check if the stock symbol is valid
- **Connection errors**: Verify internet connection
- **Import errors**: Ensure all dependencies are installed via `pip install -r requirements.txt`