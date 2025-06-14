from concurrent.futures.thread import ThreadPoolExecutor
from typing import List, Optional

import typer
from rich.console import Console

from runtools.runcore import connector
from runtools.runcore.criteria import JobRunCriteria, LifecycleCriterion
from runtools.runcore.env import get_env_config
from runtools.runcore.run import Stage
from runtools.runcore.util import MatchingStrategy, parse_duration_to_sec
from runtools.taro import cli

app = typer.Typer(invoke_without_command=True)
console = Console()


@app.callback()
def wait(
        instance_patterns: List[str] = typer.Argument(
            metavar="PATTERN",
            help="Instance ID patterns to specify which instances to wait for"
        ),
        env: Optional[str] = cli.ENV_OPTION_FIELD,
        stage: Stage = typer.Option(
            Stage.ENDED.value,
            "-s", "--stage",
            help="Stage to wait for"
        ),
        timeout: Optional[str] = typer.Option(
            None,
            "-t", "--timeout",
            help="Maximum time to wait before exiting (e.g., '30s', '5m', '1h'). Default: wait forever"
        ),
        history_window: Optional[str] = typer.Option(
            None,
            "--history-window",
            "-H",
            help="Check history for specified duration before waiting (e.g., '10s', '5m', '1h', '1d'). Default: disabled"
        ),
):
    """
    Wait for job instances to reach specific stages.

    This command blocks until the specified number of instances reach the
    target stage, then exits. Useful for scripting and automation.

    Examples:
        # Wait for any instance to complete
        taro wait "*"

        # Wait for an instance with 'backup1' run ID to start running
        taro wait @backup1 --stage RUNNING

        # Wait for instance with job name 'job' and run ID '123' to end with a 60 sec timeout
        taro wait job@123 --timeout 60s

        # Wait with a 10 sec history window (race condition protection)
        taro wait "batch*" -h 10s

        # Check if daily backup ran in the last 24 hours, then wait if not
        taro wait daily-backup -h 1d
    """
    executor = ThreadPoolExecutor(max_workers=len(instance_patterns))
    env_config = get_env_config(env)
    watchers = []
    with connector.create(env_config) as conn:
        for pattern in instance_patterns:
            run_match = JobRunCriteria.parse(pattern, MatchingStrategy.FN_MATCH)
            run_match += LifecycleCriterion(stage=stage)
            watcher = conn.watcher(run_match)
            watchers.append(watcher)
            executor.submit(watch_for_run, watcher, parse_duration_to_sec(timeout) if timeout else None)
        try:
            executor.shutdown()
        except KeyboardInterrupt as e:
            for w in watchers:
                w.cancel()
            executor.shutdown()
            raise e


def watch_for_run(watcher, timeout_sec):
    completed = watcher.wait(timeout=timeout_sec)
    if completed:
        console.print(
            f"\n[green]✓[/] [bold]{watcher.matched_runs[0].instance_id}[/bold] reached awaited stage")
    elif not watcher.is_cancelled:
        console.print(f"\n[yellow]⏱️  Timeout after {timeout_sec} seconds[/]")
