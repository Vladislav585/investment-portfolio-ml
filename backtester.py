import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

class BacktestEngine:
    def __init__(self, full_prices, portfolio_engine_class, analyzer_class):
        # Защита от пустых значений и делистинга
        self.prices = full_prices.replace(0, np.nan).ffill()
        self.engine_class = portfolio_engine_class
        self.analyzer_class = analyzer_class

    def run_dynamic_test(self, start_date='2020-01-01', window_years=2, risk_free_rate=0.14):
        current_date = pd.to_datetime(start_date)
        end_history = self.prices.index.max()
        
        # Списки для накопления ежедневных доходностей
        strategy_returns = { 'SAFE': [], 'OPTIMAL': [], 'PROFIT': [], 'RISKY': [] }
        market_returns = []

        print(f"\n[AI-SYSTEM] Запуск Walk-Forward симуляции...")

        while current_date + pd.DateOffset(years=1) <= end_history:
            train_start = current_date - pd.DateOffset(years=window_years)
            train_end = current_date
            test_end = current_date + pd.DateOffset(years=1)

            # 1. Обучение: используем Анализатор для подготовки данных прошлого
            train_prices = self.prices.loc[train_start:train_end]
            analyzer = self.analyzer_class(train_prices)
            stats = analyzer.analyze() 

            # 2. Оптимизация: ищем веса на основе данных прошлого
            engine = self.engine_class(train_prices, stats)
            try:
                all_portfolios = engine.build_portfolios(risk_free_rate=risk_free_rate)
            except Exception as e:
                print(f"   ! Ошибка в периоде {train_end.year}: {e}")
                current_date = test_end
                continue

            # 3. Тест: проверяем веса на данных будущего года
            test_slice_prices = self.prices.loc[train_end:test_end]
            # Получаем чистые доходности через Анализатор (чтобы фильтр 20% сработал)
            test_analyzer = self.analyzer_class(test_slice_prices)
            clean_test_returns = test_analyzer.get_cleaned_returns()

            for name in strategy_returns.keys():
                if name in all_portfolios:
                    weights = all_portfolios[name][1]
                    tickers = list(weights.keys())
                    # Доходность за каждый день: сумма (веса * доходности акций)
                    p_daily = (clean_test_returns[tickers] * pd.Series(weights)).sum(axis=1)
                    strategy_returns[name].append(p_daily)

            # Собираем бенчмарк рынка (среднее) для этого же периода
            market_returns.append(clean_test_returns.mean(axis=1))
            
            print(f"   > Сформированы портфели на {test_end.year} год. (Обучение: {train_start.year}-{train_end.year})")
            current_date = test_end

        # Вызываем финальную сборку и отрисовку
        self._finalize_and_plot(strategy_returns, market_returns, risk_free_rate)

    def _finalize_and_plot(self, strategy_returns, market_returns, rf):
        """ Собирает все куски доходностей в единые кривые и выводит отчет """
        results_curves = {}
        
        # 1. Готовим данные по рынку
        if market_returns:
            m_final_ret = pd.concat(market_returns)
            results_curves['MARKET'] = (1 + m_final_ret).cumprod()
            
            print("\n" + "="*95)
            print(f" ИТОГОВЫЙ ОТЧЕТ ПО ДИНАМИЧЕСКИМ СТРАТЕГИЯМ (С ЕЖЕГОДНЫМ ПЕРЕСЧЕТОМ)")
            print("="*95)
            print(f"{'Стратегия':<25} | {'Доходность':>10} | {'Просадка':>10} | {'Шарп':>8} | {'Сортино':>8}")
            print("-" * 95)
            self._print_metrics("РЫНОК (Бенчмарк)", m_final_ret, rf)

        # 2. Готовим данные по каждой ИИ-стратегии
        for name, ret_list in strategy_returns.items():
            if not ret_list: continue
            combined_ret = pd.concat(ret_list)
            results_curves[name] = (1 + combined_ret).cumprod()
            self._print_metrics(name, combined_ret, rf)
        
        print("="*95)
        
        # 3. Рисуем график
        self._plot_curves(results_curves)

    def _print_metrics(self, name, returns, rf):
        cum_ret = (1 + returns).cumprod()
        total_ret = cum_ret.iloc[-1] - 1
        mdd = ((cum_ret - cum_ret.cummax()) / cum_ret.cummax()).min()
        
        # Годовые показатели
        ann_ret = returns.mean() * 252
        ann_vol = returns.std() * np.sqrt(252)
        
        # Коэффициент Шарпа
        sharpe = (ann_ret - rf) / ann_vol if ann_vol > 0 else 0
        
        # --- НОВОЕ: КОЭФФИЦИЕНТ СОРТИНО ---
        # Считаем отклонение только для отрицательных доходностей
        negative_returns = returns[returns < 0]
        downside_std = negative_returns.std() * np.sqrt(252)
        sortino = (ann_ret - rf) / downside_std if downside_std > 0 else 0
        
        print(f"{name:<25} | {total_ret:>10.1%} | {mdd:>10.1%} | {sharpe:>8.2f} | {sortino:>8.2f}")

    def _plot_curves(self, curves):
        """ Отрисовка графиков доходности """
        plt.figure(figsize=(12, 7))
        for name, series in curves.items():
            linewidth = 3 if name == 'OPTIMAL' else 1.5
            linestyle = '--' if name == 'MARKET' else '-'
            plt.plot(series, label=name, linewidth=linewidth, linestyle=linestyle)
        
        plt.title("Динамика капитала: Ежегодная переборка портфелей (Walk-Forward)")
        plt.xlabel("Дата")
        plt.ylabel("Рост 1 рубля")
        plt.legend()
        plt.grid(True, alpha=0.2)
        plt.show()
