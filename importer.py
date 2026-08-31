import requests
import pandas as pd
import os
import time
from datetime import datetime

class MoexFullImporter:
    def __init__(self, cache_file="data/moex_massive_history.csv"):
        self.cache_file = cache_file
        self.history_url = "https://iss.moex.com/iss/history/engines/stock/markets/shares/boards/TQBR/securities/"
        self.session = requests.Session()

    def get_massive_data(self, min_volume=15_000_000, start="2000-01-01", min_history_years=1, force_update=False):
        """
        start: с какого года искать историю (по умолчанию с 2010)
        min_history_years: удалять акции, которые торгуются меньше этого срока
        """
        if os.path.exists(self.cache_file) and not force_update:
            print(f"[КЭШ] Загрузка истории из файла...")
            return pd.read_csv(self.cache_file, index_col=0, parse_dates=True)

        print(f"[СЕТЬ] Начинаю сбор всей истории с {start}...")
        tickers = self._get_all_active_tickers(min_volume)
        data_dict = {}
        today = datetime.now().strftime("%Y-%m-%d")

        for i, t in enumerate(tickers):
            try:
                history = self._get_ticker_history(t, start, today)
                
                if not history.empty:
                    #Проверка на "возраст" акции
                    days_active = (history.index[-1] - history.index[0]).days
                    if days_active / 365.25 >= min_history_years:
                        data_dict[t] = history
                    else:
                        print(f"Skipped {t}: too young ({days_active} days)")
                
                time.sleep(0.05)
                if (i+1) % 10 == 0:
                    print(f"Загружено {i+1}/{len(tickers)}...")
            except Exception as e:
                print(f"Ошибка на {t}: {e}")

        print("\nОбъединение данных (может занять время)...")
        #Соединяем по датам. Акции, которые начались позже, просто будут иметь NaN в начале
        massive_df = pd.concat(data_dict, axis=1)
        
        #Заполняем редкие пропуски (выходные) методом "последнее известное"
        massive_df = massive_df.ffill()

        massive_df.to_csv(self.cache_file)
        print(f"[УСПЕХ] Сохранено в CSV. Матрица: {massive_df.shape} (Дней, Акций)")
        return massive_df

    def _get_all_active_tickers(self, min_daily_volume_rub):
        url = "https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities.json"
        res = self.session.get(url).json()
        market_data = pd.DataFrame(res['marketdata']['data'], columns=res['marketdata']['columns'])
        return market_data[market_data['VALTODAY'] >= min_daily_volume_rub]['SECID'].tolist()

    def _get_ticker_history(self, ticker, start_date, end_date):
        all_history = []
        start_row = 0
        while True:
            url = f"{self.history_url}{ticker}.json?from={start_date}&till={end_date}&start={start_row}"
            res = self.session.get(url).json()
            if 'history' not in res or not res['history']['data']: break
            
            df_part = pd.DataFrame(res['history']['data'], columns=res['history']['columns'])
            all_history.append(df_part[['TRADEDATE', 'CLOSE']])
            
            if len(res['history']['data']) < 100: break
            start_row += 100
            
        if not all_history: return pd.Series()
        df = pd.concat(all_history).drop_duplicates('TRADEDATE')
        df['TRADEDATE'] = pd.to_datetime(df['TRADEDATE'])
        return df.set_index('TRADEDATE')['CLOSE']
