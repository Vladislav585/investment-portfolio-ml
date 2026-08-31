import pandas as pd
from importer import MoexFullImporter
from analyzer import MarketAnalyzer

# 1. Загружаем данные (либо скачиваем, либо берем из готового CSV)
importer = MoexFullImporter(cache_file="moex_massive_history.csv")
df = importer.get_massive_data(min_volume=15_000_000, start="2000-01-01", min_history_years=1, force_update=False) # df — это уже таблица DataFrame

# 2. Передаем ТАБЛИЦУ в анализатор, а не название файла
analyzer = MarketAnalyzer(df) 
analyzer.analyze()
analyzer.show_console_summary()
analyzer.export_to_txt()