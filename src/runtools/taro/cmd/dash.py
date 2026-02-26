"""Dashboard TUI command — persistent overview of active instances and history."""

from typing import Optional

import typer

from runtools.runcore import connector
from runtools.runcore.criteria import JobRunCriteria
from runtools.runcore.util import MatchingStrategy
from runtools.taro import cli
from runtools.taro.tui.dashboard import DashboardApp

app = typer.Typer(invoke_without_command=True)


@app.callback()
def dash(
        pattern: Optional[str] = typer.Argument(default=None, help="Instance ID pattern (job_id, run_id, or job_id@run_id)"),
        env: Optional[str] = cli.ENV_OPTION_FIELD,
        history: int = typer.Option(50, "--history", "-n", help="Maximum number of history rows to display"),
):
    """Open a persistent dashboard TUI with active instances and history.

    The dashboard shows two live-updating tables: active instances on top and
    completed runs below. Selecting a row opens the instance detail view;
    dismissing it returns to the dashboard.

    Examples:
        taro dash
        taro dash "backup*"
        taro dash --env production
        taro dash -n 100
    """
    run_match = JobRunCriteria.parse(pattern, MatchingStrategy.PARTIAL) if pattern else JobRunCriteria()

    with connector.connect(env) as conn:
        instances = list(conn.get_instances(run_match))
        history_runs = conn.read_history_runs(run_match, asc=False, limit=history)
        DashboardApp(conn, instances, history_runs, run_match=run_match).run()
