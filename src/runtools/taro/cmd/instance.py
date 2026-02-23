"""Instance detail TUI command — shows a detailed view of a single job instance."""

from typing import Optional

import typer
from rich.console import Console

from runtools.runcore import connector
from runtools.runcore.criteria import JobRunCriteria
from runtools.runcore.job import JobInstance, JobRun
from runtools.runcore.util import MatchingStrategy
from runtools.taro import cli
from runtools.taro.tui.instance_screen import InstanceApp
from runtools.taro.tui.selector import select_instance_or_run

app = typer.Typer(invoke_without_command=True)
console = Console(stderr=True)


@app.callback()
def instance(
        pattern: Optional[str] = typer.Argument(default=None, help="Instance ID pattern (job_id, run_id, or job_id@run_id)"),
        env: Optional[str] = cli.ENV_OPTION_FIELD,
):
    """Open a detailed TUI view for a job instance.

    Tries to find a live (active) instance first. If not found, falls back to history.
    If multiple instances match or no pattern is given, prompts for selection.

    Examples:
        taro instance
        taro instance my-pipeline
        taro instance "my-pipeline@batch-42"
        taro instance my-pipeline --env production
    """
    run_match = JobRunCriteria.parse(pattern, MatchingStrategy.PARTIAL) if pattern else JobRunCriteria()

    with connector.connect(env) as conn:
        instances = list(conn.get_instances(run_match))

        history_runs = conn.read_history_runs(run_match, asc=False, limit=10)

        # Deduplicate: exclude history runs that are also active
        active_ids = {inst.id for inst in instances}
        history_runs = [r for r in history_runs if r.instance_id not in active_ids]

        total = len(instances) + len(history_runs)

        if total == 0:
            if pattern:
                console.print(f"[red]No instance found matching:[/] {pattern}")
            else:
                console.print("[red]No instances found[/]")
            raise typer.Exit(1)

        # Single match with explicit pattern — open directly
        if total == 1 and pattern:
            if instances:
                _run_live(instances[0])
            else:
                _run_historical(history_runs[0])
            return

        # Multiple matches or no pattern — show combined selector
        selected = select_instance_or_run(conn, instances, history_runs, run_match=run_match)
        if isinstance(selected, JobInstance):
            _run_live(selected)
        elif isinstance(selected, JobRun):
            _run_historical(selected)


def _run_live(job_instance: JobInstance):
    """Launch the TUI app with a live instance."""
    InstanceApp(instance=job_instance).run()


def _run_historical(job_run: JobRun):
    """Launch the TUI app with a historical run."""
    InstanceApp(job_run=job_run).run()
