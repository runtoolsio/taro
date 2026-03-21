from typing import Optional

import typer
from rich.console import Console

from runtools.runcore.connector import resolve_env_dir, clean_stale_component_dirs
from runtools.runcore.env import load_env_config
from runtools.taro import cli

app = typer.Typer(invoke_without_command=True)
console = Console()


@app.callback()
def clean(env: Optional[str] = cli.ENV_OPTION_FIELD):
    """Remove stale component directories left by dead processes."""
    entry = cli.select_env(env)
    env_config = load_env_config(entry)
    env_dir = resolve_env_dir(env_config.id, env_config.layout.root_dir)

    removed = clean_stale_component_dirs(env_dir)
    if removed:
        console.print(f"Cleaned {len(removed)} stale component directories:")
        for d in removed:
            console.print(f"  {d}")
    else:
        console.print(f"No stale component directories found in {env_dir}")
