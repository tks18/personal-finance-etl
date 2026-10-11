<img
  src="https://raw.githubusercontent.com/tks18/personal-finance-etl/master/logo.png"
  alt="Personal Finance ETL"
  width="160"
/>

# Personal Finance ETL

**A local-first financial data engineering, accounting, BI, and quantitative decision-support platform.**

I built Personal Finance ETL to turn fragmented financial evidence into one reconciled, tax-aware, decision-ready financial state.

It powers my daily financial workflow and month-end close: investment accounting, portfolio analysis, cash-flow reconciliation, wealth tracking, tax estimates, and FIRE modelling through one connected data lineage.

[![PyPI](https://img.shields.io/pypi/v/personal-finance-etl?label=PyPI)](https://pypi.org/project/personal-finance-etl/)
![Python](https://img.shields.io/badge/Python-3.13%2B-3776AB?logo=python&logoColor=white)
![Local First](https://img.shields.io/badge/Architecture-Local--First-2F855A)
![Typed](https://img.shields.io/badge/Typing-mypy%20%2B%20Pyright-4B5563)

**Explore:** [Architecture](#the-system) · [Financial engines](#6--fifo-tax-lot-accounting) · [Performance](#19--performance) · [11-domain technical docs](#explore-the-11-domain-technical-universe) · [Wiki](https://github.com/tks18/personal-finance-etl/wiki)

---

## The system

```mermaid
flowchart TB
    SRC["Financial Sources<br/>Bank · Broker · Excel · CSV · SQLite · Market Data"]
    CP["SQLite Control Plane<br/>Artifacts · Payloads · Sync State<br/>Runs · Failures · Logs · Config Provenance"]
    BR["DuckDB Bronze<br/>20 Source Contracts · Persistent State"]
    CAN["Canonical Financial Model<br/>Polars Lazy DAG · FinancialRules"]
    IQ["Investment Quant Engine<br/>FIFO · Broker Reconciliation · Shadow Benchmark<br/>Tax State · XIRR · Drawdown"]
    TAX["Tax Engine<br/>Classifications · Tax Events · Evidence Quality"]
    WA["Wealth Presentation Engine<br/>Ledger · Cash Flow · Net Worth<br/>Budget · FIRE · Monte Carlo"]
    SG["DuckDB Silver + Gold<br/>24 Silver Contracts · 22 Gold Marts"]
    META["Lean DuckDB Meta<br/>Current Projection · Data Contracts"]
    APP["Power BI · CLI · Desktop"]

    SRC --> CP
    CP --> BR
    BR --> CAN
    CAN --> IQ
    CAN --> WA
    IQ --> TAX
    TAX --> WA
    IQ --> WA
    IQ --> SG
    TAX --> SG
    WA --> SG
    CP -. current-state mirror .-> META
    SG --> APP
    META --> APP
```

The architecture is deliberately split into two planes:

> **SQLite owns operational truth and raw evidence. DuckDB owns analytical state.**

That boundary is the spine of the current system.

---

## What this project actually combines

This repository is one production system, but its implementation crosses several engineering disciplines.

| Plane | Production evidence |
| --- | --- |
| **Data Engineering** | Content-addressed raw artifacts, change-aware ingestion, persistent Bronze, deterministic Silver/Gold rebuilds, contract-driven publication |
| **Python Engineering** | Pydantic models, repositories, facades, protocols, process isolation, multiprocessing, strict typing |
| **Software Architecture** | Authoritative Control Plane, analytical plane separation, explicit contracts, strategy seams, transactional orchestration |
| **BI Engineering** | Canonical semantics, explicit grain, Silver facts/dimensions, Gold decision marts, Power BI serving |
| **Finance** | Household ledger, transfers, cash/non-cash semantics, FIFO tax lots, holding periods, tax-aware wealth |
| **Investment Analytics** | Broker reconciliation, shadow benchmarks, XIRR, after-tax XIRR, active return, drawdown |
| **Quantitative Engineering** | Numba Monte Carlo, market regimes, fat tails, jumps, stochastic inflation, human-capital shocks |
| **Reliability** | Run lifecycle, stale-run recovery, replay/self-healing, failure persistence, coordinated Snapshot/Restore |
| **Observability** | Run-scoped logs, stage/ISIN/process context, worker tracing, structured failures, compressed execution history |
| **Product Engineering** | Backend facade, Rich CLI, desktop GUI, packaged offline documentation, manifest-driven docs runtime |

The implementation is the evidence; the rest of this README shows where those disciplines meet in production.

---

## Why I built it

The original question was simple:

> **Where exactly do I stand financially?**

Answering it properly was not.

A bank transaction is not useful merely because it has a date and amount. An investment balance is not economically complete without market value and tax state. A portfolio return is not meaningful if irregular cash flows are aggregated incorrectly. A cash-flow dashboard is not trustworthy if it cannot explain actual movement in cash accounts.

The problem gradually became:

```text
What happened?
      ↓
What does it mean financially?
      ↓
Can I reconcile it?
      ↓
What is the current economic state?
      ↓
What decisions does that state support?
```

That is why this repository grew from an ETL workflow into a financial platform.

### The production workload

The architecture is not built around a toy folder containing a handful of sample statements.

My earlier **24 September 2026** snapshot contained **1,608 source artifacts**. My more recent operating workload contains **1,629 artifacts**; both numbers describe actual points in the project’s evolution.

The source population includes:

- daily broker snapshots for **stocks**,
- daily broker snapshots for **mutual funds**,
- historical transaction and market files,
- financial/reference masters,
- mappings and opening-state inputs,
- my personal finance SQLite database,
- and other source/reference artifacts required to reconstruct the financial model.

The broker snapshot population alone grows by approximately **two files per day**:

```text
1 stock snapshot
+
1 mutual-fund snapshot
        ↓
~2 additional source artifacts / day
```

So the ingestion problem is continuously growing even when the financial model itself does not change.

```mermaid
flowchart LR
    HIST["Existing Source History<br/>1,608 artifacts<br/>24 Sep 2026"] --> DISC["Discovery"]
    DAILY["Daily Broker Growth<br/>+ stock snapshot<br/>+ mutual-fund snapshot"] --> DISC
    DISC --> HASH["Identity + Hash Policy"]
    HASH --> CP["SQLite Control Plane"]
    CP --> ACT{"Changed?"}
    ACT -->|"No"| SKIP["Reuse Existing Bronze State"]
    ACT -->|"New / Changed"| BR["Synchronize Affected Bronze Partition"]
    SKIP --> FULL["Complete Bronze State"]
    BR --> FULL
    FULL --> REBUILD["Deterministic Silver / Gold Rebuild"]
```

That workload is one reason the architecture distinguishes:

```text
discover everything
        ≠
reprocess everything
```

The Control Plane, content hashing, synchronization state, persistent Bronze, and file-aware upserts exist because repeatedly reparsing an ever-growing source history would be wasteful and operationally opaque.

At the same time, Silver and Gold remain deterministically rebuildable from complete Bronze state, which keeps downstream correctness simpler than trying to incrementally patch every analytical dependency.

The scale therefore shaped the architecture:

> **Incrementalize expensive source synchronization. Rebuild derived financial truth from a complete canonical state.**

The figures above describe my production environment at that date, not a benchmark dataset bundled with the repository.

---

## The architecture at a glance

I intentionally chose a two-database, multi-engine architecture for a single-user product. The unusual part is not the database count; it is the separation of **evidence, computation, and decision surfaces**.

```mermaid
flowchart LR
    subgraph Evidence["Evidence and operational authority"]
        F["Financial files and databases"] --> CP["SQLite Control Plane"]
        CP --> B["Persistent DuckDB Bronze"]
    end
    subgraph Compute["Canonical computation"]
        B --> P["Polars transformation DAG"]
        P --> I["Investment Quant"]
        I --> T["Tax Engine"]
        T --> W["Wealth / FIRE"]
    end
    subgraph Serve["Contracted serving"]
        I --> S["Silver + Gold"]
        T --> S
        W --> S
        S --> BI["Power BI and local consumers"]
    end
```

### Different kinds of state, different owners

```mermaid
classDiagram
    class SQLiteControlPlane {
      +artifact identities
      +retained payloads
      +run history
      +configuration provenance
    }
    class DuckDBWarehouse {
      +Bronze source state
      +Silver canonical state
      +Gold decision marts
      +Meta projections
    }
    class PersonalFinanceEngine {
      +run pipeline
      +backup / restore
    }
    PersonalFinanceEngine --> SQLiteControlPlane
    PersonalFinanceEngine --> DuckDBWarehouse
```

These diagrams are architectural views, not claims of distributed atomicity. The cross-database commit boundary and healing strategy are described in [Transaction Boundaries](docs/operations/transaction-boundaries.md).

---

## 1 · The Control Plane

The most important production-hardening change was moving operational authority into SQLite.

The facade is intentionally small:

```python
class ControlPlane:
    """Authoritative orchestrator for ETL Control Plane operations."""

    def __init__(self, base_path: str, db_name: str = "Raw_Documents.sqlite"):
        self.db = SQLiteManager(base_path, db_name)
        self.artifacts = ArtifactRepository(self.db)
        self.runs = RunRepository(self.db)
        self.file_sync = FileSyncService(self.artifacts)

    def begin_transaction(self) -> None:
        self.db.begin_transaction()

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
```

The important part is the ownership model:

```text
ControlPlane
├── ArtifactRepository
│   └── artifact identity · hashes · payloads · sync state
├── RunRepository
│   └── lifecycle · config snapshots · failures · execution logs
└── FileSyncService
    └── discovery reconciliation · change detection
```

The ETL orchestrator consumes those responsibilities rather than manipulating SQLite control tables directly.

With more than sixteen hundred artifacts in the current production source population and new broker evidence arriving daily, that boundary gives ingestion a durable memory of **what exists, what changed, what has already reached Bronze, and which run acted on it**.

### Run lifecycle

A run is created before analytical work begins:

```python
run_id = cp.runs.start_run(
    cfg_json=self.cfg.model_dump_json(),
    rules_json=self.rules.model_dump_json() if self.rules else None,
)

self.db_manager.conn.execute("BEGIN TRANSACTION")
cp.begin_transaction()

cp.runs.update_run_status(run_id, "RUNNING")
```

Successful publication moves through an explicit commit state:

```python
cp.runs.update_run_status(run_id, "COMMITTING")

self.db_manager.conn.execute("COMMIT")
cp.commit()

cp.runs.finish_run(run_id, "SUCCESS")
```

Failures are rolled back and then persisted as operational history.

The Control Plane retains:

- artifact identity and payload state,
- file synchronization state,
- content-hashed Settings snapshots,
- content-hashed FinancialRules snapshots,
- run lifecycle,
- failures,
- tracebacks,
- and complete execution logs.

DuckDB no longer competes with SQLite for ownership of historical run truth.

---

## 2 · Raw evidence before derived state

Source artifacts are registered and persisted before they become analytical data.

```mermaid
flowchart LR
    DISC["Discover"] --> HASH["Identify / Hash"]
    HASH --> RAW["Persist Raw Artifact"]
    RAW --> PEND["PENDING_BRONZE"]
    PEND --> EXT["Extract from Persisted Evidence"]
    EXT --> BR["Bronze"]
    BR --> SYNC["SYNCED"]
```

The pipeline can therefore scan the full source population while making only the new or changed subset actionable:

```python
new_files, changed_files, _ = cp.file_sync.sync_with_disk(
    discovered_files,
    self.cfg.FILE_HASH_POLICY,
    full_replace_categories,
)

actionable_all = {
    category: new_files.get(category, []) + changed_files.get(category, [])
    for category in discovered_files
}
```

That makes ingestion stateful without making downstream analytics incrementally fragile.

### Bronze uses source semantics

Reference/current-state sources can be fully replaced.

Historical/event sources use file-aware replacement so one changed source does not destroy unrelated history.

Then the complete Bronze state is read for deterministic downstream reconstruction.

That combination gives the system:

```text
incremental source synchronization
             +
deterministic analytical reconstruction
```

rather than forcing one persistence strategy onto every layer.

---

## 3 · Polars as the canonical compute plane

After Bronze synchronization, the complete analytical state enters a Polars transformation DAG.

```text
Source-shaped Bronze
        ↓
Lazy transformations
        ↓
Canonical household contracts
        +
Canonical investment contracts
        +
Benchmark / macro contracts
```

The pipeline keeps lazy frames composable until collection is meaningful, and independent presentation nodes can be collected together:

```python
results = pl.collect_all(
    lazy_frames,
    engine="streaming",
)
```

This is where source vocabulary stops being the downstream interface.

Bank, broker, Excel, CSV, and reference-specific structure is converted into financial concepts such as:

```text
Income
Expense
Transfer
Opening Balance
Investment Master
Purchase
Sale
Market Observation
Benchmark Observation
```

The analytical engines consume those concepts, not source worksheets.

---

## 4 · Explicit analytical contracts

Silver and Gold publication is driven by a lightweight contract registry.

```python
@dataclass
class DataContract:
    contract_id: str
    layer: str
    physical_table: str
    domain: str
    grain: str
    producer: str
    publication_order: int
```

A Gold contract is explicit about both physical destination and analytical meaning:

```python
DataContract(
    "df_f_investment_analytics_isin",
    "gold",
    "gold.Investment_By_ISIN",
    "Investments",
    "Date-ISIN",
    "InvestmentQuantEngine",
    200,
)
```

Publication consumes those contracts in declared order:

```python
contracts = sorted(
    (c for c in DATA_CONTRACT_REGISTRY if c.layer == "gold"),
    key=lambda c: c.publication_order,
)

for contract in contracts:
    if contract.contract_id in dfs:
        self._write(
            dfs[contract.contract_id],
            contract.physical_table,
        )
```

This removes table/layer inference from the publication path.

The contract itself states:

```text
What is this dataset?
Where does it live?
What domain owns it?
What does one row mean?
Who produces it?
When is it published?
```

The registry makes analytical identity inspectable before a frame ever reaches DuckDB.

---

## 5 · Bronze, Silver, and Gold contracts

The warehouse is Medallion-inspired, but each layer has a precise contract boundary.

The current analytical surface is:

```text
20 Bronze contracts
24 Silver contracts
22 Gold marts
```

Bronze is no longer an implicit staging area. Its registry declares source category, physical table, and replacement semantics before canonical reconstruction begins.

```mermaid
flowchart LR
    RAW["SQLite<br/>Evidence + Control"] --> BR["Bronze<br/>Source-Shaped State"]
    BR --> SIL["Silver<br/>Canonical Financial State"]
    SIL --> GOLD["Gold<br/>Decision-Support Marts"]
    CP["Control Plane"] -. latest-run projection .-> META["DuckDB Meta"]
```

### Silver

The current architecture publishes **24 canonical Silver contracts**:

```text
24 registered canonical datasets
(dimension, reference, and fact grains)
```

Silver includes canonical household activity, investment transactions, market/reference state, and deep lot-level investment analytics.

### Gold

The contract registry declares **22 Gold marts** across:

Gold is intentionally multi-grain. The authoritative inventory of all 22 outputs, including their declared grains and physical schemas, lives in [Gold Data Contracts](docs/reference/gold-data-contracts.md).

```text
Month
Month × Asset
Month × Expense Category
Month × Income Category
Month × ISIN
Date × ISIN
Date × Subtype
Date × Class
Date × Instrument Type
Date × Sector
Date × Industry
Date × Portfolio
```

A number does not have complete analytical meaning without its grain.

---

## Financial events are not just rows

My financial engine distinguishes source transactions, canonical events, lot inventory, tax classifications, and analytical summaries. Each stage answers a different question.

```mermaid
sequenceDiagram
    participant S as Source evidence
    participant C as Canonical model
    participant F as FIFO engine
    participant T as Tax engine
    participant G as Silver / Gold
    S->>C: Normalize transactions and identities
    C->>F: Purchases and disposals
    F->>F: Consume chronological acquisition lots
    F-->>T: Realized events and provenance
    T-->>G: Classified tax estimates and review flags
    F-->>G: Lot and return analytics
```

The detailed lot rules live in [FIFO and Lot Accounting](docs/finance/fifo-and-lot-accounting.md); the tax evidence boundary lives in [Tax Event Provenance](docs/finance/tax-event-provenance.md).

---

## 6 · FIFO tax-lot accounting

Investment purchases create tax lots.

Sales consume the oldest active inventory first.

The production implementation is deliberately stateful:

```python
while rem > 0 and self._active_lots:
    lot = self._active_lots[0]
    consumed = min(rem, lot.qty)

    age_sale = max((sell_date - lot.date).days, 1)
    holding_type = self.fy_table.get_holding_type(
        age_sale,
        self.tax_type,
        self.tax_subtype,
        lot.date,
        sell_date,
    )

    pnl = (price - lot.price) * consumed if lot.price > 0 else 0.0
```

A partial disposal preserves the remaining lot and proportionally reduces its shadow benchmark exposure:

```python
new_shadow_qty = (
    lot.shadow_qty - (lot.shadow_qty * (rem / lot.qty))
    if lot.shadow_qty
    else 0
)

self._active_lots[0] = TaxLot(
    date=lot.date,
    qty=lot.qty - rem,
    price=lot.price,
    shadow_qty=new_shadow_qty,
    bm_buy=lot.bm_buy,
)
```

That one piece of state supports several downstream questions at once:

```text
FIFO disposal
     ↓
realized P&L
     ↓
sale-date holding classification
     ↓
tax state
     ↓
remaining active inventory
     ↓
future market + benchmark state
```

The investment engine therefore reconstructs stateful investment history rather than reducing broker transactions to grouped totals.

---

## 7 · Broker reconciliation

Transaction history explains how the portfolio got here.

Broker-reported state anchors where it is now.

> **Transactions explain history; broker state anchors current truth.**

The FIFO portfolio can reconcile reconstructed quantity against reported quantity:

```python
if broker_qty > current_units + 1e-8:
    diff = broker_qty - current_units
    self.buy(market_date, diff, 0.0, 0.0, benchmark_price)

elif broker_qty < current_units - 1e-8:
    diff = current_units - broker_qty
    # consume reconstructed inventory until reported quantity is matched
```

Cost basis can also be reconciled against broker-reported buy value.

This is an explicit operational policy, not a claim that historical transaction evidence is always complete.

That distinction matters for tax interpretation.

---

## 8 · Shadow benchmark portfolio

Benchmark analysis follows actual capital deployment.

Each investment purchase creates equivalent benchmark exposure.

```mermaid
flowchart LR
    CASH["Capital Deployment"] --> REAL["Real Investment Lot"]
    CASH --> SHADOW["Shadow Benchmark Lot"]
    REAL --> RR["Actual Return State"]
    SHADOW --> BR["Benchmark Return State"]
    RR --> ACTIVE["Active Return"]
    BR --> ACTIVE
```

When a real lot is partially sold, shadow benchmark quantity is reduced proportionally.

The comparison therefore asks:

> **What happened to the same economic capital if it had been deployed into the configured benchmark at the same time?**

That preserves capital-deployment timing in the comparison instead of subtracting two unrelated point-to-point returns.

---

## 9 · Cash-flow-aware returns

The solver wrapper is intentionally small:

```python
def calculate_xirr(dates: list[date], amounts: list[float]) -> float:
    try:
        result = xirr(dates, amounts)
        return float(result) if result is not None else float("nan")
    except Exception:
        return float("nan")
```

The difficult part is not calling `xirr()`.

The difficult part is constructing the correct dated cash-flow series at the required grain.

```text
ISIN XIRR
≠ average(lot returns)

Class XIRR
≠ average(ISIN XIRR)

Portfolio XIRR
≠ average(security XIRR)
```

Portfolio return is reconstructed from portfolio-level dated flows and terminal value.

The current serving model focuses on decision-useful measures:

- CAGR
- XIRR
- After-Tax XIRR
- Benchmark CAGR
- Benchmark XIRR
- Active Return
- Max Drawdown
- realized/unrealized tax state

Older Sharpe/Sortino/Calmar/beta/tracking-error style machinery was deliberately removed from the production path.

**Compute what supports the decision. Do not preserve complexity because it once existed.**

---

## 10 · Financial policy is validated configuration

Operational configuration and financial meaning are separate contracts.

A policy such as rebalancing tolerance belongs in `FinancialRules`, not inside a presentation formula.

```python
class PortfolioManagementRules(BaseModel):
    rebalance_tolerance_pct_points: float = Field(
        default=5.0,
        ge=0.0,
    )
```

The analytical builder consumes that policy rather than embedding the threshold:

```text
FinancialRules
      ↓
validated policy
      ↓
portfolio-management builder
      ↓
allocation drift / rebalance state
```

The same policy plane carries concepts around:

- income semantics,
- expense semantics,
- cash/non-cash treatment,
- cash pools,
- asset classifications,
- target allocation,
- tax parameters,
- FIRE assumptions,
- market regimes,
- human-capital shocks,
- glide paths,
- and withdrawal behaviour.

> **Parameters belong in configuration. Genuinely different behaviour belongs behind adapters or strategies.**

---

## 11 · Household ledger and wealth

Household activity is reconstructed from:

```text
Opening Balances
Income
Expenses
Transfers
```

Transfers remain distinct from income and expense so internal movement does not manufacture financial performance.

The model also keeps several concepts separate that are easy to blur in a spreadsheet:

```text
cash income       ≠ total income
cash expense      ≠ total expense
book wealth       ≠ market wealth
market wealth     ≠ after-tax wealth
savings growth    ≠ organic market growth
```

Investment market and tax state flows back into the household balance sheet.

```mermaid
flowchart LR
    HH["Household Ledger"] --> BOOK["Book Wealth"]
    INV["Investment Market State"] --> MARKET["Market Wealth"]
    TAX["Investment Tax State"] --> AFTER["After-Tax Wealth"]
    BOOK --> MARKET
    MARKET --> AFTER
    AFTER --> PLAN["Planning / FIRE"]
```

This is why the investment engine and household engine are not separate applications.

They are different views of one financial state.

---

## 12 · Cash-flow reconciliation

A categorized expense report can look plausible while still failing to explain actual cash movement.

The system therefore anchors cash flow to configured cash-pool balances.

```text
Opening Cash
    +
Operating Activity
    +
Investing Activity
    +
Financing Activity
    +
Internal Transfer Treatment
    =
Calculated Closing Cash
```

Then:

```text
Actual Closing Cash
        -
Calculated Closing Cash
        =
Unreconciled Difference
```

A non-zero difference remains visible.

It is a data-quality and financial-reconciliation signal, not something to zero out for a prettier dashboard.

---

## 13 · FIRE is downstream of financial truth

FIRE does not begin from a manually entered portfolio number.

It consumes connected household state:

```text
After-Tax Market Wealth
        +
Trailing Spending
        +
Trailing Savings
        +
FinancialRules
        ↓
Current-State FIRE
        ↓
Deterministic Planning
        ↓
Monte Carlo
```

The stochastic model can represent:

- Bull / Bear / Stagflation regimes,
- Markov regime transitions,
- fat-tailed return shocks,
- jump events,
- stochastic inflation,
- human-capital shocks,
- glide paths,
- portfolio drag,
- dynamic withdrawal rules,
- and sequence-of-returns risk.

The simulation is accelerated with NumPy/Numba because this is a numerical workload, not a dataframe transformation problem.

The Gold serving contract intentionally exposes selected planning outputs rather than every simulation statistic:

```text
P10 / P50 / P90 months to FI
modelled probability of success
projected P50 FI date
base / stressed runway
P50 nominal terminal wealth
```

These are **scenario distributions under configured assumptions**, not predictions.

---

## 14 · Failure, recovery, and observability are part of the architecture

Per-instrument investment work runs in parallel.

A failed worker is not allowed to disappear from a successful portfolio. The failure propagates into the orchestrator, becomes structured Control Plane history, and prevents partial analytical state from being published as success.

```python
cp.runs.log_run_failure(
    run_id=run_id,
    failed_isin=failed_isin,
    stage="InvestmentQuantEngine",
    error_type="RuntimeError",
    error_message=error_msg,
    traceback_log=traceback.format_exc(),
)
```

The system also keeps a complete run-scoped forensic log:

```text
run_id
  ├── stage
  ├── ISIN
  ├── process
  ├── module
  ├── function
  ├── source line
  └── traceback / message
          ↓
cross-process logging queue
          ↓
compressed execution log
          ↓
cp_runs.execution_log
```

Structured failures answer **what failed**. The execution log preserves **what happened around it**.

### Recovery follows the normal pipeline

The Control Plane can challenge the analytical plane rather than blindly trusting a previous `SYNCED` state.

```mermaid
flowchart LR
    CP["Control Plane<br/>Artifact = SYNCED"] --> CHECK["Validate DuckDB State"]
    CHECK --> OK{"Registry, table and<br/>artifact state healthy?"}
    OK -->|"Yes"| KEEP["Keep SYNCED"]
    OK -->|"No"| PEND["PENDING_BRONZE"]
    PEND --> REPLAY["Normal Bronze Replay"]
    REPLAY --> SYNC["SYNCED"]
```

Normal discovery merges:

```text
new
+
changed
+
PENDING_BRONZE
```

into one actionable path.

A pure source rename is treated as provenance migration across the Control Plane, raw payload relationship, Bronze ownership, and DuckDB Meta projection. Financial state does not change merely because a file moved.

---

### The operational lifecycle is explicit

```mermaid
stateDiagram-v2
    [*] --> Created
    Created --> Running
    Running --> Completed: successful publication and finalization
    Running --> Failed: exception or unsuccessful execution
    Running --> Interrupted: abnormal termination / stale run
    Failed --> [*]
    Completed --> [*]
    Interrupted --> [*]
```

This is a conceptual lifecycle summary. The precise persisted status values and recovery transitions are specified in [Run Lifecycle](docs/control-plane/run-lifecycle.md).

---

## 15 · Coordinated Snapshot + Restore

SQLite and DuckDB are treated as one logical recovery unit:

```text
Raw_Documents.sqlite
+
Personal_Finance_DB.duckdb
```

Snapshot creation runs under the production lock, uses SQLite's backup API, preserves the DuckDB recovery state, and packages the pair into one archive.

Restore validates the archive before touching production state and follows an **all-new or all-old** rule:

```mermaid
flowchart LR
    ZIP["Validated Snapshot"] --> LOCK["Production Lock"]
    LOCK --> OLD["Preserve Current Recovery Unit"]
    OLD --> NEW["Install Snapshot Pair"]
    NEW --> OK{"Complete?"}
    OK -->|"Yes"| KEEP["Keep Restored Pair"]
    OK -->|"No"| ROLL["Remove Partial Restore"]
    ROLL --> BACK["Restore Complete Previous Pair"]
```

This is still a local-first application. The reliability model is deliberately application-coordinated rather than distributed.

---

## 16 · Lean DuckDB Meta (six physical tables)

DuckDB Meta is intentionally not the historical operational authority.

It contains current analytical context beside the warehouse:

```text
m_File_Registry
m_Table_Row_Counts
m_Financial_Rules
m_Settings
m_Data_Contracts
```

`m_Data_Contracts` exposes the current analytical registry itself: contract identity, layer, physical table, domain, grain, producer, replacement semantics, and publication order.

Historical execution truth remains in SQLite.

> **The Control Plane is authoritative. DuckDB Meta is the current analytical projection.**

---

## 17 · Documentation is a local application too

The documentation is packaged with the application and discovered through one manifest.

```mermaid
flowchart LR
    MD["README + docs/*.md"] --> MAN["manifest.json"]
    MAN --> CAT["DocsCatalog"]
    CAT --> RENDER["DocsRenderer"]
    MER["Bundled Mermaid"] --> RENDER
    RENDER --> NAV["Navigation + TOC"]
    NAV --> CLI["CLI Docs"]
    NAV --> GUI["Desktop Docs"]
```

The renderer provides manifest-driven discovery, canonical internal navigation, Markdown rendering, a generated H1/H2/H3 table of contents, and bundled Mermaid rendering without a CDN dependency.

One documentation tree therefore serves GitHub, CLI, Desktop, and the packaged distribution.

The [GitHub Wiki](https://github.com/tks18/personal-finance-etl/wiki) has a different job:

```text
README  → SHOW
Wiki    → TEACH
/docs   → SPECIFY
Code    → PROVE
```

Yes, the documentation explaining the architecture now has an architecture. 😅

---

## 18 · Application surfaces

The financial logic sits behind a backend facade rather than being implemented separately in every interface.

```text
                 PersonalFinanceEngine
                         │
            ┌────────────┼────────────┐
            ▼            ▼            ▼
          CLI          Desktop     Headless
                         │
                         ▼
                      Power BI
```

The shared application surface includes pipeline execution, coordinated Snapshot/Restore, configuration, and packaged documentation.

The surfaces have different jobs. The engine remains shared.

That principle dates back to much earlier projects in my engineering journey and remains one of the architectural instincts I keep returning to.

---

## 19 · Performance

The production-hardening cycle also removed analytical work that no longer supported the serving contract.

That included legacy risk calculations and associated presentation processing.

### Daily operating snapshot

This is a real personal-finance workload, not a synthetic stress-test dataset. I currently use the platform with the following observed characteristics:

| Operating characteristic | My observation |
| --- | ---: |
| Source artifacts | **1,629** |
| Cached end-to-end run | **~20 seconds** |
| Fresh end-to-end run | **~40 seconds** |
| Financial validation | Reconciled against my actual financial records, down to the paise |
| Deployment model | Local-first, single-user |

The cached and fresh timings describe different workloads. They are not directly comparable to the earlier hardening benchmarks, and I do not treat them as universal performance guarantees.

```mermaid
xychart-beta
    title "Observed end-to-end runtime (seconds)"
    x-axis ["Cached", "Fresh"]
    y-axis "Seconds" 0 --> 45
    bar [20, 40]
```

> The durations above are observed totals, not measured stage timings. The chart compares elapsed time only; it does not imply the two runs share identical internal stage boundaries.

### Why the pipeline stays responsive

```mermaid
flowchart LR
    DISC["Discover 1,629 artifacts"] --> HASH{"New or changed?"}
    HASH -->|Yes| SYNC["Synchronize affected Bronze inputs"]
    HASH -->|No| KEEP["Reuse persistent Bronze state"]
    SYNC --> REBUILD["Rebuild canonical analytics"]
    KEEP --> REBUILD
    REBUILD --> CONTRACT["Validate and publish Silver / Gold"]
```

The key architectural distinction is **incremental source synchronization followed by a coherent analytical rebuild**. I do not advertise the entire pipeline as end-to-end incremental.

My earlier **24 September 2026** benchmark recorded 1,608 artifacts and a reduction from approximately 23 seconds to 14–17 seconds following a hardening cycle. That is a historical measurement, not today's baseline.

The larger engineering lesson remains the same:

> **Process what changed. Preserve what did not. Rebuild what must remain financially coherent.**

The platform is sophisticated because the financial semantics demand it, not because I need a distributed cluster to reconcile my own expenses. That would be a *very* expensive way to buy peace of mind. 😂

---

## 20 · Technology ownership

The stack is deliberately heterogeneous.

| Technology | Responsibility |
| --- | --- |
| **SQLite** | Authoritative Control Plane, raw artifacts/payloads, run history, failures, compressed execution logs, configuration provenance |
| **DuckDB** | 20 Bronze + 24 Silver + 22 Gold analytical contracts and lean current-state Meta |
| **Polars** | Lazy/vectorized transformation and analytical computation |
| **Pydantic** | Operational and financial-policy contracts |
| **PyXIRR** | Irregular dated return solving |
| **NumPy / Numba** | Numerical stochastic simulation |
| **multiprocessing** | Per-instrument analytical parallelism and process isolation |
| **Rich** | CLI |
| **CustomTkinter** | Desktop application |
| **Power BI** | Decision-oriented analytical consumption |

The question is not which tool wins.

It is which tool should own the responsibility.

---

## 21 · Running the project

> **Important:** installing the package does not make the current source contracts portable to an arbitrary financial environment.

Requires **Python 3.13+**.

### Install

```bash
pip install personal-finance-etl
```

### CLI

```bash
shan-fin
```

The CLI exposes pipeline execution, documentation, coordinated snapshot creation, and restore workflows.

### Desktop

```bash
shan-fin-gui
```

The desktop surface shares the same backend engine and exposes pipeline execution, Snapshot/Restore, configuration, and the packaged documentation portal.

### Development

```bash
git clone https://github.com/tks18/personal-finance-etl.git
cd personal-finance-etl
pip install -e .
```

A working deployment also requires:

- valid operational Settings,
- valid FinancialRules,
- reference/mapping inputs,
- and source contracts compatible with the current adapters.

See:

- [Installation](docs/getting-started/installation.md)
- [Configuration](docs/getting-started/configuration.md)
- [Running the Pipeline](docs/getting-started/running-the-pipeline.md)

---

## 22 · Is this plug-and-play?

**No, not yet.**

The current system is production software built around my financial environment.

Substantial parts are already reusable:

```text
Control Plane
Raw evidence lifecycle
Bronze synchronization
deterministic reconstruction
canonical modelling patterns
investment engine
wealth engine
contract registry
application architecture
documentation runtime
```

But another financial environment can still require customization of:

- bank/broker source contracts,
- mappings,
- statement layouts,
- asset pipelines,
- financial classifications,
- jurisdictional tax behaviour,
- reconciliation policy,
- and selected analytical assumptions.

I would rather make that boundary explicit than call a purpose-built system "fully configurable" before it is.

---

## 23 · What comes next

The platform architecture is now intentionally stable.

The next maturity work is about formalizing and protecting the financial behavior already exercised against production data.

```mermaid
flowchart TB
    NOW["Operational platform in daily use"]
    NOW --> DOMAIN["Formalize selected financial-domain invariants"]
    NOW --> TEST["Expand executable financial regression fixtures"]
    NOW --> OPS["Strengthen fault-injection and recovery coverage"]
    DOMAIN --> EVOLVE["Feature-driven evolution"]
    TEST --> EVOLVE
    OPS --> EVOLVE
    EVOLVE --> NEW["New sources · Assets · Models · Decision questions"]
```

The current financial model remains the production baseline.

The next step is to convert that practical confidence into more explicit domain contracts and executable regression protection.

See the full [Roadmap](docs/about/roadmap.md).

---

## 24 · Explore the project

The project has intentionally different knowledge surfaces.

| Surface | Job | Start here |
| --- | --- | --- |
| **README** | **SHOW** — what the system is and why it is interesting | You are here |
| **Wiki** | **TEACH** — guided mental models and system journeys | [Explore the Wiki](https://github.com/tks18/personal-finance-etl/wiki) |
| **`/docs`** | **SPECIFY** — architecture, methodology, contracts, configuration, and developer reference | [Open `/docs`](docs/README.md) |
| **Code** | **PROVE** — implementation authority | [Browse `src/`](src/personal_finance_etl) |

### Explore the 11-domain technical universe

I organize the technical reference by ownership. Each domain goes deep on its own responsibility instead of reproducing the same architecture in eleven places.

| Domain | What I document | Entry point |
| --- | --- | --- |
| Architecture | System boundaries, dependencies, execution | [Architecture](docs/architecture/README.md) |
| Control Plane | Artifact identity, provenance, run lifecycle, healing | [Control Plane](docs/control-plane/README.md) |
| Data Engineering | Discovery, Bronze, transformation, publication | [Data Engineering](docs/data-engineering/README.md) |
| Finance | FIFO, FX, benchmarks, taxation, wealth, FIRE | [Finance](docs/finance/README.md) |
| Configuration | Financial rules, validation, reproducibility | [Configuration](docs/configuration/README.md) |
| Reference | Physical contracts, schemas, identities, API | [Reference](docs/reference/README.md) |
| Interfaces | Application facade, CLI, desktop, docs renderer | [Interfaces](docs/interfaces/README.md) |
| Operations | Recovery, transactions, performance, observability | [Operations](docs/operations/README.md) |
| Developer | Extensions, testing, debugging, maintenance | [Developer](docs/developer/README.md) |
| Getting Started | Installation and daily workflows | [Getting Started](docs/getting-started/README.md) |
| About | Project evolution, roadmap, my engineering journey | [About](docs/about/README.md) |

**Suggested deep dives:** [Execution Lifecycle](docs/architecture/execution-lifecycle.md) · [Identity Contracts](docs/reference/identity-contracts.md) · [Benchmark Attribution](docs/finance/benchmark-attribution.md) · [Backup and Restore](docs/operations/backup-and-restore.md) · [Documentation Renderer](docs/interfaces/documentation-renderer.md)

The Wiki and `/docs` deliberately overlap in **concept**, not in **job**.

The Wiki helps a reader understand the system. `/docs` shows exactly how it works.

---

## 25 · Engineering principles

A few principles survive almost every refactor.

### Preserve evidence

Derived analytical state can be rebuilt. Original financial evidence deserves a separate durability boundary.

### Make ownership explicit

SQLite owns operational truth. DuckDB owns analytical state.

### Respect grain

A metric without grain is an invitation to calculate the right formula over the wrong financial object.

### Reconcile against independent truth

Cash movement and broker state are valuable precisely because they can challenge reconstructed state.

### Keep financial policy explicit

A threshold or classification that changes financial meaning should not hide inside a presentation expression.

### Let different workloads use different compute models

Polars is excellent for lazy/vectorized transformations.

FIFO is stateful.

Monte Carlo is numerical.

One abstraction does not need to win every argument.

### Compute richly. Publish selectively.

A metric earns Gold real estate because it supports a decision, not because it was difficult to calculate.

### Generalize from working behaviour

I prefer extracting abstractions from a production vertical system over designing a universal framework before the variation exists.

---

## 26 · About the builder

I am a **Chartered Accountant who builds data-intensive software systems**.

My engineering path moved through web development, Python, data analytics, data engineering, BI automation, software architecture, semantic/local-AI systems, and eventually into projects where those disciplines meet finance.

Personal Finance ETL is currently the clearest convergence of that journey.

The longer story is in **[About Me](docs/about/about-me.md)**.

---

## Final note

This started because I wanted a better month-end view of my own finances.

It now has:

```text
an authoritative SQLite Control Plane
a DuckDB warehouse with 20 Bronze / 24 Silver / 22 Gold contracts and six Meta tables
a Polars canonical transformation DAG
FIFO tax-lot accounting
broker reconciliation
shadow benchmark portfolios
cash-flow reconciliation
tax-aware wealth
Numba Monte Carlo
run-scoped cross-process forensic logging
coordinated Snapshot + Restore
Power BI
CLI + desktop surfaces
and a fully local manifest-driven documentation application
```

Is that a lot of engineering for personal finance?

Yes.

But it is not architecture built around a hypothetical problem.

**I use the system. The financial state reconciles. The outputs guide real decisions.**

That is the part I care about.

---

## License

See [LICENSE](LICENSE) for usage terms.
