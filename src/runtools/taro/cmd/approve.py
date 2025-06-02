from typing import List, Optional

import typer
from rich.console import Console

from runtools.runcore import connector
from runtools.runcore.criteria import JobRunCriteria
from runtools.runcore.env import get_env_config
from runtools.runcore.util import MatchingStrategy
from runtools.taro import cli

app = typer.Typer(invoke_without_command=True)
console = Console()


@app.callback()
def approve(
        instance_patterns: List[str] = cli.INSTANCE_PATTERNS,
        phase: str = typer.Option(..., "--phase", "-p", help="Phase ID"),
        env_id: Optional[str] = cli.ENV_OPTION_FIELD,
):
    """Approve jobs waiting in pending state"""
    approved = False
    env_config = get_env_config(env_id)
    with connector.create(env_config) as conn:
        instances = conn.get_instances(JobRunCriteria.parse_all(instance_patterns, strategy=MatchingStrategy.FN_MATCH))
        for inst in instances:
            pc = inst.find_phase_control_by_id(phase)
            if pc:
                pc.approve()
                approved = True
                console.print(f"[green]\uf00c[/] Approved [bold]{inst.id}[/]")

    if approved:
        console.print(f"\nDone in [cyan]{env_config.id}[/]")
    else:
        console.print(f"\n[yellow]\uf071[/] No instances approved in [cyan]{env_config.id}[/]")
