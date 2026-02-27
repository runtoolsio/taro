from typing import Optional

import typer
from rich.console import Console

from runtools.runcore.connector import resolve_env_dir, clean_stale_component_dirs
from runtools.runcore.env import get_env_config, EnvironmentNotFoundError, LocalEnvironmentConfig, \
    DEFAULT_LOCAL_ENVIRONMENT
from runtools.runcore.paths import ConfigFileNotFoundError
from runtools.taro import cli

app = typer.Typer(invoke_without_command=True)
console = Console()


@app.callback()
def clean(env: Optional[str] = cli.ENV_OPTION_FIELD):
    """Remove stale component directories left by dead processes."""
    try:
        env_config = get_env_config(env)
    except (EnvironmentNotFoundError, ConfigFileNotFoundError):
        env_config = None

    if env_config and not isinstance(env_config, LocalEnvironmentConfig):
        console.print(f"[yellow]Clean is only supported for local environments (got '{env_config.type}')[/]")
        raise typer.Exit(1)

    if isinstance(env_config, LocalEnvironmentConfig):
        env_dir = resolve_env_dir(env_config.id, env_config.layout.root_dir)
    else:
        env_dir = resolve_env_dir(env or DEFAULT_LOCAL_ENVIRONMENT)

    removed = clean_stale_component_dirs(env_dir)
    if removed:
        console.print(f"Cleaned {len(removed)} stale component directories:")
        for d in removed:
            console.print(f"  {d}")
    else:
        console.print(f"No stale component directories found in {env_dir}")
