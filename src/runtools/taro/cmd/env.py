from typing import Optional

import typer
from rich.console import Console
from rich.padding import Padding

from runtools.runcore.env import get_env_config, get_env_configs
from runtools.runcore.util.files import format_toml
from runtools.taro import cli

app = typer.Typer(name="env", invoke_without_command=True)
console = Console()


@app.callback()
def env(
        env: Optional[str] = cli.ENV_OPTION_FIELD,
        all_envs: bool = typer.Option(False, "--all", "-a", help="Show all environments"),
):
    """Show resolved environment configuration"""
    env_configs = get_env_configs().values() if all_envs else [get_env_config(env)]
    for i, env_config in enumerate(env_configs):
        if all_envs:
            if i > 0:
                console.print()
            console.print(Padding(f"[dim]Environment:[/] [ {env_config.id} ]", pad=(0, 0, 0, 0)))
        toml_output = format_toml(env_config.model_dump(mode='json'))
        print(toml_output)
        if all_envs:
            console.print(f"[dim]{'─' * 30}[/]")
