from dataclasses import dataclass

import polars as pl

from personal_finance_etl.backend.config.financial_rules import FinancialRules


@dataclass
class CarryForwardLoss:
    origin_fy: str
    gain_type: str  # "ST" or "LT"
    amount: float  # always negative (a loss)
    expiry_fy: str


@dataclass
class SetOffDetail:
    """Granular set-off breakdown for one FY × gain_type row."""

    FY: str
    Gain_Type: str  # "ST" or "LT"
    # Gross current-year figures (before any set-off)
    Gross_STCG: float
    Gross_STCL: float
    Gross_LTCG: float
    Gross_LTCL: float
    # Brought-forward amounts consumed THIS FY (from carry-forward pool)
    BF_STCL_Used: float
    BF_LTCL_Used: float
    # Intra-year set-offs (current-year losses vs current-year gains)
    CY_STCL_vs_STCG: float  # step 1
    CY_STCL_vs_LTCG: float  # step 2
    CY_LTCL_vs_LTCG: float  # step 3
    # Net after all set-offs
    Net_Taxable_Income: float
    # Amounts carried forward to next year
    Closing_STCL: float
    Closing_LTCL: float


class LossSetOffProcessor:
    """Applies the frozen 4-step capital-loss set-off order and carry-forward.

    Indian Income Tax set-off order (frozen contract):
        Step 1: Current-year STCL → current-year STCG.
        Step 2: Remaining current-year STCL → current-year LTCG.
        Step 3: Current-year LTCL → remaining current-year LTCG.
        Step 4: LTCL CANNOT offset STCG (no action).

    Brought-forward losses (from prior years) are applied AFTER current-year
    intra-year netting, in the same ST/LT order.
    """

    def __init__(self, lf_events: pl.LazyFrame, rules: FinancialRules | None):
        self.lf_events = lf_events
        self.rules = rules

    # Helpers

    def _get_fy_start_year(self, fy_str: str) -> int:
        """Parse a FY string like '2023-24' and return the start calendar year (2023).

        Returns 9999 for empty or malformed strings so that invalid FYs sort
        last rather than raising during chronological ordering.
        """
        if not fy_str:
            return 9999
        try:
            return int(fy_str.split("-")[0])
        except Exception:
            return 9999

    def _get_expiry_fy(self, fy_str: str, years_forward: int = 8) -> str:
        """Compute the FY string *years_forward* years after *fy_str*.

        Indian tax law allows capital losses to be carried forward for up to
        8 assessment years.  The default ``years_forward=8`` encodes this
        statutory limit.

        Example: '2023-24' + 8 → '2031-32'.
        """
        start = self._get_fy_start_year(fy_str)
        if start == 9999:
            return "9999-00"
        end_start = start + years_forward
        return f"{end_start}-{str(end_start + 1)[-2:]}"

    # Core processing

    def process(self) -> pl.LazyFrame:
        """Apply intra-year and inter-year set-offs. Returns a LazyFrame with
        one row per FY × Gain_Type (ST/LT) for capital gains, plus ordinary
        income rows passed through unchanged.
        """
        schema = {
            "FY": pl.Utf8,
            "Income_Head": pl.Utf8,
            "Tax_Method": pl.Utf8,
            "Gain_Type": pl.Utf8,
            "Net_Taxable_Income": pl.Float64,
            "Set_Off_Amount": pl.Float64,
            "Carried_Forward_Loss": pl.Float64,
            # Granular breakdown required by f_Tax_FY_State contract
            "STCL_Used_Against_STCG": pl.Float64,
            "STCL_Used_Against_LTCG": pl.Float64,
            "LTCL_Used_Against_LTCG": pl.Float64,
            "Brought_Forward_STCL": pl.Float64,
            "Brought_Forward_LTCL": pl.Float64,
        }

        def _eager_process(df_events: pl.DataFrame) -> pl.DataFrame:
            if df_events.is_empty():
                return pl.DataFrame(schema=schema)

            # Split ordinary income (pass-through) vs capital gains.
            # Exclude CHECK_REQUIRED events from the CG set-off pool: their
            # Realized_Gain_Loss is derived from a synthetic RECONCILIATION lot
            # whose cost basis is unknown.  Including them would distort the
            # set-off math with unreliable figures.  They remain in the gold
            # reconciliation table for human review and resolution.
            df_cg = df_events.filter(
                (pl.col("Tax_Method") == "capital_gains")
                & (pl.col("Tax_Sub_Head") != "CHECK_REQUIRED")
            )
            df_ordinary = df_events.filter(pl.col("Tax_Method") != "capital_gains")

            df_ord_results = pl.DataFrame()
            if not df_ordinary.is_empty():
                df_ord_results = (
                    df_ordinary.group_by(["FY", "Income_Head", "Tax_Method"])
                    .agg([pl.col("Taxable_Amount").sum().alias("Net_Taxable_Income")])
                    .with_columns(
                        pl.lit(None).cast(pl.Utf8).alias("Gain_Type"),
                        pl.lit(0.0).alias("Set_Off_Amount"),
                        pl.lit(0.0).alias("Carried_Forward_Loss"),
                        pl.lit(0.0).alias("STCL_Used_Against_STCG"),
                        pl.lit(0.0).alias("STCL_Used_Against_LTCG"),
                        pl.lit(0.0).alias("LTCL_Used_Against_LTCG"),
                        pl.lit(0.0).alias("Brought_Forward_STCL"),
                        pl.lit(0.0).alias("Brought_Forward_LTCL"),
                    )
                    .select(list(schema.keys()))
                )

            if df_cg.is_empty():
                return df_ord_results

            # Aggregate raw CG per FY and Gain_Type into signed amounts
            # Positive = gain, negative = loss (using Realized_Gain_Loss)
            df_cg_agg = (
                df_cg.group_by(["FY", "Gain_Type"])
                .agg([pl.col("Realized_Gain_Loss").sum().alias("Net_Gain_Loss")])
                .sort("FY")
            )

            # Build per-FY dict: {fy: {"ST": signed_float, "LT": signed_float}}
            cg_dict: dict[str, dict[str, float]] = {}
            for row in df_cg_agg.iter_rows(named=True):
                fy = str(row["FY"])
                gt = str(row["Gain_Type"])
                val = float(row["Net_Gain_Loss"] or 0.0)
                if fy not in cg_dict:
                    cg_dict[fy] = {"ST": 0.0, "LT": 0.0}
                if gt in ("ST", "LT"):
                    cg_dict[fy][gt] += val

            fys = sorted(cg_dict.keys(), key=self._get_fy_start_year)

            # Carry-forward pool: accumulated losses from prior years
            carry_forward_pool: list[CarryForwardLoss] = []

            results: list[dict[str, object]] = []

            for fy in fys:
                raw_st = cg_dict[fy]["ST"]  # signed: positive=STCG, negative=STCL
                raw_lt = cg_dict[fy]["LT"]  # signed: positive=LTCG, negative=LTCL

                # Decompose into gains and losses (always non-negative).
                cy_stcg = max(0.0, raw_st)
                cy_stcl = abs(min(0.0, raw_st))
                cy_ltcg = max(0.0, raw_lt)
                cy_ltcl = abs(min(0.0, raw_lt))

                # --- Intra-year set-offs (current FY, frozen 4-step order) ---

                # Step 1: current STCL → current STCG
                step1 = min(cy_stcl, cy_stcg)
                cy_stcg -= step1
                cy_stcl -= step1

                # Step 2: remaining current STCL → current LTCG
                step2 = min(cy_stcl, cy_ltcg)
                cy_ltcg -= step2
                cy_stcl -= step2

                # Step 3: current LTCL → remaining current LTCG
                step3 = min(cy_ltcl, cy_ltcg)
                cy_ltcg -= step3
                cy_ltcl -= step3

                # Step 4: LTCL CANNOT offset STCG (no action needed)

                # --- Inter-year set-offs (brought-forward from prior years) ---
                # Expire losses whose 8-year window has passed
                carry_forward_pool = [
                    cf
                    for cf in carry_forward_pool
                    if self._get_fy_start_year(cf.expiry_fy) >= self._get_fy_start_year(fy)
                ]

                # Track how much BF was consumed
                bf_stcl_used = 0.0
                bf_ltcl_used = 0.0

                # BF-STCL → net STCG
                for cf in carry_forward_pool:
                    if cy_stcg <= 0:
                        break
                    if cf.gain_type == "ST" and cf.amount < 0:
                        avail = -cf.amount
                        use = min(cy_stcg, avail)
                        cy_stcg -= use
                        cf.amount += use
                        bf_stcl_used += use

                # BF-STCL → net LTCG
                for cf in carry_forward_pool:
                    if cy_ltcg <= 0:
                        break
                    if cf.gain_type == "ST" and cf.amount < 0:
                        avail = -cf.amount
                        use = min(cy_ltcg, avail)
                        cy_ltcg -= use
                        cf.amount += use
                        bf_stcl_used += use

                # BF-LTCL → net LTCG
                for cf in carry_forward_pool:
                    if cy_ltcg <= 0:
                        break
                    if cf.gain_type == "LT" and cf.amount < 0:
                        avail = -cf.amount
                        use = min(cy_ltcg, avail)
                        cy_ltcg -= use
                        cf.amount += use
                        bf_ltcl_used += use

                # --- Carry remaining current-year losses forward ---
                bf_stcl_opening = sum(
                    -cf.amount
                    for cf in carry_forward_pool
                    if cf.gain_type == "ST" and cf.amount < 0
                )
                bf_ltcl_opening = sum(
                    -cf.amount
                    for cf in carry_forward_pool
                    if cf.gain_type == "LT" and cf.amount < 0
                )

                closing_stcl = 0.0
                if cy_stcl > 0:
                    carry_forward_pool.append(
                        CarryForwardLoss(
                            origin_fy=fy,
                            gain_type="ST",
                            amount=-cy_stcl,
                            expiry_fy=self._get_expiry_fy(fy),
                        )
                    )
                    closing_stcl = cy_stcl

                closing_ltcl = 0.0
                if cy_ltcl > 0:
                    carry_forward_pool.append(
                        CarryForwardLoss(
                            origin_fy=fy,
                            gain_type="LT",
                            amount=-cy_ltcl,
                            expiry_fy=self._get_expiry_fy(fy),
                        )
                    )
                    closing_ltcl = cy_ltcl

                total_st_setoff = step1 + step2 + bf_stcl_used
                total_lt_setoff = step3 + bf_ltcl_used

                results.append(
                    {
                        "FY": fy,
                        "Income_Head": "Capital_Gains",
                        "Tax_Method": "capital_gains",
                        "Gain_Type": "ST",
                        "Net_Taxable_Income": cy_stcg,
                        "Set_Off_Amount": total_st_setoff,
                        "Carried_Forward_Loss": -closing_stcl,
                        "STCL_Used_Against_STCG": step1,
                        "STCL_Used_Against_LTCG": step2,
                        "LTCL_Used_Against_LTCG": 0.0,
                        "Brought_Forward_STCL": bf_stcl_opening,
                        "Brought_Forward_LTCL": 0.0,
                    }
                )

                results.append(
                    {
                        "FY": fy,
                        "Income_Head": "Capital_Gains",
                        "Tax_Method": "capital_gains",
                        "Gain_Type": "LT",
                        "Net_Taxable_Income": cy_ltcg,
                        "Set_Off_Amount": total_lt_setoff,
                        "Carried_Forward_Loss": -closing_ltcl,
                        "STCL_Used_Against_STCG": 0.0,
                        "STCL_Used_Against_LTCG": 0.0,
                        "LTCL_Used_Against_LTCG": step3,
                        "Brought_Forward_STCL": 0.0,
                        "Brought_Forward_LTCL": bf_ltcl_opening,
                    }
                )

            df_cg_results = pl.DataFrame(results, schema=schema)

            if df_ord_results.is_empty():
                return df_cg_results
            return pl.concat([df_cg_results, df_ord_results], how="diagonal_relaxed")

        # Collect eagerly — the stateful carry-forward loop cannot be vectorised inside
        # map_batches (which may be called per batch, losing inter-FY state). Collect once,
        # process in Python, then re-lazify the typed result.
        df_events = self.lf_events.collect()
        result_df = _eager_process(df_events)
        return result_df.lazy()
