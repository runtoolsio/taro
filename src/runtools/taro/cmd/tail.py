from typing import List, Optional

import typer
from rich.console import Console
from runtools.runcore import connector

from runtools.runcore.criteria import JobRunCriteria
from runtools.runcore.env import get_env_config
from runtools.runcore.util import MatchingStrategy
from runtools.taro import cli

app = typer.Typer(name="tail", invoke_without_command=True)
console = Console()


@app.callback()
def tail(
        instance_patterns: List[str] = typer.Argument(
            default=None,
            metavar="PATTERN",
            help="Instance filter patterns"
        ),
        env: Optional[str] = cli.ENV_OPTION_FIELD,
        follow: bool = typer.Option(
            False,
            "-f", "--follow",
            help="Keep printing"
        ),
):
    """Print last output from job instances"""
    run_match = JobRunCriteria.parse_all(instance_patterns,
                                         MatchingStrategy.PARTIAL) if instance_patterns else JobRunCriteria.all()
    with connector.create(get_env_config(env)) as conn:
        for inst in conn.get_instances(run_match):
            console.print(f"\n[bold cyan]{'─' * 20}[/] [bold]{inst.job_id}@{inst.run_id}[/] [bold cyan]{'─' * 20}[/]")
            tail_list = inst.output.tail()
            for output_line in tail_list:
                if output_line.is_error:
                    console.print(f"[red]{output_line.text}[/]", highlight=False)
                else:
                    console.print(output_line.text, highlight=False)
