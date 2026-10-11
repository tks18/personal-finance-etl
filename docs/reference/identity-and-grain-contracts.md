# Identity and Grain Contracts

I use different identity contracts for source artifacts, household ledger events, canonical investment transactions, FIFO lots, realized disposals, reconciliation mutations and tax evidence. Treating these as interchangeable creates duplicate counting and broken lineage.

```mermaid
flowchart LR
A["Source UID / Purchase_ID"] --> B["Canonical event"] --> C["Lot / realized event"] --> D["Tax / Gold"]
```

### Implementation anchor: Identity serialization

Source: `src/personal_finance_etl/backend/utils/identity.py`

```python


def generate_deterministic_id(namespace: str, fields: dict[str, Any]) -> str:
    """Generate a stable deterministic ID using Canonical ID Serialization v2.

    Known namespaces retain their established field order and hashes. New or
    changed field sets use sorted keys until an explicit order is registered.
    """
    pairs = [
        [canonicalize_value(key), canonicalize_value(value)]
        for key, value in _ordered_identity_fields(namespace, fields)
    ]
    payload = json.dumps(
        [namespace, "v2", pairs], ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    hash_str = hashlib.sha256(payload).hexdigest()
    return f"{namespace}_{hash_str[:16]}"
```

## Identity hierarchy

| Entity | Defining authority | Intended meaning |
| --- | --- | --- |
| Ledger transaction | Source UID | Household financial record |
| Purchase/Sale | Canonical investment transform | Economic transaction |
| Lot | Quant FIFO | Acquisition lot identity |
| Realized event | Quant FIFO | Disposal portion of an acquisition lot |
| Reconciliation event | Quant reconciliation | Explainable adjustment/mutation |
| TaxEvent | Ledger or Quant event + tax sub-head | Tax-preparation evidence |
| Artifact event | SQLite Control Plane | Observation or lifecycle transition |

## Registry grain inventory

| Table | Grain | Producer |
| --- | --- | --- |
| `silver.d_Calendar` | `Day` | `CoreEngine` |
| `silver.d_Income_Category` | `Category` | `CoreEngine` |
| `silver.d_Income_Subcategory` | `Subcategory` | `CoreEngine` |
| `silver.d_Expense_Category` | `Category` | `CoreEngine` |
| `silver.d_Expense_Subcategory` | `Subcategory` | `CoreEngine` |
| `silver.d_Asset_Category` | `Category` | `CoreEngine` |
| `silver.d_Asset_SubCategory` | `Subcategory` | `CoreEngine` |
| `silver.d_Currency` | `Currency` | `CoreEngine` |
| `silver.d_Investment_Benchmark_Master` | `Benchmark` | `CoreEngine` |
| `silver.f_Currency_FX_Rates` | `Date-Currency` | `CoreEngine` |
| `silver.d_Investment_Master` | `ISIN` | `CoreEngine` |
| `silver.d_Macro_Parameters` | `FinancialYear` | `CoreEngine` |
| `silver.f_Income_Transactions` | `Transaction` | `CoreEngine` |
| `silver.f_Expense_Transactions` | `Transaction` | `CoreEngine` |
| `silver.f_Transfer_Transactions` | `Transaction` | `CoreEngine` |
| `silver.f_Opening_Balances` | `Balance` | `CoreEngine` |
| `silver.f_Investment_Market_Data` | `Quote` | `CoreEngine` |
| `silver.f_Investment_Purchase_Data` | `Trade` | `CoreEngine` |
| `silver.f_Investment_Sale_Data` | `Trade` | `CoreEngine` |
| `silver.f_Investment_Benchmark_Data` | `Quote` | `CoreEngine` |
| `silver.f_Investment_Analytics_Lot` | `ISIN-Lot` | `InvestmentQuantEngine` |
| `silver.f_Investment_Realized_Events` | `RealizedEvent` | `InvestmentQuantEngine` |
| `silver.f_Investment_Reconciliation_Events` | `ReconEvent` | `InvestmentQuantEngine` |
| `silver.f_Tax_Events` | `TaxEvent` | `TaxEngine` |
| `gold.Tax_Year_Summary` | `FY` | `TaxEngine` |
| `gold.Tax_Income_Breakdown` | `FY-Head-SubHead-Source` | `TaxEngine` |
| `gold.Tax_Reconciliation` | `FY-SubHead` | `TaxEngine` |
| `gold.Core_Monthly_Fact` | `Month` | `WealthPresentationEngine` |
| `gold.Wealth_Asset_Breakdown` | `Month-Asset` | `WealthPresentationEngine` |
| `gold.Cashflow_Expense_Breakdown` | `Month-ExpenseCategory` | `WealthPresentationEngine` |
| `gold.Cashflow_Income_Breakdown` | `Month-IncomeCategory` | `WealthPresentationEngine` |
| `gold.Wealth_FIRE_Analytics` | `Month` | `WealthPresentationEngine` |
| `gold.Forecast_Budget_Variance` | `Month` | `WealthPresentationEngine` |
| `gold.Investment_Portfolio_Summary` | `Month-ISIN` | `InvestmentQuantEngine` |
| `gold.Cashflow_Efficiency_Analytics` | `Month` | `WealthPresentationEngine` |
| `gold.Cashflow_Activity_Summary` | `Month` | `WealthPresentationEngine` |
| `gold.Investment_By_ISIN` | `Date-ISIN` | `InvestmentQuantEngine` |
| `gold.Investment_By_Subtype` | `Date-Subtype` | `InvestmentQuantEngine` |
| `gold.Investment_By_Class` | `Date-Class` | `InvestmentQuantEngine` |
| `gold.Investment_By_Instrument_Type` | `Date-InstrumentType` | `InvestmentQuantEngine` |
| `gold.Investment_By_Sector` | `Date-Sector` | `InvestmentQuantEngine` |
| `gold.Investment_By_Industry` | `Date-Industry` | `InvestmentQuantEngine` |
| `gold.Investment_By_Portfolio` | `Date` | `InvestmentQuantEngine` |
| `gold.Investment_By_Geo` | `Date-Geo` | `InvestmentQuantEngine` |
| `gold.Investment_By_Country` | `Date-Country` | `InvestmentQuantEngine` |
| `gold.Investment_By_Currency` | `Date-Currency` | `InvestmentQuantEngine` |

## Uniqueness and financial semantics

A declared grain is not automatically enforced as a physical database key. I check the producer's canonical identifiers and the schema constraints independently. For example, two sale rows on the same ISIN/date may represent distinct economic events; a row index is not a durable financial ID.

## Full rebuilds and logical immutability

A Silver fact can be physically replaced on a rebuild. Logical identity remains stable when the defining inputs and serialization contract are unchanged. A corrected economic event may legitimately receive a different ID when defining attributes change.

## Observation provenance

Run IDs and timestamps explain when the system observed or processed an entity. They do not belong in deterministic financial identity unless the identity contract explicitly models an observation rather than the economic event.

## Aggregation discipline

- Income and realized gains/losses are signed flows, additive over compatible dimensions.
- Wealth and holdings are stock measures, not additive across dates.
- XIRR, CAGR, rates and Monte Carlo percentiles are non-additive.
- Tax estimates are indicative and must remain distinguishable from final statutory tax.
- A reconstructed market-state row is not an acquisition-lot row.

[← Reference index](README.md)
