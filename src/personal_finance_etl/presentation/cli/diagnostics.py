"""Rich terminal presentation handlers for PFETL configuration diagnostics.

Owns
----
- Terminal formatting and table/panel rendering for diagnostic subcommands:
  validate-config, check-sources, preview-mapping, preview-identity, preview-plan, dry-run-admission.
- Actionable error remediation guidance and progress bar rendering.

Does not own
-------------
- Diagnostic compilation or execution (owned by application.diagnostics.service).
- Direct Pandera validation or Polars transformations (owned by application layer).
- Storage persistence or database commits (presentation layer is strictly read-only).
"""

from __future__ import annotations

import argparse

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from personal_finance_etl.application.facade import PersonalFinanceEngine
from personal_finance_etl.contracts.diagnostics import (
    AdmissionDryRunResult,
    ConfigValidationResult,
    DiagnosticSeverity,
    IdentityPreviewResult,
    MappingPreviewResult,
    PlanPreviewResult,
    SourceCheckResult,
    SourceReachabilityStatus,
)

__all__ = [
    "handle_check_sources",
    "handle_dry_run_admission",
    "handle_preview_identity",
    "handle_preview_mapping",
    "handle_preview_plan",
    "handle_validate_config",
]

console = Console()


def handle_validate_config(args: argparse.Namespace, engine: PersonalFinanceEngine) -> int:
    """Execute validate-config diagnostic command and render human-readable results.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments.
    engine : PersonalFinanceEngine
        Configured engine facade.

    Returns
    -------
    int
        0 on success, 1 on validation error.
    """
    config_path = getattr(args, "config", None) or "config.toml"
    rules_path = getattr(args, "rules", None) or "rules.toml"
    sources_path = getattr(args, "sources", None) or "sources.toml"

    console.print(
        Panel(
            f"[bold cyan]Validating Configuration Triad:[/bold cyan]\n"
            f"[dim]Settings:[/dim] {config_path}\n"
            f"[dim]Rules:   [/dim] {rules_path}\n"
            f"[dim]Sources: [/dim] {sources_path}",
            title="[bold magenta]pfetl validate-config[/bold magenta]",
            border_style="cyan",
        )
    )

    result: ConfigValidationResult = engine.validate_all_configs(
        config_path=config_path,
        rules_path=rules_path,
        sources_path=sources_path,
    )

    if result.active_capabilities:
        caps_str = ", ".join(
            f"[bold green]{c.value}[/bold green]" for c in result.active_capabilities
        )
        console.print(f"[bold]Active Capabilities:[/bold] {caps_str}\n")

    if result.is_valid:
        binding_info = (
            f", and {result.compiled_bindings_count} compiled source bindings."
            if result.compiled_bindings_count > 0
            else "."
        )
        console.print(
            Panel(
                "[bold green]✓ ALL CONFIGURATION FILES ARE VALID & CONTRACT-COMPLIANT.[/bold green]\n"
                f"Resolved {len(result.active_capabilities)} capabilities, {len(result.active_datasets)} active Bronze datasets{binding_info}",
                title="[bold green]Validation Passed[/bold green]",
                border_style="green",
            )
        )
        return 0

    table = Table(title="[bold red]Configuration Issues & Diagnostics[/bold red]", expand=True)
    table.add_column("Severity", style="bold", width=10)
    table.add_column("Category", style="cyan", width=12)
    table.add_column("Location", style="yellow", width=25)
    table.add_column("Message", style="white")
    table.add_column("Remediation Hint", style="italic green")

    for issue in result.issues:
        sev_color = "red" if issue.severity == DiagnosticSeverity.ERROR else "yellow"
        table.add_row(
            f"[{sev_color}]{issue.severity.value}[/{sev_color}]",
            issue.category,
            issue.location,
            issue.message,
            issue.remediation,
        )

    console.print(table)
    console.print()
    return 1


