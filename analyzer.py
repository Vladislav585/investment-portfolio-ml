import pandas as pd
import numpy as np
from datetime import timedelta

class MarketAnalyzer:
    def __init__(self, df):
        self.data = df
        # 1. Считаем ежедневную доходность
        self.returns = self.data.pct_change()

        # !!! ФИЛЬТР АНОМАЛИЙ: убираем скачки > 50% в день (ошибки данных/сплиты)
        # Мы заменяем их на NaN, чтобы они не участвовали в расчете среднего
        self.returns = self.returns.mask(self.returns.abs() > 0.5)
        
        self.stats = None

    def analyze(self):
        # ОПРЕДЕЛЯЕМ ПЕРИОДЫ
        # Последняя дата в наших данных
        end_date = self.returns.index.max()
        # Дата 2 года назад
        start_2y = end_date - timedelta(days=2*365)

        # 2. РАСЧЕТ ЗА ВЕСЬ ПЕРИОД (Глобальный)
        yield_global = self.returns.mean() * 252
        vol_global = self.returns.std() * np.sqrt(252)

        # 3. РАСЧЕТ ЗА ПОСЛЕДНИЕ 2 ГОДА (Свежий)
        returns_2y = self.returns.loc[start_2y:]
        yield_recent = returns_2y.mean() * 252

        # 4. СОБИРАЕМ ТАБЛИЦУ
        self.stats = pd.DataFrame({
            'Yield_Global': yield_global,
            'Yield_Recent': yield_recent,
            'Volatility': vol_global
        })

        # Убираем NaN (акции, которые не торговались в последние 2 года, если такие есть)
        self.stats = self.stats.dropna()

        # 5. КЛАССИФИКАЦИЯ (по Глобальной доходности)
        self.stats['Group'] = pd.qcut(
            self.stats['Yield_Global'], 
            q=3, 
            labels=['Laggards', 'Neutral', 'Leaders']
        )
        
        # Добавляем колонку "Trend" (Тренд): 
        # Если свежая доходность выше глобальной — акция ускоряется, если ниже — замедляется.
        self.stats['Trend'] = np.where(
            self.stats['Yield_Recent'] > self.stats['Yield_Global'], 
            "Accelerating", "Slowing"
        )

        self.stats = self.stats.sort_values(by='Yield_Global', ascending=False)
        return self.stats

    def show_console_summary(self):
        if self.stats is None: self.analyze()

        print("\n" + "="*85)
        print(f" ДИНАМИЧЕСКИЙ АНАЛИЗ РЫНКА (История vs 2 года, {len(self.stats)} акций)")
        print("="*85)
        
        # Названия колонок для вывода
        cols = ['Yield_Global', 'Yield_Recent', 'Trend', 'Volatility']

        print("\n>>> ТОП-10 ИСТОРИЧЕСКИХ ЛИДЕРОВ (Leaders)")
        # Форматируем вывод, чтобы доходности были в процентах
        summary = self.stats[self.stats['Group'] == 'Leaders'].head(10)[cols].copy()
        print(summary)

        print("\n>>> 10 АКЦИЙ СРЕДНЕГО ЭШЕЛОНА (Neutral)")
        neutral_stocks = self.stats[self.stats['Group'] == 'Neutral']
        mid = len(neutral_stocks) // 2
        print(neutral_stocks.iloc[mid-5 : mid+5][cols])

        print("\n>>> ТОП-10 АУТСАЙДЕРОВ (Laggards)")
        print(self.stats[self.stats['Group'] == 'Laggards'].tail(10)[cols])
        print("\n" + "="*85)

    def export_to_txt(self, filename="market_dynamics.txt"):
        if self.stats is None: self.analyze()
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"ОТЧЕТ ПО ДИНАМИКЕ 107 АКЦИЙ MOEX (История vs Последние 2 года)\n")
            f.write("-" * 80 + "\n")
            f.write(f"{'Тикер':<10} | {'Группа':<10} | {'Global %':>10} | {'Recent %':>10} | {'Trend':<15}\n")
            f.write("-" * 80 + "\n")
            for ticker, row in self.stats.iterrows():
                f.write(f"{ticker:<10} | {row['Group']:<10} | {row['Yield_Global']:>9.1%} | {row['Yield_Recent']:>9.1%} | {row['Trend']:<15}\n")
        print(f"\n[УСПЕХ] Отчет по динамике создан: {filename}")