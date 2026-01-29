"""
Financial Analysis Expert - Comprehensive Financial Analysis Toolkit
"""

import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
from scipy import stats
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

class FinancialAnalyzer:
    """
    Comprehensive financial analysis toolkit for stocks, portfolios, and market data
    """
    
    def __init__(self):
        self.data = None
        self.tickers = []
        
    def fetch_stock_data(self, tickers, period="1y", interval="1d"):
        """
        Fetch stock data from Yahoo Finance
        
        Args:
            tickers: List of stock tickers or single ticker
            period: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
            interval: Data interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)
        """
        if isinstance(tickers, str):
            tickers = [tickers]
            
        self.tickers = tickers
        data = yf.download(tickers, period=period, interval=interval)
        
        if len(tickers) == 1:
            # For single ticker, flatten the column structure
            data.columns = [col[0] for col in data.columns]
        
        self.data = data
        return data
    
    def calculate_returns(self, price_column='Close'):
        """
        Calculate daily returns for the data
        """
        if self.data is None:
            raise ValueError("No data available. Please fetch data first.")
            
        returns = self.data[price_column].pct_change().dropna()
        
        if len(self.tickers) == 1:
            returns = returns.to_frame('Returns')
            
        return returns
    
    def basic_statistics(self, returns=None):
        """
        Calculate basic statistical measures
        """
        if returns is None:
            returns = self.calculate_returns()
            
        stats_dict = {
            'Mean': returns.mean(),
            'Std Dev': returns.std(),
            'Median': returns.median(),
            'Min': returns.min(),
            'Max': returns.max(),
            'Skewness': returns.skew(),
            'Kurtosis': returns.kurtosis()
        }
        
        return pd.DataFrame(stats_dict)
    
    def calculate_sharpe_ratio(self, returns=None, risk_free_rate=0.02):
        """
        Calculate Sharpe Ratio
        
        Args:
            returns: Returns data
            risk_free_rate: Annual risk-free rate (default 2%)
        """
        if returns is None:
            returns = self.calculate_returns()
            
        # Convert annual risk-free rate to daily
        daily_rf = risk_free_rate / 252
        
        excess_returns = returns - daily_rf
        sharpe_ratio = excess_returns.mean() / excess_returns.std() * np.sqrt(252)
        
        return sharpe_ratio
    
    def calculate_sortino_ratio(self, returns=None, risk_free_rate=0.02):
        """
        Calculate Sortino Ratio (downside risk adjusted return)
        """
        if returns is None:
            returns = self.calculate_returns()
            
        daily_rf = risk_free_rate / 252
        excess_returns = returns - daily_rf
        
        # Calculate downside deviation
        downside_returns = excess_returns[excess_returns < 0]
        downside_deviation = downside_returns.std()
        
        sortino_ratio = excess_returns.mean() / downside_deviation * np.sqrt(252)
        
        return sortino_ratio
    
    def calculate_max_drawdown(self, prices=None):
        """
        Calculate Maximum Drawdown
        """
        if prices is None:
            prices = self.data['Close'] if 'Close' in self.data.columns else self.data
            
        if len(self.tickers) == 1:
            prices = prices.to_frame()
            
        rolling_max = prices.expanding().max()
        drawdown = (prices - rolling_max) / rolling_max
        max_drawdown = drawdown.min()
        
        return max_drawdown
    
    def calculate_var(self, returns=None, confidence_level=0.05):
        """
        Calculate Value at Risk (VaR)
        
        Args:
            returns: Returns data
            confidence_level: Confidence level (default 5% VaR)
        """
        if returns is None:
            returns = self.calculate_returns()
            
        var_historical = returns.quantile(confidence_level)
        
        # Parametric VaR (assuming normal distribution)
        mean = returns.mean()
        std = returns.std()
        var_parametric = mean + stats.norm.ppf(confidence_level) * std
        
        return pd.DataFrame({
            'Historical VaR': var_historical,
            'Parametric VaR': var_parametric
        })
    
    def calculate_beta(self, stock_returns, market_returns):
        """
        Calculate Beta coefficient
        
        Args:
            stock_returns: Stock returns
            market_returns: Market returns (e.g., S&P 500)
        """
        covariance = np.cov(stock_returns.dropna(), market_returns.dropna())[0][1]
        market_variance = np.var(market_returns.dropna())
        beta = covariance / market_variance
        
        return beta
    
    def portfolio_analysis(self, weights=None):
        """
        Perform portfolio analysis
        
        Args:
            weights: Portfolio weights (default: equal weight)
        """
        if self.data is None:
            raise ValueError("No data available. Please fetch data first.")
            
        returns = self.calculate_returns()
        
        if weights is None:
            weights = np.array([1/len(self.tickers)] * len(self.tickers))
        
        # Portfolio returns
        portfolio_returns = (returns * weights).sum(axis=1)
        
        # Portfolio metrics
        portfolio_stats = {
            'Annual Return': portfolio_returns.mean() * 252,
            'Annual Volatility': portfolio_returns.std() * np.sqrt(252),
            'Sharpe Ratio': self.calculate_sharpe_ratio(portfolio_returns),
            'Sortino Ratio': self.calculate_sortino_ratio(portfolio_returns),
            'Max Drawdown': self.calculate_max_drawdown(portfolio_returns).min(),
            'VaR (5%)': self.calculate_var(portfolio_returns).iloc[0, 0]
        }
        
        return portfolio_stats, portfolio_returns
    
    def correlation_analysis(self):
        """
        Calculate correlation matrix for the assets
        """
        returns = self.calculate_returns()
        correlation_matrix = returns.corr()
        
        return correlation_matrix
    
    def technical_indicators(self, ticker):
        """
        Calculate basic technical indicators for a specific ticker
        """
        if self.data is None:
            raise ValueError("No data available. Please fetch data first.")
        
        if len(self.tickers) > 1:
            price_data = self.data['Close'][ticker]
        else:
            price_data = self.data['Close']
        
        # Moving Averages
        ma_20 = price_data.rolling(window=20).mean()
        ma_50 = price_data.rolling(window=50).mean()
        ma_200 = price_data.rolling(window=200).mean()
        
        # RSI (Relative Strength Index)
        delta = price_data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        # Bollinger Bands
        bb_period = 20
        bb_std = 2
        bb_middle = price_data.rolling(window=bb_period).mean()
        bb_upper = bb_middle + (price_data.rolling(window=bb_period).std() * bb_std)
        bb_lower = bb_middle - (price_data.rolling(window=bb_period).std() * bb_std)
        
        indicators = pd.DataFrame({
            'Price': price_data,
            'MA_20': ma_20,
            'MA_50': ma_50,
            'MA_200': ma_200,
            'RSI': rsi,
            'BB_Upper': bb_upper,
            'BB_Middle': bb_middle,
            'BB_Lower': bb_lower
        })
        
        return indicators
    
    def plot_price_chart(self, tickers=None):
        """
        Plot price chart for specified tickers
        """
        if self.data is None:
            raise ValueError("No data available. Please fetch data first.")
        
        if tickers is None:
            tickers = self.tickers
        
        plt.figure(figsize=(12, 6))
        
        if len(self.tickers) == 1:
            plt.plot(self.data.index, self.data['Close'], label=self.tickers[0])
        else:
            for ticker in tickers:
                plt.plot(self.data.index, self.data['Close'][ticker], label=ticker)
        
        plt.title('Stock Price Chart')
        plt.xlabel('Date')
        plt.ylabel('Price')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.show()
    
    def plot_returns_distribution(self, ticker=None):
        """
        Plot returns distribution
        """
        returns = self.calculate_returns()
        
        if ticker and len(self.tickers) > 1:
            returns_data = returns[ticker]
        else:
            returns_data = returns.iloc[:, 0] if len(self.tickers) > 1 else returns
            
        plt.figure(figsize=(12, 8))
        
        # Histogram
        plt.subplot(2, 2, 1)
        plt.hist(returns_data.dropna(), bins=50, alpha=0.7, density=True)
        plt.title('Returns Distribution')
        plt.xlabel('Daily Returns')
        plt.ylabel('Density')
        
        # Q-Q Plot
        plt.subplot(2, 2, 2)
        stats.probplot(returns_data.dropna(), dist="norm", plot=plt)
        plt.title('Q-Q Plot')
        
        # Time Series
        plt.subplot(2, 2, 3)
        plt.plot(returns_data.index, returns_data.cumsum())
        plt.title('Cumulative Returns')
        plt.xlabel('Date')
        plt.ylabel('Cumulative Return')
        
        # Box Plot
        plt.subplot(2, 2, 4)
        plt.boxplot(returns_data.dropna())
        plt.title('Returns Box Plot')
        plt.ylabel('Daily Returns')
        
        plt.tight_layout()
        plt.show()
    
    def generate_report(self, ticker=None):
        """
        Generate comprehensive financial report
        """
        if self.data is None:
            raise ValueError("No data available. Please fetch data first.")
        
        print("=" * 60)
        print("FINANCIAL ANALYSIS REPORT")
        print("=" * 60)
        print(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Tickers: {', '.join(self.tickers)}")
        print(f"Data Period: {self.data.index[0].strftime('%Y-%m-%d')} to {self.data.index[-1].strftime('%Y-%m-%d')}")
        print()
        
        # Basic Statistics
        print("BASIC STATISTICS")
        print("-" * 30)
        returns = self.calculate_returns()
        basic_stats = self.basic_statistics(returns)
        print(basic_stats.round(4))
        print()
        
        # Risk Metrics
        print("RISK METRICS")
        print("-" * 30)
        sharpe = self.calculate_sharpe_ratio(returns)
        sortino = self.calculate_sortino_ratio(returns)
        max_dd = self.calculate_max_drawdown()
        var = self.calculate_var(returns)
        
        risk_metrics = pd.DataFrame({
            'Sharpe Ratio': sharpe,
            'Sortino Ratio': sortino,
            'Max Drawdown': max_dd,
            'VaR (5%)': var.iloc[:, 0]
        })
        print(risk_metrics.round(4))
        print()
        
        # Correlation Analysis
        if len(self.tickers) > 1:
            print("CORRELATION MATRIX")
            print("-" * 30)
            corr_matrix = self.correlation_analysis()
            print(corr_matrix.round(4))
            print()
        
        # Current Prices
        print("CURRENT PRICES")
        print("-" * 30)
        if len(self.tickers) == 1:
            print(f"{self.tickers[0]}: ${self.data['Close'].iloc[-1]:.2f}")
        else:
            for ticker in self.tickers:
                price = self.data['Close'][ticker].iloc[-1]
                print(f"{ticker}: ${price:.2f}")
        print()
        
        print("=" * 60)
        print("END OF REPORT")
        print("=" * 60)


# Example usage
if __name__ == "__main__":
    # Initialize analyzer
    analyzer = FinancialAnalyzer()
    
    # Example: Analyze tech stocks
    tickers = ['AAPL', 'GOOGL', 'MSFT', 'AMZN']
    
    # Fetch data
    print("Fetching stock data...")
    data = analyzer.fetch_stock_data(tickers, period="1y")
    
    # Generate comprehensive report
    analyzer.generate_report()
    
    # Portfolio analysis with equal weights
    portfolio_stats, portfolio_returns = analyzer.portfolio_analysis()
    print("\nPORTFOLIO STATISTICS (Equal Weights)")
    print("-" * 40)
    for metric, value in portfolio_stats.items():
        print(f"{metric}: {value:.4f}")
    
    # Technical analysis for first stock
    print(f"\nTECHNICAL INDICATORS FOR {tickers[0]}")
    print("-" * 40)
    indicators = analyzer.technical_indicators(tickers[0])
    print(indicators.tail())
