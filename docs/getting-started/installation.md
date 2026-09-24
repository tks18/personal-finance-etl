# Installation

This guide covers installing Personal Finance ETL and preparing the local Python environment required to run it.

The package is built for **Python 3.13+** and is designed as a local application. Installing the package gives you the runtime, CLI, desktop entry point, and packaged documentation, but it does **not** make an arbitrary financial environment compatible automatically.

A usable deployment also requires valid operational configuration, financial rules, mappings/reference inputs, and source contracts that the current extractors understand.

> If you are evaluating the repository rather than running it against compatible financial sources, the [System Architecture](../architecture/system-architecture.md) and [Project Overview](../about/project.md) are better starting points.

---

## Prerequisites

### Python

Personal Finance ETL requires:

```text
Python >= 3.13
```

Check the active interpreter:

```bash
python --version
```

On systems where multiple Python installations coexist, use the Python 3.13+ interpreter explicitly.

### Local filesystem access

The application needs access to the configured locations used for:

- source financial data,
- statement files,
- reference/mapping inputs,
- DuckDB analytical storage,
- SQLite Raw Document Store storage,
- and snapshots or related local outputs.

Because the project is local-first, filesystem permissions are part of the runtime environment.

### Compatible financial inputs

The current v6 implementation is purpose-built around my source environment.

Installation alone does not provide universal adapters for arbitrary banks or brokers.

Before expecting a successful pipeline run, review:

- [Configuration](configuration.md)
- [Financial Rules](../configuration/financial-rules.md)
- [Adding a Data Source](../developer/adding-data-sources.md)

---

## Install from PyPI

For a normal package installation:

```bash
pip install personal-finance-etl
```

This installs the package and its declared runtime dependencies.

After installation, the application exposes two primary entry points:

```text
shan-fin
shan-fin-gui
```

### CLI

Launch the terminal application:

```bash
shan-fin
```

### Desktop application

Launch the graphical application:

```bash
shan-fin-gui
```

The desktop frontend is an application surface over the same backend engine rather than a separate analytical implementation.

---

## Install from source

For development or repository exploration:

```bash
git clone https://github.com/tks18/personal-finance-etl.git
cd personal-finance-etl
pip install -e .
```

Editable installation keeps the active package linked to the working source tree.

That is the preferred setup when modifying:

- extractors,
- transformations,
- analytical engines,
- schemas,
- configuration models,
- application code,
- or documentation integration.

For development conventions and static-analysis tooling, see [Development Guide](../developer/development-guide.md).

---

## Recommended isolated environment

I recommend using a dedicated virtual environment rather than installing into a shared global Python environment.

A standard Python workflow is:

```bash
python -m venv .venv
```

Activate it using the mechanism appropriate to your shell, then install the package:

```bash
python -m pip install --upgrade pip
pip install -e .
```

The exact activation command is shell/platform-specific, so this documentation avoids pretending one command is universal.

---

## What gets installed

The package includes the production Python application and packaged documentation.

At a high level, the runtime includes components for:

- configuration validation,
- source ingestion,
- SQLite Raw Store persistence,
- DuckDB analytical storage,
- Polars transformations,
- investment analytics,
- wealth and cash-flow analytics,
- FIRE simulation,
- CLI operation,
- desktop operation,
- and documentation access.

The application is not notebook-driven.

It is installed and executed as a Python package with application entry points.

---

## Core technology stack

The package uses several technologies for distinct workloads.

| Technology | Runtime role |
| --- | --- |
| Python 3.13+ | Application runtime |
| SQLite | Raw/control persistence |
| DuckDB | Analytical warehouse |
| Polars | Transformation and analytical compute |
| Pydantic | Configuration and financial-policy validation |
| NumPy / Numba | Numerical simulation |
| PyXIRR | Irregular cash-flow returns |
| Rich | CLI |
| CustomTkinter | Desktop UI |
| Power BI | External BI consumption |

For the architectural reasoning behind these choices, see [Design Decisions](../architecture/design-decisions.md).

---

## Installation is not configuration

A successful package installation only proves that Python can import and launch the application.

It does not prove that the pipeline can process a financial environment.

The runtime still needs operational settings describing locations such as:

- source database folders,
- statement folders,
- reference/mapping files,
- and local persistence targets.

It also needs `FinancialRules` describing financial semantics such as:

- income and expense treatment,
- asset classifications,
- investment classifications,
- tax parameters,
- budgets,
- target allocations,
- and FIRE assumptions.

The next step after installation is therefore [Configuration](configuration.md).

---

## Validate the application surface

After installation, confirm that the entry point resolves:

```bash
shan-fin
```

or launch the desktop interface:

```bash
shan-fin-gui
```

A successful launch verifies the application surface.

A successful **pipeline run** requires the configured data environment described in the next guides.

---

## Local-first implications

The architecture intentionally avoids requiring a hosted application backend or cloud analytical warehouse.

That means installation remains relatively self-contained, but I also retain responsibility for:

- protecting local financial data,
- backing up important local files,
- maintaining source/configuration paths,
- and managing the local Python environment.

The [Reliability & Recovery](../architecture/reliability-and-recovery.md) guide explains what the software can reconstruct and what still requires sound local backup practice.

---

## Troubleshooting installation

### `shan-fin` is not found

Confirm that:

1. the package installed successfully,
2. you are using the environment into which it was installed,
3. the environment's executable/script directory is on the active shell path.

You can also verify package installation with:

```bash
python -m pip show personal-finance-etl
```

### Python version is too old

Use Python 3.13 or newer.

Do not work around the declared version requirement by forcing installation into an older interpreter and assuming runtime compatibility.

### The application launches but the pipeline fails

That is usually no longer an installation problem.

Move to:

- [Configuration](configuration.md)
- [Running the Pipeline](running-the-pipeline.md)
- [Adding a Data Source](../developer/adding-data-sources.md)

depending on the failure.

### A source is unsupported

The current implementation is not a universal parser.

Supporting a materially different source can require an extractor/adapter and canonical transformation work.

See [Adding a Data Source](../developer/adding-data-sources.md).

---

## Next steps

Recommended order:

```text
Install
   ↓
Configure operational settings
   ↓
Configure financial rules
   ↓
Validate source compatibility
   ↓
Run the pipeline
```

Continue with:

- [Configuration](configuration.md)
- [Running the Pipeline](running-the-pipeline.md)
- [Financial Rules](../configuration/financial-rules.md)

[← Getting Started](README.md) · [← Documentation Home](../README.md)
