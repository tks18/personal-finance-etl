# About

This section explains the **story, scope, philosophy, and future direction** of Personal Finance ETL.

The project is both an operational personal-finance system and an engineering project spanning data engineering, BI, Python architecture, financial modelling, and quantitative planning.

> **Start here:** [Project Overview](project.md) explains why the system exists and how it evolved from a month-end data problem into a local financial platform.

## Pages

| Page | Purpose |
| --- | --- |
| [Project Overview](project.md) | Project origin, real-world use, engineering philosophy, current scope, limitations, and evolution |
| [Roadmap](roadmap.md) | Long-term direction toward configuration-driven sources, canonical contracts, adapters, strategies, and broader deployability |

## Current state

I currently run v6 as a **working vertical implementation** built around my financial environment.

Its infrastructure and many analytical components are reusable, while source contracts, mappings, parts of the tax regime, and selected policies remain purpose-built.

That distinction is central to the project:

```text
Working vertical system
        ↓
Understand embedded assumptions
        ↓
Extract parameters into configuration
        ↓
Extract behaviour behind adapters / strategies
        ↓
Preserve analytical equivalence
        ↓
More reusable platform
```

The goal is not to rewrite a functioning system into an abstract framework. It is to generalize it progressively without losing the behaviour that made it useful in the first place.

[← Documentation Home](../README.md)
