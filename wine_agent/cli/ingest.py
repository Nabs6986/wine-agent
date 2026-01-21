"""
Ingestion CLI Commands
======================

CLI commands for managing the wine data ingestion pipeline.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from wine_agent.ingestion.adapters import get_adapter_info, list_adapters
from wine_agent.ingestion.jobs import (
    JobStatus,
    enqueue_ingestion,
    get_job_status,
    ingest_source_sync,
)
from wine_agent.ingestion.registry import get_default_registry, reset_default_registry

console = Console()
ingest_app = typer.Typer(help="Ingestion pipeline commands")
sources_app = typer.Typer(help="Source management commands")
jobs_app = typer.Typer(help="Job management commands")

ingest_app.add_typer(sources_app, name="sources")
ingest_app.add_typer(jobs_app, name="jobs")


@ingest_app.command("run")
def run_ingestion(
    source: str = typer.Option(..., "--source", "-s", help="Source name to ingest"),
    max_urls: Optional[int] = typer.Option(None, "--max", "-m", help="Maximum URLs to process"),
    sync: bool = typer.Option(False, "--sync", help="Run synchronously (blocking)"),
) -> None:
    """
    Run the ingestion pipeline for a source.

    Examples:
        wine-agent ingest run --source=test-wines --max=10 --sync
        wine-agent ingest run -s test-wines -m 50
    """
    registry = get_default_registry()
    source_config = registry.get_source(source)

    if source_config is None:
        rprint(f"[red]Error:[/red] Source '{source}' not found")
        rprint("\nAvailable sources:")
        for s in registry.list_sources():
            status = "[green]enabled[/green]" if s.enabled else "[yellow]disabled[/yellow]"
            rprint(f"  • {s.name} ({status})")
        raise typer.Exit(1)

    if not source_config.enabled:
        rprint(f"[yellow]Warning:[/yellow] Source '{source}' is disabled")
        if not typer.confirm("Run anyway?"):
            raise typer.Exit(0)

    rprint(f"\n[bold]Starting ingestion for source:[/bold] {source}")
    rprint(f"  Domain: {source_config.domain}")
    rprint(f"  Adapter: {source_config.adapter}")
    if max_urls:
        rprint(f"  Max URLs: {max_urls}")

    if sync:
        # Run synchronously
        rprint("\n[dim]Running synchronously...[/dim]\n")

        with console.status("[bold blue]Ingesting...[/bold blue]"):
            result = asyncio.run(ingest_source_sync(source, max_urls))

        # Display results
        _display_job_result(result.to_dict())

        if result.status == JobStatus.FAILED:
            raise typer.Exit(1)
    else:
        # Enqueue for async processing
        rprint("\n[dim]Enqueueing job for async processing...[/dim]")

        try:
            job_id = asyncio.run(enqueue_ingestion(source, max_urls))
            rprint(f"\n[green]Job enqueued successfully![/green]")
            rprint(f"Job ID: [bold]{job_id}[/bold]")
            rprint("\nCheck status with:")
            rprint(f"  wine-agent ingest jobs status {job_id}")
        except Exception as e:
            rprint(f"\n[red]Error:[/red] Failed to enqueue job: {e}")
            rprint("\nMake sure Redis is running:")
            rprint("  docker-compose up -d redis")
            raise typer.Exit(1)


@ingest_app.command("worker")
def start_worker(
    burst: bool = typer.Option(False, "--burst", help="Run in burst mode (exit when queue empty)"),
) -> None:
    """
    Start the ingestion worker.

    The worker processes queued ingestion jobs from Redis.

    Examples:
        wine-agent ingest worker
        wine-agent ingest worker --burst
    """
    rprint("[bold]Starting ingestion worker...[/bold]")
    rprint("Press Ctrl+C to stop\n")

    try:
        from arq import run_worker

        from wine_agent.ingestion.jobs import WorkerSettings

        # Run the worker
        run_worker(WorkerSettings, burst=burst)
    except ImportError:
        rprint("[red]Error:[/red] arq package not installed")
        rprint("Install with: pip install arq")
        raise typer.Exit(1)
    except Exception as e:
        rprint(f"[red]Error:[/red] Worker failed: {e}")
        rprint("\nMake sure Redis is running:")
        rprint("  docker-compose up -d redis")
        raise typer.Exit(1)


# Sources subcommands


@sources_app.command("list")
def list_sources(
    all_sources: bool = typer.Option(False, "--all", "-a", help="Show all sources including disabled"),
) -> None:
    """
    List configured ingestion sources.

    Examples:
        wine-agent ingest sources list
        wine-agent ingest sources list --all
    """
    registry = get_default_registry()
    sources = registry.list_sources() if all_sources else registry.list_enabled_sources()

    if not sources:
        rprint("[yellow]No sources configured[/yellow]")
        rprint("\nAdd sources to config/sources.yaml")
        return

    table = Table(title="Ingestion Sources")
    table.add_column("Name", style="bold")
    table.add_column("Domain")
    table.add_column("Adapter")
    table.add_column("Status")
    table.add_column("Rate Limit")

    for source in sources:
        status = "[green]enabled[/green]" if source.enabled else "[yellow]disabled[/yellow]"
        rate = f"{source.rate_limit.requests_per_second}/s"
        table.add_row(source.name, source.domain, source.adapter, status, rate)

    console.print(table)


@sources_app.command("show")
def show_source(
    name: str = typer.Argument(..., help="Source name"),
) -> None:
    """
    Show detailed information about a source.

    Examples:
        wine-agent ingest sources show test-wines
    """
    registry = get_default_registry()
    source = registry.get_source(name)

    if source is None:
        rprint(f"[red]Error:[/red] Source '{name}' not found")
        raise typer.Exit(1)

    status = "[green]enabled[/green]" if source.enabled else "[yellow]disabled[/yellow]"

    rprint(f"\n[bold]Source: {source.name}[/bold]")
    rprint(f"  Status: {status}")
    rprint(f"  Domain: {source.domain}")
    rprint(f"  Adapter: {source.adapter}")
    if source.description:
        rprint(f"  Description: {source.description}")

    rprint("\n[bold]Rate Limiting:[/bold]")
    rprint(f"  Requests/second: {source.rate_limit.requests_per_second}")
    rprint(f"  Burst limit: {source.rate_limit.burst_limit}")

    if source.allowlist:
        rprint("\n[bold]Allowlist Patterns:[/bold]")
        for pattern in source.allowlist:
            rprint(f"  • {pattern}")

    if source.denylist:
        rprint("\n[bold]Denylist Patterns:[/bold]")
        for pattern in source.denylist:
            rprint(f"  • {pattern}")

    if source.seed_urls:
        rprint("\n[bold]Seed URLs:[/bold]")
        for url in source.seed_urls:
            rprint(f"  • {url}")

    # Show adapter info
    adapter_info = get_adapter_info(source.adapter)
    if adapter_info:
        rprint("\n[bold]Adapter Info:[/bold]")
        rprint(f"  Name: {adapter_info['name']}")
        rprint(f"  Version: {adapter_info['version']}")
        rprint(f"  Class: {adapter_info['class']}")


@sources_app.command("enable")
def enable_source(
    name: str = typer.Argument(..., help="Source name"),
) -> None:
    """
    Enable a source.

    Note: This only affects the in-memory registry.
    To persist, edit config/sources.yaml.

    Examples:
        wine-agent ingest sources enable test-wines
    """
    registry = get_default_registry()

    if registry.enable_source(name):
        rprint(f"[green]Source '{name}' enabled[/green]")
        rprint("\n[dim]Note: Edit config/sources.yaml to persist this change[/dim]")
    else:
        rprint(f"[red]Error:[/red] Source '{name}' not found")
        raise typer.Exit(1)


@sources_app.command("disable")
def disable_source(
    name: str = typer.Argument(..., help="Source name"),
) -> None:
    """
    Disable a source.

    Note: This only affects the in-memory registry.
    To persist, edit config/sources.yaml.

    Examples:
        wine-agent ingest sources disable test-wines
    """
    registry = get_default_registry()

    if registry.disable_source(name):
        rprint(f"[yellow]Source '{name}' disabled[/yellow]")
        rprint("\n[dim]Note: Edit config/sources.yaml to persist this change[/dim]")
    else:
        rprint(f"[red]Error:[/red] Source '{name}' not found")
        raise typer.Exit(1)


@sources_app.command("adapters")
def list_source_adapters() -> None:
    """
    List available adapters.

    Examples:
        wine-agent ingest sources adapters
    """
    adapters = list_adapters()

    if not adapters:
        rprint("[yellow]No adapters registered[/yellow]")
        return

    table = Table(title="Available Adapters")
    table.add_column("Name", style="bold")
    table.add_column("Version")
    table.add_column("Class")

    for adapter_name in adapters:
        info = get_adapter_info(adapter_name)
        if info:
            table.add_row(info["name"], info["version"], info["class"])

    console.print(table)


# Jobs subcommands


@jobs_app.command("status")
def job_status(
    job_id: Optional[str] = typer.Argument(None, help="Job ID to check"),
) -> None:
    """
    Check the status of ingestion jobs.

    Examples:
        wine-agent ingest jobs status
        wine-agent ingest jobs status abc123
    """
    if job_id:
        # Get specific job
        try:
            result = asyncio.run(get_job_status(job_id))

            if result is None:
                rprint(f"[yellow]Job '{job_id}' not found[/yellow]")
                raise typer.Exit(1)

            rprint(f"\n[bold]Job: {job_id}[/bold]")
            rprint(f"  Status: {result.get('status', 'unknown')}")

            if result.get("result"):
                _display_job_result(result["result"])

        except Exception as e:
            rprint(f"[red]Error:[/red] Failed to get job status: {e}")
            rprint("\nMake sure Redis is running")
            raise typer.Exit(1)
    else:
        # List recent jobs
        rprint("[yellow]Job listing not yet implemented[/yellow]")
        rprint("Specify a job ID to check its status:")
        rprint("  wine-agent ingest jobs status <job_id>")


def _display_job_result(result: dict) -> None:
    """Display job result in a formatted table."""
    status = result.get("status", "unknown")
    status_color = {
        "completed": "green",
        "running": "blue",
        "pending": "yellow",
        "failed": "red",
    }.get(status, "white")

    rprint(f"\n[bold]Results:[/bold]")
    rprint(f"  Status: [{status_color}]{status}[/{status_color}]")
    rprint(f"  Source: {result.get('source_name', 'N/A')}")

    if result.get("duration_seconds"):
        rprint(f"  Duration: {result['duration_seconds']:.1f}s")

    rprint(f"\n[bold]Statistics:[/bold]")
    rprint(f"  URLs discovered: {result.get('urls_discovered', 0)}")
    rprint(f"  URLs fetched: {result.get('urls_fetched', 0)}")
    rprint(f"  Listings created: {result.get('listings_created', 0)}")
    rprint(f"  Entities created: {result.get('entities_created', 0)}")
    rprint(f"  Entities matched: {result.get('entities_matched', 0)}")
    rprint(f"  Review queue: {result.get('review_queue_count', 0)}")

    errors = result.get("errors", [])
    if errors:
        rprint(f"\n[bold red]Errors ({len(errors)}):[/bold red]")
        for error in errors[:10]:  # Show first 10
            rprint(f"  • {error}")
        if len(errors) > 10:
            rprint(f"  ... and {len(errors) - 10} more")
