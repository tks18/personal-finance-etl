from datetime import date
from typing import Any

from personal_finance_etl.backend.engines.analytics.core.math import calculate_risk_metrics
from personal_finance_etl.backend.engines.analytics.pipeline.processor.benchmark import BenchmarkPriceProvider
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
    ]:
        """
        Returns:
            (beta, t_err_ann, up_capture, down_capture,
             inst_sharpe, inst_sortino, inst_calmar, inst_max_dd,
             bm_sharpe,   bm_sortino,   bm_calmar,   bm_max_dd)
        """
        past_dates = [d for d in self.valid_dates if first_p_date <= d <= m_date]
        rfr = self.fy_table.get_risk_free_rate(m_date)
        return calculate_risk_metrics(
            self.inst_ret_map, self.bm_ret_map, past_dates, self.periods_per_year, rfr
        )
