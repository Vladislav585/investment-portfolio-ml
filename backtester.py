import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

class BacktestEngine:
    def __init__(self, price_data):
        self.data = price_data
        #Считаем доходности
        self.returns = self.data.pct_change()
        self.returns = self.returns.mask(self.returns.abs() > 0.5)

    def _get_market_benchmark(self, days):
        """ Вспомогательный метод для расчета поведения 'рынка' через медиану """
        #Берем медиану
        market_daily = self.returns.median(axis=1).tail(days)
        return market_daily

    def run_period(self, weights, years):
        days = int(years * 252)
        if days > len(self.returns): return None
            
        window_returns = self.returns.tail(days)
        tickers = list(weights.keys())
        w_series = pd.Series(weights)
        
        #Доходность нашего портфеля
        portfolio_daily = (window_returns[tickers] * w_series).sum(axis=1)
        cum_return = (1 + portfolio_daily).cumprod()
        
        #Метрики
        total_return = cum_return.iloc[-1] - 1
        rolling_max = cum_return.cummax()
        drawdown = (cum_return - rolling_max) / rolling_max
        max_drawdown = drawdown.min()
        
        #Шарп (учитываем безрисковую ставку 14%)
        excess_ret = portfolio_daily.mean() * 252 - 0.14
        std_ret = portfolio_daily.std() * np.sqrt(252)
        sharpe = excess_ret / std_ret if std_ret != 0 else 0
        
        return {
            'cum_series': cum_return,
            'total_return': total_return,
            'max_drawdown': max_drawdown,
            'sharpe': sharpe
        }

    def compare_strategies(self, portfolios_dict, periods=[1, 2, 3, 5]):
        print("\n" + "="*80)
        print(" СИНХРОНИЗИРОВАННЫЙ БЕКТЕСТ (РЫНОК = МЕДИАНА)")
        print("="*80)

        for yr in periods:
            days = yr * 252
            if days > len(self.returns): continue
            
            print(f"\n>>> ГОРИЗОНТ: {yr} ГОД(А)/ЛЕТ")
            print(f"{'Стратегия':<25} | {'Доходность':>10} | {'Просадка':>10} | {'Шарп':>8}")
            print("-" * 65)
            
            #Считаем Рынок
            m_daily = self._get_market_benchmark(days)
            m_cum = (1 + m_daily).cumprod()
            m_ret = m_cum.iloc[-1] - 1
            m_dd = ((m_cum - m_cum.cummax()) / m_cum.cummax()).min()
            m_sharpe = (m_daily.mean() * 252 - 0.14) / (m_daily.std() * np.sqrt(252))
            
            print(f"{'РЫНОК (Типичная акция)':<25} | {m_ret:>10.1%} | {m_dd:>10.1%} | {m_sharpe:>8.2f}")

            for name, (perf, weights) in portfolios_dict.items():
                res = self.run_period(weights, yr)
                if res:
                    print(f"{name:<25} | {res['total_return']:>10.1%} | {res['max_drawdown']:>10.1%} | {res['sharpe']:>8.2f}")
        
    def plot_backtest_charts(self, portfolios_dict, years=3):
        days = years * 252
        plt.figure(figsize=(12, 7))
        
        #Рынок (через медиану)
        m_daily = self._get_market_benchmark(days)
        m_cum = (1 + m_daily).cumprod()
        plt.plot(m_cum.values, label='РЫНОК (Медиана)', color='black', linestyle='--', alpha=0.8)

        #Наши портфели
        for name, (perf, weights) in portfolios_dict.items():
            res = self.run_period(weights, years)
            if res:
                plt.plot(res['cum_series'].values, label=f"Портфель {name}", linewidth=2)
        
        plt.title(f"Сравнение роста капитала за {years} года (Рынок без выбросов)")
        plt.legend()
        plt.grid(True, alpha=0.2)
        plt.show()