def handle_check_sources(args: argparse.Namespace, engine: PersonalFinanceEngine) -> int:
    """Execute check-sources diagnostic command checking reachability and selectors.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments.
    engine : PersonalFinanceEngine
        Configured engine facade.

    Returns
    -------
    int
        0 on success, 1 if any source/selector is unreachable or invalid.
    """
    sources_path = getattr(args, "sources", None) or "sources.toml"
    config_path = getattr(args, "config", None) or "config.toml"

    console.print(f"[bold cyan]Checking Source Reachability from:[/bold cyan] {sources_path}\n")

    result: SourceCheckResult = engine.check_sources(
        sources_path=sources_path,
        config_path=config_path,
    )

    if not result.sources:
        console.print(f"[bold red]✗ No sources found or failed to parse {sources_path}.[/bold red]")
        for issue in result.issues:
            console.print(f"[red]• {issue.message}[/red] -> [green]{issue.remediation}[/green]")
        return 1

    table = Table(title="[bold cyan]Evidence Source Reachability Matrix[/bold cyan]", expand=True)
    table.add_column("Source ID", style="bold cyan")
    table.add_column("Provider", style="magenta")
    table.add_column("Location", style="dim")
    table.add_column("Status", style="bold")
    table.add_column("Details", style="white")

    for s in result.sources:
        status_color = "green" if s.status == SourceReachabilityStatus.REACHABLE else "red"
        table.add_row(
            str(s.source_id),
            s.provider_type.value,
            s.location,
            f"[{status_color}]{s.status.value}[/{status_color}]",
            s.message,
        )

    console.print(table)
    console.print()

    # Selectors Table
    sel_table = Table(title="[bold cyan]Dataset Selector Diagnostics[/bold cyan]", expand=True)
    sel_table.add_column("Dataset ID", style="bold cyan")
    sel_table.add_column("Selector Type", style="dim")
    sel_table.add_column("Target Selector", style="yellow")
    sel_table.add_column("Status", style="bold")
    sel_table.add_column("Notes / Available Targets", style="white")

    for s in result.sources:
        for ds_sel in s.dataset_selectors:
            st_color = "green" if ds_sel.is_valid else "red"
            notes = ds_sel.details
            if not ds_sel.is_valid and ds_sel.available_targets:
                notes += f" (Available: {list(ds_sel.available_targets)})"
            sel_table.add_row(
                ds_sel.dataset_id.value,
                ds_sel.selector_type,
                ds_sel.selector_target,
                f"[{st_color}]{'VALID' if ds_sel.is_valid else 'INVALID'}[/{st_color}]",
                notes,
            )

    console.print(sel_table)
    console.print()

    return 0 if result.is_all_reachable else 1


