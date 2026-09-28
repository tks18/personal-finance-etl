# Architecture

This section explains **how Personal Finance ETL is put together and why those boundaries exist**.

The current architecture separates operational truth from analytical state:

```mermaid
flowchart LR
    SRC["Sources"] --> CP["SQLite Control Plane<br/>evidence · runs · failures · provenance"]
    CP --> BR["DuckDB Bronze<br/>16 contracts"]
    BR --> CAN["Canonical Polars Model"]
    CAN --> ENG["Investment + Wealth Engines"]
    ENG --> SG["Silver + Gold<br/>20 Silver · 17 Gold"]
    CP -. projection .-> META["Lean DuckDB Meta<br/>5 tables"]
```

> **SQLite owns operational truth and raw evidence. DuckDB owns analytical state.**

The current physical contract surface is:

```text
SQLite Control Plane   6 tables
DuckDB Bronze         16 contracts
DuckDB Silver         20 contracts
DuckDB Gold           17 marts
DuckDB Meta            5 tables
```

Reliability is part of the architecture rather than an operational afterthought: stale-run recovery, `PENDING_BRONZE` replay, artifact-level Bronze healing, cross-process forensic logging, and coordinated Snapshot/Restore all reuse the same ownership boundaries described in this section.


## Production boundary

The Control Plane exposes focused repositories rather than leaking SQLite mechanics into orchestration:

```python
class ControlPlane:
    def __init__(self, base_path: str, db_name: str = "Raw_Documents.sqlite"):
        self.db = SQLiteManager(base_path, db_name)
        self.artifacts = ArtifactRepository(self.db)
        self.runs = RunRepository(self.db)
        self.file_sync = FileSyncService(self.artifacts)
```

That boundary now anchors artifact lifecycle, run lifecycle, configuration provenance, failure history and recovery.

## Read in this order

| Guide | Question |
| --- | --- |
| [System Architecture](system-architecture.md) | What are the major planes, components and dependency directions? |
| [Data Lifecycle](data-lifecycle.md) | How does a source artifact become decision-ready analytical state? |
| [Warehouse Architecture](warehouse-architecture.md) | What belongs in SQLite, Bronze, Silver, Gold and Meta? |
| [Data Model](data-model.md) | What are the canonical financial objects and grains? |
| [Reliability & Recovery](reliability-and-recovery.md) | What happens when processing fails, state disappears or a rebuild is required? |
| [Design Decisions](design-decisions.md) | Why these technologies and boundaries instead of plausible alternatives? |

## Architecture through different lenses

```text
Operational
→ Control Plane · transactions · failures · recovery

Data Engineering
→ discovery · hashing · Bronze synchronization · deterministic rebuild

Software
→ repositories · facade · contracts · strategies · process boundaries

Finance
→ canonical semantics · lot state · household state · analytical grain

BI
→ Silver contracts · Gold marts · Power BI serving
```

The substantive pages show the production code behind those claims.

[← Documentation Home](../README.md)
