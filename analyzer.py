import pandas as pd
import numpy as np

class MarketAnalyzer:
    def __init__(self, df):
        self.data = df
        # Считаем доходности и сразу чистим их от аномалий (сплитов/глюков)
        self.returns = self.data.pct_change().mask(self.data.pct_change().abs() > 0.2)
        self.stats = None

    def get_cleaned_returns(self):
        """ Возвращает очищенную матрицу доходностей для бектеста """
        return self.returns

    def analyze(self, recent_years=2):
        """ Считает метрики для каждой акции и делит на группы """
        # Считаем доходность за весь период (Global)
        yield_global = self.returns.mean() * 252
        
        # Считаем доходность за последние N лет (Recent)
        last_date = self.returns.index.max()
        start_recent = last_date - pd.DateOffset(years=recent_years)
        yield_recent = self.returns.loc[start_recent:].mean() * 252
        
        volatility = self.returns.std() * np.sqrt(252)

        self.stats = pd.DataFrame({
            'Yield_Global': yield_global,
            'Yield_Recent': yield_recent,
            'Volatility': volatility
        }).dropna()

        # Классификация
        self.stats['Group'] = pd.qcut(self.stats['Yield_Global'], q=3, labels=['Laggards', 'Neutral', 'Leaders'])
        self.stats['Trend'] = np.where(self.stats['Yield_Recent'] > self.stats['Yield_Global'], "Accelerating", "Slowing")
        
        return self.stats