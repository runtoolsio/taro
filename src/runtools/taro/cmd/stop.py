from typing import List

import typer
from rich.console import Console

from runtools.runcore import connector
from runtools.runcore.criteria import JobRunCriteria
from runtools.runcore.env import get_env_config
from runtools.runcore.util import MatchingStrategy
from runtools.taro import printer, cli, cliutil
from runtools.taro.view.instance import JOB_ID, RUN_ID, INSTANCE_ID, CREATED, PHASES

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
            console.print(f'No instances to stop: {" ".join(instance_patterns)}')
            return

        if not force:
            console.print('Instances to stop:')
            printer.print_table(instances, [JOB_ID, RUN_ID, INSTANCE_ID, CREATED, PHASES],
                                show_header=True, pager=False)
            if not cliutil.user_confirmation(yes_on_empty=True, catch_interrupt=True):
                return

        for instance in instances:
            instance.stop()
            console.print(f'Stopped {instance.id}')
