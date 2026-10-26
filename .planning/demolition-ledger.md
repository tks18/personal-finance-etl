# Observability Demolition Census Ledger & Phase 0 Baseline Report

> **Classification Target State**: Every surviving legacy logging callsite, status queue transport,
> and heuristic string-parsing mechanism is cataloged and assigned an explicit migration destination.

## 1. Executive Summary & Ledger Statistics

- **Total Cataloged Callsites**: 302
- **MIGRATE**: 290 callsites (to be transformed into canonical `ObservabilityEvent`)
- **DELETE**: 7 callsites (to be permanently eradicated: `infer_log_level`, raw config dumps, dead helpers)
- **SEPARATE_DATA_TRANSPORT**: 3 callsites (isolating `DataFrame` from status payloads)
- **KEEP_AS_ADAPTER**: 2 callsites (raw stdout/stderr compatibility capture)

### Breakdown by Functional Category

| Category | Total Callsites | MIGRATE | DELETE | SEPARATE_DATA_TRANSPORT | KEEP_AS_ADAPTER |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Application / Infrastructure Logging | 153 | 153 | 0 | 0 | 0 |
| Configuration / Rules Dump | 2 | 0 | 2 | 0 | 0 |
| Direct Forensic Sink Registration | 1 | 0 | 1 | 0 | 0 |
| Domain Service Logging | 10 | 10 | 0 | 0 | 0 |
| EngineStatusMessage Construction | 42 | 42 | 0 | 0 | 0 |
| Lifecycle & Recovery Logging | 32 | 32 | 0 | 0 | 0 |
| Provider & Worker Logging | 47 | 47 | 0 | 0 | 0 |
| QueueStream | 6 | 6 | 0 | 0 | 0 |
| Stdout / Stderr Capture | 2 | 0 | 0 | 0 | 2 |
| UI Progress / Data Transport | 3 | 0 | 0 | 3 | 0 |
| infer_log_level Reference | 4 | 0 | 4 | 0 | 0 |

---

## 2. Authoritative Phase 0 Performance Baseline

Empirical evidence captured under production conditions for regression gate certification (Phases 12 & 13):

### 2.1 Operational Pipeline Baselines
- **Cached Pipeline Execution Median**: 28.0 s
- **Cold Pipeline Execution Median**: 48.0 s
- **Estimated Event Volume**: ~1200 events / run
- **Cached Normal Mode Acceptance Gate (≤0.5% regression)**: $\le 28.140$ s
- **Cold Normal Mode Acceptance Gate (≤0.5% regression)**: $\le 48.240$ s
- **Debug Mode Acceptance Gate (≤1.5% regression)**: $\le 28.420$ s

### 2.2 Live Production Run Evidence
- **Runtime**: 28.81 s
- **Transformed Nodes**: 46
- **Unique ISINs**: 147
- **Financial Files Scanned**: 1627
- **Open Tax Lots Tracked**: 341
- **Raw Trace Size**: 339.4 KB (1192 lines)
- **Compressed Trace Size (Zlib Level 6)**: 32.9 KB (10.32x compression ratio)

### 2.3 Legacy Logging Micro-Benchmark (10,000 Records)
- **Total Elapsed Time**: 200.59 ms
- **Throughput**: 49,853 records/second
- **Log File Size**: 2450.8 KB
- **Peak Memory RSS**: 28.46 MB
- **CPU Impact**: 0.0%

| Compression Level | Compressed Size | Compression Ratio | Compression Duration |
| :---: | :---: | :---: | :---: |
| Level 1 | 44.3 KB | 55.26x | 4.216 ms |
| Level 6 | 35.9 KB | 68.28x | 11.361 ms |
| Level 9 | 27.0 KB | 90.63x | 16.484 ms |

---

## 3. Comprehensive Callsite Demolition Ledger

