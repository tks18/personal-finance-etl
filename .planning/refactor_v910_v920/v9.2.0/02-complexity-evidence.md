# v9.2.0 — Complexity Evidence

| Measure | v9.0.1 | v9.2.0 Phase 1 Target |
| --- | ---: | ---: |
| Public functions >80 lines | 56 | 56 |
| Public functions >150 lines | 27 | 27 |
| Estimated CC >=10 | ~70 | ~70 |
| Estimated CC >=20 | 17 | 17 |
| Estimated CC >=30 | 10 | 10 |
| Nesting depth >=4 | 32 | 32 |
| Nesting depth >=5 | 17 | 17 |

## Highest-value hotspots

| Function | Lines | Approx. CC | Treatment |
| --- | ---: | ---: | --- |
| `IsinProcessor.process` | 655 | 129 | Highest-priority decomposition |
| `_run_mc_simulations_numba` | 435 | 80 | Numerical-kernel exception unless evidence says otherwise |
| `SnapshotGenerator.generate` | 266 | 47 | Decompose cohesive responsibilities |
| `FileSyncService._sync_with_disk` | 171 | 42 | Simplify state/branching |
| `restore_snapshot` | 219 | 40 | Simplify recovery branches carefully |
| `IsinPipeline.process_all` | 316 | 34 | Decompose orchestration |
| `heal_duckdb_registry` | 95 | 32 | Simplify recovery decisions |
| `map_quant_sub_head` | 76 | 31 | High priority despite modest length |
| `AggregationService.run` | 457 | 24 | Split sequential aggregation responsibilities |

## Phase 1 Hotspot Classification Summary

| Classification Disposition | Count | Architectural Intent |
| --- | ---: | --- |
| `DECOMPOSE` | 14 | Multi-stage orchestrators decomposed into cohesive sub-routines |
| `SIMPLIFY_BRANCHING` | 31 | Complex condition ladders streamlined via guard clauses and dispatch |
| `EXTRACT_POLICY` | 4 | Hardcoded rules extracted into declarative policy lookup tables |
| `KEEP_COHESIVE` | 41 | Linear LazyFrame pipelines preserved to avoid artificial fragmentation |
| `NUMERICAL_KERNEL_EXCEPTION` | 1 | Numba JIT Monte Carlo simulation kernel preserved for performance |
| `DECLARATIVE_EXCEPTION` | 6 | Declarative layout, HTML templates, and schema tables preserved |
| `STATEFUL_ALGORITHM_EXCEPTION` | 4 | Inherently sequential FIFO matching and XIRR bisection algorithms |
| **Total Callables Classified** | **101** | **100% of remediation map categorized prior to refactoring** |

Metrics guide review; they are not scoreboards.
