"""
Portfolio Optimization Module
Advanced portfolio construction and optimization techniques
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize
import matplotlib.pyplot as plt
from financial_analyzer import FinancialAnalyzer

class PortfolioOptimizer:
    """
    Advanced portfolio optimization using Modern Portfolio Theory and beyond
    """
    
    def __init__(self):
        self.analyzer = FinancialAnalyzer()
        self.returns = None
        self.mean_returns = None
        self.cov_matrix = None
        
    def prepare_data(self, tickers, period="1y"):
        """
        Prepare data for optimization
        """
        self.analyzer.fetch_stock_data(tickers, period)
        self.returns = self.analyzer.calculate_returns()
        self.mean_returns = self.returns.mean()
        self.cov_matrix = self.returns.cov()
        
        return self.returns
    
    def efficient_frontier(self, num_portfolios=1000, risk_free_rate=0.02):
        """
        Calculate efficient frontier
        
        Args:
            num_portfolios: Number of random portfolios to generate
            risk_free_rate: Risk-free rate for Sharpe ratio calculation
        """
        num_assets = len(self.mean_returns)
        
        # Generate random portfolios
        results = np.zeros((4, num_portfolios))
        weights_record = []
        
        for i in range(num_portfolios):
            # Generate random weights
            weights = np.random.random(num_assets)
            weights /= np.sum(weights)
            weights_record.append(weights)
            
            # Calculate portfolio metrics
            portfolio_return = np.sum(self.mean_returns * weights) * 252
            portfolio_stddev = np.sqrt(np.dot(weights.T, np.dot(self.cov_matrix * 252, weights)))
            sharpe_ratio = (portfolio_return - risk_free_rate) / portfolio_stddev
            
            results[0,i] = portfolio_return
            results[1,i] = portfolio_stddev
            results[2,i] = sharpe_ratio
            results[3,i] = portfolio_return / (1 + portfolio_stddev)  # Sortino-like ratio
        
        # Convert to DataFrame
        columns = ['Return', 'Volatility', 'Sharpe', 'Return/Vol']
        results_df = pd.DataFrame(results.T, columns=columns)
        
        return results_df, weights_record
    
    def optimize_portfolio(self, objective='sharpe', risk_free_rate=0.02, target_return=None):
        """
        Optimize portfolio weights based on objective function
        
        Args:
            objective: 'sharpe', 'min_variance', 'max_return', or 'target_return'
            risk_free_rate: Risk-free rate
            target_return: Target return for target_return optimization
        """
        num_assets = len(self.mean_returns)
        args = (self.mean_returns, self.cov_matrix, risk_free_rate)
        
        constraints = {'type': 'eq', 'fun': lambda weights: np.sum(weights) - 1}
        bounds = tuple((0, 1) for _ in range(num_assets))
        
        if objective == 'sharpe':
            def neg_sharpe(weights, mean_returns, cov_matrix, risk_free_rate):
                portfolio_return = np.sum(mean_returns * weights) * 252
                portfolio_stddev = np.sqrt(np.dot(weights.T, np.dot(cov_matrix * 252, weights)))
                return -(portfolio_return - risk_free_rate) / portfolio_stddev
            
            result = minimize(neg_sharpe, num_assets * [1./num_assets], args=args,
                            method='SLSQP', bounds=bounds, constraints=constraints)
            
        elif objective == 'min_variance':
            def portfolio_variance(weights, mean_returns, cov_matrix, risk_free_rate):
                return np.dot(weights.T, np.dot(cov_matrix * 252, weights))
            
            result = minimize(portfolio_variance, num_assets * [1./num_assets], args=args,
                            method='SLSQP', bounds=bounds, constraints=constraints)
            
        elif objective == 'max_return':
            def neg_return(weights, mean_returns, cov_matrix, risk_free_rate):
                return -np.sum(mean_returns * weights) * 252
            
            result = minimize(neg_return, num_assets * [1./num_assets], args=args,
                            method='SLSQP', bounds=bounds, constraints=constraints)
            
        elif objective == 'target_return':
            if target_return is None:
                raise ValueError("target_return must be specified for target_return optimization")
            
            constraints = [
                {'type': 'eq', 'fun': lambda weights: np.sum(weights) - 1},
                {'type': 'eq', 'fun': lambda weights: np.sum(self.mean_returns * weights) * 252 - target_return}
            ]
            
            def portfolio_variance(weights, mean_returns, cov_matrix, risk_free_rate):
                return np.dot(weights.T, np.dot(cov_matrix * 252, weights))
            
            result = minimize(portfolio_variance, num_assets * [1./num_assets], args=args,
                            method='SLSQP', bounds=bounds, constraints=constraints)
        
        return result
    
    def risk_parity_portfolio(self):
        """
        Calculate risk parity (equal risk contribution) portfolio
        """
        num_assets = len(self.mean_returns)
        
        def risk_budget_objective(weights):
            # Calculate portfolio risk
            portfolio_variance = np.dot(weights.T, np.dot(self.cov_matrix, weights))
            portfolio_volatility = np.sqrt(portfolio_variance)
            
            # Calculate marginal contribution to risk
            marginal_contrib = np.dot(self.cov_matrix, weights) / portfolio_volatility
            
            # Calculate contribution to risk
            contrib_to_risk = weights * marginal_contrib
            
            # Calculate difference from equal risk contribution
            equal_contrib = portfolio_volatility / num_assets
            risk_diff = contrib_to_risk - equal_contrib
            
            return np.sum(risk_diff ** 2)
        
        constraints = {'type': 'eq', 'fun': lambda weights: np.sum(weights) - 1}
        bounds = tuple((0, 1) for _ in range(num_assets))
        
        result = minimize(risk_budget_objective, num_assets * [1./num_assets],
                         method='SLSQP', bounds=bounds, constraints=constraints)
        
        return result
    
    def black_litterman(self, views, view_confidences, tau=0.025, risk_free_rate=0.02):
        """
        Black-Litterman portfolio optimization
        
        Args:
            views: Dictionary of views {asset: expected_return}
            view_confidences: Dictionary of confidence levels {asset: confidence}
            tau: Uncertainty parameter
            risk_free_rate: Risk-free rate
        """
        num_assets = len(self.mean_returns)
        
        # Market equilibrium returns (CAPM)
        market_weights = np.ones(num_assets) / num_assets  # Assume market cap weighted
        market_return = np.sum(self.mean_returns * market_weights) * 252
        market_variance = np.dot(market_weights.T, np.dot(self.cov_matrix * 252, market_weights))
        risk_aversion = (market_return - risk_free_rate) / market_variance
        
        # Equilibrium excess returns
        pi = risk_aversion * np.dot(self.cov_matrix * 252, market_weights)
        
        # Setup views matrix
        P = np.zeros((len(views), num_assets))
        Q = np.zeros(len(views))
        Omega = np.zeros((len(views), len(views)))
        
        for i, (asset, expected_return) in enumerate(views.items()):
            asset_idx = list(self.mean_returns.index).index(asset)
            P[i, asset_idx] = 1
            Q[i] = expected_return * 252  # Annualized
            confidence = view_confidences.get(asset, 0.5)
            Omega[i, i] = (confidence ** 2) * np.dot(P[i], np.dot(self.cov_matrix * 252, P[i].T))
        
        # Black-Litterman formula
        tau_sigma = tau * self.cov_matrix * 252
        omega_inv = np.linalg.inv(Omega)
        p_tau_sigma_inv = np.dot(P, np.linalg.inv(tau_sigma))
        
        # Posterior expected returns
        bl_return = np.linalg.inv(np.linalg.inv(tau_sigma) + np.dot(P.T, omega_inv).dot(P))
        bl_return = bl_return.dot(np.dot(np.linalg.inv(tau_sigma), pi) + np.dot(P.T, omega_inv).dot(Q))
        
        # Posterior covariance matrix
        bl_cov = np.linalg.inv(np.linalg.inv(tau_sigma) + np.dot(P.T, omega_inv).dot(P))
        
        # Optimize with Black-Litterman inputs
        self.mean_returns = pd.Series(bl_return / 252, index=self.mean_returns.index)
        self.cov_matrix = bl_cov / 252
        
        return self.optimize_portfolio('sharpe', risk_free_rate)
    
    def plot_efficient_frontier(self, num_portfolios=1000, risk_free_rate=0.02):
        """
        Plot efficient frontier with optimal portfolios
        """
        results_df, weights_record = self.efficient_frontier(num_portfolios, risk_free_rate)
        
        # Find optimal portfolios
        max_sharpe_idx = results_df['Sharpe'].idxmax()
        min_vol_idx = results_df['Volatility'].idxmin()
        
        max_sharpe_portfolio = results_df.loc[max_sharpe_idx]
        min_vol_portfolio = results_df.loc[min_vol_idx]
        
        plt.figure(figsize=(12, 8))
        plt.scatter(results_df['Volatility'], results_df['Return'], c=results_df['Sharpe'], 
                   cmap='viridis', alpha=0.6, s=10)
        plt.colorbar(label='Sharpe Ratio')
        
        # Plot optimal portfolios
        plt.scatter(max_sharpe_portfolio['Volatility'], max_sharpe_portfolio['Return'], 
                   color='red', marker='*', s=200, label='Max Sharpe Ratio')
        plt.scatter(min_vol_portfolio['Volatility'], min_vol_portfolio['Return'], 
                   color='blue', marker='*', s=200, label='Min Volatility')
        
        plt.xlabel('Volatility (Risk)')
        plt.ylabel('Expected Return')
        plt.title('Efficient Frontier')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.show()
        
        return max_sharpe_portfolio, min_vol_portfolio
    
    def portfolio_composition_chart(self, weights, title="Portfolio Composition"):
        """
        Plot portfolio composition pie chart
        """
        if isinstance(weights, dict):
            labels = list(weights.keys())
            sizes = list(weights.values())
        else:
            labels = list(self.mean_returns.index)
            sizes = weights
        
        plt.figure(figsize=(10, 8))
        plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
        plt.title(title)
        plt.axis('equal')
        plt.show()
    
    def backtest_portfolio(self, weights, rebalance_freq='M'):
        """
        Simple backtesting of portfolio strategy
        
        Args:
            weights: Portfolio weights
            rebalance_freq: Rebalancing frequency ('D', 'W', 'M', 'Q')
        """
        # Calculate portfolio returns
        portfolio_returns = (self.returns * weights).sum(axis=1)
        
        # Calculate cumulative returns
        cumulative_returns = (1 + portfolio_returns).cumprod()
        
        # Calculate performance metrics
        total_return = cumulative_returns.iloc[-1] - 1
        annual_return = portfolio_returns.mean() * 252
        annual_volatility = portfolio_returns.std() * np.sqrt(252)
        sharpe_ratio = (annual_return - 0.02) / annual_volatility
        max_drawdown = (cumulative_returns / cumulative_returns.expanding().max() - 1).min()
        
        # Plot results
        plt.figure(figsize=(12, 8))
        
        plt.subplot(2, 1, 1)
        plt.plot(cumulative_returns.index, cumulative_returns)
        plt.title('Portfolio Cumulative Returns')
        plt.ylabel('Cumulative Return')
        plt.grid(True, alpha=0.3)
        
        plt.subplot(2, 1, 2)
        plt.plot(portfolio_returns.index, portfolio_returns.cumsum())
        plt.title('Portfolio Returns Over Time')
        plt.ylabel('Cumulative Daily Returns')
        plt.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.show()
        
        # Print performance summary
        print("BACKTESTING RESULTS")
        print("-" * 30)
        print(f"Total Return: {total_return:.2%}")
        print(f"Annual Return: {annual_return:.2%}")
        print(f"Annual Volatility: {annual_volatility:.2%}")
        print(f"Sharpe Ratio: {sharpe_ratio:.3f}")
        print(f"Max Drawdown: {max_drawdown:.2%}")
        
        return {
            'total_return': total_return,
            'annual_return': annual_return,
            'annual_volatility': annual_volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown
        }


# Example usage
if __name__ == "__main__":
    optimizer = PortfolioOptimizer()
    
    # Prepare data
    tickers = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA']
    optimizer.prepare_data(tickers, period="2y")
    
    # Plot efficient frontier
    max_sharpe, min_vol = optimizer.plot_efficient_frontier()
    
    # Optimize for maximum Sharpe ratio
    result = optimizer.optimize_portfolio('sharpe')
    optimal_weights = result.x
    
    print("\nOPTIMAL PORTFOLIO WEIGHTS (Max Sharpe)")
    print("-" * 40)
    for i, ticker in enumerate(tickers):
        print(f"{ticker}: {optimal_weights[i]:.2%}")
    
    # Portfolio composition chart
    optimizer.portfolio_composition_chart(optimal_weights, "Optimal Portfolio Composition")
    
    # Backtest the optimal portfolio
    backtest_results = optimizer.backtest_portfolio(optimal_weights)
    
    # Risk parity portfolio
    risk_parity_result = optimizer.risk_parity_portfolio()
    risk_parity_weights = risk_parity_result.x
    
    print("\nRISK PARITY PORTFOLIO WEIGHTS")
    print("-" * 40)
    for i, ticker in enumerate(tickers):
        print(f"{ticker}: {risk_parity_weights[i]:.2%}")
