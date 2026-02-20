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

app = typer.Typer(invoke_without_command=True)
console = Console(stderr=True)


@app.callback()
def instance(
        pattern: str = typer.Argument(help="Instance ID pattern (job_id, run_id, or job_id@run_id)"),
        env: Optional[str] = cli.ENV_OPTION_FIELD,
):
    """Open a detailed TUI view for a job instance.

    Tries to find a live (active) instance first. If not found, falls back to history.
    If multiple instances match, prompts for selection.

    Examples:
        taro instance my-pipeline
        taro instance "my-pipeline@batch-42"
        taro instance my-pipeline --env production
    """
    run_match = JobRunCriteria.parse(pattern, MatchingStrategy.PARTIAL)

    with connector.connect(env) as conn:
        # Try active instances first
        instances = list(conn.get_instances(run_match))

        if len(instances) == 1:
            _run_live(instances[0])
            return

        if len(instances) > 1:
            selected = _select_instance(instances)
            if selected is not None:
                _run_live(selected)
            return

        # No active instances — try history
        history_runs = conn.read_history_runs(run_match, asc=False, limit=10)

        if not history_runs:
            console.print(f"[red]No instance found matching:[/] {pattern}")
            raise typer.Exit(1)

        if len(history_runs) == 1:
            _run_historical(history_runs[0])
            return

        selected_run = _select_run(history_runs)
        if selected_run is not None:
            _run_historical(selected_run)


def _run_live(job_instance: JobInstance):
    """Launch the TUI app with a live instance."""
    InstanceApp(instance=job_instance).run()


def _run_historical(job_run: JobRun):
    """Launch the TUI app with a historical run."""
    InstanceApp(job_run=job_run).run()


def _select_instance(instances) -> Optional[JobInstance]:
    """Prompt user to select from multiple active instances."""
    console.print("\n[bold]Multiple active instances found:[/]\n")
    for i, inst in enumerate(instances, 1):
        snap = inst.snap()
        stage = snap.lifecycle.stage.name
        console.print(f"  [{i}] {snap.job_id}@{snap.run_id}  {stage}")

    console.print()
    selection = typer.prompt("Select instance number (or 'q' to quit)", default="1")
    if selection.lower() == "q":
        return None
    try:
        idx = int(selection) - 1
        if 0 <= idx < len(instances):
            return instances[idx]
    except ValueError:
        pass
    console.print("[red]Invalid selection[/]")
    return None


def _select_run(runs) -> Optional[JobRun]:
    """Prompt user to select from multiple historical runs."""
    console.print("\n[bold]Multiple historical runs found:[/]\n")
    for i, run in enumerate(runs, 1):
        term = run.lifecycle.termination
        status_name = term.status.name if term else run.lifecycle.stage.name
        console.print(f"  [{i}] {run.job_id}@{run.run_id}  {status_name}")

    console.print()
    selection = typer.prompt("Select run number (or 'q' to quit)", default="1")
    if selection.lower() == "q":
        return None
    try:
        idx = int(selection) - 1
        if 0 <= idx < len(runs):
            return runs[idx]
    except ValueError:
        pass
    console.print("[red]Invalid selection[/]")
    return None
