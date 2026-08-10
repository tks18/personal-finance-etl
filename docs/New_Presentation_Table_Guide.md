# Senior Engineer's Guide: Creating Gold Presentation Tables

Welcome to the presentation layer handover. The Gold layer in our Medallion architecture represents highly aggregated, BI-ready tables (dashboards, PowerBI, Tableau). 

At this stage, all data is strictly typed and clean (originating from Silver). We use the **Builder Pattern** for all presentation logic, relying exclusively on `Polars` for vectorized aggregations. 

Follow this guide to systematically construct, register, and persist a new Gold table.

---

## Step 1: Architect the Gold DDL (`src/load/schema/gold.py`)
Every Gold table must be pre-defined via DDL. We do not infer schemas here because BI tools rely on stable, predictable column types.

**Rules:**
- Prefix tables with `p_` (presentation).
- Use standard types (`DOUBLE` for floats, `BIGINT` for integers, `DATE`, `TEXT`, `BOOLEAN`).
- No Foreign Keys are strictly required in Gold (as it is flattened for BI), but keep identifiers clean.

```sql
CREATE TABLE IF NOT EXISTS gold.p_Advanced_Cohort_Analysis (
    -- Identifiers
    MONTH_START_DATE DATE,
    YEAR_MONTH TEXT,
    -- Cohort Metrics
    Cohort_Size BIGINT,
    Average_Tenure_Days DOUBLE,
    -- Financials
    Cumulative_Spend DOUBLE,
    "Spend_YoY_Growth_%" DOUBLE,  -- Note the quotes for special characters
    -- Flags
    Is_High_Value_Cohort BOOLEAN
);
```

---

## Step 2: Implement the Builder (`src/engines/presentation/modules/`)
Create a new file (e.g., `src/engines/presentation/modules/cohort_analysis.py`).

**Understanding the Inputs:**
- `dfs`: A dictionary containing all Silver `LazyFrame` and `DataFrame` objects.
- `base_lf`: A dictionary of *core* Gold tables that have already been computed (e.g., Inflation, Net Worth, Ledger). Always reuse these rather than recalculating base metrics!
- `rules`: The Pydantic `FinancialRules` config.

**Builder Contract:**
1. You must implement a `.build() -> pl.LazyFrame | None` method.
2. Return `None` gracefully if required upstream data is missing.
3. Keep execution in `LazyFrame` mode as long as possible. The master engine handles `.collect()` parallelization.

```python
import polars as pl

class CohortAnalysisBuilder:
    def __init__(self, dfs: dict[str, pl.DataFrame | pl.LazyFrame], base_lf: dict[str, pl.LazyFrame], rules):
        self.dfs = dfs
        self.base_lf = base_lf
        self.rules = rules

    def build(self) -> pl.LazyFrame | None:
        # 1. Fetch dependencies (Silver facts/dims)
        lf_txns = self.dfs.get("df_f_expense_transactions")
        
        # Or fetch core base metrics calculated earlier in the DAG
        lf_inflation = self.base_lf.get("lf_inflation_factors")
        
        if lf_txns is None or lf_inflation is None:
            return None
            
        # 2. Polars Vectorized Logic
        lf_cohort = (
            lf_txns
            .group_by(["MONTH_START_DATE", "YEAR_MONTH"])
            .agg([
                pl.col("UID").count().alias("Cohort_Size"),
                pl.col("BASE_AMOUNT").sum().alias("Cumulative_Spend")
            ])
            .with_columns([
                (pl.col("Cumulative_Spend") > 10000).alias("Is_High_Value_Cohort")
            ])
        )
        
        return lf_cohort
```

---

## Step 3: Integrate into the Presentation DAG (`src/engines/presentation/wealth_engine.py`)
The `WealthPresentationEngine` acts as the orchestrator for all presentation builders. It controls the dependency graph (what gets built first).

1. **Import your new builder at the top.**
```python
from src.engines.presentation.modules.cohort_analysis import CohortAnalysisBuilder
```

2. **Execute it in the `run()` method.**
Be mindful of where you place it. If it doesn't depend on other modules, it can go anywhere. If it depends on `lf_risk`, place it after `RiskMetricsBuilder`.

Map the result to a unique `df_p_...` key in the `results` dictionary.

```python
    def run(self, dfs: Mapping[str, pl.DataFrame | pl.LazyFrame]) -> dict[str, pl.LazyFrame]:
        # ... Base metrics (Inflation, Ledger, NW) are built here ...
        # ... results dictionary initialized ...

        # -> Your Module Addition <-
        results["df_p_tf_cohort_analysis"] = CohortAnalysisBuilder(
            dfs, base_lf, rules=self.rules
        ).build()
        
        # The engine will automatically replace NaNs with True Nulls before returning!
        return {
            key: lf.with_columns(cs.float().fill_nan(None))
            for key, lf in results.items()
            if lf is not None
        }
```

---

## Step 4: Map to DuckDB (`src/load/gold.py`)
The final step is telling the `GoldLayer` how to map your Python dictionary key to the DuckDB schema you created in Step 1.

Update the `table_mappings` in `GoldLayer.load`:
```python
    def load(self, dfs: dict[str, pl.DataFrame]) -> None:
        table_mappings = {
            # ... existing mappings
            "df_p_tf_cohort_analysis": "gold.p_Advanced_Cohort_Analysis",
        }
        
        # Phase 1: Wipes schema
        # Phase 2: Inserts all data based on this mapping dictionary
```

### Summary of Execution Flow
1. The orchestrator calls `WealthPresentationEngine.run()`.
2. Your builder (`CohortAnalysisBuilder`) lazily computes the aggregations.
3. The engine replaces mathematical `NaN` values with `None` (DuckDB requires this for PowerBI/BI tool compatibility).
4. `ETLOrchestrator` uses `pl.collect_all(..., engine="streaming")` to run your builder and all others *in parallel*.
5. `GoldLayer` truncates the old schema and inserts the fresh `pl.DataFrame` directly into DuckDB. 

This architecture guarantees peak performance, zero stale data, and strict ACID compliance on failure.
