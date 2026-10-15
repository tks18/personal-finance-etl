"""Logging infrastructure and formatters.

Owns
----
- Process-wide logging configuration and handler setups.
- Multi-process logging queues and formatters.
- Log file rotation and formatting.

Does not own
-------------
- UI log viewer presentation widgets (owned by presentation).
- Cross-process status message definitions (owned by contracts.application).
"""

