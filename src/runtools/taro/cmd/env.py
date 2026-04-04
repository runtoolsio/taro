import os
import subprocess
import tempfile
import tomllib
from typing import Optional

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.padding import Padding

from runtools.runcore.env import (
    LocalEnvironmentConfig, EnvironmentEntry,
    available_environments, load_env_config, save_env_config, lookup,
    create_environment, delete_environment,
    EnvironmentNotFoundError, EnvironmentAlreadyExistsError,
)
from runtools.runcore.util.files import format_toml, read_toml_file
from runtools.taro import cli

app = typer.Typer(name="env", invoke_without_command=True, no_args_is_help=True)
console = Console()


@app.command()
def create(
        name: str = typer.Argument(..., help="Environment name"),
        path: Optional[str] = typer.Option(None, "--path", "-p", help="Custom path for the database file"),
):
    """Create a new local environment (SQLite DB + registry entry)."""
    try:
        entry = EnvironmentEntry(id=name, driver='sqlite', location=path)  # TODO: creation wizard for driver selection
        create_environment(entry, LocalEnvironmentConfig(id=name))
        console.print(f"[green]Created environment '[bold]{name}[/bold]'[/]")
    except EnvironmentAlreadyExistsError:
        console.print(f"[red]Environment '{name}' already exists[/]")
        raise typer.Exit(1)


@app.command("list")
def list_envs():
    """List available environments."""
    envs = available_environments()
    if not envs:
        console.print("No environments available. Run [bold]taro env create <name>[/] to create one.")
        return
    for entry in envs:
        label = "[dim](built-in)[/]" if entry.is_builtin_local else f"[dim]{entry.driver}[/]"
        path_info = entry.location or "(default)"
        console.print(f"  [bold]{entry.id}[/]  {label}  {path_info}")


@app.command()
def delete(
        name: str = typer.Argument(..., help="Environment name to delete"),
        force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
):
    """Delete environment (DB file + registry entry)."""
    try:
        lookup(name)  # validate it exists (and is not built-in local)
    except EnvironmentNotFoundError:
        console.print(f"[red]Environment '{name}' not found[/]")
        raise typer.Exit(1)

    if not force:
        confirm = input(f"Delete environment '{name}' and its data? [y/N] ").strip().lower()
        if confirm != 'y':
            console.print("Cancelled")
            raise typer.Exit()

    delete_environment(name)
    console.print(f"[green]Deleted environment '[bold]{name}[/bold]'[/]")


@app.command()
def show(
        env_id: Optional[str] = cli.ENV_OPTION_FIELD,
):
    """Show DB-stored configuration for an environment."""
    entry = cli.select_env(env_id)
    env_config = load_env_config(entry)
    console.print(Padding(f"[dim]Environment:[/] [ {entry.id} ]", pad=(0, 0, 0, 0)))
    print(format_toml(env_config.model_dump(mode='json')))


@app.command()
def edit(
        env_id: Optional[str] = cli.ENV_OPTION_FIELD,
):
    """Edit DB-stored configuration in $EDITOR."""
    entry = cli.select_env(env_id)
    env_config = load_env_config(entry)

    dump = env_config.model_dump(mode='json', exclude={'type', 'id'})
    original_content = (
        "# Environment configuration (TOML format)\n"
        "# Lines starting with # are comments and ignored.\n"
        "#\n"
        "# Example plugin config:\n"
        "# [[plugins.sns.rules]]\n"
        '# term_status = "failed"\n'
        '# topic_arn = "arn:aws:sns:eu-west-1:123:alerts"\n'
        "\n"
        + format_toml(dump) + "\n"
    )

    editor = os.environ.get('EDITOR', 'vi')
    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write(original_content)
        tmp_path = f.name

    try:
        result = subprocess.run([editor, tmp_path])
        if result.returncode != 0:
            console.print("[red]Editor exited with error[/]")
            raise typer.Exit(1)

        edited = read_toml_file(tmp_path)
        original_normalized = tomllib.loads(format_toml(dump))
        if edited == original_normalized:
            console.print("[dim]No changes made[/dim]")
            os.unlink(tmp_path)
            return
        edited['type'] = 'local'
        edited['id'] = entry.id
        new_config = LocalEnvironmentConfig.model_validate(edited)
        save_env_config(entry, new_config)
        console.print(f"[green]Configuration saved for '{entry.id}'[/]")
    except typer.Exit:
        raise
    except (tomllib.TOMLDecodeError, ValidationError) as e:
        console.print(f"[red]Invalid configuration:[/] {e}")
        console.print(f"[dim]Temp file kept at: {tmp_path}[/dim]")
        raise typer.Exit(1)
    else:
        os.unlink(tmp_path)
