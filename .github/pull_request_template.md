# Pull Request

## What changed?

<!-- Describe the smallest coherent change made by this PR. -->

## Why?

<!-- What problem, financial requirement, or engineering requirement does it solve? -->

## Change type

- [ ] Source adapter / extractor
- [ ] Asset pipeline / strategy
- [ ] Financial methodology
- [ ] FinancialRules / Settings / reference configuration
- [ ] Control Plane / reliability
- [ ] Silver / Gold analytical contract
- [ ] Performance / refactor
- [ ] CLI / GUI / Power BI
- [ ] Build / packaging
- [ ] Documentation
- [ ] Other

## Financial impact

**Does this intentionally change financial truth or methodology?**

- [ ] No
- [ ] Yes

If yes, explain the previous methodology, new methodology, why it is correct, and expected output differences. If no, preserve financial-output equivalence where applicable.

## Contract impact

- [ ] No persisted contract change
- [ ] `DataContract` registry reviewed
- [ ] DuckDB DDL reviewed
- [ ] Grain reviewed
- [ ] Publication order reviewed
- [ ] Meta row-count mapping reviewed
- [ ] Power BI / downstream consumers reviewed

## Validation

- [ ] Ruff passes
- [ ] mypy passes
- [ ] Pyright passes
- [ ] Representative pipeline run completed
- [ ] Financial outputs reconciled where applicable
- [ ] Failure / rollback behaviour reviewed where applicable
- [ ] Build/package validation completed where applicable
- [ ] Documentation impact reviewed
- [ ] No real or sensitive personal financial data is included

## Reconciliation notes

<!-- Summarize equivalence checks such as positions, FIFO lots, tax state, XIRR, net worth, cash-flow reconciliation, FIRE, and Silver/Gold row counts. -->

## Documentation

<!-- List /docs, Wiki, README, contract-reference, or release-note changes. -->

## Additional context

<!-- Screenshots and logs must be synthetic or thoroughly sanitized. -->
