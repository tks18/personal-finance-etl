# Identity & Grain Contracts

Grain answers **what one row represents**. Identity answers **what makes that financial thing the same thing again**.

Those concepts overlap, but they are not synonyms. A table can have a valid physical primary key and still have the wrong economic grain. A deterministic ID can be stable while a downstream aggregation violates that grain.

## Analytical grain catalog

| Layer | Dataset | Grain |
|---|---|---|
| Gold | `gold.Core_Monthly_Fact` | `Month` |
| Gold | `gold.Wealth_Asset_Breakdown` | `Month-Asset` |
| Gold | `gold.Cashflow_Expense_Breakdown` | `Month-ExpenseCategory` |
| Gold | `gold.Cashflow_Income_Breakdown` | `Month-IncomeCategory` |
| Gold | `gold.Wealth_FIRE_Analytics` | `Month` |
| Gold | `gold.Forecast_Budget_Variance` | `Month` |
| Gold | `gold.Investment_Portfolio_Summary` | `Month-ISIN` |
| Gold | `gold.Cashflow_Efficiency_Analytics` | `Month` |
| Gold | `gold.Cashflow_Activity_Summary` | `Month` |
| Gold | `gold.Investment_By_ISIN` | `Date-ISIN` |
| Gold | `gold.Investment_By_Subtype` | `Date-Subtype` |
| Gold | `gold.Investment_By_Class` | `Date-Class` |
| Gold | `gold.Investment_By_Instrument_Type` | `Date-InstrumentType` |
| Gold | `gold.Investment_By_Sector` | `Date-Sector` |
| Gold | `gold.Investment_By_Industry` | `Date-Industry` |
| Gold | `gold.Investment_By_Portfolio` | `Date` |
| Gold | `gold.Investment_By_Geo` | `Date-Geo` |
| Gold | `gold.Investment_By_Country` | `Date-Country` |
| Gold | `gold.Investment_By_Currency` | `Date-Currency` |
| Gold | `gold.Tax_Year_Summary` | `FY` |
| Gold | `gold.Tax_Income_Breakdown` | `FY-Head-SubHead-Source` |
| Gold | `gold.Tax_Reconciliation` | `FY-SubHead` |
| Silver | `silver.d_Calendar` | `Day` |
| Silver | `silver.d_Income_Category` | `Category` |
| Silver | `silver.d_Income_Subcategory` | `Subcategory` |
| Silver | `silver.d_Expense_Category` | `Category` |
| Silver | `silver.d_Expense_Subcategory` | `Subcategory` |
| Silver | `silver.d_Asset_Category` | `Category` |
| Silver | `silver.d_Asset_SubCategory` | `Subcategory` |
| Silver | `silver.d_Currency` | `Currency` |
| Silver | `silver.d_Investment_Benchmark_Master` | `Benchmark` |
| Silver | `silver.f_Currency_FX_Rates` | `Date-Currency` |
| Silver | `silver.d_Investment_Master` | `ISIN` |
| Silver | `silver.d_Macro_Parameters` | `FinancialYear` |
| Silver | `silver.f_Income_Transactions` | `Transaction` |
| Silver | `silver.f_Expense_Transactions` | `Transaction` |
| Silver | `silver.f_Transfer_Transactions` | `Transaction` |
| Silver | `silver.f_Opening_Balances` | `Balance` |
| Silver | `silver.f_Investment_Market_Data` | `Quote` |
| Silver | `silver.f_Investment_Purchase_Data` | `Trade` |
| Silver | `silver.f_Investment_Sale_Data` | `Trade` |
| Silver | `silver.f_Investment_Benchmark_Data` | `Quote` |
| Silver | `silver.f_Investment_Analytics_Lot` | `ISIN-Lot` |
| Silver | `silver.f_Investment_Realized_Events` | `RealizedEvent` |
| Silver | `silver.f_Investment_Reconciliation_Events` | `ReconEvent` |
| Silver | `silver.f_Tax_Events` | `TaxEvent` |


## Deterministic identity namespaces

| Namespace | Defining fields |
|---|---|
| `PURCHASE` | ISIN · Date · Price · Quantity · CURRENCY_ID |
| `SALE` | ISIN · Date · Sell_Price · Quantity · CURRENCY_ID |
| `LOT` | multiple legal field sets; purchase lots, reconciliation lots, reconciliation groups |
| `REALIZED` | Sale_ID · Lot_ID |
| `RECON_GROUP` | ISIN · Reconciliation_Date · Adjustment_Type · Broker/Reconstructed quantity + cost basis |
| `RECON_EVENT` | Reconciliation_Group_ID · Lot_ID · Adjustment_Type |
| `RECON_LOT_GROUP` | ISIN · Reconciliation_Date · Adjustment_Type · Quantity |
| `TAX` | Source_Type · Source_ID · Tax_Sub_Head |


## Canonical serialization

The identity implementation normalizes values before hashing:

```python
match val:
    case None:
        return "<NULL>"
    case bool():
        return "true" if val else "false"
    case datetime():
        return val.isoformat()
    case date():
        return val.strftime("%Y-%m-%d")
```

It also normalizes numeric values through `Decimal`, Unicode strings through NFC, and strips surrounding whitespace.

Known namespaces use contract-defined field order. Unknown/new namespaces fall back to sorted field names so identity remains deterministic rather than caller-insertion-order dependent.

The payload is serialized as:

```text
[namespace, "v2", [[key, value], ...]]
```

then SHA-256 hashed and truncated to a 16-hex-character suffix prefixed by the namespace.

The `v2` marker is a **technical identity protocol version**, not an application release number.

## Grain is not primary-key syntax

Consider `gold.Investment_By_ISIN` with grain `Date-ISIN`.

The grain tells downstream analytics that one row represents one instrument on one valuation date. Whether the physical table declares a composite SQL primary key is secondary to that semantic contract.

## Join discipline

Before joining two datasets, ask:

1. What is the grain on each side?
2. Is the join one-to-one, one-to-many, or many-to-many at those grains?
3. Which side may legally duplicate the other?
4. Does the join preserve the intended output grain?

Many-to-many joins in financial data deserve suspicion until proven necessary.

## Identity continuity through rebuilds

Deterministic IDs allow analytical rebuilds to recreate the same entity identity when the same economic evidence and namespace contract are present.

That supports:

- replay comparison;
- lineage continuity;
- reconciliation;
- stable downstream relationships.

Changing identity fields/order/normalization is therefore a contract migration, not a refactor detail.

## Related specifications

- [Deterministic Identity & Replay](../architecture/deterministic-identity-and-replay.md)
- [Investment Data Model](../finance/investment-data-model.md)
- [Data Contract & Schema Evolution](../developer/data-contract-and-schema-evolution.md)
