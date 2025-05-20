from typing import List

import typer
from rich.console import Console

from runtools.runcore import connector
from runtools.runcore.criteria import JobRunCriteria
from runtools.runcore.env import resolve_env_configs

app = typer.Typer(invoke_without_command=True)
console = Console()

def env_option():
    return typer.Option((), "--env", "-e", help="Target environment")


@app.callback()
def approve(
        instance_patterns: List[str] = typer.Argument(..., help="One or more instance ID (metadata) patterns",
                                                      metavar="PATTERN"),
        phase: str = typer.Option(..., "--phase", "-p", help="Phase ID"),
        env_ids: List[str] = env_option(),
):
    env_configs = resolve_env_configs(*env_ids)
    approved = False
    for env_name, env_conf in env_configs.items():
        with connector.create(env_conf) as conn:
            instances = conn.get_instances(JobRunCriteria.parse_all(instance_patterns))
            for inst in instances:
                pc = inst.find_phase_control_by_id(phase)
                if pc:
                    pc.approve()
                    approved = True
                    console.print(f"[green]\uf00c[/] Approved [bold]{inst.id}[/] ([cyan]{env_name}[/])")

    env_list = ", ".join(f"[cyan]{name}[/]" for name in sorted(env_configs))
    if approved:
        console.print(f"\nDone in {env_list}")
    else:
        console.print(f"\n[yellow]\uf071[/] No instances approved in {env_list}")