| Category | Classification | File & Line | Target Symbol | Action & Strategy |
| :--- | :---: | :--- | :--- | :--- |
| Configuration / Rules Dump | **DELETE** | `src/personal_finance_etl/application/pipeline/lifecycle.py:92` | `logger.debug(...)` | Full unrestricted configuration/rules JSON dump in logger. Replace with SYSTEM_CONFIG_FINGERPRINT. |
| Configuration / Rules Dump | **DELETE** | `src/personal_finance_etl/application/pipeline/lifecycle.py:100` | `logger.debug(...)` | Full unrestricted configuration/rules JSON dump in logger. Replace with SYSTEM_CONFIG_FINGERPRINT. |
| Direct Forensic Sink Registration | **DELETE** | `src/personal_finance_etl/application/pipeline/lifecycle.py:162` | `JsonlForensicSink(...)` | Direct synchronous forensic sink attachment on execution path. Replace with async queue/listener. |
| infer_log_level Reference | **DELETE** | `tests/test_legacy_logging_demolition.py:106` | `infer_log_level(...)` | Prohibited string/boolean severity inference. Eradicate completely. |
| infer_log_level Reference | **DELETE** | `tests/test_legacy_logging_demolition.py:107` | `infer_log_level(...)` | Prohibited string/boolean severity inference. Eradicate completely. |
| infer_log_level Reference | **DELETE** | `tests/test_legacy_logging_demolition.py:108` | `infer_log_level(...)` | Prohibited string/boolean severity inference. Eradicate completely. |
| infer_log_level Reference | **DELETE** | `tests/test_legacy_logging_demolition.py:109` | `infer_log_level(...)` | Prohibited string/boolean severity inference. Eradicate completely. |
| Stdout / Stderr Capture | **KEEP_AS_ADAPTER** | `src/personal_finance_etl/application/pipeline/worker.py:116` | `sys.stdout = ...` | Subprocess stdout/stderr capture stream. Retain as explicit adapter emitting RAW_STDOUT / RAW_STDERR. |
| Stdout / Stderr Capture | **KEEP_AS_ADAPTER** | `src/personal_finance_etl/application/pipeline/worker.py:117` | `sys.stderr = ...` | Subprocess stdout/stderr capture stream. Retain as explicit adapter emitting RAW_STDOUT / RAW_STDERR. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/ingestion/asset_strategies.py:100` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/ingestion/asset_strategies.py:106` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/ingestion/asset_strategies.py:111` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/ingestion/asset_strategies.py:116` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/ingestion/asset_strategies.py:213` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/ingestion/asset_strategies.py:218` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/ingestion/asset_strategies.py:260` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/ingestion/asset_strategies.py:267` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/ingestion/asset_strategies.py:276` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/ingestion/asset_strategies.py:281` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/ingestion/coordinator.py:93` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/ingestion/coordinator.py:102` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/ingestion/coordinator.py:216` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/ingestion/coordinator.py:259` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/application/ingestion/coordinator.py:267` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/ingestion/coordinator.py:299` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/ingestion/coordinator.py:303` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/application/ingestion/coordinator.py:320` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/ingestion/coordinator.py:342` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/application/ingestion/coordinator.py:351` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/ingestion/market_sync.py:85` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/ingestion/market_sync.py:103` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/ingestion/market_sync.py:111` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/ingestion/market_sync.py:152` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/ingestion/market_sync.py:153` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/application/ingestion/market_sync.py:162` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/application/ingestion/market_sync.py:184` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/application/ingestion/market_sync.py:197` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/application/ingestion/market_sync.py:211` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/ingestion/market_sync.py:274` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/ingestion/market_sync.py:278` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/ingestion/market_sync.py:288` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/ingestion/market_sync.py:328` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/ingestion/market_sync.py:330` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/ingestion/market_sync.py:358` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/ingestion/market_sync.py:392` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/ingestion/market_sync.py:411` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/ingestion/market_sync.py:469` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/ingestion/market_sync.py:470` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/application/ingestion/market_sync.py:479` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/application/ingestion/market_sync.py:501` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/application/ingestion/market_sync.py:514` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/application/ingestion/market_sync.py:533` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/application/investments/aggregation_service/pipeline.py:58` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/investments/aggregation_service/pipeline.py:77` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/investments/aggregation_service/pipeline.py:87` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/investments/aggregation_service/pipeline.py:92` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/application/investments/context.py:192` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/application/investments/isin_service/pipeline.py:288` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/investments/isin_service/pipeline.py:464` | `logger.error(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/investments/isin_service/pipeline.py:473` | `logger.error(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/investments/isin_service/pipeline.py:493` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/investments/isin_service/processor.py:126` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/application/investments/isin_service/worker.py:103` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/application/investments/isin_service/worker.py:112` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/application/investments/isin_service/worker.py:120` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/investments/quant_service.py:112` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/execution.py:200` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/application/pipeline/execution.py:201` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/execution.py:242` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/execution.py:253` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/execution.py:279` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/application/pipeline/execution.py:280` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/execution.py:293` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/application/pipeline/execution.py:294` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/execution.py:296` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/execution.py:356` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/execution.py:372` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/execution.py:401` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/execution.py:408` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/execution.py:469` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/execution.py:485` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/execution.py:497` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/execution.py:506` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/execution.py:515` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/execution.py:535` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/execution.py:568` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/execution.py:584` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/execution.py:594` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/execution.py:612` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/execution.py:613` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Lifecycle & Recovery Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/lifecycle.py:98` | `logger.debug(...)` | Lifecycle state or recovery diagnostic log. Migrate to canonical ObservabilityEvent. |
| Lifecycle & Recovery Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/lifecycle.py:106` | `logger.debug(...)` | Lifecycle state or recovery diagnostic log. Migrate to canonical ObservabilityEvent. |
| Lifecycle & Recovery Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/lifecycle.py:107` | `logger.debug(...)` | Lifecycle state or recovery diagnostic log. Migrate to canonical ObservabilityEvent. |
| Lifecycle & Recovery Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/lifecycle.py:124` | `logger.info(...)` | Lifecycle state or recovery diagnostic log. Migrate to canonical ObservabilityEvent. |
| Lifecycle & Recovery Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/lifecycle.py:174` | `logger.warning(...)` | Lifecycle state or recovery diagnostic log. Migrate to canonical ObservabilityEvent. |
| Lifecycle & Recovery Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/lifecycle.py:188` | `logger.debug(...)` | Lifecycle state or recovery diagnostic log. Migrate to canonical ObservabilityEvent. |
| Lifecycle & Recovery Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/lifecycle.py:217` | `logger.debug(...)` | Lifecycle state or recovery diagnostic log. Migrate to canonical ObservabilityEvent. |
| Lifecycle & Recovery Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/lifecycle.py:255` | `logger.info(...)` | Lifecycle state or recovery diagnostic log. Migrate to canonical ObservabilityEvent. |
| Lifecycle & Recovery Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/lifecycle.py:279` | `logger.debug(...)` | Lifecycle state or recovery diagnostic log. Migrate to canonical ObservabilityEvent. |
| Lifecycle & Recovery Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/lifecycle.py:281` | `logger.warning(...)` | Lifecycle state or recovery diagnostic log. Migrate to canonical ObservabilityEvent. |
| Lifecycle & Recovery Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/lifecycle.py:289` | `logger.error(...)` | Lifecycle state or recovery diagnostic log. Migrate to canonical ObservabilityEvent. |
| Lifecycle & Recovery Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/lifecycle.py:291` | `logger.warning(...)` | Lifecycle state or recovery diagnostic log. Migrate to canonical ObservabilityEvent. |
| Lifecycle & Recovery Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/lifecycle.py:297` | `logger.error(...)` | Lifecycle state or recovery diagnostic log. Migrate to canonical ObservabilityEvent. |
| Lifecycle & Recovery Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/lifecycle.py:375` | `logger.exception(...)` | Lifecycle state or recovery diagnostic log. Migrate to canonical ObservabilityEvent. |
| Lifecycle & Recovery Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/lifecycle.py:382` | `logger.error(...)` | Lifecycle state or recovery diagnostic log. Migrate to canonical ObservabilityEvent. |
| Lifecycle & Recovery Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/lifecycle.py:403` | `logger.info(...)` | Lifecycle state or recovery diagnostic log. Migrate to canonical ObservabilityEvent. |
| Lifecycle & Recovery Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/lifecycle.py:432` | `logger.debug(...)` | Lifecycle state or recovery diagnostic log. Migrate to canonical ObservabilityEvent. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/application/pipeline/orchestrator.py:117` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/application/pipeline/orchestrator.py:135` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/orchestrator.py:142` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/transformer.py:81` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/transformer.py:106` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/transformer.py:129` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/transformer.py:162` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/transformer.py:169` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/transformer.py:182` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/transformer.py:184` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/application/pipeline/transformer.py:186` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/transformer.py:215` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/transformer.py:219` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/transformer.py:225` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/transformer.py:230` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/pipeline/transformer.py:234` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/application/pipeline/worker.py:68` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/application/pipeline/worker.py:83` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| QueueStream | **MIGRATE** | `src/personal_finance_etl/application/pipeline/worker.py:116` | `QueueStream(...)` | Stdout/stderr interception wrapper. Reduce to raw canonical stdout/stderr adapter or remove. |
| QueueStream | **MIGRATE** | `src/personal_finance_etl/application/pipeline/worker.py:117` | `QueueStream(...)` | Stdout/stderr interception wrapper. Reduce to raw canonical stdout/stderr adapter or remove. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/application/pipeline/worker.py:128` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/application/pipeline/worker.py:189` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/application/pipeline/worker.py:198` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/wealth/wealth_service.py:132` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/wealth/wealth_service.py:133` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/application/wealth/wealth_service.py:140` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/contracts/observability.py:482` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| Domain Service Logging | **MIGRATE** | `src/personal_finance_etl/domain/fire/inflation.py:174` | `logger.error(...)` | Domain computation logging. Replace with boundary ObservabilityEvent or module logger. |
| Domain Service Logging | **MIGRATE** | `src/personal_finance_etl/domain/market/benchmarks.py:58` | `logger.warning(...)` | Domain computation logging. Replace with boundary ObservabilityEvent or module logger. |
| Domain Service Logging | **MIGRATE** | `src/personal_finance_etl/domain/market/benchmarks.py:162` | `logger.warning(...)` | Domain computation logging. Replace with boundary ObservabilityEvent or module logger. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/domain/market/benchmarks.py:205` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| Domain Service Logging | **MIGRATE** | `src/personal_finance_etl/domain/market/benchmarks.py:219` | `logger.info(...)` | Domain computation logging. Replace with boundary ObservabilityEvent or module logger. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/domain/market/benchmarks.py:222` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| Domain Service Logging | **MIGRATE** | `src/personal_finance_etl/domain/market/macro.py:190` | `logger.error(...)` | Domain computation logging. Replace with boundary ObservabilityEvent or module logger. |
| Domain Service Logging | **MIGRATE** | `src/personal_finance_etl/domain/market/macro.py:191` | `logger.error(...)` | Domain computation logging. Replace with boundary ObservabilityEvent or module logger. |
| Domain Service Logging | **MIGRATE** | `src/personal_finance_etl/domain/market/macro.py:299` | `logger.warning(...)` | Domain computation logging. Replace with boundary ObservabilityEvent or module logger. |
| Domain Service Logging | **MIGRATE** | `src/personal_finance_etl/domain/market/macro.py:340` | `logger.warning(...)` | Domain computation logging. Replace with boundary ObservabilityEvent or module logger. |
| Domain Service Logging | **MIGRATE** | `src/personal_finance_etl/domain/market/macro.py:366` | `logger.warning(...)` | Domain computation logging. Replace with boundary ObservabilityEvent or module logger. |
| Domain Service Logging | **MIGRATE** | `src/personal_finance_etl/domain/market/macro.py:392` | `logger.warning(...)` | Domain computation logging. Replace with boundary ObservabilityEvent or module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/control_plane/artifact_repository.py:190` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/control_plane/artifact_repository.py:334` | `logger.warning(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/control_plane/artifact_repository.py:531` | `logger.exception(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/control_plane/artifact_repository.py:534` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/control_plane/artifact_repository.py:677` | `logger.warning(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/control_plane/artifact_repository.py:709` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/control_plane/artifact_repository.py:774` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/control_plane/artifact_repository.py:876` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/control_plane/connection.py:179` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/control_plane/connection.py:202` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/control_plane/connection.py:203` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/control_plane/connection.py:211` | `logger.warning(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/control_plane/connection.py:216` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/control_plane/connection.py:265` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/control_plane/connection.py:276` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/control_plane/connection.py:285` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/control_plane/connection.py:298` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/control_plane/connection.py:380` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/control_plane/connection.py:385` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/control_plane/connection.py:393` | `logger.warning(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/control_plane/connection.py:395` | `logger.exception(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/control_plane/file_sync.py:154` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/control_plane/file_sync.py:156` | `logger.warning(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/control_plane/file_sync.py:162` | `logger.warning(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/control_plane/file_sync.py:188` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/control_plane/file_sync.py:230` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/control_plane/file_sync.py:241` | `logger.warning(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/control_plane/file_sync.py:252` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/control_plane/file_sync.py:344` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/control_plane/run_repository.py:622` | `logger.warning(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/observability/archival.py:101` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/observability/archival.py:114` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/observability/archival.py:122` | `logger.warning(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/observability/archival.py:154` | `logger.warning(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/observability/archival.py:169` | `logger.warning(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/observability/retention.py:109` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/observability/retention.py:125` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/observability/retention.py:127` | `logger.warning(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/observability/retention.py:134` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/files/csv.py:36` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/files/csv.py:57` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/files/csv.py:84` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/files/csv.py:103` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/files/excel.py:60` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/files/excel.py:63` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/files/excel.py:72` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/files/excel.py:82` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/files/excel.py:95` | `logger.warning(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/files/excel.py:99` | `logger.warning(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/files/excel.py:118` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/files/excel.py:121` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/files/excel.py:131` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/files/excel.py:138` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/files/excel.py:162` | `logger.warning(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/files/excel.py:170` | `logger.warning(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/files/excel.py:189` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/files/excel.py:196` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/files/excel.py:204` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/files/excel.py:216` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/files/excel.py:240` | `logger.warning(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/files/excel.py:244` | `logger.warning(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/files/excel.py:263` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/files/excel.py:266` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/files/excel.py:273` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/files/excel.py:277` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/files/excel.py:312` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/files/excel.py:318` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/files/excel.py:322` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/files/locator.py:95` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/files/locator.py:113` | `logger.info(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/files/sqlite.py:95` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/market/benchmark.py:104` | `logger.warning(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/market/benchmark.py:186` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/market/benchmark.py:200` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/market/benchmark.py:230` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/market/benchmark.py:403` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/market/benchmark.py:447` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/market/common.py:100` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/market/common.py:119` | `logger.warning(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/market/common.py:186` | `logger.info(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/market/currency.py:160` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/market/currency.py:174` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/market/currency.py:202` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/market/currency.py:366` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/market/currency.py:410` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/market/us_market.py:167` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| Provider & Worker Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/market/us_market.py:197` | `logger.debug(...)` | Provider/worker diagnostic call. Migrate to canonical ObservabilityEvent. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/market/us_market.py:355` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/infrastructure/providers/market/us_market.py:401` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| Lifecycle & Recovery Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/recovery/backup.py:188` | `logger.error(...)` | Lifecycle state or recovery diagnostic log. Migrate to canonical ObservabilityEvent. |
| Lifecycle & Recovery Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/recovery/backup.py:208` | `logger.info(...)` | Lifecycle state or recovery diagnostic log. Migrate to canonical ObservabilityEvent. |
| Lifecycle & Recovery Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/recovery/backup.py:216` | `logger.warning(...)` | Lifecycle state or recovery diagnostic log. Migrate to canonical ObservabilityEvent. |
| Lifecycle & Recovery Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/recovery/backup.py:233` | `logger.error(...)` | Lifecycle state or recovery diagnostic log. Migrate to canonical ObservabilityEvent. |
| Lifecycle & Recovery Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/recovery/backup.py:242` | `logger.error(...)` | Lifecycle state or recovery diagnostic log. Migrate to canonical ObservabilityEvent. |
| Lifecycle & Recovery Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/recovery/backup.py:246` | `logger.error(...)` | Lifecycle state or recovery diagnostic log. Migrate to canonical ObservabilityEvent. |
| Lifecycle & Recovery Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/recovery/restore.py:245` | `logger.critical(...)` | Lifecycle state or recovery diagnostic log. Migrate to canonical ObservabilityEvent. |
| Lifecycle & Recovery Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/recovery/restore.py:262` | `logger.warning(...)` | Lifecycle state or recovery diagnostic log. Migrate to canonical ObservabilityEvent. |
| Lifecycle & Recovery Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/recovery/restore.py:332` | `logger.error(...)` | Lifecycle state or recovery diagnostic log. Migrate to canonical ObservabilityEvent. |
| Lifecycle & Recovery Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/recovery/restore.py:342` | `logger.warning(...)` | Lifecycle state or recovery diagnostic log. Migrate to canonical ObservabilityEvent. |
| Lifecycle & Recovery Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/recovery/restore.py:351` | `logger.error(...)` | Lifecycle state or recovery diagnostic log. Migrate to canonical ObservabilityEvent. |
| Lifecycle & Recovery Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/recovery/restore.py:360` | `logger.info(...)` | Lifecycle state or recovery diagnostic log. Migrate to canonical ObservabilityEvent. |
| Lifecycle & Recovery Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/recovery/restore.py:381` | `logger.error(...)` | Lifecycle state or recovery diagnostic log. Migrate to canonical ObservabilityEvent. |
| Lifecycle & Recovery Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/recovery/restore.py:398` | `logger.error(...)` | Lifecycle state or recovery diagnostic log. Migrate to canonical ObservabilityEvent. |
| Lifecycle & Recovery Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/recovery/restore.py:409` | `logger.error(...)` | Lifecycle state or recovery diagnostic log. Migrate to canonical ObservabilityEvent. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/bronze.py:91` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/bronze.py:98` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/bronze.py:122` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/bronze.py:130` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/bronze.py:156` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/bronze.py:158` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/bronze.py:169` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/bronze.py:199` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/bronze.py:241` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/bronze.py:258` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/bronze.py:292` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/bronze.py:327` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/bronze.py:362` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/bronze.py:374` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/bronze.py:383` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/connection.py:72` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/connection.py:77` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/connection.py:85` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/connection.py:89` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/connection.py:91` | `logger.warning(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/gold.py:62` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/gold.py:79` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/gold.py:118` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/meta/healing.py:242` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/meta/healing.py:278` | `logger.warning(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/meta/healing.py:285` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/meta/layer.py:106` | `logger.debug(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/meta/layer.py:299` | `logger.warning(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/meta/layer.py:343` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/meta/layer.py:350` | `logger.warning(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/meta/layer.py:365` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/meta/layer.py:385` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/silver.py:106` | `logger.error(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/silver.py:111` | `logger.error(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/silver.py:115` | `logger.error(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/silver.py:167` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| Application / Infrastructure Logging | **MIGRATE** | `src/personal_finance_etl/infrastructure/warehouse/silver.py:206` | `logger.info(...)` | General logger invocation. Normalize to ObservabilityEvent or scoped module logger. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/presentation/desktop/app.py:315` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/presentation/desktop/app.py:329` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/presentation/desktop/app.py:370` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/presentation/desktop/app.py:380` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/presentation/desktop/app.py:390` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/presentation/desktop/app.py:436` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/presentation/desktop/app.py:446` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| EngineStatusMessage Construction | **MIGRATE** | `src/personal_finance_etl/presentation/desktop/app.py:456` | `EngineStatusMessage(...)` | Direct EngineStatusMessage instantiation. Migrate to ObservabilityEvent. |
| QueueStream | **MIGRATE** | `tests/test_legacy_logging_demolition.py:83` | `QueueStream(...)` | Stdout/stderr interception wrapper. Reduce to raw canonical stdout/stderr adapter or remove. |
| QueueStream | **MIGRATE** | `tests/test_legacy_logging_demolition.py:96` | `QueueStream(...)` | Stdout/stderr interception wrapper. Reduce to raw canonical stdout/stderr adapter or remove. |
| QueueStream | **MIGRATE** | `tests/test_phase9_orchestration_and_bootstrap.py:217` | `QueueStream(...)` | Stdout/stderr interception wrapper. Reduce to raw canonical stdout/stderr adapter or remove. |
| QueueStream | **MIGRATE** | `tests/test_phase9_orchestration_and_bootstrap.py:228` | `QueueStream(...)` | Stdout/stderr interception wrapper. Reduce to raw canonical stdout/stderr adapter or remove. |
| UI Progress / Data Transport | **SEPARATE_DATA_TRANSPORT** | `src/personal_finance_etl/application/investments/quant_service.py:88` | `EngineStatusMessage(data=...)` | Carries DataFrame payload across status channel. Separate into typed data transport contract. |
| UI Progress / Data Transport | **SEPARATE_DATA_TRANSPORT** | `src/personal_finance_etl/application/pipeline/worker.py:172` | `EngineStatusMessage(data=...)` | Carries DataFrame payload across status channel. Separate into typed data transport contract. |
| UI Progress / Data Transport | **SEPARATE_DATA_TRANSPORT** | `tests/test_legacy_logging_demolition.py:71` | `EngineStatusMessage(data=...)` | Carries DataFrame payload across status channel. Separate into typed data transport contract. |

---

## 4. Phase 0 Success Gate Sign-Off

- [x] 100% of legacy logging and status callsites cataloged and classified.
- [x] Baseline performance benchmarks recorded in `.planning/baseline_benchmark.json`.
- [x] Demolition ledger committed to `.planning/demolition-ledger.md`.
- [x] Zero unidentified logging or status paths remaining.