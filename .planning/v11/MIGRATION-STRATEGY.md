# One-Time Migration Strategy

The v11 program intentionally prefers a controlled one-time local migration over permanent compatibility infrastructure.

## Authority split

Preserve:
- source/reference evidence;
- Raw Store payloads;
- Control Plane operational history;
- FinancialRules;
- deterministic financial identities and formulas.

Rebuild:
- DuckDB Bronze/Silver/Gold/derived Meta state where appropriate.

## Ordered migration

1. certify v11.0.0 baseline and create snapshot;
2. remove docs portal/runtime baggage;
3. migrate Settings and reference-file names/content;
4. rename/rebuild Bronze and prove row/evidence equivalence;
5. perform Silver disposition archaeology;
6. cut over Silver household/reference vocabulary;
7. cut over Silver investment/event/tax vocabulary;
8. map Gold and Power BI dependencies;
9. cut over Gold household/wealth/FIRE/tax vocabulary;
10. cut over Gold investment vocabulary and Power BI queries;
11. add household/wealth analytics;
12. add investment/tax analytics;
13. migrate CLI product identity and operator services;
14. migrate GUI to PySide6;
15. certify the final system.

No long-lived compatibility views, dual table publication, or deprecated warehouse aliases are planned.
