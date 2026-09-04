# Инвестиционный портфель MOEX (AI Pipeline)

> **Languages:** [🇷🇺 Русский](#russian-version) | [🇺🇸 English](#english-version)

<a id="russian-version"></a>

Автоматизированная система полного цикла для анализа и построения инвестиционных портфелей на акциях Московской биржи.

**Критическая особенность:** в проекте реализована методология **Out-of-Sample (тестирование вне выборки)** по схеме **Walk-Forward**. Система делит время на скользящие окна: портфель рассчитывается только на исторических данных (окно обучения — 2 года), после чего его доходность проверяется на **следующем годе**, который модель никогда не видела. Затем окно сдвигается — и всё повторяется. Это полностью исключает «заглядывание в будущее» (Lookahead Bias): модель принимает решения, основываясь только на прошлом, и проверяет их на реальном рынке.

> ⚠️ Дисклеймер: Проект носит исследовательский характер. Прошлые результаты не гарантируют будущую доходность.

---

## Возможности

- **Zero Lookahead Bias:** Честное разделение данных. Оптимизация весов происходит на одном временном отрезке, а проверка доходности — на совершенно другом (следующем годе).
- **Walk-Forward ребалансировка:** Ежегодный пересчет состава портфелей в бэктесте — как в реальном управлении капиталом.
- **Stress-Testing 2025:** Успешное прохождение проверки на реальном обвале рынка РФ в 2025 году (сверка с индексом полной доходности MCFTR).
- **Direct MOEX Access:** Сбор данных напрямую с серверов Московской биржи через ISS API (режим TQBR).
- **Data Caching & Isolation:** Автоматическое кэширование котировок и хранение данных в изолированной папке `data/`.
- **Hybrid Strategy:** Сочетание «Ядра» (голубые фишки — ликвидные гиганты) и «Спутников» (высокодоходные активы, отобранные кластеризацией KMeans).
- **4 профиля риска:** От консервативного (SAFE) до спекулятивного (RISKY) — под разные цели инвестора.

---

## Архитектура проекта

Проект построен по модульному принципу: каждый модуль отвечает за один этап конвейера, а `pipeline.py` связывает их в единую систему.

```
pipeline.py  ──►  Точка входа (оркестратор)
    │
    ├─► importer.py    (MoexFullImporter)   ──►  Сбор и кэширование котировок с MOEX ISS API
    │
    └─► backtester.py  (BacktestEngine)    ──►  Walk-Forward симуляция и итоговые отчеты
          │
          ├─► analyzer.py   (MarketAnalyzer)    ──►  Очистка данных, метрики, классификация акций
          └─► optimizer.py  (PortfolioEngine)   ──►  Отбор активов и оптимизация весов

check_market.py ──► Диагностический скрипт (сверка бенчмарков с реальным индексом MCFTR)
```

| Модуль | Класс | Назначение |
|---|---|---|
| `pipeline.py` | — | Точка входа: загружает данные и запускает динамический тест |
| `importer.py` | `MoexFullImporter` | Скачивает всю историю акций и индексов с MOEX, фильтрует по ликвидности, кэширует в CSV |
| `analyzer.py` | `MarketAnalyzer` | Считает доходности/волатильность, чистит аномалии, делит акции на группы |
| `optimizer.py` | `PortfolioEngine` | Отбирает активы (кластеризация + фильтры) и оптимизирует веса 4 портфелей |
| `backtester.py` | `BacktestEngine` | Прогоняет Walk-Forward тест, считает метрики, строит графики |
| `check_market.py` | — | Диагностика: проверяет, насколько внутренний бенчмарк совпадает с реальным рынком |

## Логика работы (пошагово)

### Шаг 1. Сбор данных — `importer.py`

- Через **ISS API Московской биржи** (режим `TQBR`) получает список всех активных тикеров и оставляет только ликвидные бумаги с дневным оборотом **≥ 15 млн ₽** (`VALTODAY`).
- Скачивает **полную историю цен закрытия с 2000 года** с постраничной пагинацией (по 100 строк на запрос).
- Отсекает «молодые» бумаги, торгующиеся **менее 1 года**.
- Склеивает всё в единую матрицу **(дни × акции)**; редкие пропуски заполняются методом «последнее известное значение» (`ffill`).
- Результат кэшируется в `data/moex_massive_history.csv` — повторные запуски работают мгновенно из кэша (обновление — через `force_update=True`).
- Метод `get_index_history()` дополнительно умеет грузить полную историю индексов (`IMOEX`, `MCFTR`) для сравнения.

### Шаг 2. Очистка и метрики — `analyzer.py`

- Доходности считаются как `pct_change()`, после чего **аномальные дневные колебания (|r| > 20%) маскируются в NaN** — защита от сплитов, делистингов и технических глюков биржи.
- Для каждой акции рассчитываются:
  - **Yield_Global** — годовая доходность за весь период истории;
  - **Yield_Recent** — годовая доходность за последние 2 года;
  - **Volatility** — годовая волатильность.
- Классификация: деление по квантилям `Yield_Global` на группы **Laggards / Neutral / Leaders**, а также определение тренда **Accelerating / Slowing** (сравнение недавней и глобальной доходности).

### Шаг 3. Отбор активов — `optimizer.py`

1. **Кандидаты:** только группы `Leaders` и `Neutral` с положительной недавней доходностью.
2. **Ядро:** 19 обязательных голубых фишек (`SBER`, `GAZP`, `LKOH`, `GMKN`, `ROSN`, `NVTK`, `TATN`, `PLZL` и др.) — гарантия ликвидности.
3. **Спутники:** кластеризация **KMeans (k=6)** по признакам `[Yield_Recent, Volatility]` после `StandardScaler`; из каждого кластера берутся **топ-2 акции по недавней доходности**.
4. **Де-корреляция:** пары акций с корреляцией выше **0.85** сокращаются — остается та, у которой лучше коэффициент Шарпа.
5. **Momentum-фильтр:** остаются только акции, выросшие за последние **63 торговых дня (~3 месяца)**. Если рынок обвалился и не растет никто — берутся топ-7 лучших по тренду (защита от пустого рынка).

### Шаг 4. Оптимизация весов — `optimizer.py`

- **Ожидаемая доходность (mu):** EMA-доходность (`span=252`) — экспоненциально взвешенная, быстрее реагирует на свежие данные, чем простое среднее.
- **Риск (S):** **полуковариация** (`semicovariance`, benchmark=0) — в риске учитываются только падения, поэтому оптимизация ориентирована на коэффициент **Сортино**.
- **Лимиты весов:** голубые фишки — от 3% до 20% (ядро всегда присутствует в портфеле), остальные активы — до 15%. Защита от концентрации в одной бумаге.

Формируются **4 портфеля** под разные профили риска:

| Портфель | Метод | Суть |
|---|---|---|
| **SAFE** | Минимизация волатильности | Максимально спокойный вариант |
| **OPTIMAL** | Максимизация Шарпа | Лучший баланс риск/доходность |
| **PROFIT** | Заданная доходность (SAFE + 8 п.п.) | Агрессивный рост (fallback: max Sharpe с лимитом 25%) |
| **RISKY** | Max Sharpe на топ-5 лидерах momentum | Спекулятивный (веса 1–40%) |

### Шаг 5. Walk-Forward тестирование — `backtester.py`

- Старт в **2020 году**, окно обучения — **2 года**, тест — **следующий календарный год**, затем окно сдвигается на год вперед. Цикл повторяется до конца данных.
- На каждой итерации: Анализатор готовит статистику **только по прошлому** → Оптимизатор строит 4 портфеля → их веса применяются к **будущему году**.
- Дневная доходность портфеля = сумма произведений весов на дневные доходности акций.
- Бенчмарк **MARKET** — равновзвешенный рынок: средняя дневная доходность всех бумаг выборки.
- Итоговые метрики по каждой стратегии: **Total Return, Max Drawdown, Sharpe, Sortino** (Сортино считается по downside-волатильности — только отрицательные дни).
- Финал: график кривых роста 1 рубля (matplotlib), где OPTIMAL выделен жирной линией, а рынок — пунктиром.

> Параметр `risk_free_rate=0.14` — безрисковая ставка (ключевая ставка ЦБ РФ), задается при запуске.

---

## Ключевые методологические решения

- **Zero Lookahead:** на каждом шаге бэктеста модель видит строго прошлое окно (2 года), а проверяется строго на будущем годе. Один и тот же код используется и в тесте, и для построения реальных портфелей.
- **Единый препроцессинг:** фильтр аномалий (|r| > 20%) применяется одинаково и на обучении, и на тесте.
- **Полуковариация вместо обычной ковариации:** риск измеряется только по отрицательным отклонениям — портфели устойчивее к просадкам.
- **Жесткие границы весов:** ни одна акция не может «захватить» портфель; ядро голубых фишек всегда присутствует.
- **Валидация бенчмарка:** `check_market.py` сверяет внутренние расчеты с реальным индексом MCFTR (индекс полной доходности МосБиржи) на стрессовом периоде 2025 года.

---

## Технологии и зависимости

| Библиотека | Назначение |
|---|---|
| **pandas, numpy** | Обработка матриц данных и математические расчеты |
| **requests** | Взаимодействие с официальным API Московской биржи |
| **scikit-learn** | Кластеризация KMeans и стандартизация признаков |
| **PyPortfolioOpt** | Оптимизация Марковица (Efficient Frontier), полуковариация, EMA-доходности |
| **matplotlib** | Визуализация результатов тестирования |

## Быстрый старт

```bash
git clone https://github.com/Vladislav585/investment-portfolio-ml.git
cd investment-portfolio-ml
pip install pandas numpy requests scikit-learn PyPortfolioOpt matplotlib
python pipeline.py
```

- Требуется **Python 3.12+**.
- Первый запуск скачает всю историю с MOEX (несколько минут), далее данные берутся из кэша `data/`.

## Структура проекта

```
├── pipeline.py        # Точка входа: данные + запуск Walk-Forward теста
├── importer.py        # Загрузчик MOEX ISS API, фильтры ликвидности, кэш CSV
├── analyzer.py        # Метрики, очистка аномалий, классификация акций
├── optimizer.py       # Кластеризация, фильтры, оптимизация 4 портфелей
├── backtester.py      # Walk-Forward движок, метрики Шарп/Сортино, графики
├── check_market.py    # Диагностика бенчмарка против реального MCFTR (2025)
└── data/              # Кэш котировок (создается автоматически)
```

## Лицензия и авторское право

© 2026 Vladislav585. Данное ПО распространяется на условиях **некоммерческого использования**.

**Отказ от ответственности:** Автор не несет ответственности за любые финансовые последствия. Все расчеты являются теоретическими.


<div align="center">
  <hr size="3" width="100%" color="gray">
  <h2 id="english-version">🇺🇸 English Version</h2>
  <hr size="3" width="100%" color="gray">
</div>

# MOEX Investment Portfolio (AI Pipeline)

An end-to-end automated system for analyzing and building investment portfolios on Moscow Exchange (MOEX) stocks.

**Key feature:** the project implements an **Out-of-Sample** testing methodology based on a **Walk-Forward** scheme. The timeline is split into sliding windows: a portfolio is computed using historical data only (a 2-year training window), and its performance is then verified on the **following year** — data the model has never seen. The window then shifts forward, and the process repeats. This completely eliminates Lookahead Bias: the model makes decisions based only on the past and is evaluated on the real market.

> ⚠️ Disclaimer: This is a research project. Past performance does not guarantee future returns.

---

## Features

- **Zero Lookahead Bias:** Honest data separation. Weight optimization happens on one time segment, while performance is verified on a completely different one (the following year).
- **Walk-Forward rebalancing:** Annual portfolio recomputation during the backtest — just like real portfolio management.
- **Stress-Testing 2025:** Successfully passed verification against the real Russian market crash of 2025 (cross-checked with the MCFTR total-return index).
- **Direct MOEX Access:** Data is collected directly from Moscow Exchange servers via the ISS API (TQBR board).
- **Data Caching & Isolation:** Automatic quote caching and isolated data storage in the `data/` folder.
- **Hybrid Strategy:** A combination of a "Core" (blue-chip giants) and "Satellites" (high-yield assets selected via KMeans clustering).
- **4 risk profiles:** From conservative (SAFE) to speculative (RISKY).

---

## Architecture

The project is modular: each module handles one stage of the pipeline, and `pipeline.py` wires them together.

```
pipeline.py  ──►  Entry point (orchestrator)
    │
    ├─► importer.py    (MoexFullImporter)   ──►  Data collection & caching from MOEX ISS API
    │
    └─► backtester.py  (BacktestEngine)    ──►  Walk-Forward simulation & final reports
          │
          ├─► analyzer.py   (MarketAnalyzer)    ──►  Data cleaning, metrics, stock classification
          └─► optimizer.py  (PortfolioEngine)   ──►  Asset selection & weight optimization

check_market.py ──► Diagnostic script (benchmark validation against the real MCFTR index)
```

| Module | Class | Purpose |
|---|---|---|
| `pipeline.py` | — | Entry point: loads data and runs the dynamic test |
| `importer.py` | `MoexFullImporter` | Downloads the full stock & index history from MOEX, filters by liquidity, caches to CSV |
| `analyzer.py` | `MarketAnalyzer` | Computes returns/volatility, cleans anomalies, groups stocks |
| `optimizer.py` | `PortfolioEngine` | Selects assets (clustering + filters) and optimizes weights for 4 portfolios |
| `backtester.py` | `BacktestEngine` | Runs the Walk-Forward test, computes metrics, plots charts |
| `check_market.py` | — | Diagnostics: checks how closely the internal benchmark matches the real market |

## How It Works (Step by Step)

### Step 1. Data Collection — `importer.py`

- Uses the **MOEX ISS API** (`TQBR` board) to fetch all active tickers and keeps only liquid stocks with a daily turnover of **≥ 15M RUB** (`VALTODAY`).
- Downloads the **full closing-price history since 2000** with pagination (100 rows per request).
- Discards "young" stocks trading for **less than 1 year**.
- Merges everything into a single **(days × stocks)** matrix; rare gaps are filled with the last known value (`ffill`).
- The result is cached in `data/moex_massive_history.csv` — subsequent runs load instantly from the cache (refresh via `force_update=True`).
- The `get_index_history()` method can additionally fetch full index history (`IMOEX`, `MCFTR`) for comparison.

### Step 2. Cleaning & Metrics — `analyzer.py`

- Returns are computed via `pct_change()`, after which **abnormal daily moves (|r| > 20%) are masked as NaN** — protection against splits, delistings, and exchange glitches.
- For each stock the following metrics are calculated:
  - **Yield_Global** — annualized return over the full history;
  - **Yield_Recent** — annualized return over the last 2 years;
  - **Volatility** — annualized volatility.
- Classification: stocks are split by `Yield_Global` quantiles into **Laggards / Neutral / Leaders**, plus a trend flag **Accelerating / Slowing** (comparing recent vs. global returns).

### Step 3. Asset Selection — `optimizer.py`

1. **Candidates:** only `Leaders` and `Neutral` groups with positive recent returns.
2. **Core:** 19 mandatory blue chips (`SBER`, `GAZP`, `LKOH`, `GMKN`, `ROSN`, `NVTK`, `TATN`, `PLZL`, etc.) — a liquidity guarantee.
3. **Satellites:** **KMeans clustering (k=6)** on `[Yield_Recent, Volatility]` features after `StandardScaler`; the **top-2 stocks by recent return** are taken from each cluster.
4. **De-correlation:** stock pairs with correlation above **0.85** are reduced — the one with the better Sharpe ratio stays.
5. **Momentum filter:** only stocks that grew over the last **63 trading days (~3 months)** remain. If the market crashed and nothing is rising, the top-7 momentum leaders are kept (protection against an empty universe).

### Step 4. Weight Optimization — `optimizer.py`

- **Expected returns (mu):** EMA historical return (`span=252`) — exponentially weighted, reacts faster to fresh data than a simple mean.
- **Risk (S):** **semicovariance** (`benchmark=0`) — only downside moves count as risk, so the optimization is oriented toward the **Sortino** ratio.
- **Weight bounds:** blue chips — 3% to 20% (the core is always present in the portfolio), other assets — up to 15%. Protection against concentration in a single stock.

**4 portfolios** are built for different risk profiles:

| Portfolio | Method | Purpose |
|---|---|---|
| **SAFE** | Minimum volatility | The calmest option |
| **OPTIMAL** | Maximum Sharpe ratio | The best risk/return balance |
| **PROFIT** | Target return (SAFE + 8 pp) | Aggressive growth (fallback: max Sharpe with a 25% cap) |
| **RISKY** | Max Sharpe on top-5 momentum leaders | Speculative (weights 1–40%) |

### Step 5. Walk-Forward Testing — `backtester.py`

- Starts in **2020** with a **2-year** training window, tests on the **following calendar year**, then shifts the window one year forward. The cycle repeats until the data ends.
- At each iteration: the Analyzer prepares statistics **from the past only** → the Optimizer builds 4 portfolios → their weights are applied to the **future year**.
- Daily portfolio return = the sum of weights multiplied by daily stock returns.
- The **MARKET** benchmark is an equal-weighted market: the average daily return of all stocks in the sample.
- Final metrics per strategy: **Total Return, Max Drawdown, Sharpe, Sortino** (Sortino is computed on downside volatility — negative days only).
- Finale: a capital growth chart ("growth of 1 ruble", matplotlib), where OPTIMAL is highlighted with a thick line and the market is dashed.

> The `risk_free_rate=0.14` parameter is the risk-free rate (the Bank of Russia key rate), set at launch.

---

## Key Methodological Decisions

- **Zero Lookahead:** at every backtest step the model sees strictly the past window (2 years) and is verified strictly on the future year. The same code is used both in the test and for building real portfolios.
- **Unified preprocessing:** the anomaly filter (|r| > 20%) is applied identically to both training and testing.
- **Semicovariance instead of plain covariance:** risk is measured only on negative deviations — portfolios are more resilient to drawdowns.
- **Hard weight bounds:** no single stock can "capture" the portfolio; the blue-chip core is always present.
- **Benchmark validation:** `check_market.py` cross-checks internal calculations against the real MCFTR index (MOEX Total Return index) on the stressful 2025 period.

---

## Technologies & Dependencies

| Library | Purpose |
|---|---|
| **pandas, numpy** | Data matrix processing and mathematical calculations |
| **requests** | Interaction with the official Moscow Exchange API |
| **scikit-learn** | KMeans clustering and feature standardization |
| **PyPortfolioOpt** | Markowitz optimization (Efficient Frontier), semicovariance, EMA returns |
| **matplotlib** | Visualization of backtest results |

## Quick Start

```bash
git clone https://github.com/Vladislav585/investment-portfolio-ml.git
cd investment-portfolio-ml
pip install pandas numpy requests scikit-learn PyPortfolioOpt matplotlib
python pipeline.py
```

- Requires **Python 3.12+**.
- The first run downloads the full history from MOEX (a few minutes); after that, data is taken from the `data/` cache.

## Project Structure

```
├── pipeline.py        # Entry point: data + Walk-Forward test launch
├── importer.py        # MOEX ISS API loader, liquidity filters, CSV cache
├── analyzer.py        # Metrics, anomaly cleaning, stock classification
├── optimizer.py       # Clustering, filters, optimization of 4 portfolios
├── backtester.py      # Walk-Forward engine, Sharpe/Sortino metrics, charts
├── check_market.py    # Benchmark diagnostics against the real MCFTR (2025)
└── data/              # Quote cache (created automatically)
```

## License & Copyright

© 2026 Vladislav585. This software is distributed under a **non-commercial use** license.

**Disclaimer:** The author is not liable for any financial consequences. All calculations are theoretical.



