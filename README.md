# Инвестиционный портфель MOEX (AI Pipeline)

> **Languages:** [🇷🇺 Русский](#russian-version) | [🇺🇸 English](#english-version)

Автоматизированная система полного цикла для анализа и построения инвестиционных портфелей на акциях Московской биржи. 

**Критическая особенность:** В проекте реализована методология **Out-of-Sample (тестирование вне выборки)**. Система разделяет данные на исторический период обучения (2021–2024) и будущий период тестирования (2025+). Это полностью исключает «заглядывание в будущее» (Lookahead Bias): модель принимает решения, основываясь только на прошлом, и проверяет их на реальном рынке.

> ⚠️ Дисклеймер: Проект носит исследовательский характер. Прошлые результаты не гарантируют будущую доходность.

---

## Возможности

- **Zero Lookahead Bias:** Честное разделение данных. Оптимизация весов происходит на одном временном отрезке, а проверка доходности — на совершенно другом.
- **Stress-Testing 2025:** Успешное прохождение проверки на реальном обвале рынка РФ в 2025 году.
- **Direct MOEX Access:** Сбор данных напрямую с серверов Московской биржи через ISS API (режим TQBR).
- **Data Caching & Isolation:** Автоматическое кэширование котировок и хранение отчетов в изолированной папке `data/`.
- **Hybrid Strategy:** Сочетание «Ядра» (17 обязательных ликвидных гигантов) и «Спутников» (высокодоходные активы, отобранные кластеризацией KMeans).

---

## Технологии и зависимости

Для работы проекта требуются следующие библиотеки:

| Библиотека | Назначение |
|---|---|
| **pandas, numpy** | Обработка матриц данных и математические расчеты |
| **requests** | Взаимодействие с официальным API Московской биржи |
| **scikit-learn** | Кластеризация KMeans и стандартизация признаков |
| **PyPortfolioOpt** | Оптимизация Марковица (Efficient Frontier) и Ledoit-Wolf ковариация |
| **matplotlib** | Визуализация результатов тестирования |

---

## Установка и запуск

### 1. Клонирование репозитория
```bash
git clone https://github.com/vladislav585/moex-ai-portfolio.git
cd moex-ai-portfolio
```

### 2. Установка библиотек
Для корректной работы оптимизатора на Windows может потребоваться установка `cvxpy`.
```bash
pip install pandas numpy requests scikit-learn matplotlib PyPortfolioOpt
```

### 3. Запуск конвейера
```bash
python pipeline.py
```
*При первом запуске программа автоматически создаст папку `data/` и скачает историю торгов (может занять 2-3 минуты).*

---

## Структура проекта

```
Портфель/
├── pipeline.py                    # Точка входа: разделение данных (Train/Test) и запуск цикла
├── importer.py                    # Загрузчик: сбор истории цен с MOEX ISS API
├── analyzer.py                    # Аналитик: расчет метрик и трендов на Train-выборке
├── optimizer.py                   # ИИ-ядро: кластеризация и поиск весов на Train-выборке
├── backtester.py                  # Валидатор: Out-of-Sample тест стратегий на Test-выборке
├── data/                          # Изолированное хранилище данных (.csv) и отчетов (.txt)
└── README.md
```

---

## Лицензия и авторское право

© 2026 Vladislav585. Данное ПО распространяется на условиях **некоммерческого использования**. 

**Отказ от ответственности:** Автор не несет ответственности за любые финансовые последствия. Все расчеты являются теоретическими.

<br/><br/>
<div align="center">
  <hr size="3" width="100%" color="gray">
  <h2 id="english-version">🇺🇸 English Version</h2>
  <hr size="3" width="100%" color="gray">
</div>
<br/>

# MOEX Investment Portfolio (AI Pipeline)

Automated full-cycle system for constructing investment portfolios based on Moscow Exchange (MOEX) stocks.

**Key Feature:** The project implements a rigorous **Out-of-Sample** methodology. Data is split into a historical training period (2021–2024) and a future testing period (2025+). This completely eliminates **Lookahead Bias**: the model makes decisions based solely on the past and verifies them on the real 2025 market.

---

## Features

- **No Lookahead Bias:** True data separation. Portfolio weights are optimized on one timeframe and verified on another.
- **Stress-Tested in 2025:** Proven efficiency during the real Russian market crash of 2025.
- **Direct MOEX Access:** Data fetched directly from MOEX servers via the official ISS API.
- **Data Caching:** Automatic CSV-based caching ensures subsequent runs are near-instant.
- **Hybrid Selection:** "Core + Satellites" strategy (17 Blue Chips + top KMeans-selected assets).

---

## Technologies & Dependencies

| Library | Purpose |
|---|---|
| **pandas, numpy** | Data processing and numerical calculations |
| **requests** | Interaction with official MOEX ISS API |
| **scikit-learn** | KMeans clustering and feature scaling |
| **PyPortfolioOpt** | Efficient Frontier and Ledoit-Wolf shrinkage |
| **matplotlib** | Visualization of backtest results |

---

## Installation & Setup

### 1. Clone the repository
```bash
git clone https://github.com/vladislav585/moex-ai-portfolio.git
cd moex-ai-portfolio
```

### 2. Install dependencies
```bash
pip install pandas numpy requests scikit-learn matplotlib PyPortfolioOpt
```

### 3. Run the pipeline
```bash
python pipeline.py
```
*Note: On the first run, the system will create the `data/` folder and download historical data (takes 2-3 minutes).*

---

## Configuration

| Parameter | Location | Value | Description |
|---|---|---|---|
| `split_date` | `pipeline.py` | 2025-01-01 | Boundary between training and testing data |
| `risk_free_rate`| `pipeline.py` | 0.14 | Risk-free rate (benchmark for Sharpe Ratio) |
| `min_volume` | `importer.py` | 15,000,000 | Minimum daily volume filter (RUB) |

---

## License & Copyright

© 2026 Vladislav585. This software is provided for **Non-Commercial Use Only**.

**Disclaimer:** All calculations are theoretical. The author is not responsible for any financial losses. All rights reserved.
