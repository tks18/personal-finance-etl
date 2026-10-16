# v9.1.0 — Typing Exception Register

| ID | Location | Category | Reason | Narrowing point / removal condition |
| --- | --- | --- | --- | --- |
| TYP-001 | `src/personal_finance_etl/infrastructure/control_plane/facade.py:47` | `THIRD_PARTY_TYPING_GAP` | `FileLock` lacks complete typing stubs / py.typed marker | Narrowed in `ControlPlane` lock context management |
| TYP-002 | `src/personal_finance_etl/infrastructure/logging/setup.py:124` | `THIRD_PARTY_TYPING_GAP` | `multiprocessing.managers.BaseManager` dynamic proxy manager | Narrowed in `setup_logger` process lifecycle |
| TYP-003 | `src/personal_finance_etl/infrastructure/preferences/repository.py:46,53,57` | `SERIALIZATION_BOUNDARY` | Dynamic JSON user preferences file dictionary | Narrowed when loading into `PreferencesManager` state |
| TYP-004 | `src/personal_finance_etl/domain/fire/simulation.py:43,493` | `NUMBA_OR_LIBRARY_LIMITATION` | Numba `@njit(parallel=True)` compilation kernel generator types | Narrowed at `monte_carlo_fire_batch` entry and return (`pl.Series`) |
| TYP-005 | `src/personal_finance_etl/presentation/desktop/base_tab.py:19` | `THIRD_PARTY_TYPING_GAP` | CustomTkinter dynamic widget dispatch and event typing | Narrowed to `EngineStatusMessage` in event handling |

Allowed categories:

```text
THIRD_PARTY_TYPING_GAP
SERIALIZATION_BOUNDARY
GENUINELY_HETEROGENEOUS
NUMBA_OR_LIBRARY_LIMITATION
UNTYPED_EXTERNAL_BOUNDARY
```

Do not use this register to preserve anonymous stable financial/application contracts.
