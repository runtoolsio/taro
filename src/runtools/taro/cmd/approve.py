from typing import List

import typer
from rich.console import Console

from runtools.runcore import connector
from runtools.runcore.criteria import JobRunCriteria
from runtools.runcore.env import get_env_configs, get_default_env_config
from runtools.taro import cli

app = typer.Typer(invoke_without_command=True)
console = Console()


@app.callback()
def approve(
        instance_patterns: List[str] = cli.INSTANCE_PATTERNS,
        phase: str = typer.Option(..., "--phase", "-p", help="Phase ID"),
        env_ids: List[str] = cli.ENV_OPTION_FIELD,
):
    env_configs = get_env_configs(*env_ids).values() if env_ids else [get_default_env_config()]
    approved = False
    for env_conf in env_configs:
        with connector.create(env_conf) as conn:
            instances = conn.get_instances(JobRunCriteria.parse_all(instance_patterns))
            for inst in instances:
                pc = inst.find_phase_control_by_id(phase)
                if pc:
                    pc.approve()
                    approved = True
                    console.print(f"[green]\uf00c[/] Approved [bold]{inst.id}[/] ([cyan]{env_conf.id}[/])")

    env_list = ", ".join(f"[cyan]{env_conf.id}[/]" for env_conf in sorted(env_configs))
    if approved:
        console.print(f"\nDone in {env_list}")
    else:
        console.print(f"\n[yellow]\uf071[/] No instances approved in {env_list}")
