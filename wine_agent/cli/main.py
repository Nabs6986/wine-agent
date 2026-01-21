"""Wine Agent CLI using Typer."""

import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

import typer
from dotenv import load_dotenv

# Load .env file from current directory or project root
_env_paths = [
    Path.cwd() / ".env",
    Path(__file__).parent.parent.parent / ".env",
]
for _env_path in _env_paths:
    if _env_path.exists():
        load_dotenv(_env_path)
        break

app = typer.Typer(
    name="wine-agent",
    help="Wine Agent - A local-first app for capturing and managing wine tasting notes",
    add_completion=False,
)


def _check_ai_config() -> None:
    """Check and display AI configuration status."""
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    provider = os.environ.get("AI_PROVIDER", "anthropic")

    if anthropic_key and anthropic_key != "your-anthropic-api-key-here":
        typer.echo(f"  AI Provider: Anthropic (configured)")
    elif openai_key and openai_key != "your-openai-api-key-here":
        typer.echo(f"  AI Provider: OpenAI (configured)")
    else:
        typer.echo("  AI Provider: Not configured (conversion will create placeholder drafts)")
        typer.echo("  Tip: Set ANTHROPIC_API_KEY in .env file to enable AI conversion")


@app.command()
def run(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind to"),
    reload: bool = typer.Option(
        False, "--reload", "-r", help="Enable auto-reload for development"
    ),
) -> None:
    """Start the Wine Agent web server."""
    import uvicorn

    typer.echo(f"Starting Wine Agent on http://{host}:{port}")
    _check_ai_config()
    typer.echo("Press Ctrl+C to stop the server")
    typer.echo("")

    uvicorn.run(
        "wine_agent.web.app:app",
        host=host,
        port=port,
        reload=reload,
    )


@app.command()
def init_db() -> None:
    """Initialize the database (create tables)."""
    from wine_agent.db.engine import init_db as db_init

    typer.echo("Initializing database...")
    db_init()
    typer.echo("Database initialized successfully!")


@app.command()
def version() -> None:
    """Show the Wine Agent version."""
    typer.echo("Wine Agent v0.1.0")


@app.command()
def check_config() -> None:
    """Check the current configuration status."""
    typer.echo("Wine Agent Configuration")
    typer.echo("=" * 40)

    # Check .env file
    env_found = False
    for _env_path in _env_paths:
        if _env_path.exists():
            typer.echo(f"  .env file: {_env_path}")
            env_found = True
            break
    if not env_found:
        typer.echo("  .env file: Not found")

    # Check AI config
    _check_ai_config()

    # Check database
    from wine_agent.db.engine import get_database_url
    db_url = get_database_url()
    typer.echo(f"  Database: {db_url}")


def _get_db_path() -> Path:
    """Get the current database file path."""
    from wine_agent.db.engine import get_database_url

    url = get_database_url()
    # Extract path from sqlite:///path format
    if url.startswith("sqlite:///"):
        return Path(url[10:])
    return Path(url)


def _is_valid_sqlite(path: Path) -> bool:
    """Check if a file is a valid SQLite database."""
    if not path.exists():
        return False
    try:
        conn = sqlite3.connect(str(path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
        conn.close()
        return True
    except sqlite3.DatabaseError:
        return False


@app.command()
def backup(
    output_dir: Path = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Directory to save backup (default: same directory as database)",
    ),
    include_exports: bool = typer.Option(
        False,
        "--include-exports",
        "-e",
        help="Also export all notes as JSON and Markdown",
    ),
) -> None:
    """Create a timestamped backup of the database."""
    db_path = _get_db_path()

    if not db_path.exists():
        typer.echo(f"Error: Database not found at {db_path}", err=True)
        raise typer.Exit(1)

    # Determine output directory
    if output_dir is None:
        output_dir = db_path.parent
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create timestamped backup filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"wine_agent_backup_{timestamp}.db"
    backup_path = output_dir / backup_filename

    # Copy database file
    typer.echo(f"Creating backup...")
    shutil.copy2(db_path, backup_path)

    # Get file size
    size_bytes = backup_path.stat().st_size
    if size_bytes < 1024:
        size_str = f"{size_bytes} bytes"
    elif size_bytes < 1024 * 1024:
        size_str = f"{size_bytes / 1024:.1f} KB"
    else:
        size_str = f"{size_bytes / (1024 * 1024):.1f} MB"

    typer.echo(f"  Backup created: {backup_path}")
    typer.echo(f"  Size: {size_str}")

    # Optionally export notes
    if include_exports:
        from wine_agent.db.engine import get_session
        from wine_agent.services.export_service import ExportService

        export_dir = output_dir / f"wine_agent_export_{timestamp}"
        export_dir.mkdir(parents=True, exist_ok=True)

        with get_session() as session:
            export_service = ExportService(session)

            # Export JSON
            json_content = export_service.export_notes_json(status="published")
            json_path = export_dir / "notes.json"
            json_path.write_text(json_content)
            typer.echo(f"  JSON export: {json_path}")

            # Export CSV
            csv_content = export_service.export_notes_csv(status="published")
            csv_path = export_dir / "notes.csv"
            csv_path.write_text(csv_content)
            typer.echo(f"  CSV export: {csv_path}")

    typer.echo("")
    typer.echo("Backup completed successfully!")


@app.command()
def restore(
    backup_path: Path = typer.Argument(..., help="Path to the backup file to restore"),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompt",
    ),
) -> None:
    """Restore the database from a backup file."""
    backup_path = Path(backup_path)

    # Validate backup file
    if not backup_path.exists():
        typer.echo(f"Error: Backup file not found: {backup_path}", err=True)
        raise typer.Exit(1)

    if not _is_valid_sqlite(backup_path):
        typer.echo(f"Error: Invalid SQLite database: {backup_path}", err=True)
        raise typer.Exit(1)

    db_path = _get_db_path()

    # Show info and confirm
    backup_size = backup_path.stat().st_size
    typer.echo(f"Backup file: {backup_path}")
    typer.echo(f"Backup size: {backup_size / 1024:.1f} KB")
    typer.echo(f"Target database: {db_path}")

    if db_path.exists():
        current_size = db_path.stat().st_size
        typer.echo(f"Current database size: {current_size / 1024:.1f} KB")
        typer.echo("")
        typer.echo("WARNING: This will overwrite your current database!")

    if not force:
        confirm = typer.confirm("Do you want to proceed?")
        if not confirm:
            typer.echo("Restore cancelled.")
            raise typer.Exit(0)

    # Create safety backup of current database before restore
    if db_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safety_backup = db_path.parent / f"wine_agent_pre_restore_{timestamp}.db"
        shutil.copy2(db_path, safety_backup)
        typer.echo(f"Safety backup created: {safety_backup}")

    # Restore from backup
    typer.echo("Restoring database...")
    shutil.copy2(backup_path, db_path)

    typer.echo("")
    typer.echo("Database restored successfully!")
    typer.echo("Note: Restart the web server if it's running.")


if __name__ == "__main__":
    app()
