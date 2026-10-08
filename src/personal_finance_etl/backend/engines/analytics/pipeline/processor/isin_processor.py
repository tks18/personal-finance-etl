from datetime import date
from typing import Any, cast

import polars as pl

from personal_finance_etl.backend.config.financial_rules import FinancialRules
from personal_finance_etl.backend.engines.analytics.core.fifo import FIFOPortfolio
from personal_finance_etl.backend.engines.analytics.core.math import calculate_cagr, calculate_xirr
from personal_finance_etl.backend.engines.analytics.pipeline.processor.benchmark import (
    BenchmarkPriceProvider,
)
from personal_finance_etl.backend.engines.analytics.pipeline.processor.snapshot import (
    SnapshotGenerator,
)
from personal_finance_etl.backend.engines.analytics.rules.macro import FYMacroParametersTable
from personal_finance_etl.backend.types.analytics import (
    CashflowRecord,
    ISINProcessResult,
    ISINTags,
    SnapshotRecord,
    TerminalValueRecord,
)
from personal_finance_etl.backend.utils.helpers import to_date_obj
from personal_finance_etl.backend.utils.logger import logger


class IsinProcessor:
    def __init__(
        self,
        fy_table: FYMacroParametersTable,
        start_date: date | None,
        end_date: date | None,
        rules: FinancialRules,
        fx_provider: Any = None,
    ) -> None:
        self.fy_table = fy_table
        self.start_date = start_date
        self.end_date = end_date
        self.rules = rules
        self.fx_provider = fx_provider

    def process(
        self,
        isin: str,
        p_inst: list[dict[str, Any]],
        s_inst: list[dict[str, Any]],
        m_inst: list[dict[str, Any]],
        master_row: dict[str, Any],
        bm_map: dict[date, float],
    ) -> ISINProcessResult | None:
        if not m_inst:
            return None

        logger.debug(f"[Processor] ISIN {isin} computing across {len(m_inst)} historical dates.")

        tax_type = str(master_row.get("TAX_TYPE", "equity"))
        tax_subtype = str(master_row.get("TAX_SUBTYPE", "listed"))
        bench_id = master_row.get("BENCHMARK_ID")

        bm_provider = BenchmarkPriceProvider(bench_id, None, prebuilt_map=bm_map)
        snapshot_generator = SnapshotGenerator(self.fy_table, self.rules, isin, master_row)

        default_curr = getattr(self.rules, "DEFAULT_CURRENCY_ID", "INR_INR")
        fifo = FIFOPortfolio(tax_type, tax_subtype, self.fy_table, default_curr)
        cf_dates: list[date] = []
        cf_amounts: list[float] = []
        bm_cf_amounts: list[float] = []
        bm_cf_amounts_local: list[float] = []

        first_p_date = (
            to_date_obj(p_inst[0]["Date"])
            if p_inst
            else (to_date_obj(m_inst[0]["Date"]) if m_inst else None)
        )
        if not first_p_date:
            return None

        p_idx = s_idx = 0
        isin_cashflows: list[CashflowRecord] = []
        isin_terminals: dict[date, TerminalValueRecord] = {}
        isin_realized: list[dict[str, float | date]] = []
        isin_recon_events: list[dict[str, Any]] = []
        isin_snapshots: list[SnapshotRecord] = []
        running_peak_price = 0.0
        running_max_dd = 0.0

        for m_row in m_inst:
            m_date = to_date_obj(m_row["Date"])
            if not m_date or m_date < first_p_date:
                continue

            while p_idx < len(p_inst):
                row_dt_obj = to_date_obj(p_inst[p_idx]["Date"])
                if row_dt_obj is None or row_dt_obj > m_date:
                    break
                row = p_inst[p_idx]
                qty = float(row["Quantity"])
                b_price = float(row["Price"])

                v_val = row.get("Value")
                buy_val = float(v_val) if v_val is not None else float(qty * b_price)

                bm_p_raw = bm_provider.get_bm_price(row_dt_obj)
                if not bm_p_raw or bm_p_raw <= 0:
                    bm_p_raw = float("nan")

                _pl_val = row.get("Price_Local")
                price_local = float(_pl_val) if _pl_val is not None else b_price
                currency_id = (
                    row.get("CURRENCY_ID")
                    or master_row.get("CURRENCY_ID")
                    or getattr(self.rules, "DEFAULT_CURRENCY_ID", "INR_INR")
                )
                fx_rate_buy = (
                    self.fx_provider.get_rate(row_dt_obj, currency_id) if self.fx_provider else 1.0
                )
                fx_rate_buy = fx_rate_buy if fx_rate_buy is not None else float("nan")

                # Assume bm_p_raw is in local currency (e.g. USD). Then INR value is bm_p_raw * fx_rate_buy.
                bm_buy_local = float(bm_p_raw)
                bm_buy_inr = float(bm_p_raw * fx_rate_buy)

                shadow_q = buy_val / bm_buy_inr if bm_buy_inr > 0 else 0.0

                purchase_id = row.get("Purchase_ID")

                fifo.buy(
                    row_dt_obj,
                    qty,
                    b_price,
                    shadow_q,
                    bm_buy_inr,
                    price_local=price_local,
                    fx_rate_buy=fx_rate_buy,
                    currency_id=currency_id,
                    bm_buy_local=bm_buy_local,
                    purchase_id=purchase_id,
                )
                cf_dates.append(row_dt_obj)
                cf_amounts.append(-buy_val)
                bm_cf_amounts.append(-buy_val)
                buy_val_local = float(qty * price_local)
                bm_cf_amounts_local.append(-buy_val_local)
                isin_cashflows.append(
                    CashflowRecord(date=row_dt_obj, amount=-buy_val, amount_local=-buy_val_local)
                )
                p_idx += 1

            while s_idx < len(s_inst):
                row_dt_obj = to_date_obj(s_inst[s_idx]["Date"])
                if row_dt_obj is None or row_dt_obj > m_date:
                    break
                row = s_inst[s_idx]
                s_qty = float(row["Quantity"])

                row_p_val: float | None = row.get("Price")
                sv_val: float | None = row.get("Sell_Value")

                if row_p_val is not None:
                    s_price = float(row_p_val)
                elif sv_val is not None and s_qty > 0:
                    s_price = float(sv_val) / s_qty
                else:
                    s_price = float(m_row.get("Closing_Price", 0.0))

                s_val = float(sv_val) if sv_val is not None else float(s_qty * s_price)

                _spl_val = row.get("Sell_Price_Local")
                s_price_local = float(_spl_val) if _spl_val is not None else s_price
                s_val_local = float(s_qty * s_price_local)
                currency_id = (
                    row.get("CURRENCY_ID")
                    or master_row.get("CURRENCY_ID")
                    or getattr(self.rules, "DEFAULT_CURRENCY_ID", "INR_INR")
                )
                fx_rate_sell = (
                    self.fx_provider.get_rate(row_dt_obj, currency_id) if self.fx_provider else 1.0
                )
                fx_rate_sell = fx_rate_sell if fx_rate_sell is not None else float("nan")

                cf_dates.append(row_dt_obj)
                cf_amounts.append(s_val)
                isin_cashflows.append(
                    CashflowRecord(date=row_dt_obj, amount=s_val, amount_local=s_val_local)
                )

                sale_id = row.get("Sale_ID")

                events = fifo.sell(
                    row_dt_obj,
                    s_qty,
                    s_price,
                    price_local=s_price_local,
                    fx_rate_sell=fx_rate_sell,
                    sale_id=sale_id,
                )

                # Calculate benchmark sell value
                bm_sell_price_local = bm_provider.get_bm_price(row_dt_obj)
                bm_sell_price_local = (
                    bm_sell_price_local if bm_sell_price_local is not None else float("nan")
                )
                bm_sell_price_inr = bm_sell_price_local * fx_rate_sell
                shadow_qty_sold = sum(e.get("shadow_qty_sold", 0.0) for e in events)
                bm_cf_amounts.append(shadow_qty_sold * bm_sell_price_inr)
                bm_cf_amounts_local.append(shadow_qty_sold * bm_sell_price_local)

                isin_realized.extend(events)
                s_idx += 1

            m_recon_bm_price = bm_provider.get_bm_price(m_date)
            if not m_recon_bm_price or m_recon_bm_price <= 0:
                m_recon_bm_price = float("nan")
            cf_recon, qty_recon_events = fifo.reconcile_quantity(m_row.get("Quantity"), m_date, m_recon_bm_price)
            for re in qty_recon_events:
                re["ISIN"] = isin
            isin_recon_events.extend(qty_recon_events)
            for cf in cf_recon:
                amt = cast(float, cf["amount"])
                cf_dates.append(cast(date, cf["date"]))
                cf_amounts.append(amt)
                bm_cf_amounts.append(amt)
                bm_cf_amounts_local.append(amt)
                isin_cashflows.append(
                    CashflowRecord(date=cast(date, cf["date"]), amount=amt, amount_local=amt)
                )

            cb_recon_events = fifo.reconcile_cost_basis(m_row.get("Buy_Value"), m_row.get("Buy_Value_Local"), m_date)
            for re in cb_recon_events:
                re["ISIN"] = isin
            isin_recon_events.extend(cb_recon_events)

            if not fifo.active_lots:
                continue

            if self.start_date and m_date < self.start_date:
                continue
            if self.end_date and m_date > self.end_date:
                continue

            m_price = float(m_row["Closing_Price"])
            m_bm_price = bm_provider.get_bm_price(m_date)
            if not m_bm_price or m_bm_price <= 0:
                m_bm_price = float("nan")

            fx_rate_snap = 1.0
            if (
                fifo.active_lots
                and fifo.active_lots[0].currency_id
                and fifo.active_lots[0].currency_id
                != getattr(self.rules, "DEFAULT_CURRENCY_ID", "INR_INR")
                and self.fx_provider
            ):
                fx_rate_snap = self.fx_provider.get_rate(m_date, fifo.active_lots[0].currency_id)
                fx_rate_snap = fx_rate_snap if fx_rate_snap is not None else float("nan")

            m_bm_price_inr = m_bm_price * fx_rate_snap

            closing_units = fifo.get_closing_units()
            terminal_val = fifo.get_terminal_value(m_price)
            shadow_terminal_val = fifo.get_shadow_terminal_value(m_bm_price_inr)
            shadow_terminal_val_local = fifo.get_shadow_terminal_value(m_bm_price)

            terminal_val_local = 0.0
            for lot in fifo.active_lots:
                if (
                    lot.currency_id
                    and lot.currency_id != getattr(self.rules, "DEFAULT_CURRENCY_ID", "INR_INR")
                    and self.fx_provider
                ):
                    fx_rate_snap_lot = self.fx_provider.get_rate(m_date, lot.currency_id)
                    m_price_local = (
                        m_price / fx_rate_snap_lot
                        if (fx_rate_snap_lot is not None and fx_rate_snap_lot > 0)
                        else float("nan")
                    )
                    terminal_val_local += lot.qty * m_price_local
                else:
                    terminal_val_local += lot.qty * m_price

            pt = isin_terminals.setdefault(m_date, TerminalValueRecord())
            pt.val += terminal_val
            pt.shadow_val += shadow_terminal_val
            pt.val_local += terminal_val_local
            pt.shadow_val_local += shadow_terminal_val_local

            after_tax_terminal_val = 0.0
            for lot in fifo.active_lots:
                if lot.qty <= 1e-8:
                    continue
                lbd = lot.date
                holding_type = self.fy_table.get_holding_type(
                    tax_type, tax_subtype, lbd or m_date, m_date
                )
                ltcg_rate, stcg_rate = self.fy_table.get_tax_rates(
                    tax_type, tax_subtype, lbd or m_date, m_date
                )
                pnl = (m_price - lot.price) * lot.qty
                unreal_ltcg = max(0.0, pnl) if holding_type == "LTCG" else 0.0
                unreal_stcg = max(0.0, pnl) if holding_type == "STCG" else 0.0
                ltcg_tax = unreal_ltcg * ltcg_rate
                stcg_tax = unreal_stcg * stcg_rate
                after_tax_terminal_val += (lot.qty * m_price) - (ltcg_tax + stcg_tax)

            pt.after_tax_val += after_tax_terminal_val

            inst_xirr = calculate_xirr(cf_dates + [m_date], cf_amounts + [terminal_val])
            bm_xirr_val = calculate_xirr(cf_dates + [m_date], bm_cf_amounts + [shadow_terminal_val])
            inst_after_tax_xirr = calculate_xirr(
                cf_dates + [m_date], cf_amounts + [after_tax_terminal_val]
            )

            inst_active_return = inst_xirr - bm_xirr_val
            is_lagging = inst_xirr < bm_xirr_val

            inst_cagr = inst_bm_cagr = 0.0
            if closing_units > 0:
                avg_cost = fifo.get_average_cost()
                avg_bm_cost = fifo.get_average_bm_cost()

                weighted_days = (
                    sum(lot.qty * (m_date - lot.date).days for lot in fifo.active_lots if lot.date)
                    / closing_units
                )
                inst_age = max(int(weighted_days), 1)

                if avg_cost > 0:
                    inst_cagr = calculate_cagr(avg_cost, m_price, inst_age)
                if avg_bm_cost > 0:
                    inst_bm_cagr = calculate_cagr(avg_bm_cost, m_bm_price_inr, inst_age)

            if m_price > running_peak_price:
                running_peak_price = m_price

            if running_peak_price > 0:
                current_dd = (m_price - running_peak_price) / running_peak_price
                if current_dd < running_max_dd:
                    running_max_dd = current_dd

            inst_max_dd = running_max_dd

            inst_metrics = {
                "cagr": inst_cagr,
                "bm_cagr": inst_bm_cagr,
                "xirr": inst_xirr,
                "bm_xirr": bm_xirr_val,
                "after_tax_xirr": inst_after_tax_xirr,
                "active_return": inst_active_return,
                "is_lagging": is_lagging,
                "max_drawdown": inst_max_dd,
            }

            # Local XIRR Calculation
            cf_dates_local = [c.date for c in isin_cashflows if c.date <= m_date]
            cf_amounts_local = [c.amount_local for c in isin_cashflows if c.date <= m_date]
            inst_xirr_local = calculate_xirr(
                cf_dates_local + [m_date], cf_amounts_local + [terminal_val_local]
            )

            bm_cf_dates_local = cf_dates_local
            bm_cf_local = bm_cf_amounts_local[: len(cf_dates_local)]
            inst_bm_xirr_local = calculate_xirr(
                bm_cf_dates_local + [m_date], bm_cf_local + [shadow_terminal_val_local]
            )

            inst_metrics["xirr_local"] = inst_xirr_local
            inst_metrics["bm_xirr_local"] = inst_bm_xirr_local
            inst_metrics["active_return_local"] = inst_xirr_local - inst_bm_xirr_local
            inst_metrics["fx_xirr_impact"] = inst_xirr - inst_xirr_local

            snapshots = snapshot_generator.generate(
                fifo, m_date, m_price, m_bm_price, inst_metrics, fx_provider=self.fx_provider
            )
            isin_snapshots.extend(snapshots)

        while p_idx < len(p_inst):
            row_dt_obj = to_date_obj(p_inst[p_idx]["Date"])
            if not row_dt_obj:
                p_idx += 1
                continue
            row = p_inst[p_idx]
            qty = float(row["Quantity"])
            b_price = float(row["Price"])
            v_val = row.get("Value")
            buy_val = float(v_val) if v_val is not None else float(qty * b_price)

            bm_p_raw = bm_provider.get_bm_price(row_dt_obj)
            if not bm_p_raw or bm_p_raw <= 0:
                bm_p_raw = float("nan")

            _pl_val = row.get("Price_Local")
            price_local = float(_pl_val) if _pl_val is not None else b_price
            currency_id = (
                row.get("CURRENCY_ID")
                or master_row.get("CURRENCY_ID")
                or getattr(self.rules, "DEFAULT_CURRENCY_ID", "INR_INR")
            )
            fx_rate_buy = (
                self.fx_provider.get_rate(row_dt_obj, currency_id) if self.fx_provider else 1.0
            )
            fx_rate_buy = fx_rate_buy if fx_rate_buy is not None else float("nan")

            # Assume bm_p_raw is in local currency (e.g. USD). Then INR value is bm_p_raw * fx_rate_buy.
            bm_buy_local = float(bm_p_raw)
            bm_buy_inr = float(bm_p_raw * fx_rate_buy)

            shadow_q = buy_val / bm_buy_inr if bm_buy_inr > 0 else 0.0

            purchase_id = row.get("Purchase_ID")

            fifo.buy(
                row_dt_obj,
                qty,
                b_price,
                shadow_q,
                bm_buy_inr,
                price_local=price_local,
                fx_rate_buy=fx_rate_buy,
                currency_id=currency_id,
                bm_buy_local=bm_buy_local,
                purchase_id=purchase_id,
            )
            cf_dates.append(row_dt_obj)
            cf_amounts.append(-buy_val)
            bm_cf_amounts.append(-buy_val)
            buy_val_local = float(qty * price_local)
            bm_cf_amounts_local.append(-buy_val_local)
            isin_cashflows.append(
                CashflowRecord(date=row_dt_obj, amount=-buy_val, amount_local=-buy_val_local)
            )
            p_idx += 1

        while s_idx < len(s_inst):
            row_dt_obj = to_date_obj(s_inst[s_idx]["Date"])
            if not row_dt_obj:
                s_idx += 1
                continue
            row = s_inst[s_idx]
            s_qty = float(row["Quantity"])
            row_p_val = row.get("Price")
            sv_val = row.get("Sell_Value")

            if row_p_val is not None:
                s_price = float(row_p_val)
            elif sv_val is not None and s_qty > 0:
                s_price = float(sv_val) / s_qty
            else:
                s_price = 0.0

            s_val = float(sv_val) if sv_val is not None else float(s_qty * s_price)

            _spl_val = row.get("Sell_Price_Local")
            s_price_local = float(_spl_val) if _spl_val is not None else s_price
            s_val_local = float(s_qty * s_price_local)
            currency_id = (
                row.get("CURRENCY_ID")
                or master_row.get("CURRENCY_ID")
                or getattr(self.rules, "DEFAULT_CURRENCY_ID", "INR_INR")
            )
            fx_rate_sell = (
                self.fx_provider.get_rate(row_dt_obj, currency_id) if self.fx_provider else 1.0
            )
            fx_rate_sell = fx_rate_sell if fx_rate_sell is not None else float("nan")

            cf_dates.append(row_dt_obj)
            cf_amounts.append(s_val)
            isin_cashflows.append(
                CashflowRecord(date=row_dt_obj, amount=s_val, amount_local=s_val_local)
            )

            sale_id = row.get("Sale_ID")

            events = fifo.sell(
                row_dt_obj,
                s_qty,
                s_price,
                price_local=s_price_local,
                fx_rate_sell=fx_rate_sell,
                sale_id=sale_id,
            )

            # Calculate benchmark sell value
            bm_sell_price_local = bm_provider.get_bm_price(row_dt_obj)
            bm_sell_price_local = (
                bm_sell_price_local if bm_sell_price_local is not None else float("nan")
            )
            bm_sell_price_inr = bm_sell_price_local * fx_rate_sell
            shadow_qty_sold = sum(e.get("shadow_qty_sold", 0.0) for e in events)
            bm_cf_amounts.append(shadow_qty_sold * bm_sell_price_inr)
            bm_cf_amounts_local.append(shadow_qty_sold * bm_sell_price_local)

            isin_realized.extend(events)
            s_idx += 1

        schema_overrides = {
            "BM_Buy_Price": pl.Float64,
            "BENCHMARK_ID": pl.String,
            "Buy_Date": pl.Date,
        }
        df = (
            pl.DataFrame(
                [s.model_dump(by_alias=True) for s in isin_snapshots],
                schema_overrides=schema_overrides,
            )
            if isin_snapshots
            else None
        )

        tags = ISINTags(
            **{
                "class": str(master_row.get("INSTRUMENT_CLASS", "Unknown")),
                "subtype": str(master_row.get("INSTRUMENT_SUBTYPE", "Unknown")),
                "instrument_type": str(master_row.get("INSTRUMENT_TYPE", "Unknown")),
                "sector": str(master_row.get("SECTOR", "Unknown")),
                "industry": str(master_row.get("INDUSTRY", "Unknown")),
                "geo": str(master_row.get("GEO", "Unknown")),
                "country": str(master_row.get("COUNTRY", "Unknown")),
                "currency": str(
                    master_row.get("CURRENCY_ID")
                    or getattr(self.rules, "DEFAULT_CURRENCY_ID", "INR_INR")
                ),
            }
        )
        return ISINProcessResult(
            df_snapshots=df,
            cashflows=isin_cashflows,
            terminals=isin_terminals,
            realized_events=isin_realized,
            tags=tags,
        )
