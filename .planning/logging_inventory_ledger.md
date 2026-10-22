# Complete Logging & Status Migration Ledger (Phase 0)

> **Classification Schema:** `callsite → event code → audience → severity → context → action`

## 1. Executive Summary & Census Statistics

- **Total Inventoried Callsites:** 296
  - Python `logger` Callsites: 247
  - `EngineStatusMessage` Producers: 46
  - Pipeline Streams / Control Plane Telemetry: 3

### Breakdown by Architectural Layer

| Layer | Callsite Count | % of Total |
|---|---|---|
| `infrastructure` | 144 | 48.6% |
| `application` | 132 | 44.6% |
| `domain` | 12 | 4.1% |
| `presentation` | 8 | 2.7% |

### Breakdown by Diagnostic Severity

| Severity | Count | % of Total |
|---|---|---|
| `INFO` | 118 | 39.9% |
| `DEBUG` | 115 | 38.9% |
| `WARNING` | 33 | 11.1% |
| `ERROR` | 24 | 8.1% |
| `STEP` | 5 | 1.7% |
| `CRITICAL` | 1 | 0.3% |

### Breakdown by Audience Projection

| Audience | Count | Target Sink |
|---|---|---|
| `FORENSIC` | 207 | JSONL Async Debug Trace |
| `USER` | 81 | CLI / Desktop UI |
| `USER, CONTROL_PLANE` | 6 | CLI / Desktop UI & Control Plane SQLite |
| `CONTROL_PLANE` | 1 | JSONL Async Debug Trace & Control Plane SQLite |
| `CONTROL_PLANE, USER` | 1 | CLI / Desktop UI & Control Plane SQLite |

### Breakdown by Migration Action

| Migration Action | Count | Modernization Phase |
|---|---|---|
| `MIGRATE_TO_FORENSIC_EVENT` | 188 | Phase 5 & 6 |
| `CONVERT_PREFIX_TO_STRUCTURED_EVENT` | 56 | Phase 5 (Prefix Demolition) |
| `MIGRATE_TO_USER_NARRATIVE` | 49 | Phase 4 & 5 |
| `DEMOLISH_SEVERITY_INFERENCE` | 1 | Phase 9 (Demolition) |
| `BENCHMARK_AND_OPTIMIZE_ZLIB_LEVEL` | 1 | Phase 7 (Control Plane) |
| `MIGRATE_TO_STRUCTURED_FAILURE_EVENT` | 1 | Phase 5 & 6 |

---

## 2. Complete Inventory Ledger

