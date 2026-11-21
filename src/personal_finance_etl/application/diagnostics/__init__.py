"""Application diagnostics services and configuration inspection workflows.

Owns
----
- DiagnosticService: Non-I/O application service managing configuration validation, source reachability,
  mapping/identity preview, capability execution plan preview, and zero-mutation admission dry run.

Does not own
-------------
- Terminal CLI formatting or argument parsing (owned by presentation.cli.diagnostics).
- Database commits or lakehouse writes (dry run is strictly non-mutating).
- Domain calculations or tax lot matching (owned by domain layer).
"""

from personal_finance_etl.application.diagnostics.service import DiagnosticService

__all__ = ["DiagnosticService"]
