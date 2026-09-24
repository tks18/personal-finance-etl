# Getting Started

This section covers the practical path from installing **Personal Finance ETL** to running a configured pipeline.

I currently use the project as a purpose-built financial system rather than a turnkey consumer application. A working deployment therefore requires more than installing the Python package: operational paths, financial rules, mapping/reference inputs, and compatible source contracts must all agree with the environment being processed.

> **New to the project?** Read the [Project Overview](../about/project.md) first. Then start here with [Installation](installation.md).

## Guides

| Guide | Purpose |
| --- | --- |
| [Installation](installation.md) | Install the package and prepare a local Python environment |
| [Configuration](configuration.md) | Understand operational settings, source paths, mappings, and how configuration relates to financial rules |
| [Running the Pipeline](running-the-pipeline.md) | Run the CLI, desktop application, automated/headless workflows, and snapshots |

## Recommended path

```text
Installation
     ↓
Configuration
     ↓
Running the Pipeline
```

Configuration has two distinct concerns:

- **Operational settings** describe where and how the application runs.
- **Financial rules** describe how the system interprets financial meaning.

For the financial-policy layer, continue to [Financial Rules](../configuration/financial-rules.md).

[← Documentation Home](../README.md)
