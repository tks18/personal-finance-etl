# Phase 08 — Final Acceptance and Compact README

**Sprint:** 2–3 hours  
**Goal:** certify the maintenance/usability batch on real PFETL use, remove dead residue, and replace the oversized README with a concise application README.

## 1. Full automated acceptance

Run the complete Phase-2 suite. No skipped financial golden tests.

Required green areas:

- E2E Control Plane → Bronze → Silver → Gold;
- household golden numbers;
- FIFO/investment numbers and protected IDs;
- Tax/FX/benchmark numbers;
- wealth/FIRE outputs;
- observability/JSONL and snapshot/restore integrity;
- config/rules TOML round trips.

## 2. Real monthly dataset acceptance

Before the batch, capture a baseline from v11.3.1 using the real data:

- latest successful run ID/date/duration;
- key household Gold totals;
- net worth;
- portfolio value;
- realized gain/loss totals;
- XIRR/benchmark values;
- Tax summary;
- FIRE headline metrics;
- counts/hash of protected purchase/sale/lot/realized/reconciliation/tax IDs.

After all phases, run the real dataset with **default-equivalent settings/rules** and compare. Differences are allowed only if they are caused by an explicitly changed configurable assumption that Shan intentionally changed. The relocation itself must not change results.

## 3. UI acceptance checklist

### Run

- select recent/new config;
- select recent/new rules;
- pipeline run starts and UI remains responsive;
- narrative progress works;
- Snapshot/Restore still works.

### Configuration

- load Settings;
- edit/save/reload;
- Save As and recent-file tracking;
- load FinancialRules;
- edit scalar/list/dict/matrix;
- invalid values never overwrite file;
- changed active profile is used on next run.

### Logs

- current JSONL files discovered from selected Settings;
- filtering/search works;
- error detail/traceback renders;
- malformed line does not crash viewer.

### System

- status/info load;
- doctor checks display remediation;
- no direct persistence imports in presentation.

## 4. Dead-code/dependency cleanup

After final behavior is proven:

- remove unused old `UnifiedETLTab` methods/classes superseded by tabs;
- remove unused imports/assets;
- verify `customtkinter` remains the only desktop toolkit;
- remove dependencies no longer used after docs/test cleanup;
- inspect `package.json`/Yarn only for release automation before deleting anything; do not remove merely because docs are gone;
- run import/search for deleted docs/tool paths;
- build package/installer if that is part of Shan's normal distribution workflow.

## 5. Rewrite root README

Target **150–250 lines**, not another documentation corpus.

Recommended structure:

```text
# Personal Finance ETL
short purpose statement

## What it does
household + investments + Tax + wealth/FIRE + operations

## Architecture
one compact Mermaid diagram

## Core capabilities
concise table/bullets

## Install / run
uv/install + pfetl commands

## Configuration
Settings + FinancialRules profiles; mention desktop editors

## Desktop
Run / Configuration / Logs / System

## Data model
20 Bronze / 24 Silver / 22 Gold, one sentence per layer

## Reliability
Control Plane, Raw Store, observability, recovery

## Testing
small golden/E2E philosophy

## Analytics
Power BI today; Analytics Studio is a separate future consumer repo

## License / creator
```

No docs links, Wiki links, Codacy/CodeRabbit/DeepWiki badges, huge implementation walkthroughs, or phase history.

## 6. Freeze rule

After this phase, PFETL Core is considered **maintenance-stable**. New work must be triggered by an actual monthly-finance need or correctness defect. Analytical exploration/reporting moves to the separate Analytics Studio repository.

## Exit criteria

- all automated and real-data acceptance checks are green;
- no requested maintenance-debt files/docs remain;
- Settings/FinancialRules are user-editable from CustomTkinter;
- logs/system views are useful;
- README is concise;
- no pending UI rewrite or hidden migration remains;
- repository is ready to serve as the stable producer for Analytics Studio.