def handle_preview_mapping(args: argparse.Namespace, engine: PersonalFinanceEngine) -> int:
    """Execute preview-mapping command displaying field mappings and normalization sequence.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments.
    engine : PersonalFinanceEngine
        Configured engine facade.

    Returns
    -------
    int
        0 on success, 1 on failure.
    """
    dataset_id = getattr(args, "dataset", None)
    if not dataset_id:
        console.print(
            "[bold red]Error:[/bold red] Target dataset argument required (e.g. pfetl preview-mapping household_transactions)."
        )
        return 1

    sources_path = getattr(args, "sources", None) or "sources.toml"

    try:
        preview: MappingPreviewResult = engine.preview_mapping(
            dataset_id=dataset_id,
            sources_path=sources_path,
        )
    except Exception as e:
        console.print(f"[bold red]Failed to preview mapping for '{dataset_id}':[/bold red] {e}")
        return 1

    header_lines = [
        f"[bold]Dataset:[/bold] [cyan]{preview.dataset_id.value}[/cyan]",
        f"[bold]Bound Source:[/bold] [yellow]{preview.source_id if preview.source_id else 'None'}[/yellow]",
        f"[bold]Provider Type:[/bold] [magenta]{preview.provider_type.value if preview.provider_type else 'None'}[/magenta]",
    ]
    if preview.source_binding_id:
        route_str = f" (Route: [cyan]{preview.canonical_route_id or 'direct'}[/cyan])"
        header_lines.append(
            f"[bold]Compiled Binding:[/bold] [blue]{preview.source_binding_id}[/blue]{route_str}"
        )

    console.print(
        Panel(
            "\n".join(header_lines),
            title="[bold green]Dataset Normalization & Mapping Preview[/bold green]",
            border_style="green",
        )
    )

    table = Table(title=f"Column Mapping: {preview.dataset_id.value}", expand=True)
    table.add_column("Raw Source Field", style="bold yellow")
    table.add_column("Canonical Bronze Target", style="bold green")

    for src_f, canon_f in preview.field_mappings:
        table.add_row(src_f, canon_f)

    console.print(table)
    console.print()

    if preview.pre_rename_rules:
        console.print("[bold cyan]Pre-Rename Normalization Operations:[/bold cyan]")
        for r in preview.pre_rename_rules:
            console.print(f"  • {r}")
        console.print()

    if preview.post_rename_rules:
        console.print("[bold cyan]Post-Rename Normalization Operations:[/bold cyan]")
        for r in preview.post_rename_rules:
            console.print(f"  • {r}")
        console.print()

    return 0


def handle_preview_identity(args: argparse.Namespace, engine: PersonalFinanceEngine) -> int:
    """Execute preview-identity command displaying row identity strategy and sample IDs.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments.
    engine : PersonalFinanceEngine
        Configured engine facade.

    Returns
    -------
    int
        0 on success, 1 on collision or error.
    """
    dataset_id = getattr(args, "dataset", None)
    if not dataset_id:
        console.print(
            "[bold red]Error:[/bold red] Target dataset argument required (e.g. pfetl preview-identity household_transactions)."
        )
        return 1

    sources_path = getattr(args, "sources", None) or "sources.toml"
    config_path = getattr(args, "config", None) or "config.toml"

    try:
        preview: IdentityPreviewResult = engine.preview_identity(
            dataset_id=dataset_id,
            sources_path=sources_path,
            config_path=config_path,
        )
    except Exception as e:
        console.print(f"[bold red]Failed to preview identity for '{dataset_id}':[/bold red] {e}")
        return 1

    status_tag = (
        "[bold red]COLLISION DETECTED[/bold red]"
        if preview.collision_detected
        else "[bold green]UNIQUE / VERIFIED[/bold green]"
    )

    console.print(
        Panel(
            f"[bold]Dataset:[/bold] [cyan]{preview.dataset_id.value}[/cyan]\n"
            f"[bold]Contract Requirement:[/bold] [yellow]{preview.requirement.value}[/yellow]\n"
            f"[bold]Strategy:[/bold] [magenta]{preview.strategy_kind}[/magenta]\n"
            f"[bold]Target Fields:[/bold] {', '.join(preview.strategy_target_fields) or 'None'}\n"
            f"[bold]Namespace:[/bold] {preview.namespace or 'N/A'}\n"
            f"[bold]Status:[/bold] {status_tag}",
            title="[bold green]Bronze Row Identity Strategy Preview[/bold green]",
            border_style="red" if preview.collision_detected else "green",
        )
    )

    if preview.sample_ids:
        console.print("[bold cyan]Bounded Sample Generated Row IDs:[/bold cyan]")
        for i, s_id in enumerate(preview.sample_ids[:10], 1):
            console.print(f"  [{i}] [dim cyan]{s_id}[/dim cyan]")
        console.print()

    if preview.collision_detected and preview.collision_diagnostic:
        console.print(
            Panel(
                preview.collision_diagnostic,
                title="[bold red]Collision Diagnostic[/bold red]",
                border_style="red",
            )
        )
        return 1

    return 0


