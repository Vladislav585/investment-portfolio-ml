import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

class BacktestEngine:
    def __init__(self, test_prices):
        # Берем только тот кусок цен, на котором ТЕСТИРУЕМ (будущее)
        self.data = test_prices
        self.returns = self.data.pct_change().mask(self.data.pct_change().abs() > 0.5)
        self.market_benchmark = self.returns.median(axis=1)

    def run_test(self, portfolios_dict):
        print("\n" + "="*80)
        print(" РЕАЛЬНЫЙ ТЕСТ: РАБОТА ПОРТФЕЛЕЙ В 2025 ГОДУ (OUT-OF-SAMPLE)")
        print("="*80)
        print(f"{'Стратегия':<20} | {'Доходность':>10} | {'Просадка':>10} | {'Шарп':>8}")
        print("-" * 55)

        # 1. Считаем Рынок (Медиана)
        m_cum = (1 + self.market_benchmark).cumprod()
        m_ret = m_cum.iloc[-1] - 1
        m_dd = ((m_cum - m_cum.cummax()) / m_cum.cummax()).min()
        print(f"{'РЫНОК (Медиана)':<20} | {m_ret:>10.1%} | {m_dd:>10.1%} | {'-'}")

        # 2. Считаем наши 4 портфеля
        plt.figure(figsize=(12, 6))
        plt.plot(m_cum.values, label='РЫНОК', color='black', linestyle='--', alpha=0.5)

        for name, (perf, weights) in portfolios_dict.items():
            tickers = list(weights.keys())
            w_series = pd.Series(weights)
            
            # Считаем доходность на тестовых данных
            p_daily = (self.returns[tickers] * w_series).sum(axis=1)
            p_cum = (1 + p_daily).cumprod()
            
            # Метрики
            total_ret = p_cum.iloc[-1] - 1
            max_dd = ((p_cum - p_cum.cummax()) / p_cum.cummax()).min()
            
            print(f"{name:<20} | {total_ret:>10.1%} | {max_dd:>10.1%} | {'-'}")
            plt.plot(p_cum.values, label=name, linewidth=2)

        plt.title("Результаты стратегий на данных, которые модель НЕ ВИДЕЛА (2025 год)")
        plt.legend()
        plt.grid(True, alpha=0.2)
        plt.show()