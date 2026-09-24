# Data Contracts & Reference

This section is the **reference layer** of the documentation.

Architecture pages explain how the system works. Finance pages explain what the analytics mean. The reference pages describe the physical contracts that the current implementation publishes.

> Use these pages when you need the exact layer, domain, grain, producer, important fields, or downstream purpose of a dataset.

## References

| Reference | Purpose |
| --- | --- |
| [Silver Data Contracts](silver-data-contracts.md) | Reference the 20 canonical Silver dimensions/reference models and facts |
| [Gold Data Contracts](gold-data-contracts.md) | Reference the 17 decision-support marts and their analytical grains |
| [Meta Data Contracts](meta-data-contracts.md) | Reference source registry, run telemetry, row counts, settings, and financial-rules snapshots |
| [Glossary](glossary.md) | Reference architectural terminology, financial concepts, abbreviations, and project vocabulary |

## Contract format

Important datasets will follow a consistent reference structure:

```text
Purpose
Layer
Domain
Grain
Producer
Major inputs
Key fields
Downstream consumers
Assumptions / caveats
```

This separation is intentional. Python variable names and intermediate frames are implementation details; **physical analytical contracts and business meaning are the stable documentation surface**.

## Current warehouse surface

```text
Silver
  20 canonical tables

Gold
  17 decision-support marts

Meta
   5 operational/control tables
```

For conceptual relationships rather than field-level reference, see [Data Model](../architecture/data-model.md).

[← Documentation Home](../README.md)
