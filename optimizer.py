import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from pypfopt import EfficientFrontier, risk_models, expected_returns

class PortfolioEngine:
    def __init__(self, price_data, stats_df):
        self.data = price_data
        self.stats = stats_df
        #Фильтруем кандидатов: Лидеры и Нейтральные с доходностью > 0
        self.candidates_df = self.stats[
            (self.stats['Group'].isin(['Leaders', 'Neutral'])) & 
            (self.stats['Yield_Recent'] > 0)
        ].copy()

    def _filter_by_correlation(self, tickers, threshold=0.85):
        if not tickers: return []
        corr_matrix = self.data[tickers].pct_change().corr()
        to_remove = set()
        for i in range(len(tickers)):
            for j in range(i + 1, len(tickers)):
                t_a, t_b = tickers[i], tickers[j]
                if abs(corr_matrix.loc[t_a, t_b]) > threshold:
                    #Оставляем того, у кого лучше Шарп (Yield/Volatility)
                    eff_a = self.stats.loc[t_a, 'Yield_Global'] / self.stats.loc[t_a, 'Volatility']
                    eff_b = self.stats.loc[t_b, 'Yield_Global'] / self.stats.loc[t_b, 'Volatility']
                    to_remove.add(t_b if eff_a > eff_b else t_a)
        
        final = [t for t in tickers if t not in to_remove]
        print(f"[ФИЛЬТР] Исключено сильно коррелирующих акций: {len(to_remove)} шт.")
        return final

    def _apply_clustering(self, n_clusters=6):
        #Голубые фишки (MOEXBC)
        blue_chips = [
            'SBER', 'SBERP', 'GAZP', 'LKOH', 'GMKN', 'NVTK', 'ROSN', 
            'MGNT', 'TATN', 'TATNP', 'CHMF', 'PLZL', 'ALRS', 'MTSS', 
            'MOEX', 'NLMK', 'PHOR', 'BSPB', 'CBOM'
        ]
        available_blue_chips = [t for t in blue_chips if t in self.data.columns]
        print(f"[ЯДРО] Добавлено голубых фишек: {len(available_blue_chips)} шт.")

        #Кластеризация по Yield_Recent и Volatility
        scaler = StandardScaler()
        features = ['Yield_Recent', 'Volatility']
        scaled = scaler.fit_transform(self.candidates_df[features])
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        self.candidates_df['Cluster'] = kmeans.fit_predict(scaled)
        
        cluster_selected = self.candidates_df.sort_values('Yield_Recent', ascending=False) \
                                             .groupby('Cluster').head(2).index.tolist()
        
        #Объединение и де-корреляция
        all_selected = list(set(available_blue_chips + cluster_selected))
        return self._filter_by_correlation(all_selected)

    def build_portfolios(self, risk_free_rate=0.14):
        # 1. Первичный отбор (Кластеры + Ядро)
        selected_tickers = self._apply_clustering()
        
        # 2. ТРЕНДОВЫЙ ФИЛЬТР (Momentum)
        # Считаем доходность за последние 3 месяца (63 торговых дня)
        # Мы берем данные только из ПРОШЛОГО (self.data), чтобы не подглядывать в будущее
        short_trend = self.data[selected_tickers].pct_change(63).iloc[-1]
        
        # Оставляем только те акции, которые сейчас в плюсе (растущий тренд)
        trending_tickers = short_trend[short_trend > 0].index.tolist()
        
        # Защита: если рынок обвалился и никто не растет, оставляем топ-7 лучших по тренду
        if len(trending_tickers) < 7:
            trending_tickers = short_trend.nlargest(7).index.tolist()
            
        # Обрезаем данные под выжившие тикеры
        subset_data = self.data[trending_tickers]
        
        # 3. Математика (EMA доходность и Полуковариация для Сортино)
        mu = expected_returns.ema_historical_return(subset_data, span=252)
        S = risk_models.semicovariance(subset_data, benchmark=0)
        
        blue_chips = ['SBER', 'LKOH', 'GAZP', 'ROSN', 'NVTK', 'GMKN', 'TATN', 'PLZL', 'MGNT', 'BSPB', 'CBOM', 'PHOR']
        portfolios = {}

        # --- ФУНКЦИЯ ДЛЯ ГЕНЕРАЦИИ ГРАНИЦ (Bounds) под текущий набор тикеров ---
        def get_bounds(tickers):
            b = []
            for t in tickers:
                if t in blue_chips:
                    b.append((0.03, 0.20)) # Гиганты: минимум 3%
                else:
                    b.append((0.00, 0.15)) # Остальные: до 15%
            return b

        # --- 1. SAFE (Минимальный риск падения) ---
        try:
            current_bounds = get_bounds(trending_tickers)
            ef = EfficientFrontier(mu, S, weight_bounds=current_bounds)
            ef.min_volatility()
            portfolios['SAFE'] = (ef.portfolio_performance(risk_free_rate=risk_free_rate), ef.clean_weights())
        except: pass

        # --- 2. OPTIMAL (Максимальный Сортино) ---
        try:
            current_bounds = get_bounds(trending_tickers)
            ef = EfficientFrontier(mu, S, weight_bounds=current_bounds)
            ef.max_sharpe(risk_free_rate=risk_free_rate)
            portfolios['OPTIMAL'] = (ef.portfolio_performance(risk_free_rate=risk_free_rate), ef.clean_weights())
        except: pass

        # --- 3. PROFIT (Агрессивный) ---
        try:
            current_bounds = get_bounds(trending_tickers)
            ef = EfficientFrontier(mu, S, weight_bounds=current_bounds)
            # Цель: доходность SAFE + 8%
            target = portfolios['SAFE'][0][0] + 0.08
            ef.efficient_return(target_return=target)
            portfolios['PROFIT'] = (ef.portfolio_performance(risk_free_rate=risk_free_rate), ef.clean_weights())
        except:
            # Fallback на Max Sharpe с более широкими лимитами
            ef = EfficientFrontier(mu, S, weight_bounds=(0, 0.25))
            ef.max_sharpe(risk_free_rate=risk_free_rate)
            portfolios['PROFIT'] = (ef.portfolio_performance(risk_free_rate=risk_free_rate), ef.clean_weights())

        # --- 4. RISKY (Топ-5 лидеров Momentum) ---
        try:
            top_5 = short_trend.nlargest(5).index.tolist()
            mu_r, S_r = mu[top_5], S.loc[top_5, top_5]
            # Для спекуляции лимиты 1-40%
            ef_r = EfficientFrontier(mu_r, S_r, weight_bounds=(0.01, 0.40))
            ef_r.max_sharpe(risk_free_rate=risk_free_rate)
            portfolios['RISKY'] = (ef_r.portfolio_performance(risk_free_rate=risk_free_rate), ef_r.clean_weights())
        except: pass

        return portfolios

    def print_report(self, results):
        print("\n" + "="*80)
        print(" ФИНАЛЬНЫЙ ИНВЕСТИЦИОННЫЙ ОТЧЕТ")
        print("="*80)
        names = {'SAFE': "1. КОНСЕРВАТИВНЫЙ", 'OPTIMAL': "2. ОПТИМАЛЬНЫЙ", 
                 'PROFIT': "3. АГРЕССИВНЫЙ", 'RISKY': "4. СПЕКУЛЯТИВНЫЙ (MAX RISK)"}
        
        for key in names.keys():
            if key not in results: continue
            perf, weights = results[key]
            print(f"\n>>> {names[key]}")
            print(f"    Доходность: {perf[0]:.1%} | Риск: {perf[1]:.1%} | Шарп: {perf[2]:.2f}")
            active_w = {k: f"{v:.1%}" for k, v in weights.items() if v > 0.01}
            print(f"    Состав: {active_w}")