def handle_preview_plan(args: argparse.Namespace, engine: PersonalFinanceEngine) -> int:
    """Execute preview-plan command displaying active capabilities, required Bronze, and outputs.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments.
    engine : PersonalFinanceEngine
        Configured engine facade.

    Returns
    -------
    int
        0 on success, 1 on failure.
    """
    config_path = getattr(args, "config", None) or "config.toml"
    sources_path = getattr(args, "sources", None) or "sources.toml"

    try:
        plan: PlanPreviewResult = engine.preview_plan(
            config_path=config_path,
            sources_path=sources_path,
        )
    except Exception as e:
        console.print(f"[bold red]Failed to compile execution plan:[/bold red] {e}")
        return 1

    console.print(
        Panel(
            f"[bold]Plan Fingerprint:[/bold] [dim yellow]{plan.plan_fingerprint}[/dim yellow]\n"
            f"[bold]Requested Capabilities:[/bold] {', '.join(c.value for c in plan.requested_capabilities)}\n"
            f"[bold]Topological Execution Order:[/bold] {', '.join(f'[green]{c.value}[/green]' for c in plan.resolved_capabilities)}",
            title="[bold green]Authoritative Execution Plan Preview[/bold green]",
            border_style="green",
        )
    )

    table = Table(title="[bold cyan]Plan-Scoped Data Contracts[/bold cyan]", expand=True)
    table.add_column("Stage / Layer", style="bold magenta", width=20)
    table.add_column("Datasets / Contracts", style="white")

    req_bronze = ", ".join(d.value for d in plan.required_bronze_datasets) or "None"
    opt_bronze = ", ".join(d.value for d in plan.optional_bronze_datasets) or "None"
    active_silver = ", ".join(d.value for d in plan.active_silver_datasets) or "None"
    active_gold = ", ".join(d.value for d in plan.active_gold_datasets) or "None"
    enrichments = ", ".join(e.value for e in plan.required_external_enrichments) or "None"

    table.add_row("Required Bronze", req_bronze)
    table.add_row("Optional Bronze", opt_bronze)
    table.add_row("Active Silver", active_silver)
    table.add_row("Active Gold", active_gold)
    table.add_row("External Enrichments", enrichments)

    console.print(table)
    console.print()

    # Render canonical production satisfiability graph if available
    if plan.production_plan_fingerprint:
        status_text = (
            "[bold green]SATISFIABLE[/bold green]"
            if plan.is_satisfiable
            else "[bold red]UNSATISFIABLE[/bold red]"
        )
        console.print(
            Panel(
                f"[bold]Production Fingerprint:[/bold] [dim yellow]{plan.production_plan_fingerprint}[/dim yellow]\n"
                f"[bold]Satisfiability Status:[/bold] {status_text}",
                title="[bold green]Canonical Production Satisfiability[/bold green]",
                border_style="cyan",
            )
        )

    if plan.producer_resolutions:
        prod_table = Table(
            title="[bold cyan]Resolved Canonical Evidence Production Graph[/bold cyan]",
            expand=True,
        )
        prod_table.add_column("Canonical Dataset", style="bold green", width=26)
        prod_table.add_column("Kind", style="cyan", width=10)
        prod_table.add_column("Mode", style="yellow", width=8)
        prod_table.add_column("Routes / Provider / Recipe", style="white")
        prod_table.add_column("Dependencies", style="dim", width=22)

        for res in plan.producer_resolutions:
            routes_str = (
                ", ".join(res.source_routes)
                if res.source_routes
                else (res.recipe_name or res.provider_type or "-")
            )
            deps_str = ", ".join(d.value for d in res.dependencies) or "-"
            prod_table.add_row(
                res.dataset_id.value,
                res.producer_kind.upper(),
                (res.assembly_mode or "-").upper(),
                routes_str,
                deps_str,
            )

        console.print(prod_table)
        console.print()

    if plan.unsatisfied_evidence:
        unsat_table = Table(
            title="[bold red]Unsatisfied Required Canonical Evidence[/bold red]",
            expand=True,
            border_style="red",
        )
        unsat_table.add_column("Dataset", style="bold red", width=26)
        unsat_table.add_column("Mandating Capabilities", style="yellow", width=30)
        unsat_table.add_column("Diagnostic Detail", style="white")

        for unsat in plan.unsatisfied_evidence:
            caps_str = ", ".join(unsat.required_by_capabilities) or "Unknown"
            unsat_table.add_row(unsat.dataset_id.value, caps_str, unsat.reason)

        console.print(unsat_table)
        console.print()

    return 0


