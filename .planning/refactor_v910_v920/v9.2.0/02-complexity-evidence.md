# v9.2.0 — Complexity Evidence

| Measure | v9.0.1 |
| --- | ---: |
| Public functions >80 lines | 56 |
| Public functions >150 lines | 27 |
| Estimated CC >=10 | ~70 |
| Estimated CC >=20 | 17 |
| Estimated CC >=30 | 10 |
| Nesting depth >=4 | 32 |
| Nesting depth >=5 | 17 |

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

Metrics guide review; they are not scoreboards.
