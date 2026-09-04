from importer import MoexFullImporter
from analyzer import MarketAnalyzer
from optimizer import PortfolioEngine
from backtester import BacktestEngine

# 1. Загрузка данных
importer = MoexFullImporter()
df = importer.get_massive_data()

# 2. Запуск симуляции
# Передаем и Оптимизатор, и Анализатор как компоненты системы
tester = BacktestEngine(df, PortfolioEngine, MarketAnalyzer)

# Запускаем честный тест с 2020 года
tester.run_dynamic_test(start_date='2020-01-01', window_years=2, risk_free_rate=0.14)