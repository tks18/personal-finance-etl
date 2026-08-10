# Senior Engineer's Guide: Adding a New Data Source to the Medallion Pipeline

Welcome to the data ingestion handover. This document is a comprehensive, step-by-step guide on how to integrate a brand-new raw data source into our Medallion (Bronze -> Silver -> Gold) architecture. 

Our pipeline is strict: it uses `DuckDB` for state management and ACID transactions, `Polars` (specifically LazyFrames where possible) for high-performance memory execution, and `Pydantic` for configuration validation. 

If you are adding a new source (e.g., a new CSV dump from a bank or broker), follow these steps meticulously to ensure file-tracking, delta-loads, and foreign key constraints remain intact.

---

## Step 1: Update Application Configuration (`src/config/settings.py`)
Every external dependency must be strictly typed and validated before the pipeline boots. We use Pydantic `BaseModel` for this.

1. **Add the field to `Settings`:**
```python
class Settings(BaseModel):
    # ... existing configs
    NEW_BANK_STATEMENT_CSV_PATH: str = ""
```

2. **Add validation:**
To prevent the pipeline from crashing mid-execution, ensure the file is validated on startup in the `validate_config` method.
```python
    def validate_config(self) -> None:
        # ...
        required_files = [
            ("COLUMN_MASTER_PATH", self.COLUMN_MASTER_PATH),
            # Add your new source here
            ("NEW_BANK_STATEMENT_CSV_PATH", self.NEW_BANK_STATEMENT_CSV_PATH),
        ]
```

---

## Step 2: Update the Global Data Model (`src/utils/models.py`)
The pipeline passes a single `ExtractionResult` object containing `LazyFrame` representations of all raw files to the Bronze layer.

Add your new source as an attribute:
```python
@dataclass
class ExtractionResult:
    # ... existing fields
    raw_new_bank_statement: pl.LazyFrame
```

---

## Step 3: Implement the Extractor (`src/extract/`)
Create a new extractor (e.g., `src/extract/new_bank_extractor.py`) or use the existing `csv_extractor.py`.
The goal of an extractor is purely to read the file into Polars, append tracking metadata `__file_name__` and `__folder_path__`, and return a `LazyFrame`. 

*No business logic or renaming should happen here.*

**Important Extractor Rule:** 
You *must* append `__file_name__` to your dataframe. The Bronze layer uses this column to delta-delete old rows when a file is modified.
```python
import polars as pl
import os

class NewBankExtractor:
    def extract(self, file_path: str) -> pl.LazyFrame:
        return (
            pl.scan_csv(file_path)
            .with_columns([
                pl.lit(os.path.basename(file_path)).alias("__file_name__"),
                pl.lit(os.path.dirname(file_path)).alias("__folder_path__")
            ])
        )
```

In `src/pipeline/core/extractor.py` (or wherever your `_extract` logic lives), execute this extractor and map it to `ExtractionResult`.

---

## Step 4: Map to the Bronze Lakehouse (`src/load/bronze.py`)
The Bronze layer stores the raw data inside DuckDB exactly as it came from the source. **We do not write DDL for Bronze.** It dynamically infers the schema via `CREATE TABLE AS SELECT`.

1. **Update `table_mappings` in `BronzeLayer.load`:**
The mapping format is: `(ExtractionResult_Attribute, FileTracker_Category, DuckDB_Table_Name, Is_Full_Replace)`

- Set `Is_Full_Replace` to `False` if this is an append-only transaction log (like orders).
- Set it to `True` if this is a master snapshot (like a current balances file).

```python
        table_mappings = [
            # ...
            ("raw_new_bank_statement", "new_bank_category", "bronze.r_New_Bank_Statement", True),
        ]
```

2. **Retrieve it in `get_full_dataset`:**
When the transform phase starts, it requests the full merged dataset from DuckDB.
```python
    def get_full_dataset(self, original_mappings: dict) -> ExtractionResult:
        # ...
        return ExtractionResult(
            # ...
            raw_new_bank_statement=_get_lf("bronze.r_New_Bank_Statement"),
        )
```

---

## Step 5: Define the Curated Silver Schema (`src/load/schema/silver.py`)
Unlike Bronze, the Silver layer requires strict typing and schema enforcement.
Write the DDL in `SILVER_DDL`. 

**Critical Senior Eng Note:** Pay close attention to Foreign Keys! If your table relies on `d_Calendar` or `d_Currency`, enforce it.
```sql
CREATE TABLE IF NOT EXISTS silver.f_New_Bank_Transactions (
    __file_name__ TEXT,
    __folder_path__ TEXT,
    TXN_ID TEXT PRIMARY KEY,
    Date DATE NOT NULL,
    Amount DOUBLE,
    Currency_ID TEXT,
    FOREIGN KEY(Date) REFERENCES silver.d_Calendar(Date),
    FOREIGN KEY(Currency_ID) REFERENCES silver.d_Currency(UID)
);
```

---

## Step 6: Create the Transformer (`src/transform/`)
This is where business logic, casting, and renaming happen. Create a file (e.g., `src/transform/new_bank.py`).

1. The transformer must take the raw Bronze `LazyFrame`.
2. It must cast data types to exactly match the Silver DDL.
3. It should return a fully collected `pl.DataFrame` (or `LazyFrame` if your orchestrator handles the collection).

```python
import polars as pl
import polars.selectors as cs

class NewBankTransformer:
    def __init__(self, raw_lf: pl.LazyFrame):
        self.raw_lf = raw_lf
        
    def transform(self) -> pl.DataFrame:
        return (
            self.raw_lf
            .rename({
                "TxnDate": "Date",
                "Value": "Amount",
                "Curr": "Currency_ID"
            })
            .with_columns([
                pl.col("Date").str.strptime(pl.Date, "%Y-%m-%d"),
                pl.col("Amount").cast(pl.Float64)
            ])
            .collect()
        )
```

**Wire it into `src/pipeline/etl_pipeline.py` (or `src/pipeline/core/transformer.py`):**
```python
# Inside TransformationDAG.run() or ETLOrchestrator._transform()
dfs["df_f_new_bank_transactions"] = NewBankTransformer(extracted_data.raw_new_bank_statement).transform()
```

---

## Step 7: Load into Silver Layer (`src/load/silver.py`)
Finally, map the transformed dataframe to the DuckDB Silver schema.

Update `table_mappings` in `SilverLayer.load`:
```python
        table_mappings = {
            # ... Ensure dimensions (d_) are loaded BEFORE facts (f_) to avoid FK violations!
            "df_f_new_bank_transactions": "silver.f_New_Bank_Transactions",
        }
```

### Summary
By following these 7 steps, you ensure the new data source is automatically tracked for file changes (hashing/modified dates), raw data is preserved in Bronze, strictly typed in Silver, and gracefully rolled back if any Python/SQL exceptions occur during the ACID transaction block in `ETLOrchestrator`.
