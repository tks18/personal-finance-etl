# Frozen Decision Ledger

This ledger is authoritative for the v11 Shan-first program unless exact implementation evidence forces an amendment before the owning phase begins.

| Decision | Status |
| --- | --- |
| Shan-first, local-first product | FROZEN |
| Observability / Raw Store / Control Plane / recovery | KEEP |
| Docs portal, MkDocs/ReadTheDocs runtime, embedded web renderer | REMOVE |
| README + `/docs`, GitHub-native Mermaid | KEEP |
| Wiki as required documentation surface | DROP |
| Settings and FinancialRules separation | KEEP |
| One statements root | KEEP |
| File type and load semantics | CODE-OWNED |
| Hash policy | EVIDENCE-SOURCE-OWNED, NONE/CONTENT |
| Column master | KEEP |
| `benchmark_mapping.csv` | RETIRE |
| `instrument_master.csv` | CREATE VIA ONE-TIME MIGRATION |
| Bronze content | SOURCE-ORIENTED |
| Bronze physical names | SEMANTIC RENAME |
| Silver topology | KEEP ALL 24 |
| Silver merge/split | FORBIDDEN IN THIS PROGRAM |
| Gold topology | KEEP ALL 22 INITIALLY |
| Protected deterministic identities | EXACTLY PRESERVE |
| DuckDB during schema cutover | REBUILD |
| Raw Store and Control Plane history | PRESERVE |
| Source/provenance column deletion | CONSUMER-PROVEN ONLY |
| `instrument`, `fx`, `pnl`, `financial_year` vocabulary | FROZEN |
| One executable `pfetl` | FROZEN |
| Operations GUI | PYSIDE6 |
| Analytics Studio | FUTURE, READ-ONLY |
| Power BI | KEEP |
| Approved Core analytics | SIX ONLY |
| Rebalancing trade/action recommendations | DROP FOR NOW |
