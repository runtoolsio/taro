from typing import List, Optional

import typer
from rich.console import Console
from rich.padding import Padding

from runtools.runcore import connector
from runtools.runcore.criteria import JobRunCriteria, SortOption
from runtools.runcore.env import get_env_configs
from runtools.runcore.util import MatchingStrategy
from runtools.taro import printer, cli, cliutil
from runtools.taro.view import instance as view_inst

app = typer.Typer(name="ps", invoke_without_command=True)
console = Console()


@app.callback()
def ps(
        instance_patterns: List[str] = typer.Argument(
            default=None,
            metavar="PATTERN",
            help="Instance ID patterns to filter results"
        ),
        env: Optional[str] = cli.ENV_OPTION_FIELD,
        all_envs: bool = typer.Option(False, "--all", "-a", help="Show instances from all environments"),
        sort_option: SortOption = typer.Option(SortOption.CREATED, "--sort", "-s",
                                               help="Sorting criteria (created/ended/time/job_id/run_id)"),
        descending: bool = typer.Option(False, "--descending", "-d", help="Sort in descending order"),
):
    """Show active/running job instances"""
    run_match = JobRunCriteria.parse_all(instance_patterns,
                                         MatchingStrategy.PARTIAL) if instance_patterns else JobRunCriteria.all()
    if all_envs:
        env_configs = get_env_configs().values()
        connectors = [(env_config.id, connector.create(env_config)) for env_config in env_configs]
    else:
        conn = connector.connect(env)
        connectors = [(conn.env_id, conn)]

    empty_envs = []
    for env_id, conn in connectors:
        with conn:
            runs = conn.get_active_runs(run_match)

        if not runs:
            empty_envs.append(env_id)
            continue

        console.print(Padding(f"[dim]Active instances in [/][ {env_id} ]", pad=(0, 0, 0, 0)))
        columns = [view_inst.JOB_ID, view_inst.RUN_ID, view_inst.CREATED, view_inst.EXEC_TIME, view_inst.PHASES,
                   view_inst.WARNINGS,
                   view_inst.STATUS]
        runs_sorted = sort_option.sort_runs(runs, reverse=descending)
        try:
            printer.print_table(runs_sorted, columns, show_header=True, pager=False)
            console.print()
        except BrokenPipeError:
            cliutil.handle_broken_pipe(exit_code=1)

    for empty_env in empty_envs:
        console.print(f"No active instances found in [cyan]{empty_env}[/]")