def handle_dry_run_admission(args: argparse.Namespace, engine: PersonalFinanceEngine) -> int:
    """Execute dry-run-admission command performing zero-mutation pipeline admission checks.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments.
    engine : PersonalFinanceEngine
        Configured engine facade.

    Returns
    -------
    int
        0 on success, 1 on admission or validation error.
    """
    dataset_selector = getattr(args, "dataset", None) or "all"
    config_path = getattr(args, "config", None) or "config.toml"
    rules_path = getattr(args, "rules", None) or "rules.toml"
    sources_path = getattr(args, "sources", None) or "sources.toml"

    console.print(
        Panel(
            f"[bold cyan]Admission Dry Run (Zero Warehouse Mutation)[/bold cyan]\n"
            f"Dataset Target: [yellow]{dataset_selector}[/yellow]\n"
            f"Config: {config_path} | Sources: {sources_path} | Rules: {rules_path}\n"
            f"[dim]Guarantee: NO mutations to DuckDB lakehouse or SQLite Control Plane.[/dim]",
            title="[bold magenta]pfetl dry-run-admission[/bold magenta]",
            border_style="cyan",
        )
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task("[cyan]Evaluating dataset admission...", total=100.0)

        result: AdmissionDryRunResult = engine.dry_run_admission(
            dataset_selector=dataset_selector,
            config_path=config_path,
            rules_path=rules_path,
            sources_path=sources_path,
        )
        progress.update(task_id, completed=100.0)

    table = Table(title="[bold cyan]Admission Dry Run Outcome Summary[/bold cyan]", expand=True)
    table.add_column("Dataset ID", style="bold cyan")
    table.add_column("Status", style="bold")
    table.add_column("Rows Read", justify="right")
    table.add_column("Rows Admitted", justify="right")
    table.add_column("Duration", justify="right")
    table.add_column("Details / Schema Failures", style="white")

    for ds in result.dataset_results:
        color = (
            "green" if ds.status == "PASSED" else ("yellow" if ds.status == "SKIPPED" else "red")
        )
        details = ds.error_message or ""
        if ds.failures:
            details += f" ({len(ds.failures)} check failures)"
        table.add_row(
            ds.dataset_id.value,
            f"[{color}]{ds.status}[/{color}]",
            str(ds.rows_read),
            str(ds.rows_admitted),
            f"{ds.duration_seconds:.3f}s",
            details or "[dim]OK[/dim]",
        )

    console.print(table)
    console.print()

    if result.is_success:
        console.print(
            Panel(
                f"[bold green]✓ ADMISSION DRY RUN COMPLETED SUCCESSFULLY.[/bold green]\n"
                f"Total Admitted Rows: {result.total_rows_admitted} in {result.total_duration_seconds:.2f}s.\n"
                f"[dim]Production warehouse state verified 100% intact and unmutated.[/dim]",
                title="[bold green]Success[/bold green]",
                border_style="green",
            )
        )
        return 0

    console.print(
        Panel(
            "[bold red]✗ ADMISSION DRY RUN ENCOUNTERED FAILURES.[/bold red]\n"
            "Review schema violation details above and correct source evidence or configuration.",
            title="[bold red]Admission Check Failed[/bold red]",
            border_style="red",
        )
    )
    return 1
