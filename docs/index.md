---
title: Personal Finance ETL
description: From fragmented financial evidence to explainable financial state.
hide:
  - toc
---

<div class="pf-hero">
  <div class="pf-eyebrow">PERSONAL FINANCIAL SYSTEMS ENGINEERING</div>
  <h1>From fragmented financial evidence to <span>explainable financial state.</span></h1>
  <p class="pf-hero-copy">A local-first personal financial systems platform spanning data engineering, investment accounting, reconciliation, Tax evidence, wealth analytics and FIRE planning.</p>
  <div class="pf-actions">
    <a class="pf-btn pf-btn-primary" href="architecture/README/">Explore the System</a>
    <a class="pf-btn pf-btn-secondary" href="architecture/system-architecture/">View Architecture</a>
    <a class="pf-text-link" href="https://github.com/tks18/personal-finance-etl">GitHub ↗</a>
  </div>
  <div class="pf-tech-strip">Python <span>·</span> Polars <span>·</span> DuckDB <span>·</span> SQLite <span>·</span> Power BI</div>
  <div class="pf-signature">Built by <strong>Sudharshan TK · Shan.tk</strong><br><span>Chartered Accountant × Data &amp; Software Engineer</span></div>
</div>

<p class="pf-character-line">Built for one household. Engineered slightly beyond reasonable requirements. 😄</p>

<div class="pf-section-label">01 · THE PROBLEM</div>

## Personal finance rarely arrives as one clean dataset.

<div class="pf-source-row">
  <span>Household</span><span>Brokers</span><span>Market</span><span>FX</span><span>Reference</span>
</div>

The hard part is not collecting files. It is reconstructing financial state without losing the evidence that produced it.

<div class="pf-section-label">02 · THE SYSTEM</div>

## One local system. Explicit financial truth.

```mermaid
flowchart LR
    E["Evidence<br/>Household · Brokers · Market · FX"] --> C["Control Plane + Bronze<br/>History · Provenance · Source State"]
    C --> S["Canonical State<br/>Household · Market · Investments"]
    S --> F["Financial Engines<br/>FIFO · Reconciliation · Tax · FIRE"]
    F --> W["Analytical Warehouse<br/>Silver · Gold · Meta"]
    W --> D["Decisions<br/>Power BI · CLI · Desktop"]

    classDef evidence fill:#2563eb,color:#fff,stroke:#60a5fa
    classDef infra fill:#6d28d9,color:#fff,stroke:#a78bfa
    classDef finance fill:#059669,color:#fff,stroke:#34d399
    classDef presentation fill:#27272a,color:#fff,stroke:#71717a

    class E evidence
    class C,W infra
    class S,F finance
    class D presentation
```

<div class="pf-section-label">03 · FOUR PILLARS</div>

## Finance, data and software engineering in one system.

<div class="pf-grid pf-grid-2">
  <a class="pf-card" href="finance/README/">
    <div class="pf-card-kicker">01 · FINANCIAL ENGINEERING</div>
    <h3>Reconstruct the economics.</h3>
    <p>FIFO · reconciliation · performance · FX · Tax · wealth · FIRE</p>
  </a>
  <a class="pf-card" href="architecture/README/">
    <div class="pf-card-kicker">02 · DATA PLATFORM</div>
    <h3>Preserve the evidence.</h3>
    <p>Contracts · lineage · Polars · DuckDB · SQLite Control Plane</p>
  </a>
  <a class="pf-card" href="finance/metrics-and-methodology/">
    <div class="pf-card-kicker">03 · DECISION INTELLIGENCE</div>
    <h3>Serve decisions, not mystery numbers.</h3>
    <p>Portfolio analytics · household state · Power BI · planning</p>
  </a>
  <a class="pf-card" href="architecture/reliability-and-recovery/">
    <div class="pf-card-kicker">04 · RELIABILITY & SOFTWARE</div>
    <h3>Make the result believable.</h3>
    <p>Typed architecture · recovery · observability · testing · packaging</p>
  </a>
</div>

<div class="pf-section-label">04 · THE RECEIPTS</div>

## The receipts.

<div class="pf-metrics">
  <div><strong>20</strong><span>Bronze contracts</span></div>
  <div><strong>24</strong><span>Silver tables</span></div>
  <div><strong>22</strong><span>Gold tables</span></div>
  <div><strong>53</strong><span>Canonical specs</span></div>
  <div><strong>10</strong><span>Control Plane tables</span></div>
</div>

<div class="pf-section-label">05 · BUILT DIFFERENTLY</div>

## The principles are part of the architecture.

<div class="pf-grid pf-grid-2 pf-principles">
  <div class="pf-card pf-card-static"><h3>Evidence first.</h3><p>Observed and reconstructed state stay distinguishable.</p></div>
  <div class="pf-card pf-card-static"><h3>Local first.</h3><p>Sensitive personal financial evidence stays local.</p></div>
  <div class="pf-card pf-card-static"><h3>Deterministic where possible.</h3><p>Identity, reconstruction and replay are explicit.</p></div>
  <div class="pf-card pf-card-static"><h3>Explicit about uncertainty.</h3><p>Estimates, reconciliation and stochastic futures are labelled as such.</p></div>
</div>

<div class="pf-section-label">06 · EXPLORE</div>

## Pick the question you want answered.

<div class="pf-grid pf-grid-2">
  <a class="pf-route" href="architecture/system-architecture/"><strong>Understand the Architecture</strong><span>Ownership, lifecycle, Control Plane, warehouse and reliability. →</span></a>
  <a class="pf-route" href="finance/README/"><strong>Explore Financial Engineering</strong><span>Household finance, investments, Tax, wealth and FIRE. →</span></a>
  <a class="pf-route" href="developer/README/"><strong>Build on the System</strong><span>Engineering standards, extension paths, testing and release discipline. →</span></a>
  <a class="pf-route" href="reference/README/"><strong>Verify the Contracts</strong><span>Physical schemas, grain, identity and ownership. →</span></a>
</div>

<div class="pf-section-label">07 · CREATOR</div>

## Built by Shan.tk.

<div class="pf-creator">
  <div>
    <h3>Sudharshan TK</h3>
    <p class="pf-creator-role">Chartered Accountant × Data &amp; Software Engineer</p>
    <p>Personal Finance ETL is where finance, data engineering, software architecture and an unreasonable amount of curiosity ended up in the same repository.</p>
    <p><strong>Finance gave me the questions. Data gave me the structure. Software engineering let me build the answers.</strong></p>
  </div>
  <div class="pf-creator-links">
    <a href="https://github.com/tks18">GitHub ↗</a>
    <a href="https://www.linkedin.com/in/sudharshan-tk">LinkedIn ↗</a>
    <a href="about/about-me/">About Shan.tk →</a>
  </div>
</div>

<div class="pf-final-cta">
  <div>
    <span class="pf-section-label">READY TO GO DEEPER?</span>
    <h2>Preserve the evidence. Reconstruct the state. Explain the decision.</h2>
  </div>
  <a class="pf-btn pf-btn-primary" href="documentation-guide/">Open the Documentation Guide</a>
</div>
