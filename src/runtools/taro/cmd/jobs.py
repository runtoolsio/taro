"""Jobs TUI command — interactive overview of all known jobs."""

from typing import Optional

import typer

from runtools.runcore import connector
from runtools.taro import cli
from runtools.taro.tui.jobs import JobsApp

app = typer.Typer(invoke_without_command=True)


@app.callback()
def jobs(
        env: Optional[str] = cli.ENV_OPTION_FIELD,
):
    """Interactive job overview showing the last-run state of every known job.

    Lists all jobs from the full run history with their last run time, status,
    and duration.  Press Enter on a job to drill down into its recent instances
    via the dashboard view.

    Examples:
        taro jobs
        taro jobs --env production
    """
    resolved = cli.select_env(env)
    with connector.connect(resolved) as conn:
        job_stats = conn.read_run_stats()
        active_runs = conn.get_active_runs()
        JobsApp(conn, job_stats, active_runs, env_name=conn.env_id).run()
