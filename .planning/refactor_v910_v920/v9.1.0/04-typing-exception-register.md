# v9.1.0 — Typing Exception Register

All typing exceptions are also documented directly inline at their exact source code call sites with their respective `Exception TYP-00X [CATEGORY]` tags.

| ID | Location | Category | Reason | Narrowing point / removal condition |
| --- | --- | --- | --- | --- |
| TYP-001 | `src/personal_finance_etl/domain/fire/simulation.py:43,129,495,557` | `NUMBA_OR_LIBRARY_LIMITATION` | Numba `@njit(parallel=True)` compilation kernel generator types and PRNG list | Narrowed at `monte_carlo_fire_batch` entry and return (`pl.Series`) |
| TYP-002 | `src/personal_finance_etl/infrastructure/providers/market/*.py` | `THIRD_PARTY_TYPING_GAP` | `yfinance` library lacks `py.typed` marker and complete stubs | Isolated strictly to market data extraction provider modules |
| TYP-003 | `src/personal_finance_etl/presentation/desktop/*.py`, `launcher.py:80` | `THIRD_PARTY_TYPING_GAP` | `customtkinter` library lacks complete type stubs and `py.typed` marker | Isolated to UI widget framework presentation components |
| TYP-004 | `src/personal_finance_etl/presentation/docs/renderer.py:23` | `THIRD_PARTY_TYPING_GAP` | `markdown` library lacks `py.typed` marker and complete stubs | Isolated strictly to doc generation markdown rendering |
| TYP-005 | `src/personal_finance_etl/presentation/docs/guides_window.py:53`, `cli/app.py:58` | `UNTYPED_EXTERNAL_BOUNDARY` | `pywebview` window builder and Windows `sys.stdout.reconfigure` | Isolated strictly to OS presentation wrappers |

Allowed categories:

```text
THIRD_PARTY_TYPING_GAP
SERIALIZATION_BOUNDARY
GENUINELY_HETEROGENEOUS
NUMBA_OR_LIBRARY_LIMITATION
UNTYPED_EXTERNAL_BOUNDARY
```

Every survivor has an architectural reason and is strictly isolated at peripheral boundary layers. Stable core domain, business contracts, and application execution layers contain 0 unexplained `Any` and 0 undocumented exceptions.
