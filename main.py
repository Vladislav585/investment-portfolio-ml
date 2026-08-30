import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.cluster import AgglomerativeClustering, KMeans
from pypfopt import EfficientFrontier, risk_models, expected_returns, plotting

#загрузка данных
#список акций
tickers = [
    'SBER.ME', 'GAZP.ME', 'LKOH.ME', 'GMKN.ME', 'NVTK.ME', 
    'ROSN.ME', 'MGNT.ME', 'PLZL.ME', 'TATN.ME', 'CHMF.ME',
    'SNGS.ME', 'ALRS.ME', 'MOEX.ME', 'MTSS.ME', 'NLMK.ME',
    'AFLT.ME', 'BSPB.ME', 'PHOR.ME', 'RUAL.ME', 'TRNFP.ME',
    'MAGN.ME', 'CBOM.ME', 'HYDR.ME', 'IRAO.ME', 'MSNG.ME', 
    'FEES.ME', 'AFKS.ME', 'AQUA.ME', 'BELU.ME', 'PIKK.ME'
]

#данные за 5 лет
print("Загрузка данных с биржи...")
raw_data = yf.download(tickers, start="2021-01-01", end="2026-01-01")['Close']

#убираем пустые значения
data = raw_data.dropna()

#базовые метрики
#ежедневная доходность
returns_daily = data.pct_change()

#годовая доходность и риск
annual_returns = returns_daily.mean() * 252
annual_volatility = returns_daily.std() * np.sqrt(252)

#таблица
stats = pd.DataFrame({
    'Return': annual_returns,
    'Volatility': annual_volatility
})

#фикс ошибки
#убираем NaN
stats = stats.dropna() 

#кластеризация
cluster_model = AgglomerativeClustering(n_clusters=4) 
stats['Main_Group'] = cluster_model.fit_predict(stats[['Return', 'Volatility']])

#подгруппы
def identify_subgroup(row):
    if row['Return'] < 0:
        return 'Losing' #убыточные
    elif row['Volatility'] > 0.45:
        return 'Aggressive' #агрессивные
    else:
        return 'Stable' #стабильные

stats['Sub_Group'] = stats.apply(identify_subgroup, axis=1)

print("Результаты группировки акций:")
print(stats)

#оптимизация
#доходность и риск
mu = expected_returns.mean_historical_return(data)
S = risk_models.sample_cov(data)

mu = mu.replace([np.inf, -np.inf], np.nan).dropna()
S = S.loc[mu.index, mu.index] #синхронизация

print("\nПоиск оптимального портфеля (Max Sharpe)...")

try:
    # СОЗДАЕМ НОВЫЙ ОБЪЕКТ ДЛЯ МАКС ШАРПА
    ef_max_sharpe = EfficientFrontier(mu, S, weight_bounds=(0, 0.20))
    weights_sharpe = ef_max_sharpe.max_sharpe()
    cleaned_weights = ef_max_sharpe.clean_weights()
    
    print("\nРЕЗУЛЬТАТ: ПОРТФЕЛЬ МАКСИМАЛЬНОЙ ЭФФЕКТИВНОСТИ")
    ef_max_sharpe.portfolio_performance(verbose=True)

except Exception as e:
    print(f"Макс. Шарп не найден, причина: {e}")
    print("Поиск портфеля с минимальным риском...")
    # СОЗДАЕМ ОТДЕЛЬНЫЙ ОБЪЕКТ ДЛЯ МИН РИСКА
    ef_min_vol = EfficientFrontier(mu, S, weight_bounds=(0, 0.20))
    weights_sharpe = ef_min_vol.min_volatility()
    cleaned_weights = ef_min_vol.clean_weights()
    ef_min_vol.portfolio_performance(verbose=True)

#график 1
plt.figure(figsize=(12, 10))
sns.heatmap(returns_daily.corr(), annot=True, fmt=".1f", cmap='coolwarm')
plt.title('Матрица корреляции 30 крупнейших акций РФ')
plt.show()

#график 2
plt.figure(figsize=(12, 7))
for group in stats['Sub_Group'].unique():
    subset = stats[stats['Sub_Group'] == group]
    plt.scatter(subset['Volatility'], subset['Return'], label=group, s=100)

for i, ticker in enumerate(stats.index):
    plt.annotate(ticker.replace('.ME', ''), (stats.iloc[i]['Volatility'], stats.iloc[i]['Return']), 
                 xytext=(5, 5), textcoords='offset points')

plt.xlabel('Волатильность (Риск)')
plt.ylabel('Доходность (Годовая)')
plt.legend()
plt.grid(True, alpha=0.3)
plt.title('Кластеризация акций РФ по профилю риска и доходности')
plt.show()

#график 3
final_weights = {k: v for k, v in cleaned_weights.items() if v > 0.01}
plt.figure(figsize=(8, 8))
plt.pie(final_weights.values(), labels=final_weights.keys(), autopct='%1.1f%%')
plt.title('Итоговое распределение долей в лучшем портфеле')
plt.show()


print("\nСРАВНЕНИЕ: СТРАТЕГИЯ 1/N (РАВНОМЕРНАЯ)")
num_assets = len(mu)
equal_weights = {ticker: 1/num_assets for ticker in mu.index}

# Используем тот же оптимизатор, чтобы просто рассчитать показатели для этих весов
ef_equal = EfficientFrontier(mu, S)
ef_equal.set_weights(equal_weights)
ef_equal.portfolio_performance(verbose=True)