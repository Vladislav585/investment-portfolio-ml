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
        selected_tickers = self._apply_clustering()
        subset_data = self.data[selected_tickers]
        mu = expected_returns.mean_historical_return(subset_data)
        S = risk_models.CovarianceShrinkage(subset_data).ledoit_wolf()
        
        blue_chips = ['SBER', 'SBERP', 'LKOH', 'GAZP', 'ROSN', 'NVTK', 'GMKN', 'TATN', 'PLZL', 'MGNT', 'BSPB', 'CBOM', 'PHOR']
        
        portfolios = {}

        #SAFE (Минимальный риск)
        #Лимиты: гиганты от 2%, остальные от 0%
        b_safe = [(0.02, 0.15) if t in blue_chips else (0, 0.10) for t in selected_tickers]
        ef = EfficientFrontier(mu, S, weight_bounds=b_safe)
        ef.min_volatility()
        portfolios['SAFE'] = (ef.portfolio_performance(risk_free_rate=risk_free_rate), ef.clean_weights())

        #OPTIMAL (Умеренный - ЯДРО РЫНКА)
        #Лимиты: гиганты от 3% (чтобы их было видно!), остальные от 0%
        b_opt = [(0.03, 0.15) if t in blue_chips else (0, 0.15) for t in selected_tickers]
        ef = EfficientFrontier(mu, S, weight_bounds=b_opt)
        ef.max_sharpe(risk_free_rate=risk_free_rate)
        perf_opt = ef.portfolio_performance(risk_free_rate=risk_free_rate)
        portfolios['OPTIMAL'] = (perf_opt, ef.clean_weights())

        #PROFIT (Агрессивный)
        #Цель: доходность Умеренного + 5% сверху
        try:
            b_prof = [(0.01, 0.20) if t in blue_chips else (0, 0.25) for t in selected_tickers]
            ef = EfficientFrontier(mu, S, weight_bounds=b_prof)
            ef.efficient_return(target_return=perf_opt[0] + 0.05) 
            portfolios['PROFIT'] = (ef.portfolio_performance(risk_free_rate=risk_free_rate), ef.clean_weights())
        except:
            #Если не вышло, просто берем топ-5 по доходности
            top_5 = mu.nlargest(5).index.tolist()
            w_manual = {t: (0.18 if t in top_5 else 0.01) for t in selected_tickers}
            total = sum(w_manual.values())
            w_manual = {k: v/total for k, v in w_manual.items()}
            ef = EfficientFrontier(mu, S)
            ef.set_weights(w_manual)
            portfolios['PROFIT'] = (ef.portfolio_performance(risk_free_rate=risk_free_rate), w_manual)

        #RISKY (Спекулятивный)
        top_3 = mu.nlargest(3).index.tolist()
        mu_r, S_r = mu[top_3], S.loc[top_3, top_3]
        ef_r = EfficientFrontier(mu_r, S_r, weight_bounds=(0, 0.60))
        ef_r.max_sharpe(risk_free_rate=risk_free_rate)
        portfolios['RISKY'] = (ef_r.portfolio_performance(risk_free_rate=risk_free_rate), ef_r.clean_weights())

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
        print("\n" + "="*80)