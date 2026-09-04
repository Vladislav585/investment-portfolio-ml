import pandas as pd
from importer import MoexFullImporter
from analyzer import MarketAnalyzer
from optimizer import PortfolioEngine
from backtester import BacktestEngine
from backtester import BacktestEngine


#Загружаем данные
importer = MoexFullImporter(cache_file="data/moex_massive_history.csv")
df = importer.get_massive_data(min_volume=15_000_000, start="2000-01-01", min_history_years=1, force_update=False) #df — это уже таблица DataFrame

split_date = '2025-01-01'
train_df = df[df.index < split_date]  # Прошлое (для обучения)
test_df = df[df.index >= split_date]  # Будущее (для проверки)

print(f"Обучение на данных до {split_date}")
print(f"Тестирование на данных после {split_date}")

# 2. Обучаем модель на ПРОШЛОМ
analyzer = MarketAnalyzer(train_df)
stats = analyzer.analyze()

engine = PortfolioEngine(train_df, stats)
portfolios = engine.build_portfolios()
engine.print_report(portfolios)

# 3. Проверяем готовые портфели на БУДУЩЕМ (Бектест)
tester = BacktestEngine(test_df)
tester.run_test(portfolios)