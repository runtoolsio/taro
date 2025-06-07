from typing import List

import typer
from rich.console import Console
from rich.padding import Padding

from runtools.runcore import connector
from runtools.runcore.criteria import JobRunCriteria
from runtools.runcore.env import get_env_config
from runtools.runcore.util import MatchingStrategy
from runtools.taro import printer, cli, cliutil
from runtools.taro.view.instance import JOB_ID, RUN_ID, EXEC_TIME, CREATED, PHASES, STATUS

app = typer.Typer(invoke_without_command=True)
console = Console()


@app.callback()
def stop(
        instance_patterns: List[str] = typer.Argument(
            metavar="PATTERN",
            help="Instance ID patterns to match for stopping"
        ),
        env: str = cli.ENV_OPTION_FIELD,
        force: bool = typer.Option(
            False,
            "--force",
            "-f",
            help="Skip confirmation prompt and force stop all matching instances"
        ),
):
    """Stop running job instances"""
    run_match = JobRunCriteria.parse_all(instance_patterns, MatchingStrategy.FN_MATCH)
    env_config = get_env_config(env)

    with connector.create(env_config) as conn:
        instances = conn.get_instances(run_match)

        if not instances:
            console.print(f'No instances to stop in [ {env_config.id} ]')
            return

        if not force:
            console.print(Padding(f"[dim]Instances to stop in [/][ {env_config.id} ]", pad=(0, 0, 0, 0)))
            printer.print_table([i.snapshot() for i in instances],
                                [JOB_ID, RUN_ID, CREATED, EXEC_TIME, PHASES, STATUS],
                                show_header=True, pager=False)
            if not cliutil.user_confirmation(yes_on_empty=True, catch_interrupt=True, newline_before=True):
                return

        for instance in instances:
            instance.stop()
            console.print(f'Stopped {instance.id}')
