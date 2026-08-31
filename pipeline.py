import pandas as pd
from importer import MoexFullImporter
from analyzer import MarketAnalyzer
from optimizer import PortfolioEngine
from backtester import BacktestEngine


#Загружаем данные
importer = MoexFullImporter(cache_file="data/moex_massive_history.csv")
df = importer.get_massive_data(min_volume=15_000_000, start="2000-01-01", min_history_years=1, force_update=False) #df — это уже таблица DataFrame

#Анализ
analyzer = MarketAnalyzer(df) 
stats = analyzer.analyze()
analyzer.show_console_summary()
analyzer.export_to_txt(filename="data/market_dynamics.txt")

#Сборка портфелей
engine = PortfolioEngine(df, stats)
portfolios = engine.build_portfolios(risk_free_rate=0.14)

#Итоговый отчет
engine.print_report(portfolios)

backtester = BacktestEngine(df)

#Сравниваем доходность за 1, 2, 3 и 5 лет
backtester.compare_strategies(portfolios, periods=[1, 2, 3, 5])

#Рисуем графики за последние 3 года
#backtester.plot_backtest_charts(portfolios, years=3)