# Bronze Data Contracts

Bronze is the warehouse evidence layer. Its contract is intentionally different from Silver and Gold: Bronze stays close to source shape and preserves enough provenance for synchronization, replay, and forensic inspection.

Bronze physical tables are created dynamically by `BronzeLayer`; the stable catalog is therefore the **registry mapping** between extraction attributes, synchronization categories, physical tables, and replacement semantics.

## Contract authority

```python
@dataclass
class BronzeDataContract:
    extraction_attribute: str
    sync_category: str
    physical_table: str
    is_full_replace: bool
```

Source: `src/personal_finance_etl/infrastructure/warehouse/registry.py`

Unlike Silver/Gold, Bronze does not have one giant static DDL catalog. `schema/bronze.py` explicitly states that tables are created dynamically as evidence is synchronized.

## Registered Bronze contracts

| Extraction attribute | Sync category | Physical table | Mode |
|---|---|---|---|
| `household_zcategory` | `sqlite_source` | `bronze.household_zcategory` | full replace |
| `household_asset_group` | `sqlite_source` | `bronze.household_asset_group` | full replace |
| `household_assets` | `sqlite_source` | `bronze.household_assets` | full replace |
| `household_currency` | `sqlite_source` | `bronze.household_currency` | full replace |
| `household_inoutcome` | `sqlite_source` | `bronze.household_inoutcome` | full replace |
| `column_master` | `column_master` | `bronze.column_master` | full replace |
| `mutual_fund_instrument_mapping` | `mutual_fund_instrument_mapping` | `bronze.mutual_fund_instrument_mapping` | full replace |
| `instrument_master` | `instrument_master` | `bronze.instrument_master` | full replace |
| `opening_balances` | `opening_balances` | `bronze.opening_balances` | full replace |
| `benchmark_master` | `benchmark_master` | `bronze.benchmark_master` | full replace |
| `financial_year_parameters` | `financial_year_parameters` | `bronze.financial_year_parameters` | full replace |
| `currency_reference` | `currency_reference` | `bronze.currency_reference` | full replace |
| `mf_market_data` | `mf_holdings` | `bronze.mf_market_data` | incremental |
| `mf_transactions` | `mf_orders` | `bronze.mf_transactions` | incremental |
| `stock_market_data` | `stock_pl` | `bronze.stock_market_data` | incremental |
| `stock_transactions` | `stock_orders` | `bronze.stock_transactions` | incremental |
| `us_stock_transactions` | `us_stock_transactions` | `bronze.us_stock_transactions` | incremental |
| `currency_fx_rates` | `currency_history` | `bronze.currency_fx_rates` | incremental |
| `benchmark_history` | `benchmark_history` | `bronze.benchmark_history` | incremental |
| `us_stock_prices` | `us_stock_market` | `bronze.us_stock_prices` | incremental |


## Replacement semantics

### Full replace

A full-replace contract says the synchronized source represents the current complete state for that category. The Bronze table can therefore be replaced from the current authoritative evidence set.

### Incremental

Incremental contracts preserve accumulated evidence across source artifacts. Synchronization must avoid duplicating already-known content while still admitting genuinely new artifacts.

The registry exposes this distinction explicitly because the two modes have different failure and replay semantics.

```mermaid
flowchart TD
    E["Source evidence"] --> C{"Contract mode"}
    C -->|full replace| R["Rebuild Bronze table from current complete source"]
    C -->|incremental| A["Append/synchronize new evidence without duplicating known state"]
```

## Provenance columns

Bronze synchronization decorates source rows with provenance where required so downstream inspection can answer which source artifact contributed the row. The exact dynamic physical columns depend on the source shape; the stable contract is therefore **source columns + synchronization provenance**, not a universal fixed Bronze schema.

## Registry invariants

`validate_registry()` enforces that every Bronze contract has:

- a non-empty extraction attribute;
- a non-empty synchronization category;
- a non-empty physical table;
- a table name beginning with `bronze.`;
- no duplicate physical table mapping.

That means Bronze catalog integrity fails before publication if two extraction paths accidentally claim the same table.

## Authority boundary

Bronze answers:

> What evidence was synchronized into the analytical warehouse?

It does **not** answer:

> What is the canonical financial meaning of that evidence?

That responsibility begins in Silver/domain transformations.

## Related specifications

- [Data Lifecycle](../architecture/data-lifecycle.md)
- [Control Plane & Artifact Lifecycle](../architecture/control-plane-artifact-lifecycle.md)
- [Silver Data Contracts](silver-data-contracts.md)
- [Adding Data Sources](../developer/adding-data-sources.md)