| Callsite | Event Code | Audience | Severity | Context Fields | Modern Action |
|---|---|---|---|---|---|
| `application/ingestion/asset_strategies.py:100` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/ingestion/asset_strategies.py:106` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/ingestion/asset_strategies.py:111` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/ingestion/asset_strategies.py:116` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/ingestion/asset_strategies.py:213` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/ingestion/asset_strategies.py:218` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/ingestion/asset_strategies.py:260` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/ingestion/asset_strategies.py:267` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/ingestion/asset_strategies.py:276` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/ingestion/asset_strategies.py:281` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/ingestion/coordinator.py:77` | `PREFIX_EXTRACT_DETAIL` | FORENSIC | `DEBUG` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `application/ingestion/coordinator.py:202` | `EXTRACTION_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/ingestion/coordinator.py:235` | `PREFIX_QUALITY` | USER | `INFO` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `application/ingestion/coordinator.py:301` | `EXTRACTION_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/ingestion/coordinator.py:86` | `EXTRACTION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/ingestion/coordinator.py:237` | `EXTRACTION_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_USER_NARRATIVE` |
| `application/ingestion/coordinator.py:274` | `EXTRACTION_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/ingestion/coordinator.py:303` | `EXTRACTION_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_USER_NARRATIVE` |
| `application/ingestion/coordinator.py:269` | `EXTRACTION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/ingestion/coordinator.py:279` | `EXTRACTION_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_USER_NARRATIVE` |
| `application/ingestion/market_sync.py:91` | `MARKET_SYNC_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/ingestion/market_sync.py:140` | `MARKET_SYNC_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_USER_NARRATIVE` |
| `application/ingestion/market_sync.py:141` | `MARKET_SYNC_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/ingestion/market_sync.py:297` | `MARKET_SYNC_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_USER_NARRATIVE` |
| `application/ingestion/market_sync.py:299` | `MARKET_SYNC_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/ingestion/market_sync.py:321` | `MARKET_SYNC_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/ingestion/market_sync.py:421` | `MARKET_SYNC_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_USER_NARRATIVE` |
| `application/ingestion/market_sync.py:422` | `MARKET_SYNC_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/ingestion/market_sync.py:71` | `MARKET_SYNC_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/ingestion/market_sync.py:99` | `PREFIX_ENGINE_CURRENCY` | FORENSIC | `DEBUG` | `run_id, stage, component, provider, attempt, duration_ms` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `application/ingestion/market_sync.py:144` | `MARKET_SYNC_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_USER_NARRATIVE` |
| `application/ingestion/market_sync.py:164` | `MARKET_SYNC_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_USER_NARRATIVE` |
| `application/ingestion/market_sync.py:177` | `MARKET_SYNC_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_USER_NARRATIVE` |
| `application/ingestion/market_sync.py:191` | `MARKET_SYNC_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_USER_NARRATIVE` |
| `application/ingestion/market_sync.py:241` | `MARKET_SYNC_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/ingestion/market_sync.py:247` | `MARKET_SYNC_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/ingestion/market_sync.py:257` | `PREFIX_ENGINE_BENCHMARK` | FORENSIC | `DEBUG` | `run_id, stage, component, provider, attempt, duration_ms` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `application/ingestion/market_sync.py:342` | `MARKET_SYNC_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/ingestion/market_sync.py:363` | `PREFIX_ENGINE_US_MARKET` | FORENSIC | `DEBUG` | `run_id, stage, component, provider, attempt, duration_ms` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `application/ingestion/market_sync.py:425` | `MARKET_SYNC_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_USER_NARRATIVE` |
| `application/ingestion/market_sync.py:445` | `MARKET_SYNC_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_USER_NARRATIVE` |
| `application/ingestion/market_sync.py:458` | `MARKET_SYNC_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_USER_NARRATIVE` |
| `application/ingestion/market_sync.py:477` | `MARKET_SYNC_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_USER_NARRATIVE` |
| `application/investments/aggregation_service/pipeline.py:77` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/investments/aggregation_service/pipeline.py:87` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/investments/aggregation_service/pipeline.py:92` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/investments/aggregation_service/pipeline.py:58` | `GENERIC_APPLICATION_DIAGNOSTIC` | USER | `STEP` | `run_id, stage, component` | `MIGRATE_TO_USER_NARRATIVE` |
| `application/investments/context.py:192` | `GENERIC_APPLICATION_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_USER_NARRATIVE` |
| `application/investments/isin_service/pipeline.py:472` | `ISIN_WORKER_DIAGNOSTIC` | FORENSIC | `INFO` | `run_id, stage, component, isin, worker_id, rows` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/investments/isin_service/pipeline.py:277` | `ISIN_WORKER_DIAGNOSTIC` | USER | `STEP` | `run_id, stage, component, isin, worker_id, rows` | `MIGRATE_TO_USER_NARRATIVE` |
| `application/investments/isin_service/pipeline.py:462` | `ISIN_WORKER_DIAGNOSTIC` | FORENSIC | `ERROR` | `run_id, stage, component, isin, worker_id, rows` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/investments/isin_service/pipeline.py:453` | `ISIN_WORKER_DIAGNOSTIC` | FORENSIC | `ERROR` | `run_id, stage, component, isin, worker_id, rows` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/investments/isin_service/processor.py:126` | `ISIN_WORKER_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, isin, worker_id, rows` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/investments/isin_service/worker.py:103` | `ISIN_WORKER_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, isin, worker_id, rows` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/investments/isin_service/worker.py:112` | `ISIN_WORKER_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, isin, worker_id, rows` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/investments/isin_service/worker.py:120` | `ISIN_WORKER_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, isin, worker_id, rows` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/investments/quant_service.py:100` | `QUANT_DIAGNOSTIC` | FORENSIC | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/investments/quant_service.py:76` | `QUANT_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_USER_NARRATIVE` |
| `application/pipeline/execution.py:184` | `GENERIC_APPLICATION_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/execution.py:218` | `GENERIC_APPLICATION_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/execution.py:222` | `GENERIC_APPLICATION_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/execution.py:235` | `GENERIC_APPLICATION_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/execution.py:299` | `PREFIX_DISCOV` | USER | `INFO` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `application/pipeline/execution.py:337` | `GENERIC_APPLICATION_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/execution.py:392` | `PREFIX_PHASE` | USER | `INFO` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `application/pipeline/execution.py:401` | `GENERIC_APPLICATION_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/execution.py:407` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/execution.py:418` | `PREFIX_PHASE` | USER | `INFO` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `application/pipeline/execution.py:420` | `GENERIC_APPLICATION_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/execution.py:431` | `PREFIX_PHASE` | USER | `INFO` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `application/pipeline/execution.py:445` | `GENERIC_APPLICATION_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/execution.py:452` | `PREFIX_PHASE` | USER | `INFO` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `application/pipeline/execution.py:455` | `GENERIC_APPLICATION_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/execution.py:467` | `GENERIC_APPLICATION_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/execution.py:468` | `GENERIC_APPLICATION_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/execution.py:185` | `GENERIC_APPLICATION_DIAGNOSTIC` | USER | `STEP` | `run_id, stage, component` | `MIGRATE_TO_USER_NARRATIVE` |
| `application/pipeline/execution.py:236` | `GENERIC_APPLICATION_DIAGNOSTIC` | USER | `STEP` | `run_id, stage, component` | `MIGRATE_TO_USER_NARRATIVE` |
| `application/pipeline/execution.py:243` | `GENERIC_APPLICATION_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/execution.py:246` | `GENERIC_APPLICATION_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/execution.py:308` | `PREFIX_PHASE` | USER | `INFO` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `application/pipeline/execution.py:331` | `GENERIC_APPLICATION_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/execution.py:244` | `GENERIC_APPLICATION_DIAGNOSTIC` | USER | `STEP` | `run_id, stage, component` | `MIGRATE_TO_USER_NARRATIVE` |
| `application/pipeline/lifecycle.py:77` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, commit_state, failure_domain, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/lifecycle.py:83` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, commit_state, failure_domain, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/lifecycle.py:88` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, commit_state, failure_domain, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/lifecycle.py:107` | `LIFECYCLE_RUN_START` | USER | `INFO` | `run_id, stage, component, commit_state, failure_domain, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/lifecycle.py:140` | `PREFIX_DATABASE_DUCKDB` | FORENSIC | `DEBUG` | `run_id, stage, component, commit_state, failure_domain, duration_ms` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `application/pipeline/lifecycle.py:253` | `GENERIC_APPLICATION_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component, commit_state, failure_domain, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/lifecycle.py:303` | `LIFECYCLE_RUN_FAILED` | USER, CONTROL_PLANE | `ERROR` | `run_id, stage, component, commit_state, failure_domain, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/lifecycle.py:314` | `LIFECYCLE_TEARDOWN` | USER | `INFO` | `run_id, stage, component, commit_state, failure_domain, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/lifecycle.py:79` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, commit_state, failure_domain, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/lifecycle.py:81` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, commit_state, failure_domain, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/lifecycle.py:85` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, commit_state, failure_domain, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/lifecycle.py:87` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, commit_state, failure_domain, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/lifecycle.py:129` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `WARNING` | `run_id, stage, component, commit_state, failure_domain, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/lifecycle.py:163` | `LIFECYCLE_RUN_COMMITTED` | FORENSIC | `DEBUG` | `run_id, stage, component, commit_state, failure_domain, duration_ms` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `application/pipeline/lifecycle.py:191` | `GENERIC_APPLICATION_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component, commit_state, failure_domain, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/lifecycle.py:213` | `PREFIX_DATABASE_DUCKDB` | FORENSIC | `DEBUG` | `run_id, stage, component, commit_state, failure_domain, duration_ms` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `application/pipeline/lifecycle.py:215` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `WARNING` | `run_id, stage, component, commit_state, failure_domain, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/lifecycle.py:219` | `LIFECYCLE_RUN_COMMITTED` | FORENSIC | `WARNING` | `run_id, stage, component, commit_state, failure_domain, duration_ms` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `application/pipeline/lifecycle.py:310` | `LIFECYCLE_RUN_FAILED` | USER, CONTROL_PLANE | `ERROR` | `run_id, stage, component, commit_state, failure_domain, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/lifecycle.py:329` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `WARNING` | `run_id, stage, component, commit_state, failure_domain, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/lifecycle.py:217` | `GENERIC_APPLICATION_DIAGNOSTIC` | USER, CONTROL_PLANE | `ERROR` | `run_id, stage, component, commit_state, failure_domain, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/lifecycle.py:225` | `GENERIC_APPLICATION_DIAGNOSTIC` | USER, CONTROL_PLANE | `ERROR` | `run_id, stage, component, commit_state, failure_domain, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/orchestrator.py:118` | `GENERIC_APPLICATION_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/orchestrator.py:100` | `GENERIC_APPLICATION_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_USER_NARRATIVE` |
| `application/pipeline/orchestrator.py:111` | `GENERIC_APPLICATION_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_USER_NARRATIVE` |
| `application/pipeline/transformer.py:81` | `TRANSFORM_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/transformer.py:106` | `TRANSFORM_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/transformer.py:169` | `TRANSFORM_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/transformer.py:182` | `PREFIX_DAG_OPTIMIZER` | FORENSIC | `DEBUG` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `application/pipeline/transformer.py:184` | `TRANSFORM_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/transformer.py:219` | `TRANSFORM_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/transformer.py:230` | `TRANSFORM_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/transformer.py:234` | `TRANSFORM_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/transformer.py:129` | `TRANSFORM_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/transformer.py:162` | `TRANSFORM_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/transformer.py:186` | `TRANSFORM_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_USER_NARRATIVE` |
| `application/pipeline/transformer.py:215` | `PREFIX_DAG_OPTIMIZER` | FORENSIC | `DEBUG` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `application/pipeline/transformer.py:225` | `TRANSFORM_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/pipeline/worker.py:176` | `WORKER_STATUS_CAPTURE` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_USER_NARRATIVE` |
| `application/pipeline/worker.py:95` | `WORKER_STATUS_CAPTURE` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_USER_NARRATIVE` |
| `application/pipeline/worker.py:136` | `WORKER_STATUS_CAPTURE` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_USER_NARRATIVE` |
| `application/pipeline/worker.py:193` | `WORKER_STATUS_CAPTURE` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_USER_NARRATIVE` |
| `application/pipeline/worker.py:202` | `WORKER_STATUS_CAPTURE` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_USER_NARRATIVE` |
| `application/pipeline/worker.py:81` | `WORKER_STATUS_CAPTURE` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_USER_NARRATIVE` |
| `application/wealth/wealth_service.py:132` | `PREFIX_ENGINE_PRESENTATION` | FORENSIC | `DEBUG` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `application/wealth/wealth_service.py:133` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `application/wealth/wealth_service.py:142` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `domain/fire/inflation.py:174` | `PREFIX_INFLATION` | FORENSIC | `ERROR` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `domain/market/benchmarks.py:58` | `MARKET_SYNC_DIAGNOSTIC` | FORENSIC | `WARNING` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `domain/market/benchmarks.py:162` | `MARKET_SYNC_DIAGNOSTIC` | FORENSIC | `WARNING` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `domain/market/benchmarks.py:219` | `MARKET_SYNC_DIAGNOSTIC` | FORENSIC | `INFO` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `domain/market/benchmarks.py:205` | `MARKET_SYNC_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_USER_NARRATIVE` |
| `domain/market/benchmarks.py:222` | `MARKET_SYNC_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_USER_NARRATIVE` |
| `domain/market/macro.py:299` | `MARKET_SYNC_DIAGNOSTIC` | FORENSIC | `WARNING` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `domain/market/macro.py:340` | `MARKET_SYNC_DIAGNOSTIC` | FORENSIC | `WARNING` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `domain/market/macro.py:366` | `MARKET_SYNC_DIAGNOSTIC` | FORENSIC | `WARNING` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `domain/market/macro.py:392` | `MARKET_SYNC_DIAGNOSTIC` | FORENSIC | `WARNING` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `domain/market/macro.py:190` | `MARKET_SYNC_DIAGNOSTIC` | FORENSIC | `ERROR` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `domain/market/macro.py:191` | `MARKET_SYNC_DIAGNOSTIC` | FORENSIC | `ERROR` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/control_plane/artifact_repository.py:190` | `CONTROL_PLANE_DIAGNOSTIC` | FORENSIC | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/control_plane/artifact_repository.py:334` | `CONTROL_PLANE_DIAGNOSTIC` | FORENSIC | `WARNING` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/control_plane/artifact_repository.py:534` | `PREFIX_INGEST` | FORENSIC | `INFO` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/control_plane/artifact_repository.py:707` | `PREFIX_ARTIFACT` | FORENSIC | `DEBUG` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/control_plane/artifact_repository.py:772` | `PREFIX_ARTIFACT` | FORENSIC | `INFO` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/control_plane/artifact_repository.py:874` | `PREFIX_ARTIFACT` | FORENSIC | `INFO` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/control_plane/artifact_repository.py:677` | `PREFIX_ARTIFACT` | FORENSIC | `WARNING` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/control_plane/artifact_repository.py:531` | `PREFIX_INGEST_ERROR` | USER, CONTROL_PLANE | `ERROR` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/control_plane/connection.py:179` | `PREFIX_DATABASE_SQLITE` | FORENSIC | `DEBUG` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/control_plane/connection.py:202` | `PREFIX_DATABASE_SQLITE` | FORENSIC | `DEBUG` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/control_plane/connection.py:203` | `CONTROL_PLANE_DIAGNOSTIC` | FORENSIC | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/control_plane/connection.py:216` | `CONTROL_PLANE_DIAGNOSTIC` | FORENSIC | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/control_plane/connection.py:265` | `PREFIX_DATABASE_SQLITE` | FORENSIC | `DEBUG` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/control_plane/connection.py:276` | `PREFIX_DATABASE_SQLITE` | FORENSIC | `INFO` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/control_plane/connection.py:380` | `PREFIX_DATABASE_SQLITE` | FORENSIC | `DEBUG` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/control_plane/connection.py:385` | `CONTROL_PLANE_DIAGNOSTIC` | FORENSIC | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/control_plane/connection.py:393` | `CONTROL_PLANE_DIAGNOSTIC` | FORENSIC | `WARNING` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/control_plane/connection.py:211` | `PREFIX_DATABASE_SQLITE` | FORENSIC | `WARNING` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/control_plane/connection.py:285` | `PREFIX_DATABASE_SQLITE` | FORENSIC | `INFO` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/control_plane/connection.py:298` | `CONTROL_PLANE_DIAGNOSTIC` | FORENSIC | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/control_plane/connection.py:395` | `CONTROL_PLANE_DIAGNOSTIC` | USER, CONTROL_PLANE | `ERROR` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/control_plane/file_sync.py:344` | `CONTROL_PLANE_DIAGNOSTIC` | FORENSIC | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/control_plane/file_sync.py:156` | `CONTROL_PLANE_DIAGNOSTIC` | FORENSIC | `WARNING` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/control_plane/file_sync.py:188` | `PREFIX_SYNC_REMOVED` | FORENSIC | `INFO` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/control_plane/file_sync.py:230` | `PREFIX_SYNC_HEALED` | FORENSIC | `INFO` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/control_plane/file_sync.py:241` | `PREFIX_SYNC_REPAIR` | FORENSIC | `WARNING` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/control_plane/file_sync.py:154` | `PREFIX_SYNC_RENAME` | FORENSIC | `DEBUG` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/control_plane/file_sync.py:162` | `CONTROL_PLANE_DIAGNOSTIC` | FORENSIC | `WARNING` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/control_plane/file_sync.py:252` | `CONTROL_PLANE_DIAGNOSTIC` | FORENSIC | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/control_plane/run_repository.py:566` | `PREFIX_CONTROL_PLANE` | FORENSIC | `WARNING` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/logging/setup.py:94` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/logging/setup.py:115` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/logging/setup.py:182` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/logging/setup.py:183` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/logging/setup.py:176` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/logging/setup.py:179` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/logging/setup.py:88` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/logging/setup.py:105` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/logging/setup.py:124` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/providers/files/csv.py:36` | `PREFIX_EXTRACT_CSV` | FORENSIC | `DEBUG` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/providers/files/csv.py:57` | `PREFIX_EXTRACT_CSV` | FORENSIC | `DEBUG` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/providers/files/csv.py:84` | `PREFIX_EXTRACT_CSV` | FORENSIC | `DEBUG` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/providers/files/csv.py:103` | `PREFIX_EXTRACT_CSV` | FORENSIC | `DEBUG` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/providers/files/excel.py:60` | `PREFIX_EXTRACT_EXCEL` | FORENSIC | `DEBUG` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/providers/files/excel.py:82` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/providers/files/excel.py:118` | `PREFIX_EXTRACT_EXCEL` | FORENSIC | `DEBUG` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/providers/files/excel.py:138` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/providers/files/excel.py:189` | `PREFIX_EXTRACT_EXCEL` | FORENSIC | `DEBUG` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/providers/files/excel.py:218` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/providers/files/excel.py:265` | `PREFIX_EXTRACT_EXCEL` | FORENSIC | `DEBUG` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/providers/files/excel.py:279` | `PREFIX_EXTRACT_EXCEL` | FORENSIC | `DEBUG` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/providers/files/excel.py:314` | `PREFIX_EXTRACT_EXCEL` | FORENSIC | `DEBUG` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/providers/files/excel.py:324` | `PREFIX_EXTRACT_EXCEL` | FORENSIC | `DEBUG` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/providers/files/excel.py:63` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/providers/files/excel.py:72` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/providers/files/excel.py:121` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/providers/files/excel.py:131` | `PREFIX_EXTRACT_EXCEL` | FORENSIC | `DEBUG` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/providers/files/excel.py:196` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/providers/files/excel.py:204` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/providers/files/excel.py:268` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/providers/files/excel.py:275` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/providers/files/excel.py:320` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/providers/files/excel.py:95` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `WARNING` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/providers/files/excel.py:99` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `WARNING` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/providers/files/excel.py:162` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `WARNING` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/providers/files/excel.py:170` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `WARNING` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/providers/files/excel.py:242` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `WARNING` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/providers/files/excel.py:246` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `WARNING` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/providers/files/locator.py:95` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/providers/files/locator.py:115` | `PREFIX_DISCOV` | FORENSIC | `INFO` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/providers/files/sqlite.py:95` | `PREFIX_EXTRACT_SQLITE` | FORENSIC | `DEBUG` | `run_id, stage, component` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/providers/market/benchmark.py:86` | `MARKET_SYNC_DIAGNOSTIC` | FORENSIC | `WARNING` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/providers/market/benchmark.py:168` | `MARKET_SYNC_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/providers/market/benchmark.py:182` | `MARKET_SYNC_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/providers/market/benchmark.py:212` | `MARKET_SYNC_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/providers/market/benchmark.py:333` | `MARKET_SYNC_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_USER_NARRATIVE` |
| `infrastructure/providers/market/benchmark.py:283` | `MARKET_SYNC_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_USER_NARRATIVE` |
| `infrastructure/providers/market/benchmark.py:377` | `MARKET_SYNC_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_USER_NARRATIVE` |
| `infrastructure/providers/market/common.py:100` | `MARKET_SYNC_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/providers/market/common.py:186` | `MARKET_SYNC_DIAGNOSTIC` | FORENSIC | `INFO` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/providers/market/common.py:119` | `MARKET_SYNC_DIAGNOSTIC` | FORENSIC | `WARNING` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/providers/market/currency.py:142` | `MARKET_SYNC_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/providers/market/currency.py:156` | `MARKET_SYNC_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/providers/market/currency.py:184` | `MARKET_SYNC_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/providers/market/currency.py:296` | `MARKET_SYNC_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_USER_NARRATIVE` |
| `infrastructure/providers/market/currency.py:250` | `MARKET_SYNC_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_USER_NARRATIVE` |
| `infrastructure/providers/market/currency.py:340` | `MARKET_SYNC_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_USER_NARRATIVE` |
| `infrastructure/providers/market/us_market.py:149` | `MARKET_SYNC_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/providers/market/us_market.py:179` | `MARKET_SYNC_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/providers/market/us_market.py:285` | `MARKET_SYNC_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_USER_NARRATIVE` |
| `infrastructure/providers/market/us_market.py:245` | `MARKET_SYNC_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_USER_NARRATIVE` |
| `infrastructure/providers/market/us_market.py:331` | `MARKET_SYNC_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component, provider, attempt, duration_ms` | `MIGRATE_TO_USER_NARRATIVE` |
| `infrastructure/recovery/backup.py:188` | `RECOVERY_DIAGNOSTIC` | FORENSIC | `ERROR` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/recovery/backup.py:208` | `RECOVERY_DIAGNOSTIC` | FORENSIC | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/recovery/backup.py:233` | `RECOVERY_DIAGNOSTIC` | FORENSIC | `ERROR` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/recovery/backup.py:242` | `RECOVERY_DIAGNOSTIC` | FORENSIC | `ERROR` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/recovery/backup.py:246` | `RECOVERY_DIAGNOSTIC` | FORENSIC | `ERROR` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/recovery/backup.py:216` | `RECOVERY_DIAGNOSTIC` | FORENSIC | `WARNING` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/recovery/restore.py:360` | `RECOVERY_DIAGNOSTIC` | FORENSIC | `INFO` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/recovery/restore.py:351` | `RECOVERY_DIAGNOSTIC` | FORENSIC | `ERROR` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/recovery/restore.py:381` | `RECOVERY_DIAGNOSTIC` | FORENSIC | `ERROR` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/recovery/restore.py:245` | `RECOVERY_DIAGNOSTIC` | FORENSIC | `CRITICAL` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/recovery/restore.py:332` | `RECOVERY_DIAGNOSTIC` | FORENSIC | `ERROR` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/recovery/restore.py:342` | `RECOVERY_DIAGNOSTIC` | FORENSIC | `WARNING` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/recovery/restore.py:398` | `RECOVERY_DIAGNOSTIC` | FORENSIC | `ERROR` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/recovery/restore.py:409` | `RECOVERY_DIAGNOSTIC` | FORENSIC | `ERROR` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/recovery/restore.py:262` | `RECOVERY_DIAGNOSTIC` | FORENSIC | `WARNING` | `run_id, stage, component` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/warehouse/bronze.py:261` | `BRONZE_LAKEHOUSE_DIAGNOSTIC` | FORENSIC | `INFO` | `run_id, stage, component, table_name, rows, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/warehouse/bronze.py:331` | `BRONZE_LAKEHOUSE_DIAGNOSTIC` | FORENSIC | `INFO` | `run_id, stage, component, table_name, rows, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/warehouse/bronze.py:103` | `BRONZE_LAKEHOUSE_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, table_name, rows, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/warehouse/bronze.py:111` | `PREFIX_BRONZE_DETAIL` | FORENSIC | `DEBUG` | `run_id, stage, component, table_name, rows, duration_ms` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/warehouse/bronze.py:137` | `PREFIX_BRONZE_DETAIL` | FORENSIC | `DEBUG` | `run_id, stage, component, table_name, rows, duration_ms` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/warehouse/bronze.py:139` | `BRONZE_LAKEHOUSE_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, table_name, rows, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/warehouse/bronze.py:150` | `BRONZE_LAKEHOUSE_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, table_name, rows, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/warehouse/bronze.py:182` | `BRONZE_LAKEHOUSE_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, table_name, rows, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/warehouse/bronze.py:79` | `BRONZE_LAKEHOUSE_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, table_name, rows, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/warehouse/bronze.py:72` | `BRONZE_LAKEHOUSE_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, table_name, rows, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/warehouse/bronze.py:226` | `BRONZE_LAKEHOUSE_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, table_name, rows, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/warehouse/bronze.py:243` | `BRONZE_LAKEHOUSE_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, table_name, rows, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/warehouse/bronze.py:296` | `BRONZE_LAKEHOUSE_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, table_name, rows, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/warehouse/bronze.py:343` | `BRONZE_LAKEHOUSE_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, table_name, rows, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/warehouse/bronze.py:352` | `BRONZE_LAKEHOUSE_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, table_name, rows, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/warehouse/connection.py:72` | `PREFIX_DATABASE_DUCKDB` | FORENSIC | `DEBUG` | `run_id, stage, component, table_name, rows, duration_ms` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/warehouse/connection.py:77` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, table_name, rows, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/warehouse/connection.py:85` | `PREFIX_DATABASE_DUCKDB` | FORENSIC | `DEBUG` | `run_id, stage, component, table_name, rows, duration_ms` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/warehouse/connection.py:89` | `PREFIX_DATABASE_DUCKDB` | FORENSIC | `DEBUG` | `run_id, stage, component, table_name, rows, duration_ms` | `CONVERT_PREFIX_TO_STRUCTURED_EVENT` |
| `infrastructure/warehouse/connection.py:91` | `GENERIC_APPLICATION_DIAGNOSTIC` | FORENSIC | `WARNING` | `run_id, stage, component, table_name, rows, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/warehouse/gold.py:64` | `GOLD_MART_DIAGNOSTIC` | FORENSIC | `INFO` | `run_id, stage, component, table_name, rows, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/warehouse/gold.py:87` | `GOLD_MART_DIAGNOSTIC` | FORENSIC | `INFO` | `run_id, stage, component, table_name, rows, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/warehouse/gold.py:45` | `GOLD_MART_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, table_name, rows, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/warehouse/meta/healing.py:242` | `META_LAYER_DIAGNOSTIC` | FORENSIC | `INFO` | `run_id, stage, component, table_name, rows, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/warehouse/meta/healing.py:278` | `META_LAYER_DIAGNOSTIC` | FORENSIC | `WARNING` | `run_id, stage, component, table_name, rows, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/warehouse/meta/healing.py:285` | `META_LAYER_DIAGNOSTIC` | FORENSIC | `INFO` | `run_id, stage, component, table_name, rows, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/warehouse/meta/layer.py:365` | `META_LAYER_DIAGNOSTIC` | FORENSIC | `INFO` | `run_id, stage, component, table_name, rows, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/warehouse/meta/layer.py:385` | `META_LAYER_DIAGNOSTIC` | FORENSIC | `INFO` | `run_id, stage, component, table_name, rows, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/warehouse/meta/layer.py:106` | `META_LAYER_DIAGNOSTIC` | FORENSIC | `DEBUG` | `run_id, stage, component, table_name, rows, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/warehouse/meta/layer.py:299` | `META_LAYER_DIAGNOSTIC` | FORENSIC | `WARNING` | `run_id, stage, component, table_name, rows, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/warehouse/meta/layer.py:343` | `META_LAYER_DIAGNOSTIC` | FORENSIC | `INFO` | `run_id, stage, component, table_name, rows, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/warehouse/meta/layer.py:350` | `META_LAYER_DIAGNOSTIC` | FORENSIC | `WARNING` | `run_id, stage, component, table_name, rows, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/warehouse/silver.py:150` | `SILVER_MART_DIAGNOSTIC` | FORENSIC | `INFO` | `run_id, stage, component, table_name, rows, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/warehouse/silver.py:173` | `SILVER_MART_DIAGNOSTIC` | FORENSIC | `INFO` | `run_id, stage, component, table_name, rows, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/warehouse/silver.py:89` | `SILVER_MART_DIAGNOSTIC` | FORENSIC | `ERROR` | `run_id, stage, component, table_name, rows, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/warehouse/silver.py:94` | `SILVER_MART_DIAGNOSTIC` | FORENSIC | `ERROR` | `run_id, stage, component, table_name, rows, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `infrastructure/warehouse/silver.py:98` | `SILVER_MART_DIAGNOSTIC` | FORENSIC | `ERROR` | `run_id, stage, component, table_name, rows, duration_ms` | `MIGRATE_TO_FORENSIC_EVENT` |
| `presentation/desktop/app.py:329` | `GENERIC_APPLICATION_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_USER_NARRATIVE` |
| `presentation/desktop/app.py:436` | `GENERIC_APPLICATION_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_USER_NARRATIVE` |
| `presentation/desktop/app.py:315` | `GENERIC_APPLICATION_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_USER_NARRATIVE` |
| `presentation/desktop/app.py:370` | `GENERIC_APPLICATION_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_USER_NARRATIVE` |
| `presentation/desktop/app.py:380` | `GENERIC_APPLICATION_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_USER_NARRATIVE` |
| `presentation/desktop/app.py:390` | `GENERIC_APPLICATION_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_USER_NARRATIVE` |
| `presentation/desktop/app.py:446` | `GENERIC_APPLICATION_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_USER_NARRATIVE` |
| `presentation/desktop/app.py:456` | `GENERIC_APPLICATION_DIAGNOSTIC` | USER | `INFO` | `run_id, stage, component` | `MIGRATE_TO_USER_NARRATIVE` |
| `application/pipeline/worker.py:124-125` | `STREAM_STDOUT_CAPTURE` | FORENSIC | `DEBUG` | `run_id, stage, worker_id` | `DEMOLISH_SEVERITY_INFERENCE` |
| `application/pipeline/lifecycle.py:326` | `CONTROL_PLANE_ARCHIVE_LOG` | CONTROL_PLANE | `INFO` | `run_id, log_size_bytes, compression_ratio` | `BENCHMARK_AND_OPTIMIZE_ZLIB_LEVEL` |
| `application/pipeline/lifecycle.py:308` | `CONTROL_PLANE_FAIL_TELEMETRY` | CONTROL_PLANE, USER | `ERROR` | `run_id, stage, failure_domain, exception_type` | `MIGRATE_TO_STRUCTURED_FAILURE_EVENT` |
