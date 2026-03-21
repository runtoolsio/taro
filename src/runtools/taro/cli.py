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


def select_env(env_id: Optional[str] = None) -> EnvironmentEntry:
    """Select an environment, prompting the user interactively if ambiguous."""
    try:
        resolved = resolve_env_id(env_id)
    except AmbiguousEnvironmentError as e:
        import sys
        if not sys.stdin.isatty():
            _console.print(f"[red]Multiple environments available: {', '.join(e.available)}. "
                           f"Use -e/--env to select one.[/]")
            raise typer.Exit(1)
        _console.print("\n[bold]Multiple environments available:[/]")
        for i, eid in enumerate(e.available, 1):
            _console.print(f"  [cyan]{i}[/]) {eid}")
        _console.print()
        while True:
            try:
                choice = input("Select environment [1]: ").strip()
                idx = 0 if not choice else int(choice) - 1
                if 0 <= idx < len(e.available):
                    resolved = e.available[idx]
                    break
                _console.print(f"[red]Invalid choice. Enter 1-{len(e.available)}[/]")
            except (ValueError, EOFError):
                raise typer.Exit(1)
            except KeyboardInterrupt:
                raise typer.Exit(130)
    except EnvironmentNotFoundError:
        _console.print("[red]No environments found.[/] Run [bold]taro env create <name>[/] first.")
        raise typer.Exit(1)

    return lookup(resolved)
