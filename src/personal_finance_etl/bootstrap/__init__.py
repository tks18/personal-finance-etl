"""Bootstrap composition root.

Owns
----
- Concrete dependency assembly and wiring.
- Binding infrastructure implementations to application ports/protocols.
- Providing configured application façade instances to presentation.

Does not own
-------------
- Financial calculations or domain rules (owned by domain.*).
- Execution orchestration (owned by application.*).
- Direct UI invocation or user handling (owned by presentation.*).
"""

