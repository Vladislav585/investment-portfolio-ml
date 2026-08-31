# Инвестиционный портфель MOEX

> **Languages:** [🇷🇺 Русский](#russian-version) | [🇺🇸 English](#english-version)


Автоматический конвейер (pipeline) для построения инвестиционных портфелей на акциях Московской биржи. 

Система реализует полный цикл: от сбора сырых данных с серверов Московской биржи до математической оптимизации весов и верификации стратегий на исторических данных.

> ⚠️ Disclaimer: Проект носит исследовательский характер. Прошлые результаты не гарантируют будущую доходность.

---

## Возможности

- Скачивание полной истории цен закрытия по всем ликвидным акциям MOEX (режим TQBR) через официальный API ISS
- Локальный кэш данных — повторные запуски не требуют сети
- Динамический анализ каждой акции: глобальная доходность за всю историю, доходность за последние 2 года, волатильность, группа (лидер/нейтральный/аутсайдер) и тренд (ускоряется/замедляется)
- Автоматический отбор акций: «голубые фишки» + кластеризация KMeans + фильтр сильно коррелирующих бумаг
- Сборка 4 готовых портфелей разного профиля риска через оптимизацию границы эффективности (PyPortfolioOpt)
- Синхронизированный бэктест портфелей за 1, 2, 3 и 5 лет против «рынка» (медианы всех акций)
- Отчёты в консоль и в текстовый файл

---

## Структура проекта

```
Портфель/
├── pipeline.py                    # Точка входа: собирает все этапы в один сценарий
├── importer.py                    # Загрузчик истории цен с MOEX ISS API
├── analyzer.py                    # Аналитик рынка: метрики и классификация акций
├── optimizer.py                   # Сборка и оптимизация портфелей
├── backtester.py                  # Бэктест: сравнение портфелей с рынком
├── data/
│   ├── moex_massive_history.csv   # Кэш: матрица цен закрытия (даты × тикеры)
│   └── market_dynamics.txt        # Сгенерированный отчёт по динамике акций
└── .gitignore
```

---

## Архитектура

Проект построен как конвейер из 4 независимых модулей, каждый оформлен отдельным классом. Связующим звеном выступает `pipeline.py` — он передаёт результат каждого этапа на вход следующему.

### Схема потока данных

```
                MOEX ISS API (https://iss.moex.com)
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │  importer.MoexFullImporter            │
        │  загрузка истории всех ликвидных акций│──► data/moex_massive_history.csv (кэш)
        └───────────────────┬───────────────────┘
                            │  DataFrame: индекс — дата, колонки — тикеры (цены закрытия)
                            ▼
        ┌───────────────────────────────────────┐
        │  analyzer.MarketAnalyzer              │
        │  метрики + классификация акций        │──► data/market_dynamics.txt
        └───────────────────┬───────────────────┘        + консольный отчёт
                            │  stats: Yield_Global, Yield_Recent,
                            │         Volatility, Group, Trend
                            ▼
        ┌───────────────────────────────────────┐
        │  optimizer.PortfolioEngine            │
        │  отбор акций + оптимизация весов      │
        └───────────────────┬───────────────────┘
                            │  4 портфеля {SAFE, OPTIMAL, PROFIT, RISKY}
                            │  = (метрики, веса)
                            ▼
        ┌───────────────────────────────────────┐
        │  backtester.BacktestEngine            │
        │  бэктест против «рынка-медианы»       │──► консольные таблицы
        └───────────────────────────────────────┘        (+ опционально график matplotlib)
```

### Модули

#### 1. `importer.py` — класс `MoexFullImporter`

Загрузчик данных. Метод `get_massive_data()`:

1. Если кэш-файл существует и `force_update=False` — просто загружает CSV и возвращает DataFrame.
2. Иначе запрашивает список всех активных тикеров режима TQBR и оставляет только ликвидные: объём торгов за день `VALTODAY >= min_volume` (по умолчанию 15 млн руб.).
3. Для каждого тикера постранично (по 100 строк) выкачивает историю котировок `TRADEDATE` + `CLOSE` с 2000 года; пауза 0.05 сек между запросами, прогресс каждые 10 тикеров.
4. Отбрасывает «молодые» акции с историей короче `min_history_years` (по умолчанию 1 год).
5. Склеивает все Series в одну матрицу «даты × тикеры» (`pd.concat(axis=1)`), пропуски заполняет методом ffill («последнее известное значение») и сохраняет в кэш.

#### 2. `analyzer.py` — класс `MarketAnalyzer`

Считает по каждой акции:

| Метрика | Формула | Смысл |
|---|---|---|
| `Yield_Global` | средняя дневная доходность × 252 | годовая доходность за всю историю |
| `Yield_Recent` | средняя дневная доходность × 252 за последние 2 года | «свежая» доходность |
| `Volatility` | ст. отклонение дневных доходностей × √252 | годовая волатильность |
| `Group` | `pd.qcut(Yield_Global, q=3)` | терциль: `Laggards` / `Neutral` / `Leaders` |
| `Trend` | `Yield_Recent > Yield_Global` | `Accelerating` / `Slowing` |

Входные данные предварительно очищаются: дневные движения больше ±50% маскируются как NaN (защита от технических «глюков» в котировках). Акции без истории за последние 2 года удаляются (`dropna`). Результат сортируется по `Yield_Global` по убыванию.

Методы `show_console_summary()` (топ-10 лидеров, середина эшелона, топ-10 аутсайдеров) и `export_to_txt()` (полный отчёт в `data/market_dynamics.txt`).

#### 3. `optimizer.py` — класс `PortfolioEngine`

Работа устроена в три шага: отбор → оценка → оптимизация.

**Шаг 1. Отбор кандидатов (`_apply_clustering`):**
- Ядро: список «голубых фишек» (SBER, GAZP, LKOH, GMKN и др. — 19 тикеров); присутствующие в данных добавляются всегда;
- Спутники: кандидаты (только `Leaders` и `Neutral` с положительной свежей доходностью) кластеризуются `KMeans` (6 кластеров) по стандартизованным признакам `[Yield_Recent, Volatility]`; из каждого кластера берутся 2 лучшие по `Yield_Recent` — так в портфель попадают разнообразные по риску/доходности бумаги;
- Де-корреляция (`_filter_by_correlation`): из пар с |корреляция| > 0.85 удаляется акция с худшим соотношением `Yield_Global / Volatility` — чтобы не держать дубликаты.

**Шаг 2. Оценка (PyPortfolioOpt):**
- ожидаемые доходности `mu` — средняя историческая доходность (`mean_historical_return`);
- ковариационная матрица `S` — оценка Ledoit–Wolf (shrinkage), устойчивее к шуму, чем выборочная.

**Шаг 3. Сборка 4 портфелей (`build_portfolios`):**

| Портфель | Ключ | Метод оптимизации | Лимиты «голубых фишек» | Лимиты остальных | Идея |
|---|---|---|---|---|---|
| Консервативный | `SAFE` | `min_volatility` | 2–15% | 0–10% | минимальный риск |
| Оптимальный | `OPTIMAL` | `max_sharpe` | 3–15% | 0–15% | максимум Шарпа («ядро рынка») |
| Агрессивный | `PROFIT` | `efficient_return` = доходность OPTIMAL + 5 п.п. | 1–20% | 0–25% | доходность выше умеренного |
| Спекулятивный | `RISKY` | `max_sharpe` на 3 самых доходных акциях | ≤ 60% | — | максимальный риск |

Если оптимизация `PROFIT` не сходится, срабатывает запасной вариант: топ-5 акций по ожидаемой доходности получают по 18%, остальным по 1%, веса нормируются. Минимальные веса у «голубых фишек» заданы специально, чтобы крупные компании гарантированно присутствовали в портфеле.

`print_report()` выводит финальный отчёт: доходность, риск, Шарп и состав (вес > 1%) каждого портфеля.

#### 4. `backtester.py` — класс `BacktestEngine`

Проверяет портфели на истории за последние N лет (`run_period`):
- дневная доходность портфеля = взвешенная сумма доходностей его акций;
- накопленная кривая капитала — наращивание `(1 + r).cumprod()`;
- метрики: **итоговая доходность**, **максимальная просадка** (от исторического максимума кривой), **Шарп** = (годовая доходность − 14% безрисковой ставки) / волатильность.

Особенность: «рынок» здесь — не индекс MOEX, а **медианная дневная доходность всех акций** выборки (`_get_market_benchmark`). Медиана игнорирует одиночные выбросы и перекос индекса в сторону гигантов — это поведение «типичной акции», с которой портфели сравниваются на тех же датах.

`compare_strategies(periods=[1, 2, 3, 5])` печатает таблицу «портфель vs рынок» для каждого горизонта. `plot_backtest_charts()` строит график роста капитала (в текущем `pipeline.py` вызов закомментирован).

#### 5. `pipeline.py` — точка входа

```python
importer  → df (матрица цен)      # данные из кэша или сети
analyzer  → stats                  # метрики и группы акций + отчёты
optimizer → portfolios             # 4 портфеля с весами и метриками
backtester→ таблицы сравнения      # за 1, 2, 3, 5 лет
```

Ключевые параметры задаются прямо здесь: `risk_free_rate=0.14` (безрисковая ставка — ориентир на доходность ключевых депозитов), `min_volume`, `start`, горизонты бэктеста.

---

## Формат данных

**`data/moex_massive_history.csv`** — кэш истории цен:
- первая колонка `TRADEDATE` (индекс, даты торговых сессий);
- остальные колонки — тикеры (AFKS, AFLT, SBER, ...), значения — цены закрытия;
- объём: ~100+ тикеров × более 20 лет истории (≈1.8 МБ).

**`data/market_dynamics.txt`** — отчёт анализатора:

```
Тикер      | Группа     |   Global % |   Recent % | Trend
VGSB       | Leaders    |     61.1%  |     10.8%  | Slowing
...
```

---

## Технологии

| Библиотека | Назначение |
|---|---|
| pandas, numpy | обработка данных, расчёт метрик |
| requests | HTTP-запросы к MOEX ISS API |
| scikit-learn | StandardScaler + KMeans (кластеризация) |
| PyPortfolioOpt (pypfopt) | граница эффективности, Ledoit–Wolf, оптимизация весов |
| matplotlib | график роста капитала (опционально) |

*Файл `requirements.txt` в проекте отсутствует — зависимости устанавливаются вручную.*

---

## Запуск

```bash
# установка зависимостей
pip install pandas numpy requests scikit-learn PyPortfolioOpt matplotlib

# полный прогон конвейера из корня проекта
python pipeline.py
```

- **Первый запуск** (нет `data/moex_massive_history.csv`): скачивание истории ~100+ тикеров с MOEX занимает несколько минут.
- **Последующие запуски**: данные берутся из кэша мгновенно. Чтобы обновить котировки — удалите CSV или передайте `force_update=True` в `get_massive_data()`.

---

## Настройка стратегий
| Параметр | Где | Значение |	Описание |
|---|---|---|---|
| risk_free_rate | pipeline.py	| 0.14 | Безрисковая ставка (ориентир на ставку ЦБ/ОФЗ)
| weight_bounds	| optimizer.py	| 0.03 - 0.15 | Лимиты долей для голубых фишек
| target_return	| optimizer.py	| +5%	| Целевая надбавка для агрессивного портфеля
| threshold	| optimizer.py	| 0.85	| Порог фильтра корреляции

---

## Что можно настроить

| Параметр | Где | По умолчанию | Что делает |
|---|---|---|---|
| `min_volume` | `pipeline.py` | 15 000 000 руб. | фильтр ликвидности (минимальный дневной объём торгов) |
| `start` | `pipeline.py` | 2000-01-01 | с какой даты собирать историю |
| `min_history_years` | `pipeline.py` | 1 | минимальный «стаж» акции на бирже |
| `force_update` | `pipeline.py` | False | принудительно обновить кэш |
| `risk_free_rate` | `pipeline.py`, `build_portfolios` | 0.14 | безрисковая ставка для Шарпа и оптимизации |
| `periods` | `compare_strategies` | [1, 2, 3, 5] | горизонты бэктеста, лет |
| `n_clusters` | `_apply_clustering` | 6 | число кластеров KMeans |
| `threshold` | `_filter_by_correlation` | 0.85 | порог корреляции для удаления дублей |
| окно «свежей» доходности | `analyzer.analyze` | 2 года (730 дней) | период для `Yield_Recent` и `Trend` |

---

## Ключевые проектные решения

1. **Фильтр выбросов**: дневные изменения цены >50% обнуляются на входе анализатора и бэктестера — сплит или «глюк» данных не искажает статистику.
2. **Кэш вместо базы данных**: вся история — один CSV; простой и переносимый вариант для персонального использования.
3. **Медиана вместо индекса** в бэктесте: не нужно догружать данные индекса MOEX, а сравнение остаётся честным («типичная акция» на тех же датах).
4. **Гарантированное ядро**: минимальные веса голубых фишек в лимитах оптимизатора не дают модели собрать портфель только из волатильных «спутников».
5. **Shrinkage-ковариация (Ledoit–Wolf)**: ковариационная матрица сжимается, что повышает устойчивость оптимизации Марковица на ограниченной истории.

---

## Лицензия и авторское право

© 2026 Vladislav585

Данное программное обеспечение распространяется на условиях **некоммерческого использования**. 

- **Разрешено:** копировать, изменять и использовать код в личных и учебных целях.
- **Запрещено:** использовать код в коммерческих продуктах, перепродавать его или использовать для получения прибыли.

**Отказ от ответственности:** Автор не несет ответственности за любые финансовые последствия использования данного кода. Все расчеты являются теоретическими и не являются финансовой рекомендацией.

<br/><br/>
<div align="center">
  <hr size="3" width="100%" color="gray">
  <h2 id="english-version">🇺🇸 English Version</h2>
  <hr size="3" width="100%" color="gray">
</div>
<br/>


# MOEX Investment Portfolio

An automated pipeline for constructing investment portfolios based on Moscow Exchange (MOEX) stocks. The project automatically downloads the entire trading history of stocks from MOEX, analyzes the dynamics of each security, selects candidates using machine learning (clustering), optimizes portfolio weights according to Markowitz theory (Efficient Frontier), and verifies strategies via backtesting against a "typical market stock."

> ⚠️ This project is for research purposes only and does not constitute investment advice.

---

## Features

- **Full History Download:** Fetches daily closing prices for all liquid MOEX stocks (TQBR mode) via the official ISS API.
- **Local Data Cache:** CSV-based caching ensures subsequent runs do not require an active internet connection.
- **Dynamic Analysis:** Calculates global historical yield, recent 2-year yield, volatility, group classification (Leader/Neutral/Laggard), and trend (Accelerating/Slowing).
- **Automated Selection:** Hybrid strategy combining "Blue Chips" + KMeans clustering + a correlation filter to remove redundant assets.
- **Multi-Profile Optimization:** Generates 4 distinct portfolios based on risk profile using Efficient Frontier optimization (PyPortfolioOpt).
- **Synchronized Backtesting:** Tests strategies over 1, 2, 3, and 5-year horizons against the "Market" (median of all stocks).
- **Comprehensive Reporting:** Outputs results to the console and detailed text files.

---

## Project Structure

```
Portfolio/
├── pipeline.py                    # Entry point: coordinates all stages into one scenario
├── importer.py                    # Data loader: fetches price history from MOEX ISS API
├── analyzer.py                    # Market analyst: metrics and stock classification
├── optimizer.py                   # Portfolio assembly and weight optimization
├── backtester.py                  # Backtester: compares portfolios against the market
├── data/
│   ├── moex_massive_history.csv   # Cache: price matrix (dates × tickers)
│   └── market_dynamics.txt        # Generated report on stock dynamics
└── .gitignore
```

---

## Architecture

The project is built as a pipeline consisting of 4 independent modules, each implemented as a separate class. `pipeline.py` acts as the orchestrator, passing the output of each stage as input to the next.

### Data Flow Diagram

```
                MOEX ISS API (https://iss.moex.com)
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │  importer.MoexFullImporter            │
        │  history download + liquidity filter  │──► data/moex_massive_history.csv (cache)
        └───────────────────┬───────────────────┘
                            │  DataFrame: index — date, columns — tickers (Close prices)
                            ▼
        ┌───────────────────────────────────────┐
        │  analyzer.MarketAnalyzer              │
        │  metrics + stock classification       │──► data/market_dynamics.txt
        └───────────────────┬───────────────────┘        + console report
                            │  stats: Yield_Global, Yield_Recent,
                            │         Volatility, Group, Trend
                            ▼
        ┌───────────────────────────────────────┐
        │  optimizer.PortfolioEngine            │
        │  stock selection + weight optimization│
        └───────────────────┬───────────────────┘
                            │  4 portfolios {SAFE, OPTIMAL, PROFIT, RISKY}
                            │  = (metrics, weights)
                            ▼
        ┌───────────────────────────────────────┐
        │  backtester.BacktestEngine            │
        │  backtest against "median-market"     │──► console tables
        └───────────────────────────────────────┘        (+ optional matplotlib chart)
```

### Modules

#### 1. `importer.py` — `MoexFullImporter` Class

Data loader. The `get_massive_data()` method:

1. If the cache file exists and `force_update=False`, it simply loads the CSV and returns a DataFrame.
2. Otherwise, it requests a list of all active TQBR tickers and filters for liquidity: daily trading volume `VALTODAY >= min_volume` (default: 15M RUB).
3. For each ticker, it downloads `TRADEDATE` + `CLOSE` history page by page (100 rows per page); includes a 0.05s delay between requests and progress updates.
4. Discards "young" stocks with history shorter than `min_history_years` (default: 1 year).
5. Concatenates all Series into a single "dates × tickers" matrix, fills gaps using `ffill` (forward fill), and saves to cache.

#### 2. `analyzer.py` — `MarketAnalyzer` Class

Calculates the following for each stock:

| Metric | Formula | Description |
|---|---|---|
| `Yield_Global` | average daily return × 252 | Annual yield for the entire history |
| `Yield_Recent` | average daily return × 252 (last 2 years) | "Fresh" annual yield |
| `Volatility` | st. deviation of daily returns × √252 | Annualized volatility |
| `Group` | `pd.qcut(Yield_Global, q=3)` | Tercile: `Laggards` / `Neutral` / `Leaders` |
| `Trend` | `Yield_Recent > Yield_Global` | `Accelerating` / `Slowing` |

Input data is pre-cleaned: daily movements >±50% are masked as NaN to protect against technical glitches. Stocks without a 2-year history are removed.

#### 3. `optimizer.py` — `PortfolioEngine` Class

Operates in three steps: selection → estimation → optimization.

**Step 1. Candidate Selection (`_apply_clustering`):**
- **Core:** A fixed list of "Blue Chips" (SBER, GAZP, LKOH, etc.); if present in data, they are always added.
- **Satellites:** Candidates (`Leaders` and `Neutral` with positive recent yield) are clustered using `KMeans` (6 clusters) by standardized features `[Yield_Recent, Volatility]`. The top 2 by `Yield_Recent` from each cluster are chosen to ensure diversification.
- **De-correlation:** For pairs with |correlation| > 0.85, the stock with the lower `Yield_Global / Volatility` ratio is removed.

**Step 2. Estimation (PyPortfolioOpt):**
- Expected returns `mu` — based on historical mean.
- Covariance matrix `S` — Ledoit–Wolf shrinkage (more stable than sample covariance).

**Step 3. Portfolio Construction (`build_portfolios`):**

| Portfolio | Key | Optimization Method | Blue Chip Limits | Others Limits | Concept |
|---|---|---|---|---|---|
| Conservative | `SAFE` | `min_volatility` | 2–15% | 0–10% | Minimum risk |
| Optimal | `OPTIMAL` | `max_sharpe` | 3–15% | 0–15% | Maximum Sharpe Ratio |
| Aggressive | `PROFIT` | `efficient_return` (OPTIMAL + 5%) | 1–20% | 0–25% | Higher return target |
| Speculative | `RISKY` | `max_sharpe` on top 3 yielders | ≤ 60% | — | Maximum return focus |

#### 4. `backtester.py` — `BacktestEngine` Class

Evaluates portfolios over the last N years:
- Calculates cumulative capital curves using `(1 + r).cumprod()`.
- Metrics: **Total Return**, **Max Drawdown**, **Sharpe Ratio** (using a 14% risk-free rate).

**Note:** The "Market" benchmark is calculated as the **median daily return of all stocks**, which ignores outliers and provides a realistic "typical stock" comparison.

---

## Technologies

| Library | Purpose |
|---|---|
| pandas, numpy | Data processing and numerical calculations |
| requests | HTTP requests to MOEX ISS API |
| scikit-learn | KMeans clustering and feature scaling |
| PyPortfolioOpt | Efficient Frontier, Ledoit–Wolf, weight optimization |
| matplotlib | Visualization of capital growth |

---

## Usage

```bash
# Install dependencies
pip install pandas numpy requests scikit-learn PyPortfolioOpt matplotlib

# Run the pipeline
python pipeline.py
```

---

## Configuration

| Parameter | Location | Default | Description |
|---|---|---|---|
| `min_volume` | `pipeline.py` | 15,000,000 | Minimum daily volume filter |
| `start` | `pipeline.py` | 2000-01-01 | History start date |
| `risk_free_rate`| `pipeline.py` | 0.14 | Benchmark for Sharpe Ratio |
| `n_clusters` | `optimizer.py` | 6 | Number of KMeans clusters |
| `threshold` | `optimizer.py` | 0.85 | Correlation filter threshold |

---

## Key Project Decisions

1. **Outlier Filtering:** Daily price changes >50% are zeroed out to prevent data glitches from skewing statistics.
2. **Median Benchmark:** Using the median instead of a mean or a cap-weighted index provides a fairer comparison against a "typical" market participant.
3. **Guaranteed Core:** Minimum weights for Blue Chips ensure the model maintains a foundation in high-liquidity large-cap stocks.
4. **Ledoit–Wolf Shrinkage:** Improves the stability of the Markowitz optimization, especially when dealing with limited historical data.

---

## License & Copyright

© 2026 Vladislav585

This software is provided for **Non-Commercial Use Only**.

- **Permitted:** Copying, modifying, and using the code for personal or educational purposes.
- **Prohibited:** Commercial use, re-selling, or use for-profit financial services.

**Disclaimer:** The author is not responsible for any financial losses or consequences resulting from the use of this code. All calculations are theoretical and do not constitute financial advice.
