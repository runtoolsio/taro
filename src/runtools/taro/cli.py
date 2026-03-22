import sys
from typing import Optional

import typer
from rich.console import Console

from runtools.runcore.env import (
    EnvironmentEntry, AmbiguousEnvironmentError, EnvironmentNotFoundError,
    resolve_env_id, lookup,
)

_console = Console(stderr=True)

ENV_OPTION_FIELD = typer.Option(None, "--env", "-e", help="Target environment")
INSTANCE_PATTERNS = typer.Argument(..., help="One or more instance ID (metadata) patterns", metavar="PATTERN")
INSTANCE_PATTERNS_OPTIONAL = typer.Argument(
    default=None, help="Instance ID patterns (interactive selector when omitted)", metavar="PATTERN"
)


def _is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stderr.isatty()


def select_env(env_id: Optional[str] = None) -> EnvironmentEntry:
    """Select an environment, prompting the user interactively if ambiguous."""
    try:
        resolved = resolve_env_id(env_id)
    except AmbiguousEnvironmentError as e:
        if not _is_interactive():
            _console.print(f"[red]Multiple environments available: {', '.join(e.available)}. "
                           f"Use -e/--env to select one.[/]")
            raise typer.Exit(1)
        resolved = _prompt_env_select(e.available)
    except EnvironmentNotFoundError:
        _console.print("[red]No environments found.[/] Run [bold]taro env create <name>[/] first.")
        raise typer.Exit(1)

    return lookup(resolved)


def _prompt_env_select(choices: list[str]) -> str:
    import questionary
    from runtools.taro.theme import prompt_style

    try:
        result = questionary.select(
            "Select environment:", choices=choices, style=prompt_style(),
            qmark="", instruction="",
        ).ask()
    except KeyboardInterrupt:
        raise typer.Exit(130)

    if result is None:
        _console.print("[red]Selection cancelled.[/] Use -e/--env to specify an environment.")
        raise typer.Exit(1)
    return result
