import bisect
from datetime import date
from typing import Any

import numpy as np
from dateutil.relativedelta import relativedelta

from personal_finance_etl.backend.engines.analytics.core.math import (
    calculate_risk_metrics,
    extract_drawdown_metadata,
)
from personal_finance_etl.backend.engines.analytics.pipeline.processor.benchmark import (
    BenchmarkPriceProvider,
)
from personal_finance_etl.backend.engines.analytics.rules.macro import FYMacroParametersTable
from personal_finance_etl.backend.utils.helpers import to_date_obj


class RiskMetricsProvider:
    def __init__(
        self,
        m_inst: list[dict[str, Any]],
        bm_provider: BenchmarkPriceProvider,
        fy_table: FYMacroParametersTable,
    ):
        self.fy_table = fy_table
        self.bm_provider = bm_provider
        self.inst_px: dict[date, float] = {}
        for m_row in m_inst:
            d = to_date_obj(m_row["Date"])
            if d:
                self.inst_px[d] = float(m_row["Closing Price"])
        self.valid_dates = sorted(self.inst_px.keys())

        self.inst_ret_map: dict[date, float] = {}
        self.bm_ret_map: dict[date, float] = {}
        if len(self.valid_dates) > 1:
            for k in range(1, len(self.valid_dates)):
                d_c, d_p = self.valid_dates[k], self.valid_dates[k - 1]
                pc, pp = self.inst_px[d_c], self.inst_px[d_p]
                bmc, bmp = bm_provider.get_bm_price(d_c), bm_provider.get_bm_price(d_p)
                if pp > 0 and bmc and bmp and bmp > 0:
                    self.inst_ret_map[d_c] = (pc - pp) / pp
                    self.bm_ret_map[d_c] = (bmc - bmp) / bmp

        if len(self.valid_dates) > 1:
            span_days = (self.valid_dates[-1] - self.valid_dates[0]).days
            avg_gap = span_days / (len(self.valid_dates) - 1)
            self.periods_per_year = 365.0 / max(avg_gap, 0.5)
        else:
            self.periods_per_year = 252.0

    def calculate_risk(
        self, first_p_date: date, m_date: date
    ) -> tuple[
        float,
        float,
        float,
        float,
        float,
        float,
        float,
        float,
        float,
        float,
        float,
        float,
        float,
        float,
    ]:
        """
        Returns:
            (beta, t_err_ann, up_capture, down_capture,
             inst_sharpe, inst_sortino, inst_calmar, inst_current_dd, inst_max_dd,
             bm_sharpe,   bm_sortino,   bm_calmar,   bm_current_dd,   bm_max_dd)
        """
        past_dates = [d for d in self.valid_dates if first_p_date <= d <= m_date]
        rfr = self.fy_table.get_risk_free_rate(m_date)
        return calculate_risk_metrics(
            self.inst_ret_map, self.bm_ret_map, past_dates, self.periods_per_year, rfr
        )

    def calculate_time_ranges(self, m_date: date) -> dict[str, float]:

        horizons = {
            "1d": relativedelta(days=1),
            "1w": relativedelta(weeks=1),
            "1m": relativedelta(months=1),
            "3m": relativedelta(months=3),
            "6m": relativedelta(months=6),
            "12m": relativedelta(years=1),
            "3y": relativedelta(years=3),
            "5y": relativedelta(years=5),
        }
        metrics: dict[str, float] = {}

        current_px = self.inst_px.get(m_date)
        current_bm = self.bm_provider.get_bm_price(m_date)

        if current_px is None:
            return metrics

        valid_dates = [d for d in self.valid_dates if d <= m_date]
        if not valid_dates:
            return metrics

        def get_px_at_horizon(target_date: date) -> tuple[float | None, float | None]:
            idx = bisect.bisect_right(valid_dates, target_date)
            if idx > 0:
                d = valid_dates[idx - 1]
                return self.inst_px.get(d), self.bm_provider.get_bm_price(d)
            return None, None

        for label, delta in horizons.items():
            target = m_date - delta
            px, bm = get_px_at_horizon(target)

            if px and px > 0:
                metrics[f"return_{label}"] = (current_px / px) - 1.0
            if bm and current_bm and bm > 0:
                bm_ret = (current_bm / bm) - 1.0
                if px and px > 0:
                    metrics[f"alpha_{label}"] = metrics[f"return_{label}"] - bm_ret

        # YTD (Prior Year End)
        target_ytd = date(m_date.year - 1, 12, 31)
        px, bm = get_px_at_horizon(target_ytd)
        if px and px > 0:
            metrics["return_ytd"] = (current_px / px) - 1.0
        if bm and current_bm and bm > 0 and px and px > 0:
            metrics["alpha_ytd"] = metrics["return_ytd"] - ((current_bm / bm) - 1.0)

        # FY_YTD (Prior FY End)
        fy_year = m_date.year if m_date.month >= 4 else m_date.year - 1
        target_fy_ytd = date(fy_year, 3, 31)
        px, bm = get_px_at_horizon(target_fy_ytd)
        if px and px > 0:
            metrics["return_fy_ytd"] = (current_px / px) - 1.0
        if bm and current_bm and bm > 0 and px and px > 0:
            metrics["alpha_fy_ytd"] = metrics["return_fy_ytd"] - ((current_bm / bm) - 1.0)

        return metrics

    def calculate_drawdowns(self, first_p_date: date, m_date: date) -> tuple[date | None, int, int]:

        past_dates = [d for d in self.valid_dates if first_p_date <= d <= m_date]
        matching_dates = [d for d in past_dates if d in self.inst_ret_map]
        ira_list = [self.inst_ret_map[d] for d in matching_dates]

        if not ira_list:
            return None, 0, 0

        return extract_drawdown_metadata(matching_dates, np.array(ira_list))
